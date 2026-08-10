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
- **DATASET DE CANNES COMPLETO E 100% CONFERIDO** (2026-08-09): **7 baldes, 509
  registros**, 471 pares (título, ano) distintos. Conferência: **509/509
  verificado=S, ZERO P** — cada registro confirmado por 2ª fonte (Wikidata na 1ª
  passada + artigos Wikipédia por-edição nas lotes 1–3). Ver seção Conferência.
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
- [x] **Oscar / Filme, Direção, Roteiro, Filme Estrangeiro, Ator, Atriz** — via Wikidata
      SPARQL (P585 = ano da cerimônia; **recorte cerimônia ≥1929**). `data/raw/oscar_*.csv`,
      **679 registros, 97 edições (1929–2026)**. Ver "Dataset do Oscar" abaixo. verificado=N
      (fonte única Wikidata; falta conferência 2ª fonte).
- [x] **Conferência do Oscar** (flip N→S) — 679/679 via 2ª fonte Wikipedia por-cerimônia
      (commit ad991ba).
- [x] **Combinar baldes** (Cannes+Oscar) → `data/portao.json` via `scripts/build_gate.py`
      (commit 7a2d1dd). Dedupe por título+ano+diretor; **644 filmes distintos no portão**.
- [x] **Enriquecer via TMDB** (estágios 2+3) → `data/filmes.json` via `scripts/enrich.py`
      (commit e9839f7). 644 filmes com pôster, sinopse, país, duração, gêneros e streaming BR.
- [x] **Badges não-portão** — já estão no dado: `premios[]` de cada filme em `filmes.json`
      traz TODAS as vitórias, inclusive atuação. Falta só **renderizar** (etapa de front-end).

## FASE DE FRONT-END + DEPLOY (a fazer — dados prontos)
> Estado (2026-08-09): dataset fechado e enriquecido (644 filmes). O front-end atual
> (`index.html`/`app.js`/`data.js`) ainda é o app do **FilmCurator** copiado como
> placeholder (`data.js` = `window.DB` com listas de críticos Guardian/NYT). O
> `build_views.py` só gera página de conferência, não o app. Falta o app de verdade.

- [ ] **Front-end do FilmFestivals** — substituir o placeholder do FilmCurator. Ligar em
      `data/filmes.json`, descartar `data.js`. Ver ESCOPO §5–6:
  - [ ] Timeline por **ano decrescente** com label de ano dividindo a lista (âncora = `ano_ancora`).
  - [ ] **Card por filme**: badges agrupados por festival (🌴 Palma / 🏆 estatueta),
        atuação com nome entre parênteses, nota `Cannes AAAA · Oscar AAAA` só quando os anos diferem.
  - [ ] **Filtros**: fonte (Oscar/Cannes/ambos), ano (range único, mínimo dinâmico), categoria (a validar).
- [ ] **Decisões de layout em aberto** (ESCOPO §10): sinopse embaixo vs. 3ª coluna;
      filtro por categoria entra?; cor do ícone do Oscar (dourado vs. neutro).
- [ ] **Deploy GitHub Pages** — servir do `main` (metatags já apontam p/ rafaortman.github.io/filmfestivals/).
- [ ] **Streaming recorrente** (última etapa) — script agendável que reroda o TMDB
      `watch/providers` (volátil, muda toda semana). Ver seção "Streaming".

## Dataset do Oscar (2026-08-09): 679 registros, 97 edições (1929–2026)
Fonte: **Wikidata SPARQL** (query.wikidata.org). Decidido usar Wikidata direto porque
as listas por-categoria da Wikipédia via WebFetch **alucinaram** (ex.: "2024 Wicked" como
Best Picture) e **pularam anos** (resumidor). Wikidata é estruturado e não passa por
resumo.
- **Recorte: cerimônia ≥1929** (Rafa, 2026-08-09). O 1951 do ESCOPO §2 era só p/ Cannes
  (que não tem continuidade antes de 1951); o §6 já previa Oscar até 1929. Cannes segue
  1951+; Oscar vai de 1929. Assimetria aceita (filmes só-Oscar em 1929–1950 no início).
- **1933 não existe**: o Oscar não teve cerimônia em 1933 (a 6ª foi em 1934). Ausência
  correta, não buraco.
- **Ano = ano da cerimônia** (ESCOPO §4): vem do qualificador **P585** (point in time)
  do statement P166 (award received). Cobre 1929–2026.
- **Filme** (Q102427): prêmio é recebido pelo filme E pelos produtores → filtrar humanos
  (`MINUS wdt:P31 wd:Q5`). **Pessoa** (Direção Q103360, Roteiro Orig Q41417 + Adapt Q107258,
  Ator Q103916, Atriz Q103618): recebido pela pessoa; filme vem do qualificador **P1686**
  ("for work"); premiado = nome da pessoa.
- **Roteiro = balde único** (ESCOPO §8): junta Original (Q41417) + Adaptado (Q107258) +
  **Best Story/Motion Picture Story (Q504298**, categoria antiga 1929–1957) → 2–3 filmes/
  ano. NÃO é empate (sub-categorias distintas); empate só quando 2 filmes na MESMA
  sub-categoria — não ocorre.
- **QIDs**: Filme Q102427; Direção Q103360 (+ Comédia 1929 Q3451157); Roteiro Q41417 +
  Q107258 + Q504298; **Filme Estrangeiro/Internacional Q105304**; Ator Q103916; Atriz Q103618.
- Baldes: Filme 99, Direção 99, Roteiro 210, **Filme Estrangeiro 70**, Ator 100, Atriz 101
  = **679 registros**.
- **Filme Estrangeiro** (2026-08-09, novo portão — ESCOPO §3): 70 vencedores da categoria
  competitiva (1957 La Strada → 2026), sem buracos. Só a competitiva; honorários 1947–1955
  fora. Adiciona **47 filmes** que nenhum outro portão (Oscar F/D/R ou Cannes) cobria.
- **Anomalias 1929–1932 (dados corretos, modelo antigo do Oscar):** 1929 tem 2 topos de
  Filme (Wings + Sunrise/Unique-Artistic) e Direção dividida Drama (Borzage/Seventh
  Heaven) + Comédia (Milestone/Two Arabian Knights); Ator 1929 = Jannings (2 filmes),
  Atriz 1929 = Gaynor (3 filmes) — 1 pessoa, NÃO empate. **1930 teve 2 cerimônias** (2ª e
  3ª) → 2 filmes com ano=1930, NÃO empate.
- **Empate real (S)**: só os 2 da história p/ nossas categorias — Ator 1932 (March/Beery)
  e Atriz 1969 (Streisand/Hepburn). Todo o resto empate=N (hardcoded; contagem crua por
  ano não serve por causa das anomalias acima).
- **Correções manuais** (lacunas/erros do Wikidata): labels sem inglês resolvidos
  (Forrest Gump, La La Land, Darling, The Lavender Hill Mob); "Daniels" (grupo) removido
  do Filme 2022 (CODA é o certo) e do premiado quando os nomes individuais já constavam;
  **EEAAO** Direção+Roteiro datados 2022 no P585 → corrigido p/ 2023 (95ª); **Streep**
  Atriz 1983/2012 e **Sunrise/Murnau** (Filme 1929) e **Seventh Heaven/Borzage** (Direção
  1929) adicionados (statements sem P585/P1686 no Wikidata).
- Roteiro 1930 (2 cerimônias) preenchido à mão via Wikipédia por-cerimônia: Hans Kraly
  (The Patriot, 2ª) e Frances Marion (The Big House, 3ª). Sem buracos restantes.
- **verificado=N**: fonte única (Wikidata). Próximo = conferência 2ª fonte (Wikipedia
  por-cerimônia "Nth Academy Awards", ordinal = ano−1928; ou oscars.org), flip N→S.

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
- **Lote 3** (2026-08-09): 27 anos (1951–2008) conferidos, **35 registros de atuação
  virados P→S** (ator 14, atriz 21). **CANNES ZERADO: 509/509 = S, 0 P.**

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
