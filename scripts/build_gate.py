#!/usr/bin/env python3
"""
Combina os baldes de Cannes + Oscar num SET unico de filmes de PORTAO.

Portao (ESCOPO sec.3):
  Cannes -> Filme, Grande Premio (2o), Premio do Juri, Direcao, Roteiro
  Oscar  -> Filme, Direcao, Roteiro, Filme Estrangeiro
Atuacao (Ator/Atriz) NAO e portao, mas entra como badge quando o filme ja passou.

Um filme entra se venceu >=1 categoria de portao em >=1 festival (nivel do filme).
Identidade provisoria = titulo normalizado (o dedupe FINAL por identidade real vem
com o id do TMDB no enriquecimento). Diretor reconciliado dos baldes que o trazem;
colisoes de titulo (diretores diferentes sob o mesmo titulo) sao sinalizadas.

Gera data/portao.json (um objeto por filme, com todos os premios/badges e ano-ancora)
e imprime um resumo. Nao edita os baldes brutos.

Uso:  python3 scripts/build_gate.py
"""
import csv, glob, json, os, re, unicodedata
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
OUT = os.path.join(HERE, "..", "data", "portao.json")

GATE = {
    ("cannes", "Filme"), ("cannes", "Grande Prêmio"), ("cannes", "Prêmio do Júri"),
    ("cannes", "Direção"), ("cannes", "Roteiro"),
    ("oscar", "Filme"), ("oscar", "Direção"), ("oscar", "Roteiro"),
    ("oscar", "Filme Estrangeiro"),
}

def norm(t):
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t

def dtokens(d):
    """tokens de sobrenome (>=3 letras) de uma string de diretor(es)."""
    toks = set()
    for part in re.split(r"[;,/&]| and ", d):
        for w in norm(part).split():
            if len(w) >= 3:
                toks.add(w)
    return toks

def split_group(group):
    """separa registros do mesmo titulo em 1+ filmes distintos, por compatibilidade de
    diretor (mesmo titulo + diretores sem sobrenome em comum = filmes diferentes, ex.:
    remakes). Registros sem diretor (roteiro/atuacao) vao pro filme mais proximo em ano."""
    dstrings = list({r["diretor"] for r in group if r["diretor"]})
    toks = [dtokens(d) for d in dstrings]
    parent = list(range(len(dstrings)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i in range(len(dstrings)):
        for j in range(i + 1, len(dstrings)):
            if toks[i] & toks[j]:
                parent[find(i)] = find(j)
    comps = defaultdict(set)
    for i in range(len(dstrings)):
        comps[find(i)] |= toks[i]
    nodes = [{"toks": t, "recs": []} for t in comps.values()] or [{"toks": set(), "recs": []}]
    # pass 1: registros com diretor
    for r in group:
        if not r["diretor"]:
            continue
        rt = dtokens(r["diretor"])
        nd = next((n for n in nodes if rt & n["toks"]), None)
        if nd is None:
            nd = {"toks": rt, "recs": []}; nodes.append(nd)
        nd["recs"].append(r)
    # pass 2: registros sem diretor -> no mais proximo em ano
    for r in group:
        if r["diretor"]:
            continue
        nd = min(nodes, key=lambda n: min((abs(r["ano"] - x["ano"]) for x in n["recs"]),
                                          default=9999))
        nd["recs"].append(r)
    return [n["recs"] for n in nodes if n["recs"]]

def load_records():
    recs = []
    for fp in sorted(glob.glob(os.path.join(RAW, "*.csv"))):
        with open(fp, newline="") as f:
            for r in csv.DictReader(f):
                recs.append({
                    "festival": r["festival"],
                    "categoria": r["categoria"],
                    "ano": int(r["ano_premio"]),
                    "titulo": r["titulo"].strip(),
                    "diretor": r["diretor"].strip(),
                    "premiado": r["premiado"].strip(),
                    "empate": r["empate"].strip() == "S",
                    "portao": (r["festival"], r["categoria"]) in GATE,
                })
    return recs

def main():
    recs = load_records()
    by_title = defaultdict(list)
    for r in recs:
        by_title[norm(r["titulo"])].append(r)

    def make_film(recs):
        gate_recs = [r for r in recs if r["portao"]]
        if not gate_recs:
            return None  # nenhum premio de portao -> filme nao entra
        fests = sorted({r["festival"] for r in gate_recs})
        diretores = [r["diretor"] for r in recs if r["diretor"]]
        anos_por_fest = {}
        for r in gate_recs:
            anos_por_fest.setdefault(r["festival"], set()).add(r["ano"])
        premios = sorted(
            ({"festival": r["festival"], "categoria": r["categoria"], "ano": r["ano"],
              "premiado": r["premiado"], "portao": r["portao"], "empate": r["empate"]}
             for r in recs),
            key=lambda p: (p["festival"], p["ano"], p["categoria"]))
        return {
            "titulo": recs[0]["titulo"],
            "diretor": Counter(diretores).most_common(1)[0][0] if diretores else "",
            "ano_ancora": min(r["ano"] for r in gate_recs),
            "fonte": "ambos" if len(fests) == 2 else fests[0],
            "anos_portao": {f: sorted(v) for f, v in anos_por_fest.items()},
            "premios": premios,
        }

    filmes, multi = [], []
    for group in by_title.values():
        nodes = split_group(group)
        films_here = [f for f in (make_film(n) for n in nodes) if f]
        if len([n for n in nodes if any(r["portao"] for r in n)]) > 1:
            multi.append(films_here)
        filmes.extend(films_here)

    filmes.sort(key=lambda x: (-x["ano_ancora"], norm(x["titulo"])))
    json.dump(filmes, open(OUT, "w"), ensure_ascii=False, indent=1)

    # ---- resumo ----
    n = len(filmes)
    por_fonte = Counter(f["fonte"] for f in filmes)
    ambos = [f for f in filmes if f["fonte"] == "ambos"]
    print("PORTAO COMBINADO -> %s" % os.path.relpath(OUT, os.path.join(HERE, "..")))
    print("  filmes distintos no portao: %d" % n)
    print("  por fonte: Cannes-only=%d  Oscar-only=%d  ambos=%d"
          % (por_fonte.get("cannes", 0), por_fonte.get("oscar", 0), por_fonte.get("ambos", 0)))
    print("  faixa de anos-ancora: %d–%d"
          % (min(f["ano_ancora"] for f in filmes), max(f["ano_ancora"] for f in filmes)))
    print("\n  filmes premiados nos DOIS festivais (%d):" % len(ambos))
    for f in sorted(ambos, key=lambda x: -x["ano_ancora"]):
        cann = ",".join(map(str, f["anos_portao"].get("cannes", [])))
        osc = ",".join(map(str, f["anos_portao"].get("oscar", [])))
        print("     %-42s Cannes %s | Oscar %s" % (f["titulo"][:42], cann, osc))
    if multi:
        print("\n  titulos separados em filmes distintos (mesmo titulo, filmes diferentes) (%d):" % len(multi))
        for films_here in sorted(multi, key=lambda fs: fs[0]["titulo"]):
            print("     %s:" % films_here[0]["titulo"])
            for f in films_here:
                print("        - %s (%s), ancora %d" % (f["diretor"] or "?", f["fonte"], f["ano_ancora"]))

if __name__ == "__main__":
    main()
