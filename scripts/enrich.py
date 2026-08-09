"""
Enriquecimento via TMDB do set de portão (data/portao.json -> data/filmes.json).

Adaptado do enrich.py do FilmCurator. Diferenças:
  - entrada = portao.json (filmes já com prêmios/badges), não listas ranqueadas;
  - dedupe REAL por tmdb_id: dois filmes de portão que resolvem pro mesmo id são
    COLAPSADOS (junta os prêmios dos dois festivais) — é assim que os "ambos"
    cross-título (título orig vs inglês) finalmente se encontram;
  - saída = data/filmes.json (1 obj/filme: campos TMDB + prêmios + ano_ancora + fonte).

Idempotente e econômico: HTTP com cache em disco (.cache/tmdb/), match por diretor
via credits (NUNCA chuta quando há diretor), resumo minúsculo no console e detalhe
dos não-resolvidos num CSV de revisão.

Uso:
  python3 scripts/enrich.py           # dry-run: resolve, imprime resumo, grava revisão
  python3 scripts/enrich.py --commit  # grava data/filmes.json
"""
import csv, json, os, re, sys, time, subprocess, urllib.parse, hashlib, unicodedata
from datetime import date
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor

WORKERS = 8  # paralelismo (o cache em disco é por-URL, então threads não colidem)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do repo
CACHE = os.path.join(ROOT, ".cache", "tmdb")
os.makedirs(CACHE, exist_ok=True)
TODAY = date.today().isoformat()
API = "https://api.themoviedb.org/3"
PORTAO = os.path.join(ROOT, "data", "portao.json")
OUT = os.path.join(ROOT, "data", "filmes.json")
REVIEW = os.path.join(ROOT, "data", "enrich_revisao.csv")

def load_key():
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if line.startswith("TMDB_API_KEY"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    sys.exit("TMDB_API_KEY não encontrada no .env")
KEY = load_key()

COUNTRY = {
    "US":"EUA","GB":"Reino Unido","FR":"França","IT":"Itália","DE":"Alemanha",
    "JP":"Japão","KR":"Coreia do Sul","HK":"Hong Kong","TW":"Taiwan","CN":"China",
    "IN":"Índia","RU":"Rússia","SU":"Rússia","SE":"Suécia","DK":"Dinamarca","NO":"Noruega",
    "PL":"Polônia","AT":"Áustria","BE":"Bélgica","ES":"Espanha","MX":"México",
    "AR":"Argentina","BR":"Brasil","CA":"Canadá","IE":"Irlanda","NZ":"Nova Zelândia",
    "AU":"Austrália","GR":"Grécia","HU":"Hungria","RO":"Romênia","TR":"Turquia",
    "IR":"Irã","IL":"Israel","LB":"Líbano","TH":"Tailândia","CH":"Suíça","NL":"Holanda",
    "PT":"Portugal","MR":"Mauritânia","BF":"Burquina Faso","CM":"Camarões","MA":"Marrocos",
    "SN":"Senegal","TN":"Tunísia","CZ":"Tchéquia","CS":"Tchecoslováquia","FI":"Finlândia",
    "IS":"Islândia","CU":"Cuba","CL":"Chile","CO":"Colômbia","PE":"Peru","YU":"Iugoslávia",
    "BA":"Bósnia","RS":"Sérvia","GE":"Geórgia","DZ":"Argélia","PS":"Palestina","BG":"Bulgária",
    "AL":"Albânia","CI":"Costa do Marfim","EE":"Estônia","LI":"Liechtenstein","LU":"Luxemburgo",
    "LV":"Letônia","ML":"Mali","MY":"Malásia","PH":"Filipinas","PY":"Paraguai","QA":"Catar",
    "SI":"Eslovênia","TD":"Chade","VN":"Vietnã","XC":"Tchecoslováquia","XG":"Alemanha Oriental",
    "XI":"Irlanda do Norte","ZA":"África do Sul","ZW":"Zimbábue",
}
UNMAPPED = set()

PROVIDER_ALIAS = {
    "Max": "HBO Max", "Disney Plus": "Disney+", "MGM Plus": "MGM+",
    "Filmelier Plus": "Filmelier+", "Claro video": "Claro tv+", "Lionsgate+s": "Lionsgate+",
}
PROVIDER_DROP = {"Sun Nxt"}

def norm_provider(name):
    n = name.replace(" Amazon Channel", "").replace(" Apple TV Channel", "")
    n = n.replace("Amazon Prime Video", "Prime Video").replace("Prime Video with Ads", "Prime Video")
    n = n.replace("Paramount Plus", "Paramount+").replace("Paramount+ Amazon Channel", "Paramount+")
    n = n.replace("Standard with Ads", "").replace(" Premium", "").strip()
    n = PROVIDER_ALIAS.get(n, n)
    return "" if n in PROVIDER_DROP else n

def get(path, params):
    # fetcher = curl (o urllib do Python 3.7 do sistema não acha o CA bundle p/ TLS)
    params = {**params, "api_key": KEY}
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    ck = hashlib.md5(url.encode()).hexdigest() + ".json"
    cp = os.path.join(CACHE, ck)
    if os.path.exists(cp):
        return json.load(open(cp, encoding="utf-8"))
    for attempt in range(4):
        try:
            out = subprocess.run(["curl", "-sS", "--fail", url], capture_output=True,
                                 timeout=30).stdout
            data = json.loads(out)
            json.dump(data, open(cp, "w", encoding="utf-8"), ensure_ascii=False)
            time.sleep(0.2)
            return data
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1 + attempt)

def _deaccent(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def _tokens(name):
    return re.sub(r"[^\w\s]", " ", _deaccent(name).lower()).split()

def director_matches(wanted, credited):
    """mesmo sobrenome + mesma inicial do 1º nome (ignora acento/variações)."""
    for w in re.split(r";|,|/|&|\band\b", wanted):
        wt = _tokens(w)
        if not wt:
            continue
        for c in credited:
            ct = _tokens(c)
            if ct and wt[-1] == ct[-1] and wt[0][0] == ct[0][0]:
                return True
    return False

# override curado p/ casos que a busca não resolve (title.lower() -> tmdb_id).
# Títulos genéricos/obscuros que não caem no top da busca por título.
OVERRIDE = {
    "a hero": 672208,          # Ghahreman / Um Herói (Farhadi, 2021) — Cannes Grande Prêmio
    "the class": 8841,         # Entre les murs (Cantet, 2008) — Palma
    "love": 42516,             # Szerelem (Makk, 1971) — Cannes Prêmio do Júri
    "heroes of shipka": 199253,# Героите на Шипка (Vasilyev, 1955) — Cannes Direção
}

def resolve(film):
    """(tmdb_id, motivo) ou (None, motivo). Usa ano de lançamento estimado + diretor.
    Nunca chuta quando há diretor conhecido."""
    title = film["titulo"]
    key = title.lower().strip()
    if key in OVERRIDE:
        return OVERRIDE[key], "override"
    diretor = film["diretor"]
    # estimativa de ano de lançamento: Cannes=ano do festival ~ release; Oscar=cerimônia ~ release+1
    ests = []
    for p in film["premios"]:
        if p["portao"]:
            ests.append(p["ano"] if p["festival"] == "cannes" else p["ano"] - 1)
    est = min(ests) if ests else film["ano_ancora"]
    # junta candidatos de VÁRIOS anos (dedup, preserva ordem) — não para no 1º ano com hit,
    # senão um match de ano errado esconde o filme certo (ex.: Grand Hotel 1932).
    seen, cands = set(), []
    for y in [est, est - 1, est + 1, est - 2, est + 2, film["ano_ancora"], None]:
        params = {"query": title, "language": "pt-BR"}
        if y:
            params["year"] = y
        for c in get("/search/movie", params).get("results", []):
            if c["id"] not in seen:
                seen.add(c["id"]); cands.append(c)
        if cands and not diretor:
            break  # sem diretor: fica no 1º ano que retornou algo (mais provável)
    if not cands:
        return None, "não encontrado"
    if diretor:
        for cand in cands[:15]:
            crew = get(f"/movie/{cand['id']}/credits", {}).get("crew", [])
            dirs = [c["name"] for c in crew if c.get("job") == "Director"]
            if director_matches(diretor, dirs):
                return cand["id"], "ok (diretor)"
        return None, "diretor não confere"
    return cands[0]["id"], "título-only (verificar)"

def tmdb_fields(tmdb_id):
    d = get(f"/movie/{tmdb_id}", {"language": "pt-BR",
            "append_to_response": "credits,external_ids,watch/providers"})
    yr = int(d["release_date"][:4]) if d.get("release_date") else None
    countries = []
    for c in d.get("production_countries", []):
        code = c["iso_3166_1"]
        if code in COUNTRY:
            countries.append(COUNTRY[code])
        else:
            UNMAPPED.add(f"{code}={c.get('name')}")
            countries.append(c.get("name"))
    director = next((c["name"] for c in d.get("credits", {}).get("crew", []) if c.get("job") == "Director"), "")
    wp = d.get("watch/providers", {}).get("results", {}).get("BR", {}).get("flatrate", [])
    plats = sorted({m for m in (norm_provider(p["provider_name"]) for p in wp) if m})
    return {
        "tmdb_id": tmdb_id,
        "imdb_id": d.get("external_ids", {}).get("imdb_id") or "",
        "titulo_orig": d.get("original_title", ""),
        "titulo_pt": d.get("title", ""),
        "ano_lancamento": yr or "",
        "pais": " / ".join(countries),
        "diretor_tmdb": director,
        "duracao": d.get("runtime") or "",
        "generos": [g["name"] for g in d.get("genres", [])],
        "poster_path": d.get("poster_path") or "",
        "sinopse": (d.get("overview") or "").replace("\n", " ").strip(),
        "streaming": plats,
        "streaming_checked_at": TODAY,
    }

def merge_premios(films):
    """junta prêmios de vários objetos de portão (mesmo tmdb_id) num só, sem duplicar."""
    premios, seen = [], set()
    for f in films:
        for p in f["premios"]:
            k = (p["festival"], p["categoria"], p["ano"], p["premiado"])
            if k not in seen:
                seen.add(k); premios.append(p)
    premios.sort(key=lambda p: (p["festival"], p["ano"], p["categoria"]))
    gate = [p for p in premios if p["portao"]]
    fests = sorted({p["festival"] for p in gate})
    anos = {}
    for p in gate:
        anos.setdefault(p["festival"], set()).add(p["ano"])
    return premios, gate, fests, {f: sorted(v) for f, v in anos.items()}

def main():
    commit = "--commit" in sys.argv
    portao = json.load(open(PORTAO, encoding="utf-8"))

    nao_resolvidos, titulo_only = [], []
    id_to_films = defaultdict(list)

    # fase 1: resolver tmdb_id (paralela)
    def _resolve(film):
        try:
            return film, resolve(film)
        except Exception as ex:
            return film, (None, f"erro: {ex}")
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for film, (tid, reason) in ex.map(_resolve, portao):
            if not tid:
                nao_resolvidos.append((film, reason)); continue
            if "título-only" in reason:
                titulo_only.append((film, tid))
            id_to_films[tid].append(film)

    # fase 2: detalhes por tmdb_id único (paralela)
    def _detail(tid):
        try:
            return tid, tmdb_fields(tid), None
        except Exception as ex:
            return tid, None, f"detalhe falhou: {ex}"
    detalhes = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for tid, tf, err in ex.map(_detail, list(id_to_films)):
            if err:
                nao_resolvidos.append((id_to_films[tid][0], err))
            else:
                detalhes[tid] = tf

    # monta 1 filme final por tmdb_id (colapsando duplicados)
    filmes, colapsados = [], []
    for tid, group in id_to_films.items():
        if tid not in detalhes:
            continue
        if len(group) > 1:
            colapsados.append((tid, [g["titulo"] for g in group]))
        premios, gate, fests, anos = merge_premios(group)
        tf = detalhes[tid]
        filmes.append({
            **tf,
            "titulo_lista": group[0]["titulo"],
            "diretor_lista": next((g["diretor"] for g in group if g["diretor"]), ""),
            "ano_ancora": min(p["ano"] for p in gate),
            "fonte": "ambos" if len(fests) == 2 else fests[0],
            "anos_portao": anos,
            "premios": premios,
        })
    filmes.sort(key=lambda x: (-x["ano_ancora"], x["titulo_pt"].lower()))

    # ---- resumo ----
    n_in, n_out = len(portao), len(filmes)
    fonte = Counter(f["fonte"] for f in filmes)
    print("=" * 62)
    print(f"ENRIQUECIMENTO TMDB  | modo: {'COMMIT' if commit else 'DRY-RUN'}")
    print(f"portão de entrada: {n_in} filmes  ->  resolvidos p/ {n_out} tmdb_id únicos")
    print(f"não resolvidos: {len(nao_resolvidos)}  | colapsados (mesmo id): {len(colapsados)}")
    print(f"fonte final: Cannes-only={fonte.get('cannes',0)} Oscar-only={fonte.get('oscar',0)} ambos={fonte.get('ambos',0)}")
    print(f"resolvidos só por título (sem diretor — conferir): {len(titulo_only)}")
    print(f"sem pôster: {sum(1 for f in filmes if not f['poster_path'])}  | "
          f"com streaming BR: {sum(1 for f in filmes if f['streaming'])}")
    if colapsados:
        print(f"\n-- COLAPSADOS por tmdb_id ({len(colapsados)}) — os 'ambos' cross-título --")
        for tid, ts in colapsados:
            print(f"   {tid}: {' = '.join(ts)}")
    if nao_resolvidos:
        print(f"\n-- NÃO RESOLVIDOS ({len(nao_resolvidos)}) -> {os.path.relpath(REVIEW, ROOT)} --")
        for f, r in nao_resolvidos[:25]:
            print(f"   {f['titulo']} ({f['ano_ancora']}) [{f['diretor'] or 'sem diretor'}] — {r}")
        if len(nao_resolvidos) > 25:
            print(f"   ... +{len(nao_resolvidos)-25} (ver CSV)")
    if UNMAPPED:
        print("\n-- PAÍSES FORA DO MAPA (adicionar em COUNTRY) --")
        for c in sorted(UNMAPPED):
            print("   " + c)

    with open(REVIEW, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["titulo", "ano_ancora", "diretor", "fonte", "motivo"])
        for fl, r in nao_resolvidos:
            w.writerow([fl["titulo"], fl["ano_ancora"], fl["diretor"], fl["fonte"], r])

    if commit:
        json.dump(filmes, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\nGRAVADO: {os.path.relpath(OUT, ROOT)} ({n_out} filmes).")
    else:
        print("\nDRY-RUN: nada gravado (só a revisão). Rode com --commit após conferir.")

if __name__ == "__main__":
    main()
