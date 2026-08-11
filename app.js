'use strict';

// ==== FilmFestivals ====
// Mesmo objetivo do FilmCurator (ajudar a escolher um filme): filtros ricos + sorteio.
// A diferença é a base: filmes premiados em Cannes e Oscar (sem ranking/nota), numa
// timeline por ano de premiação (âncora). Dados em data/filmes.json. Ver ESCOPO.md.

const $ = id => document.getElementById(id);
const grid = $('grid');
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---- Vocabulário de prêmios ----
const FEST_NOME = { cannes: 'Cannes', oscar: 'Oscar' };
const CAT_LABEL = {
  'Filme': 'Melhor Filme',
  'Grande Prêmio': 'Grande Prêmio',
  'Prêmio do Júri': 'Prêmio do Júri',
  'Direção': 'Melhor Direção',
  'Roteiro': 'Melhor Roteiro',
  'Filme Estrangeiro': 'Filme Estrangeiro',
  'Ator': 'Melhor Ator',
  'Atriz': 'Melhor Atriz',
};
const CAT_ORDER = ['Filme', 'Grande Prêmio', 'Prêmio do Júri', 'Direção', 'Roteiro', 'Filme Estrangeiro', 'Ator', 'Atriz'];
const catRank = c => { const i = CAT_ORDER.indexOf(c); return i < 0 ? 99 : i; };
const ACTING = new Set(['Ator', 'Atriz']);

// Escala de prestígio por festival (menor = mais alto). Cada festival tem a SUA hierarquia
// (Direção vale mais no Oscar que em Cannes, de propósito). Atuação não é portão: recebe rank
// alto (90) pra entrar só como desempate, nunca decidindo o "melhor prêmio".
const LADDER = {
  cannes: { 'Filme': 1, 'Grande Prêmio': 2, 'Prêmio do Júri': 3, 'Direção': 4, 'Roteiro': 5, 'Ator': 90, 'Atriz': 90 },
  oscar: { 'Filme': 1, 'Direção': 2, 'Roteiro': 3, 'Filme Estrangeiro': 4, 'Ator': 90, 'Atriz': 90 },
};
// Vetor de prestígio: ranks de TODOS os prêmios do filme, do melhor pro pior. Comparado
// lexicograficamente — melhor prêmio primeiro; depois 2º melhor, 3º… (quem tem mais/melhores
// prêmios, inclusive atuação no fim, vem antes). Elemento faltante = pior (Infinity).
const prestigeVec = f => (f.premios || []).map(p => LADDER[p.festival]?.[p.categoria] ?? 999).sort((x, y) => x - y);
function cmpVec(va, vb) {
  const n = Math.max(va.length, vb.length);
  for (let i = 0; i < n; i++) {
    const a = va[i] ?? Infinity, b = vb[i] ?? Infinity;
    if (a !== b) return a - b;
  }
  return 0;
}

// ---- Acessores dos dados ----
const festivaisDe = f => Object.keys(f.anos_portao || {});           // ['cannes'] | ['oscar'] | ambos
const anoFest = (f, fest) => { const a = f.anos_portao?.[fest]; return a && a.length ? Math.min(...a) : null; };
const titleOf = f => f.titulo_pt || f.titulo_orig || f.titulo_lista || '';
const dirOf = f => f.diretor_tmdb || f.diretor_lista || '';
const platsOf = f => f.streaming || [];
const genresOf = f => f.generos || [];
const countriesOf = f => (f.pais ? f.pais.split('/').map(s => s.trim()).filter(Boolean) : []);

// ---- Estado ----
const state = {
  q: '',
  sources: new Set(['cannes', 'oscar']),   // festivais (união): filme passa se está em ≥1
  onlyBoth: false,                         // só filmes premiados nos DOIS festivais
  platform: '',
  country: '',
  director: '',
  genre: '',
  maxDur: 9999,
  yearMin: 0,
  yearMax: 9999,
  onlyStream: false,
  sort: 'yearDesc',
  favView: false,
};

// ---- Favoritos (localStorage) ----
const FAV_KEY = 'filmfestivals:favs';
const favs = (() => {
  try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY)) || []); }
  catch { return new Set(); }
})();
const saveFavs = () => localStorage.setItem(FAV_KEY, JSON.stringify([...favs]));

let FILMS = [];
let YMIN = 0, YMAX = 0, DUR_MAX = 321;

const HEART_SVG = '<svg viewBox="0 -960 960 960" aria-hidden="true"><path d="M480-120l-58-52q-101-91-167-157T150-447.5Q111-500 95.5-544T80-634q0-94 63-159t157-65q52 0 99 22t81 62q34-40 81-62t99-22q94 0 157 65t63 159q0 46-15.5 90T810-447.5Q771-395 705-329T538-172l-58 52Z"/></svg>';

// ---- Utilidades ----
const uniqueSorted = arr => [...new Set(arr)].sort((a, b) => a.localeCompare(b, 'pt-BR'));

function updateYearLabel() {
  $('yearVal').textContent = (state.yearMin <= YMIN && state.yearMax >= YMAX)
    ? 'todos os anos' : `${state.yearMin} – ${state.yearMax}`;
  const span = (YMAX - YMIN) || 1;
  $('yearFill').style.left = (state.yearMin - YMIN) / span * 100 + '%';
  $('yearFill').style.right = (100 - (state.yearMax - YMIN) / span * 100) + '%';
}

// ---- Filtro ----
function matches(f) {
  if (state.q) {
    const q = state.q.toLowerCase();
    const hay = `${f.titulo_pt || ''} ${f.titulo_orig || ''} ${f.titulo_lista || ''} ${dirOf(f)}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  if (!festivaisDe(f).some(fest => state.sources.has(fest))) return false;
  if (state.onlyBoth && festivaisDe(f).length < 2) return false;
  if (state.platform && !platsOf(f).includes(state.platform)) return false;
  if (state.country && !countriesOf(f).includes(state.country)) return false;
  if (state.director && dirOf(f) !== state.director) return false;
  if (state.genre && !genresOf(f).includes(state.genre)) return false;
  if (f.duracao != null && f.duracao > state.maxDur) return false;
  if (f.ano_ancora < state.yearMin || f.ano_ancora > state.yearMax) return false;
  if (state.onlyStream && platsOf(f).length === 0) return false;
  return true;
}

function sortFn(a, b) {
  switch (state.sort) {
    case 'yearDesc': return (b.ano_ancora - a.ano_ancora) || cmpVec(a._pv, b._pv) || titleOf(a).localeCompare(titleOf(b), 'pt-BR');
    case 'yearAsc': return (a.ano_ancora - b.ano_ancora) || cmpVec(a._pv, b._pv) || titleOf(a).localeCompare(titleOf(b), 'pt-BR');
    case 'titleAZ': return titleOf(a).localeCompare(titleOf(b), 'pt-BR');
    case 'durAsc': return (a.duracao ?? 9999) - (b.duracao ?? 9999);
    case 'durDesc': return (b.duracao ?? -1) - (a.duracao ?? -1);
    default: return 0;
  }
}
const isTimeline = () => state.sort === 'yearDesc' || state.sort === 'yearAsc';

// ---- Render ----
function awards(f) {
  const byFest = { cannes: [], oscar: [] };
  for (const p of f.premios || []) if (byFest[p.festival]) byFest[p.festival].push(p);
  const rows = [];
  for (const fest of ['cannes', 'oscar']) {
    const ps = byFest[fest];
    if (!ps.length) continue;
    ps.sort((a, b) => catRank(a.categoria) - catRank(b.categoria) || a.ano - b.ano);
    const txt = ps.map(p => {
      let t = CAT_LABEL[p.categoria] || p.categoria;
      if (ACTING.has(p.categoria) && p.premiado) t += ` (${p.premiado})`;
      return esc(t);
    }).join(', ');
    rows.push(`<div class="award"><img class="fest-ic" src="assets/${fest}-circle.svg" alt="${FEST_NOME[fest]}" title="${FEST_NOME[fest]}"><span class="aw-txt">${txt}</span></div>`);
  }
  return `<div class="awards">${rows.join('')}</div>`;
}

// Nota só quando os anos dos dois festivais diferem (ESCOPO §5)
function yearNote(f) {
  const c = anoFest(f, 'cannes'), o = anoFest(f, 'oscar');
  if (c != null && o != null && c !== o) return `<div class="fnote">Cannes ${c} · Oscar ${o}</div>`;
  return '';
}

function card(f) {
  const id = f.tmdb_id;
  const isFav = favs.has(id);
  const fav = `<button class="cardfav${isFav ? ' on' : ''}" data-id="${id}" type="button" aria-pressed="${isFav}" aria-label="${isFav ? 'Desfavoritar' : 'Favoritar'}">${HEART_SVG}</button>`;
  const primary = titleOf(f);
  const orig = (f.titulo_orig && f.titulo_orig !== primary) ? `<div class="cpt">${esc(f.titulo_orig)}</div>` : '';
  const poster = f.poster_path
    ? `<img class="poster" src="https://image.tmdb.org/t/p/w185${f.poster_path}" alt="Pôster de ${esc(primary)}" loading="lazy">`
    : `<div class="poster none">sem pôster</div>`;
  const genres = genresOf(f).length
    ? `<div class="genres">${genresOf(f).map(g => `<span class="gtag">${esc(g)}</span>`).join('')}</div>` : '';
  const plats = platsOf(f).length
    ? platsOf(f).map(p => `<span class="plat">${esc(p)}</span>`).join('')
    : `<span class="plat none">sem streaming BR</span>`;
  const dir = dirOf(f);
  const pais = f.pais ? esc(countriesOf(f)[0] || '') : '';
  const synText = (f.sinopse && f.sinopse.trim()) ? esc(f.sinopse) : 'Sinopse indisponível.';
  const syn = `<div class="csyn"><p class="synopsis">${synText}</p></div>`;
  const q = `${primary} ${f.ano_lancamento ?? ''} assistir online`.trim();
  return `<article class="card" data-q="${esc(q)}">
    ${fav}
    ${poster}
    <div class="cbody">
      <div class="ct">${esc(primary)}</div>
      ${orig}
      ${awards(f)}
      ${yearNote(f)}
      ${genres}
      <div class="meta">
        ${dir ? `<span><b>${esc(dir)}</b></span>` : ''}
        ${f.ano_lancamento != null ? `<span>${f.ano_lancamento}</span>` : ''}
        ${pais ? `<span>${pais}</span>` : ''}
        ${f.duracao != null ? `<span>${f.duracao} min</span>` : ''}
      </div>
      <div class="plats">${plats}</div>
    </div>
    ${syn}
  </article>`;
}

function render() {
  const base = state.favView ? FILMS.filter(f => favs.has(f.tmdb_id)) : FILMS.filter(matches);
  const list = base.slice().sort(sortFn);
  $('n').textContent = list.length;
  if (!list.length) {
    grid.innerHTML = `<div class="empty">${state.favView ? 'Nenhum favorito ainda.' : 'Nenhum filme com esses filtros.'}</div>`;
    return;
  }
  // Timeline (ordenação por ano) recebe divisores de ano; demais ordenações vão em grade lisa.
  if (isTimeline()) {
    let html = '', lastYear = null;
    for (const f of list) {
      if (f.ano_ancora !== lastYear) { html += `<div class="yearsep">${f.ano_ancora}</div>`; lastYear = f.ano_ancora; }
      html += card(f);
    }
    grid.innerHTML = html;
  } else {
    grid.innerHTML = list.map(card).join('');
  }
}

// ---- Coração global (modo favoritos) ----
function updateFavView() {
  const btn = $('favView');
  const has = favs.size > 0;
  btn.setAttribute('aria-disabled', String(!has));
  if (!has) state.favView = false;
  btn.setAttribute('aria-pressed', String(state.favView));
  btn.title = state.favView ? 'Ver todos' : 'Ver favoritos';
  btn.setAttribute('aria-label', btn.title);
}

let toastTimer;
function toast(msg) {
  const el = $('toast'); if (!el) return;
  el.textContent = msg; el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
}

function toggleFav(id) {
  id = +id;
  if (favs.has(id)) favs.delete(id); else favs.add(id);
  saveFavs(); updateFavView(); render();
}

function syncSourceChips() {
  document.querySelectorAll('#sourceChips .chip').forEach(c =>
    c.classList.toggle('on', state.sources.has(c.dataset.fest)));
}

// ---- Eventos ----
grid.addEventListener('click', e => {
  const favBtn = e.target.closest('.cardfav');
  if (favBtn) { toggleFav(favBtn.dataset.id); return; }
  if (String(window.getSelection())) return;
  const cardEl = e.target.closest('.card'); if (!cardEl) return;
  const q = cardEl.dataset.q; if (!q) return;
  window.open('https://www.google.com/search?q=' + encodeURIComponent(q), '_blank', 'noopener');
});

$('q').addEventListener('input', e => { state.q = e.target.value.trim(); render(); });

$('sourceChips').addEventListener('click', e => {
  const chip = e.target.closest('.chip'); if (!chip) return;
  const k = chip.dataset.fest;
  if (state.sources.has(k)) state.sources.delete(k); else state.sources.add(k);
  chip.classList.toggle('on');
  render();
});

$('platform').addEventListener('change', e => { state.platform = e.target.value; render(); });
$('country').addEventListener('change', e => { state.country = e.target.value; render(); });
$('director').addEventListener('change', e => { state.director = e.target.value; render(); });
$('genre').addEventListener('change', e => { state.genre = e.target.value; render(); });
$('onlyStream').addEventListener('change', e => { state.onlyStream = e.target.checked; render(); });
$('onlyBoth').addEventListener('change', e => { state.onlyBoth = e.target.checked; render(); });

$('dur').addEventListener('input', e => {
  state.maxDur = +e.target.value;
  $('durVal').textContent = state.maxDur >= DUR_MAX ? 'qualquer' : `até ${state.maxDur} min`;
  render();
});

$('yearMin').addEventListener('input', e => {
  let v = +e.target.value;
  if (v > state.yearMax) { v = state.yearMax; e.target.value = v; }
  state.yearMin = v; updateYearLabel(); render();
});
$('yearMax').addEventListener('input', e => {
  let v = +e.target.value;
  if (v < state.yearMin) { v = state.yearMin; e.target.value = v; }
  state.yearMax = v; updateYearLabel(); render();
});

$('sort').addEventListener('change', e => { state.sort = e.target.value; render(); });

$('favView').addEventListener('click', () => {
  if (favs.size === 0) {
    toast('Você ainda não favoritou nenhum filme. Toque no ♥ de um filme para salvá-lo aqui.');
    return;
  }
  state.favView = !state.favView;
  updateFavView(); render();
});

$('reset').addEventListener('click', () => {
  Object.assign(state, {
    q: '', platform: '', country: '', director: '', genre: '',
    maxDur: DUR_MAX, yearMin: YMIN, yearMax: YMAX, onlyStream: false, sort: 'yearDesc',
  });
  state.sources = new Set(['cannes', 'oscar']);
  state.onlyBoth = false;
  $('q').value = ''; $('platform').value = ''; $('country').value = ''; $('director').value = ''; $('genre').value = '';
  $('dur').value = DUR_MAX; $('durVal').textContent = 'qualquer'; $('onlyStream').checked = false; $('onlyBoth').checked = false; $('sort').value = 'yearDesc';
  $('yearMin').value = YMIN; $('yearMax').value = YMAX; updateYearLabel();
  syncSourceChips();
  render();
});

// Colapsar filtros (mobile)
const filtersEl = document.querySelector('.filters');
$('filtersToggle').addEventListener('click', () => {
  const collapsed = filtersEl.classList.toggle('collapsed');
  $('filtersToggle').setAttribute('aria-expanded', String(!collapsed));
});

// ---- Sorteio ----
const shuffleModal = $('shuffleModal');
const shuffleResult = $('shuffleResult');
const selGenre = $('lockGenre');
const selPlat = $('lockPlatform');
let currentDraw = null;

const basePool = () => FILMS.filter(matches);
function drawPool() {
  let pool = basePool();
  if (selGenre.value) pool = pool.filter(f => genresOf(f).includes(selGenre.value));
  if (selPlat.value) pool = pool.filter(f => platsOf(f).includes(selPlat.value));
  return pool;
}
const pickRandom = pool => pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;

function renderResult() {
  if (currentDraw) { shuffleResult.innerHTML = card(currentDraw); return; }
  shuffleResult.innerHTML = basePool().length === 0
    ? `<div class="modal-msg">Nenhum filme com os filtros da barra lateral.<br>Feche o sorteio e ajuste os filtros para começar.</div>`
    : `<div class="modal-msg">Nenhum filme com esse gênero e plataforma.<br>Altere os critérios abaixo e sorteie de novo.
         <br><button type="button" class="reset" id="clearReroll">Limpar critérios</button></div>`;
}

function openShuffle() {
  selGenre.value = ''; selPlat.value = '';
  currentDraw = pickRandom(basePool());
  renderResult();
  shuffleModal.classList.add('open');
}
const closeShuffle = () => shuffleModal.classList.remove('open');

$('shuffle').addEventListener('click', openShuffle);
$('shuffleClose').addEventListener('click', closeShuffle);
shuffleModal.addEventListener('click', e => { if (e.target === shuffleModal) closeShuffle(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeShuffle(); });

$('shuffleAgain').addEventListener('click', () => {
  currentDraw = pickRandom(drawPool());
  renderResult();
});

shuffleResult.addEventListener('click', e => {
  const favBtn = e.target.closest('.cardfav');
  if (favBtn) { toggleFav(favBtn.dataset.id); renderResult(); return; }
  if (e.target.closest('#clearReroll')) {
    selGenre.value = ''; selPlat.value = '';
    currentDraw = pickRandom(basePool());
    renderResult();
    return;
  }
  const cardEl = e.target.closest('.card');
  if (cardEl && cardEl.dataset.q && !String(window.getSelection())) {
    window.open('https://www.google.com/search?q=' + encodeURIComponent(cardEl.dataset.q), '_blank', 'noopener');
  }
});

// Rodapé: data da checagem de streaming mais recente
function stampUpdated() {
  const el = $('updated'); if (!el) return;
  const dates = FILMS.map(f => f.streaming_checked_at).filter(Boolean).sort();
  if (!dates.length) return;
  const [y, mo, d] = dates[dates.length - 1].split('-');
  el.textContent = `Streamings atualizados em ${d}/${mo}/${y}`;
}

// ---- Boot ----
async function boot() {
  try {
    const res = await fetch('data/filmes.json');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    FILMS = await res.json();
    FILMS.forEach(f => { f._pv = prestigeVec(f); });
  } catch (err) {
    grid.innerHTML = `<div class="empty">Não foi possível carregar os dados (${esc(err.message)}).<br>Rode via um servidor local (não abra o arquivo direto).</div>`;
    return;
  }

  // Limites de ano (âncora) e duração a partir dos dados
  const anos = FILMS.map(f => f.ano_ancora).filter(a => a != null);
  YMIN = Math.min(...anos); YMAX = Math.max(...anos);
  const durs = FILMS.map(f => f.duracao).filter(d => d != null);
  DUR_MAX = durs.length ? Math.max(...durs) : 321;
  state.yearMin = YMIN; state.yearMax = YMAX; state.maxDur = DUR_MAX;

  for (const el of [$('yearMin'), $('yearMax')]) { el.min = YMIN; el.max = YMAX; }
  $('yearMin').value = YMIN; $('yearMax').value = YMAX; updateYearLabel();
  const durEl = $('dur');
  durEl.min = Math.min(...durs); durEl.max = DUR_MAX; durEl.value = DUR_MAX;
  $('durVal').textContent = 'qualquer';

  // Selects (escalam sozinhos com os dados)
  uniqueSorted(FILMS.flatMap(platsOf)).forEach(p => $('platform').add(new Option(p, p)));
  uniqueSorted(FILMS.flatMap(countriesOf)).forEach(c => $('country').add(new Option(c, c)));
  uniqueSorted(FILMS.map(dirOf).filter(Boolean)).forEach(d => $('director').add(new Option(d, d)));
  uniqueSorted(FILMS.flatMap(genresOf)).forEach(g => $('genre').add(new Option(g, g)));
  uniqueSorted(FILMS.flatMap(genresOf)).forEach(g => selGenre.add(new Option(g, g)));
  uniqueSorted(FILMS.flatMap(platsOf)).forEach(p => selPlat.add(new Option(p, p)));

  syncSourceChips();
  updateFavView();
  stampUpdated();
  render();
}

boot();
