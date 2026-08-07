# Pipeline de dados — FilmFestivals

Fluxo definido pelo Rafa (2026-08-07):
1. **Lista de vencedores** — fonte mais confiável possível, de preferência o órgão
   oficial (oscars.org, festival-cannes.com). Se não der oficial, pega de outra
   fonte e **marca `verificado=N`** pra checar depois.
2. **Info do filme** via TMDB (pôster, sinopse, título original, diretor, país,
   duração, gêneros).
3. **Streaming BR** via TMDB `watch/providers` (região BR, flatrate).

Reaproveita `enrich.py` do filmcurator: `resolve()` casa filme→TMDB id; `build_row()`
já traz info + streaming BR numa chamada só. Chave TMDB (v3 e v4) do `.env` do
filmcurator funciona.

## Modelo de dados (ver ESCOPO.md §3–4)
- Registro granular de vitória: `festival, categoria, ano_premio, titulo, diretor,
  premiado, empate, verificado`.
- **Portão** (filme entra no banco): venceu **Filme, Direção OU Roteiro** em Oscar
  OU Cannes (nível do filme, basta 1). Atuação NÃO é portão (vira badge).
- Depois do portão, o card mostra **todas** as vitórias do filme (inclusive atuação).

### Baldes do portão a coletar
| Festival | Filme | Direção | Roteiro |
|---|---|---|---|
| Cannes | Palme/Grand Prix (topo do ano) | Prix de la mise en scène | Prix du scénario |
| Oscar | Best Picture | Best Director | qualquer categoria de escrita (balde único) |

Badges não-portão (coletar depois de fechar o set): atuação (com nome do premiado)
e demais categorias vencidas pelos filmes que já entraram.

## Status
- [x] Ambiente validado: internet OK, TMDB key OK.
- [x] **Cannes / Filme** — `data/raw/cannes_filme.csv` (83 registros, 1951–2026).
      Empates como linhas separadas; 1968/2020 cancelados omitidos.
      2026 ("Fjord"/Mungiu, 2ª Palma dele) confirmado em Deadline/Screen/IndieWire/Variety.
      Fonte: Wikipedia (Palme d'Or) + trade press. Todos `verificado=N` (falta pass oficial).
- [ ] Cannes / Direção
- [ ] Cannes / Roteiro
- [ ] Oscar / Filme  (SPARQL Q102427 testado: retorna dados mas precisa dedupe)
- [ ] Oscar / Direção
- [ ] Oscar / Roteiro
- [ ] Combinar baldes → set de filmes no portão
- [ ] Estágio 2+3: enriquecer via TMDB (adaptar enrich.py)
- [ ] Badges não-portão (atuação + outras categorias dos filmes que entraram)
- [ ] Verificação contra fontes oficiais (flip verificado=N→S)

## Decisão de método (aberta)
Cannes-topo foi curado à mão (regras difíceis do Grand Prix). Para o resto, avaliar:
- **SPARQL/Wikidata** (script repetível, estruturado) — precisa engenharia de query
  (dedupe, ano de cerimônia, prêmios de pessoa via P1686, balde de roteiro somando
  vários award items).
- **WebFetch de artigos curados** (mais simples de ler, mas passa por modelo-resumo
  que pode introduzir erro).
