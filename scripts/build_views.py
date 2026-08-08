#!/usr/bin/env python3
"""Lê os baldes de vitória (data/raw/*.csv) e gera:
  - data/cannes_por_edicao.json  (estrutura aninhada festival -> ano -> categoria)
  - <saida_html>                  (página de conferência por edição), se passada como argv[1]
Rode da raiz do repo: python3 scripts/build_views.py [saida.html]
"""
import csv, glob, json, sys, html, os, unicodedata

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "_")

# ordem e rótulo das categorias no card/edição
CAT_ORDER = ["Filme", "Grande Prêmio", "Prêmio do Júri", "Direção", "Roteiro", "Ator", "Atriz"]
# labels originais em francês (display); nomes internos das categorias ficam canônicos
CAT_LABEL = {"Filme": "Palme d'Or", "Grande Prêmio": "Grand Prix",
             "Prêmio do Júri": "Prix du Jury", "Direção": "Prix de la mise en scène",
             "Roteiro": "Prix du scénario", "Ator": "Prix d'interprétation masculine",
             "Atriz": "Prix d'interprétation féminine"}
CAT_KEY = {c: slug(c) for c in CAT_ORDER}
# onde está o nome da pessoa premiada (categorias de obra não têm)
NAME_FROM = {"Direção": "diretor", "Roteiro": "premiado", "Ator": "premiado", "Atriz": "premiado"}


def load(fest):
    data = {}
    for f in sorted(glob.glob(f"data/raw/{fest}_*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            y = r["ano_premio"]
            d = data.setdefault(y, {CAT_KEY[c]: [] for c in CAT_ORDER})
            item = {"titulo": r["titulo"]}
            nome = r.get(NAME_FROM.get(r["categoria"], ""), "")
            if nome:
                item["premiado"] = nome
            d[CAT_KEY[r["categoria"]]].append(item)
    return {y: data[y] for y in sorted(data, key=int, reverse=True)}


def main():
    cannes = load("cannes")
    out = {"cannes": cannes}
    json.dump(out, open("data/cannes_por_edicao.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"JSON: data/cannes_por_edicao.json | {len(cannes)} edições")

    if len(sys.argv) < 2:
        return
    def films(lst):
        if not lst:
            return '<span class="none">—</span>'
        parts = []
        for it in lst:
            t = html.escape(it["titulo"])
            if it.get("premiado"):
                t += f' <span class="who">({html.escape(it["premiado"])})</span>'
            parts.append(t)
        return ", ".join(parts)

    rows = []
    for y, d in cannes.items():
        cats = "".join(
            f'<div class="cat"><span class="lbl {"vencedor" if c=="Filme" else ""}">{CAT_LABEL[c]}</span>'
            f'<span class="val">{films(d[CAT_KEY[c]])}</span></div>'
            for c in CAT_ORDER)
        rows.append(f'<section class="ed"><div class="yr">{y}</div><div class="cats">{cats}</div></section>')

    doc = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Cannes por edição — conferência</title>
<style>
:root{{--bg:#0e0f13;--txt:#e8eaf0;--muted:#9aa0b0;--accent:#f5c518}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 Inter,system-ui,sans-serif;padding:28px 16px 60px}}
h1{{max-width:860px;margin:0 auto 6px;font-size:22px}}h1 span{{color:var(--accent)}}
.hint{{max-width:860px;margin:0 auto 22px;color:var(--muted);font-size:13px}}
.ed{{max-width:860px;margin:0 auto;display:grid;grid-template-columns:76px 1fr;gap:14px;padding:14px 0;border-top:1px solid #23242b}}
.yr{{font-weight:800;font-size:22px;color:var(--accent);font-variant-numeric:tabular-nums}}
.cats{{display:flex;flex-direction:column;gap:5px}}
.cat{{display:grid;grid-template-columns:210px 1fr;gap:10px;align-items:baseline}}
@media (max-width:640px){{.cat{{grid-template-columns:1fr}}}}
.lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);padding-top:2px}}
.lbl.vencedor{{color:var(--accent)}}
.val{{font-size:14.5px}}.who{{color:var(--muted)}}.none{{color:#4a4c57}}
</style></head><body>
<h1>Cannes — conferência por <span>edição</span></h1>
<div class="hint">{len(cannes)} edições (1951–2026). Labels no original em francês. "—" = não premiado no ano. Vírgula = empate entre filmes. Mise en scène (direção), scénario (roteiro) e interprétation (atuação) mostram o nome de quem ganhou.</div>
{"".join(rows)}</body></html>'''
    open(sys.argv[1], "w", encoding="utf-8").write(doc)
    print(f"HTML: {sys.argv[1]}")


if __name__ == "__main__":
    main()
