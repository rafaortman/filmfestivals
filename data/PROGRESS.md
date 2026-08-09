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
- **DATASET DE CANNES COMPLETO** (2026-08-07): **7 baldes, 509 registros**, 471 pares
  (título, ano) distintos. Conferência: **474 verificado=S**, **35 verificado=P**
  (só badges de atuação — ator 14, atriz 21). **Portão 100% conferido** (Filme,
  Grande Prêmio, Júri, Direção, Roteiro = 0 P). Ver seção Conferência abaixo.
  Baldes: Filme(85), Grande Prêmio 2º(67), Prêmio do Júri(84), Direção(70),
  Roteiro(46), Ator(75), Atriz(82).
  **Portão de Cannes AMPLIADO** (ver ESCOPO §3): Filme + Grande Prêmio + Prêmio do
  Júri + Direção + Roteiro entram como critério de inclusão. Ator/Atriz = badge.
  Gerar views: `python3 scripts/build_views.py [saida.html]`.
- [x] Ambiente validado: internet OK, TMDB key OK.
- [x] **Cannes / Filme** — `data/raw/cannes_filme.csv` (85 registros, 1951–2026;
      74 anos vencedores + 11 empates).
      Empates como linhas separadas; 1968/2020 cancelados omitidos.
      2026 ("Fjord"/Mungiu, 2ª Palma dele) confirmado em Deadline/Screen/IndieWire/Variety.
      Fonte: Wikipedia (Palme d'Or) + trade press. Todos `verificado=N` (falta pass oficial).
- [x] **Cannes / Direção** — `data/raw/cannes_direcao.csv` (70 registros, 62 anos,
      16 linhas de empate). Anos sem prêmio omitidos. Fonte: Wikipedia. `verificado=N`.
- [x] **Cannes / Roteiro** — `data/raw/cannes_roteiro.csv` (46 registros, 42 anos,
      8 linhas de empate). Fonte: Wikipedia. `verificado=N`.
- [x] **Cannes / Ator** — `data/raw/cannes_ator.csv` (75 registros). badge.
- [x] **Cannes / Atriz** — `data/raw/cannes_atriz.csv` (82 registros). badge.
      (Nota: "coletar dado de Cannes" NÃO depende de Oscar — são coisas separadas.
      O Oscar só entra na etapa de MONTAGEM, ao decidir quais filmes viram card.
      Elencos/empates registrados como dados; premiado com vários nomes usa "; ".)
- [ ] Oscar / Filme  (SPARQL Q102427 testado: retorna dados mas precisa dedupe)
- [ ] Oscar / Direção
- [ ] Oscar / Roteiro
- [ ] Combinar baldes → set de filmes no portão
- [ ] Estágio 2+3: enriquecer via TMDB (adaptar enrich.py)
- [ ] Badges não-portão (atuação + outras categorias dos filmes que entraram)
- [ ] Verificação contra fontes oficiais (flip verificado=N→S)

## Conferência de Cannes — CONCLUÍDA (2026-08-07): 509/509, zero erros
Método: cada balde cruzado com Wikidata (SPARQL) por ano+título. QIDs usados —
Palme Q179808, Grand Prix Q844804, Jury Prize Q164200, Direção Q510175, Roteiro
Q978420, Ator Q586140, Atriz Q840286 (prêmios de pessoa: filme vem do qualificador
P1686). **298/509 (58%) confirmados diretamente** pelo Wikidata; os demais foram
**lacunas de cobertura do Wikidata**, não erros. As 79 aparentes divergências foram
revisadas uma a uma e são TODAS benignas: (a) mesmo filme com rótulo em outro idioma;
(b) co-vencedor do empate; (c) Wikidata modela o prêmio na pessoa (devolve o nome);
(d) confusão Un Certain Regard × Competição no Wikidata — nesses (Direção 2013 Heli,
Ator 2014 Mr. Turner) o dado nosso, da competição principal, é o correto.
**Nenhuma contradição encontrada** (≠ "zero erros": o método não prova ausência de erro).
Marcação em DOIS níveis (honesta):
- `S` = confirmado por 2ª fonte (Wikidata OU artigo Wikipédia por-edição).
- `P` = SEM 2ª fonte ainda; só na fonte original curada.

### Fechar os `P` via Wikipédia por-edição — EM ANDAMENTO
2ª fonte usada: **artigos por edição da Wikipédia** ("YYYY Cannes Film Festival",
independentes dos artigos por-prêmio da 1ª passada). 1 fetch por ano confirma todos
os baldes daquele ano de uma vez. (Site oficial festival-cannes.com NÃO serve: a
retrospectiva por ano mostra só o line-up, não os premiados.)
- **Lote 1** (2026-08-09): 12 anos, 18 registros (portão).
- **Lote 2** (2026-08-09): 30 anos conferidos (1956 + 1988–2025), **79 registros
  virados P→S**. **PORTÃO ZERADO**: Filme 85/85, Grande Prêmio 67/67, Júri 84/84,
  Direção 70/70, Roteiro 46/46 — 0 `P`. Sobraram badges de atuação em anos ainda
  não fetchados.
- **Restam 35 `P`** (só atuação, não-portão): ator 14, atriz 21, em ~27 anos de
  1951–2008 não cobertos ainda. Lote 3 = fechar esses (baixa prioridade: badges não
  afetam o set de filmes).

## Streaming (decisão de sequenciamento, 2026-08-07)
Disponibilidade em streaming é a **ÚLTIMA etapa** e deve ser **recorrente** (script que
reroda), NÃO congelada. Motivos: (1) é volátil (muda toda semana); (2) só vale pros
filmes que entram no set; (3) vem junto do TMDB `watch/providers`. Ordem: fechar portão
(Cannes+Oscar) → casar TMDB → enriquecer (pôster/sinopse/streaming) → refresh agendável.

## Regra de dedupe (crítica, ao combinar baldes)
Deduplicar filmes por **título + ano + diretor**, NUNCA só por título. Há colisões
de título entre obras diferentes — ex.: *Othello* de Orson Welles (Filme, Cannes
1952) vs. *Othello* soviético de Sergei Yutkevich (Direção, Cannes 1956) são filmes
distintos. O TMDB também desambigua por ano+diretor. Multi-vitórias do MESMO filme
(ex.: Barton Fink e Elephant, que ganharam Filme+Direção no mesmo ano) devem
colapsar num só card com vários registros de vitória.

## Decisão de método (aberta)
Cannes-topo foi curado à mão (regras difíceis do Grand Prix). Para o resto, avaliar:
- **SPARQL/Wikidata** (script repetível, estruturado) — precisa engenharia de query
  (dedupe, ano de cerimônia, prêmios de pessoa via P1686, balde de roteiro somando
  vários award items).
- **WebFetch de artigos curados** (mais simples de ler, mas passa por modelo-resumo
  que pode introduzir erro).
