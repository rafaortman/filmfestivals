"""
Backfill pontual das sinopses faltantes em data/filmes.json.

Para cada filme com sinopse vazia, aplica a cascata do enrich (pt -> en -> qualquer
idioma) via TMDB /translations e completa o campo. Não re-roda o pipeline inteiro nem
mexe em streaming/pôster. Idempotente (o get() do enrich tem cache em disco).

Uso:  python3 scripts/backfill_sinopse.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich  # reusa get() (com cache) + best_overview() + OUT

def main():
    films = json.load(open(enrich.OUT, encoding="utf-8"))
    missing = [f for f in films if not (f.get("sinopse") or "").strip() and f.get("tmdb_id")]
    print(f"{len(missing)} filmes sem sinopse; buscando fallback (en / qualquer idioma)...")
    filled = 0
    for f in missing:
        ov = enrich.best_overview(f["tmdb_id"], "").replace("\n", " ").strip()
        if ov:
            f["sinopse"] = ov
            filled += 1
            titulo = f.get("titulo_pt") or f.get("titulo_orig") or f.get("titulo_lista") or "?"
            print(f"  + {titulo[:55]}")
    json.dump(films, open(enrich.OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    still = sum(1 for f in films if not (f.get("sinopse") or "").strip())
    print(f"\npreenchidos: {filled} | ainda sem sinopse em nenhum idioma: {still}")
    print(f"gravado em {os.path.relpath(enrich.OUT, os.path.dirname(os.path.dirname(__file__)))}")

if __name__ == "__main__":
    main()
