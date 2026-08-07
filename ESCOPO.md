# Projeto: Premiações de Cinema

> Documento de escopo e decisões. Pasta `premiacoes/` é temporária (área de
> trabalho dentro do repo do FilmCurator) — mover para o repo/deploy definitivo
> quando essa decisão for tomada. Ver "Decisões em aberto" no fim.

## 1. Natureza do produto
- **Timeline navegável** de filmes premiados, **sem ranking e sem pontuação**.
  (A ideia original de pesos/score por categoria foi descartada.)
- Ordenação padrão: **ano decrescente** (mais recente → mais antigo), com
  **label de ano** dividindo a timeline.
- Projeto **separado do FilmCurator**. Compartilha só a linguagem visual
  (paleta, tipografia), não os dados. Provavelmente rotas próprias.

## 2. Fontes e recorte temporal
- Fontes: **Oscar** e **Cannes**, só isso.
- **Só vitórias** contam (indicações são descartadas, por simplicidade).
- Recorte: **de 1951 em diante**.
  - Motivo: a partir de 1951 o festival de Cannes é anual e contínuo, com um
    "primeiro prêmio" identificável todo ano. Antes disso há anomalias:
    1946 (11 vencedores, um por país), 1947 (prêmios só por gênero, sem prêmio
    principal), e sem festival em 1948 e 1950.

## 3. Portão de inclusão (quais filmes entram no banco)
- Um filme entra se **venceu Melhor Filme, Direção OU Roteiro** — em **qualquer**
  dos dois festivais, pelo menos uma vez.
- **Nível do filme** (não por festival): basta 1 vitória de portão em 1 festival
  para o filme entrar. (Reversão de uma decisão intermediária "B" que era por
  festival — a decisão final é nível do filme.)
- Atuação (Ator/Atriz) **não é portão** — só aparece como badge (ver §5).

## 4. Modelo de dados
Guardar **registros de vitória granulares** — nunca um score agregado. O portão,
os badges, o ano-âncora e a nota são todos **derivados** desses registros.

Registro de vitória (um por prêmio ganho):
```
filme_id        — referência ao filme (título, título original, ano, país,
                  duração, gêneros, sinopse, pôster — via TMDB, como no FilmCurator)
festival        — "cannes" | "oscar"
categoria       — categoria canônica (ver mapeamento no §8)
ano_premio      — ano REAL daquele prêmio naquele festival (Cannes = ano do
                  festival; Oscar = ano da cerimônia)
premiado_nome   — nome da pessoa premiada; usado só nas categorias de ATUAÇÃO
                  (nas demais fica vazio)
```
- Um filme pode ter vários registros (várias categorias, dois festivais).
- **Unidade de exibição = o filme** (um card por filme, com seções por festival).

## 5. Card / exibição
Uma vez que o filme passou no portão, o card mostra **todos os prêmios que ele
ganhou nos dois festivais** — inclusive categorias fora do portão (atuação etc.).

### Badges de prêmio
- Agrupados por festival: **um ícone do festival** (não repetir o ícone por
  prêmio) seguido dos prêmios daquele festival **separados por vírgula**.
- Ícones: **Palma de Ouro** (Cannes) e **estatueta** (Oscar) — vetores oficiais
  em `assets/` (ver §9).
- Categorias de **atuação** trazem o nome do premiado entre parênteses:
  `Melhor Ator (Ernest Borgnine)`.
- Exemplo (filme com Filme+Roteiro em Cannes e Filme no Oscar):
  `🌴 Melhor Filme, Roteiro` · `🏆 Melhor Filme`
- Filme premiado em um festival só → só a seção daquele festival (sem a outra).

### Campos do card (herdados do FilmCurator)
Pôster · título PT · título original · gêneros · meta (diretor · país ·
**duração**) · sinopse · **favorito** (coração) · **streaming** (plataformas BR
via TMDB). Removidos: pontuação e ranking de listas (não existem aqui).

### Ano-âncora e nota
- O card é ancorado na timeline pelo **ano do prêmio de portão mais antigo**
  (mais próximo do ano de exibição do filme).
- **Nota no card** aparece **somente quando os anos dos dois festivais diferem**.
  Como o Oscar premia na cerimônia do ano seguinte, na prática quase todo filme
  premiado nos dois terá nota (ex.: `Cannes 2019 · Oscar 2020`). Filme de um
  festival só → sem nota. Filme premiado nos dois no mesmo ano → sem nota.

## 6. Filtros e ordenação
- **Ordenação:** ano decrescente (padrão).
- **Filtro de fonte:** Oscar / Cannes / ambos.
- **Filtro de ano:** **range único** (um handle, não um range duplo — um range de
  anos não faz sentido aqui). O **mínimo é dinâmico** conforme a fonte
  selecionada: Cannes-only → 1951; Oscar-only → ~1929 (1ª cerimônia); ambos → o
  menor dos dois.
- **Duração:** exibida no card, mas **não** é critério de filtro.
- (Filtro por categoria — ex.: só Melhor Filme — é candidato; validar nos testes.)

## 7. Regras específicas de Cannes
- Vale sempre o **primeiro prêmio do festival naquele ano**, **qualquer que seja
  o rótulo**. Não casar pela string do nome.
  - 1951–1954 e 1964–1974: o topo se chamava **Grand Prix**.
  - 1955–1963 e 1975+: **Palma de Ouro**.
- **Cuidado:** desde 1967 existe um **Grand Prix que é o VICE** da Palma. Esse
  prêmio de segundo lugar **nunca conta** — só o prêmio principal do ano.
- **Empates:** todos os filmes empatados recebem o prêmio (ex.: 1951 e 1952
  tiveram Palma compartilhada). Cada empatado vira um registro de vitória normal.

## 8. Mapeamento de categorias do Oscar → baldes de portão
As categorias do Oscar mudaram de nome ao longo do tempo. Mapear qualquer
variante histórica para os baldes canônicos:

- **Melhor Filme (portão):** Best Picture / Outstanding Picture / Outstanding
  Motion Picture / Best Motion Picture. (No 1º Oscar de 1927/28 houve dois
  prêmios de topo — "Outstanding Picture" e "Unique and Artistic Production";
  fora do nosso recorte de 1951+, mas registrar a regra caso o recorte mude.)
- **Direção (portão):** Best Director / Best Achievement in Directing.
- **Roteiro (portão, balde único):** qualquer categoria de escrita —
  Original Screenplay, Adapted Screenplay, Story and Screenplay, Motion Picture
  Story, Screenplay, etc. **Não** distinguimos Original de Adaptado.
- **Atuação (badge, não-portão):** Best Actor / Best Actress (e supporting, se
  quisermos exibir) — sempre com `premiado_nome`.
- **Demais categorias vencidas (badge):** exibidas como badge normal, sem nome.

Cannes já tem as equivalências diretas: Palme d'Or/Grand Prix = Filme;
Prix de la mise en scène = Direção; Prix du scénario = Roteiro (único);
Prix d'interprétation = Atuação.

## 9. Assets (nesta pasta)
- `assets/palme-dor.svg` — ícone oficial da Palma de Ouro (preenchido, dourado).
- `assets/oscar.svg` — ícone oficial da estatueta (silhueta preenchida; herda
  cor via `fill` / `currentColor`).
- Ambos usados como marcador de festival nos badges. No mockup a estatueta foi
  colorida de dourado via CSS para parear com a palma.

## 10. Decisões em aberto (para depois)
- **Repositório / deploy:** ainda indefinido. Pensar em como publicar no GitHub
  **Pages** (repo próprio? subpasta/subpath do FilmCurator? Pages separado?).
- **Layout do card:** validar nos testes — sinopse embaixo (atual no mockup) vs.
  3ª coluna à direita (como no FilmCurator).
- **Filtro por categoria** na interface: confirmar se entra.
- **Ícone do Oscar:** dourado vs. tom mais neutro — decidir junto ao layout.
- **Fonte de dados dos prêmios:** de onde puxar as listas de vencedores
  (Wikipedia/dataset próprio). Licenciamento OK — listas de premiados são dados
  públicos, não têm proteção autoral.

## 11. Referência histórica útil (Cannes)
- Palma de Ouro criada em **1955** (1ª vencedora: *Marty*, de Delbert Mann).
- **1946:** primeira edição pós-guerra premiou **11 filmes** (um por país
  participante) — gesto diplomático, não empate esportivo. Fora do recorte.
- **1947:** prêmios só por gênero, sem prêmio principal. Fora do recorte.
- **1948 e 1950:** sem festival (problemas financeiros).
