#!/usr/bin/env python3
"""
Verificacao barata do dataset do Oscar (2a fonte = Wikipedia por-categoria).

NAO edita nada. Baixa as paginas "Academy Award for Best X" (cache local em
scripts/verify_cache/), extrai o CONJUNTO de filmes-vencedores por categoria de
forma deterministica (marcador #FAEB86) e faz DIFF contra data/raw/oscar_*.csv.
So imprime divergencias -> revisao manual so das excecoes.

Uso:  python3 scripts/verify_oscar.py
"""
import json, re, os, sys, unicodedata, csv, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "verify_cache")
RAW = os.path.join(HERE, "..", "data", "raw")
UA = "filmfestivals-verify/1.0 (rafaortman@gmail.com)"

# categoria CSV -> paginas Wikipedia que a cobrem
SOURCES = {
    "filme":       ["Academy_Award_for_Best_Picture"],
    "direcao":     ["Academy_Award_for_Best_Director"],
    "roteiro":     ["Academy_Award_for_Best_Original_Screenplay",
                    "Academy_Award_for_Best_Adapted_Screenplay",
                    "Academy_Award_for_Best_Story"],
    "estrangeiro": ["Academy_Award_for_Best_International_Feature_Film"],
    "ator":        ["Academy_Award_for_Best_Actor"],
    "atriz":       ["Academy_Award_for_Best_Actress"],
}

def fetch(page):
    fp = os.path.join(CACHE, page + ".json")
    if not os.path.exists(fp):
        os.makedirs(CACHE, exist_ok=True)
        url = ("https://en.wikipedia.org/w/api.php?action=parse&page=%s"
               "&prop=wikitext&format=json&formatversion=2" % page)
        subprocess.run(["curl", "-s", "-A", UA, url, "-o", fp], check=True)
    return json.load(open(fp))["parse"]["wikitext"]

def norm(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"\(\d{4}[^)]*\)", "", t)          # (2022 film)
    t = re.sub(r"\(film\)", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t

def ceremony_year(n):
    # ano-calendario da cerimonia (bate com P585 usado no CSV)
    if n == 1: return 1929
    if n == 2: return 1930
    if 3 <= n <= 5: return 1927 + n     # 1930,1931,1932
    return 1928 + n                     # 6->1934 ... 98->2026 (gap 1933)

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
ORD = re.compile(r"\[\[(\d+)(?:st|nd|rd|th) Academy Awards")
SUBORD = re.compile(r"to the (\d+)(?:st|nd|rd|th) Academy Awards")
# link de filme = wikilink italicizado. Em wikitext: 2 aspas = italico, 3 = negrito
# (nome de pessoa!), 5 = negrito+italico. Filme => run de 2 OU >=5 aspas (nunca 3/4).
FILMLINK = re.compile(r"('{2,})\s*(\[\[[^\]]+?\]\])\s*'{2,}")

def link_title(wikilink):
    lm = LINK.search(wikilink)
    if not lm:
        return None
    return (lm.group(2) or lm.group(1))

SORT = re.compile(r"\{\{[Ss]ort\s*\|[^|{}]*\|([^{}]*)\}\}")
# filme por italico interno ao link: [[alvo|''exibicao'']]  (formato recente do Adaptado)
INNERIT = re.compile(r"\[\[[^\]|]+\|''(.+?)''\]\]")

def first_film_link(chunk):
    """titulo do 1o wikilink em italico (=filme) no trecho, ou None. Ignora negrito (pessoa).
    Cobre 3 formatos: ''[[F]]'' / '''''[[F]]''''' (aspas fora), {{sort|k|''[[F]]''}} (desembrulha),
    e '''[[alvo|''F'']]''' (italico dentro do link)."""
    chunk = re.sub(r"<ref[^>]*/>", "", chunk)
    chunk = re.sub(r"<ref[^>]*>.*?</ref>", "", chunk, flags=re.S)  # notas de rodape poluem
    chunk = SORT.sub(r"\1", chunk)
    cands = []
    for m in FILMLINK.finditer(chunk):        # aspas colando fora do [[..]]
        run = len(m.group(1))
        if run == 2 or run >= 5:              # italico; pula 3/4 (negrito = pessoa)
            cands.append((m.start(), link_title(m.group(2))))
    for m in INNERIT.finditer(chunk):         # italico dentro do display
        cands.append((m.start(), m.group(1)))
    return min(cands)[1] if cands else None

def parse_films(wt):
    """[(ordinal, titulo)] dos vencedores. Vencedor = linha (split '\\n|-') que contem #FAEB86.
    O ordinal [[Nth Academy Awards]] pode estar na propria linha OU numa linha-cabecalho acima
    (ex.: Best Story), entao rastreia o ultimo ordinal visto de cima pra baixo."""
    out, seen = [], set()
    cur = None
    for chunk in re.split(r"\n\|-", wt):
        om = ORD.search(chunk)
        if om:
            cur = int(om.group(1))
        if "FAEB86" not in chunk or cur is None:
            continue
        title = first_film_link(chunk)
        if not title:
            continue
        key = (cur, norm(title))
        if key in seen:
            continue
        seen.add(key)
        out.append((cur, title))
    return out

def parse_international(wt):
    """Pagina International nao tem tabela: lista '* [ord-link|ano]: ''[[Filme]]'''.
    Usa o ordinal do link 'submissions to the Nth Academy Awards' pra ancorar o ano."""
    out, seen = [], set()
    m = re.search(r"=+ *Winners *=+", wt)
    if not m:
        return out
    section = wt[m.end(): wt.find("\n==", m.end())]
    for line in section.splitlines():
        if not line.strip().startswith("*"):
            continue
        title = first_film_link(line)
        if not title:
            continue
        so = SUBORD.search(line)
        if not so:
            continue  # honorarios 1947-1955 (sem link de cerimonia) nao entram no CSV
        o = int(so.group(1))
        key = (o, norm(title))
        if key in seen:
            continue
        seen.add(key)
        out.append((o, title))
    return out

def load_csv(cat):
    fp = os.path.join(RAW, "oscar_%s.csv" % cat)
    rows = []
    with open(fp, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((int(r["ano_premio"]), r["titulo"]))
    return rows

def main():
    for cat, pages in SOURCES.items():
        wiki = []
        for p in pages:
            wt = fetch(p)
            wiki += parse_international(wt) if cat == "estrangeiro" else parse_films(wt)
        # colapsa por (ano_cerimonia, titulo_norm)
        wiki_map = {}   # norm_title -> set(anos)
        for o, t in wiki:
            wiki_map.setdefault(norm(t), set()).add(ceremony_year(o))
        csv_rows = load_csv(cat)
        csv_map = {}
        for y, t in csv_rows:
            csv_map.setdefault(norm(t), (y, t));
        csv_titles = {norm(t): (y, t) for y, t in csv_rows}

        only_csv = [csv_titles[k] for k in csv_titles if k not in wiki_map]
        only_wiki = [t for o, t in {(norm(t)): (o, t) for o, t in wiki}.values()
                     if norm(t) not in csv_titles]
        # so filmes; dedup only_wiki por titulo
        seen=set(); ow=[]
        for o,t in wiki:
            n=norm(t)
            if n not in csv_titles and n not in seen:
                seen.add(n); ow.append((ceremony_year(o), t))
        # ano divergente entre matched
        year_mismatch = []
        for k,(y,t) in csv_titles.items():
            if k in wiki_map and y not in wiki_map[k]:
                year_mismatch.append((t, y, sorted(wiki_map[k])))

        print("\n" + "="*70)
        print("CATEGORIA: %s   | CSV=%d filmes  Wikipedia=%d filmes  (fontes: %s)"
              % (cat.upper(), len(csv_titles), len(wiki_map), ", ".join(pages)))
        print("-"*70)
        if only_csv:
            print("  [!] NO CSV, ausente na Wikipedia (%d):" % len(only_csv))
            for y,t in sorted(only_csv):
                print("       %s  %s" % (y, t))
        if ow:
            print("  [!] Na Wikipedia, ausente no CSV (%d):" % len(ow))
            for y,t in sorted(ow):
                print("       %s  %s" % (y, t))
        if year_mismatch:
            print("  [~] Titulo bate mas ANO diverge (%d):" % len(year_mismatch))
            for t,y,ws in sorted(year_mismatch):
                print("       CSV=%s  Wiki=%s  | %s" % (y, ws, t))
        if not (only_csv or ow or year_mismatch):
            print("  OK: nenhuma divergencia de titulo/ano.")

if __name__ == "__main__":
    main()
