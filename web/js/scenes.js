// Pixel scenes, after lighthouses/web/js/scenes.js: tiny 96 × 54 canvases drawn with hard pixels at
// 15 fps and scaled up with CSS `image-rendering: pixelated`. One side-view scene per archetype for the
// top of each plant card: day/night sky from the real IST clock, and smoke, steam, rotors, water,
// conveyors and trains that follow getState().load (0..1).
//
//   const stop = mountScene(canvas, 'coal', () => ({ load: 0.7 }));   // later: stop()
//
// getState() -> { load: 0..1, t?: epoch seconds (simulated clock; default wall clock),
//                 plant?: plant record (optional: coal scenes draw sea cooling instead of a cooling tower) }
export const W = 96, H = 54;
const FPS = 15;
const scenes = new Set();
let raf = 0, last = 0;
const reduced = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
const io = typeof IntersectionObserver === 'function'
  ? new IntersectionObserver(es => { for (const e of es) if (e.target.__scene) e.target.__scene.visible = e.isIntersecting; })
  : null;

/* ---------------------------------------------------------------- helpers */
const hash = (i, s = 0) => { const x = Math.sin(i * 12.9898 + s * 78.233 + 1.7) * 43758.5453; return x - Math.floor(x); };
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
function rgb(c) { const n = parseInt(c.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
const mixCache = new Map();
function mix(a, b, t) {
  t = clamp(t, 0, 1);
  const k = a + b + Math.round(t * 32);
  let v = mixCache.get(k);
  if (v) return v;
  const A = rgb(a), B = rgb(b);
  v = '#' + A.map((x, i) => Math.round(x + (B[i] - x) * Math.round(t * 32) / 32).toString(16).padStart(2, '0')).join('');
  if (mixCache.size > 4000) mixCache.clear();
  mixCache.set(k, v);
  return v;
}
function rgba(c, a) { const [r, g, b] = rgb(c); return `rgba(${r},${g},${b},${clamp(a, 0, 1).toFixed(3)})`; }

// drawing state for the scene being drawn
let X = null, N = 0, LIT = 0;                          // ctx, night 0..1, light level for windows
const tone = c => (N < 0.02 ? c : mix(c, '#0a0f24', N * 0.6));
function raw(x, y, w, h, c) { X.fillStyle = c; X.fillRect(Math.round(x), Math.round(y), Math.max(1, Math.round(w)), Math.max(1, Math.round(h))); }
const r = (x, y, w, h, c) => raw(x, y, w, h, tone(c));
const p = (x, y, c) => raw(x, y, 1, 1, tone(c));
const pr = (x, y, c) => raw(x, y, 1, 1, c);
function line(x0, y0, x1, y1, c, toned = true) {
  x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let e = dx + dy;
  const col = toned ? tone(c) : c;
  for (;;) {
    raw(x0, y0, 1, 1, col);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * e;
    if (e2 >= dy) { e += dy; x0 += sx; }
    if (e2 <= dx) { e += dx; y0 += sy; }
  }
}
// a window: dark glass by day, lit ∝ load at night (and a little by day)
const win = (x, y, c = '#ffc46b', w = 1, h = 1) => raw(x, y, w, h, mix(tone('#4d5c68'), c, LIT));
// block with light from the left (a highlight column) and shade on the right
function block(x, y, w, h, c, o = {}) {
  r(x, y, w, h, c);
  r(x, y, 1, h, mix(c, '#ffffff', 0.18));
  r(x + w - 1, y, 1, h, mix(c, '#000000', 0.22));
  if (o.roof) r(x, y, w, 1, o.roof);
}
function sag(x0, y0, x1, y1, s, c) {                   // sagging conductor
  const n = Math.max(1, Math.abs(x1 - x0));
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    p(x0 + (x1 - x0) * u, y0 + (y1 - y0) * u + s * 4 * u * (1 - u), c);
  }
}
const sagAt = (x0, y0, x1, y1, s, u) => [x0 + (x1 - x0) * u, y0 + (y1 - y0) * u + s * 4 * u * (1 - u)];

/* -------------------------------------------------------------- the clock */
function env(t) {
  const d = t > 1e9 ? new Date(t * 1000) : new Date();
  const h = (d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600 + 5.5) % 24;
  const elev = Math.sin(Math.PI * (h - 6.1) / 12.4);
  const day = clamp(elev * 4 + 0.15, 0, 1);
  const dusk = clamp(1 - Math.abs(elev) * 4.5, 0, 1);
  return { h, elev, day, night: 1 - day, dusk };
}

function sky(e, t, hz, o = {}) {
  const top = mix(mix('#070b1e', '#4f8fcf', e.day), '#3a3f78', e.dusk * 0.6);
  const bot = mix(mix('#1d2a55', '#a9d4ee', e.day), '#f0a262', e.dusk * 0.85);
  const bands = 7;
  for (let i = 0; i < bands; i++) raw(0, Math.floor(i * hz / bands), W, Math.ceil(hz / bands) + 1, mix(top, bot, i / (bands - 1)));
  if (e.night > 0.35) for (let i = 0; i < 24; i++) {
    const tw = (0.35 + 0.65 * Math.abs(Math.sin(t * (0.6 + hash(i, 3)) + i))) * (e.night - 0.35) / 0.65;
    raw(hash(i, 1) * W, hash(i, 2) * (hz - 8), 1, 1, rgba('#dfe7ff', tw));
  }
  // sun on its arc, moon at night
  if (e.elev > -0.12) {
    const u = clamp((e.h - 6.1) / 12.4, 0, 1), sx = 6 + u * 84, sy = hz - 3 - Math.max(0, e.elev) * (hz - 8);
    const sc = mix('#fff1a8', '#ff9a4a', e.dusk);
    raw(sx - 2, sy - 1, 5, 3, sc); raw(sx - 1, sy - 2, 3, 5, sc);
    if (e.day > 0.5) { raw(sx - 4, sy, 1, 1, rgba(sc, 0.6)); raw(sx + 4, sy, 1, 1, rgba(sc, 0.6)); raw(sx, sy - 4, 1, 1, rgba(sc, 0.6)); }
  } else if (!o.noMoon) {
    raw(82, 5, 4, 4, '#e8ecf5'); raw(81, 6, 1, 2, '#e8ecf5'); raw(86, 6, 1, 2, '#e8ecf5'); raw(84, 6, 1, 1, '#c3c9d6');
  }
  // clouds
  if (!o.noClouds) for (let i = 0; i < 3; i++) {
    const cx = ((hash(i, 11) * (W + 30) + t * (0.8 + i * 0.4)) % (W + 30)) - 15, cy = 4 + i * 5 + Math.floor(hash(i, 12) * 4);
    const cc = rgba(mix(mix('#2a3355', '#ffffff', e.day), '#ffc9a0', e.dusk * 0.6), 0.85);
    raw(cx, cy, 10, 2, cc); raw(cx + 2, cy - 1, 5, 1, cc); raw(cx + 3, cy + 2, 6, 1, cc);
  }
}

function hills(hz, c, amp, seed, base = 0) {
  for (let x = 0; x < W; x++) {
    const hgt = Math.round(amp * (0.55 + 0.45 * Math.sin(x * 0.07 + seed) * Math.sin(x * 0.023 + seed * 2)) + base);
    r(x, hz - hgt, 1, hgt, c);
  }
}

function ground(y, c, speck, h = H - y) {
  r(0, y, W, h, c);
  for (let i = 0; i < 40; i++) p(Math.floor(hash(i, 31) * W), y + 1 + Math.floor(hash(i, 32) * (h - 1)), speck);
}

function sea(y, t, L = 0) {
  const c0 = mix(mix('#0a2442', '#3a76a0', 1 - N), '#e08a5a', 0), c1 = mix(mix('#061629', '#2b5e86', 1 - N), '#000000', 0);
  const rows = Math.max(1, Math.ceil((H - y) / 4));
  for (let i = 0; i < rows; i++) raw(0, y + i * 4, W, 4, mix(c0, c1, i / rows));
  for (let i = 0; i < 26; i++) {
    const yy = y + 1 + Math.floor(hash(i, 7) * (H - y - 1));
    const xx = (hash(i, 8) * W + t * (2 + 3 * hash(i, 9)) * (i % 2 ? 1 : -1) + W * 4) % W;
    raw(xx, yy, 2 + Math.floor(hash(i, 10) * 3), 1, rgba(mix('#5da9ff', '#e6f3ff', 1 - N), 0.3 + 0.2 * Math.sin(t * 2 + i)));
  }
}

// voxel puffs rising from (x, y): smoke, steam, heat; count ∝ load, none at zero load
function plume(x, y, t, L, o = {}) {
  const n = o.n || 12, life = o.life || 5, rise = o.rise || 24, drift = o.drift || 18, s0 = o.s0 || 1, grow = o.grow || 3, seed = o.seed || x;
  const cols = o.cols || ['#9a9a96', '#8a8a87', '#aaa9a4'];
  if (L < 0.02) return;
  for (let i = 0; i < n; i++) {
    const ph = t / life + i / n + hash(seed), cyc = Math.floor(ph), a = ph - cyc;
    if (hash(i + seed * 7, cyc) > L * 1.08) continue;
    const s = Math.round(s0 + grow * a);
    const px = x + drift * Math.pow(a, 1.4) + (hash(i, cyc + 1) - 0.5) * (o.spread || 3) * (0.5 + a) - s / 2;
    const py = y - rise * a * (0.6 + 0.4 * L) - s / 2;
    const c = tone(cols[i % cols.length]);
    const al = (o.alpha || 1) * (1 - a * 0.75);
    if (s >= 3) { raw(px + 1, py, s - 2, s, rgba(c, al)); raw(px, py + 1, 1, s - 2, rgba(c, al)); raw(px + s - 1, py + 1, 1, s - 2, rgba(c, al)); }
    else raw(px, py, s, s, rgba(c, al));
  }
}
const SMOKE = { cols: ['#9a9a96', '#8a8a87', '#b0afaa', '#7d7c79'] };
const STEAM = { cols: ['#f4f5f6', '#e6e8ea', '#ffffff'], life: 7, rise: 16, drift: 10, s0: 3, grow: 5, n: 14, spread: 8 };

/* ------------------------------------------------------------ components */
function chimney(x, base, top, w = 4, o = {}) {
  const hgt = base - top, y3 = top + Math.round(hgt / 3);
  for (let y = top; y < base; y++) {
    const ww = Math.round(w - (w - Math.max(2, w - 1)) * (base - y) / hgt);
    const band = o.bands !== false && y < y3 ? (Math.floor((y - top) / 2) % 2 === 0 ? '#b8342a' : '#ece9e1') : (o.color || '#aaa79e');
    r(x, y, ww, 1, band);
    p(x + ww - 1, y, mix(band, '#000000', 0.25));
  }
  r(x - 1, top, w + 1, 1, '#3a3836');
  if (o.bands !== false) r(x - 1, y3, w + 1, 1, '#4c535b');
  if (o.light !== false) { const on = (performance.now() / 1000 % 1.5) < 0.25; pr(x + 1, top - 1, on ? '#ff3a26' : mix('#5a1a14', '#ff3a26', N * 0.2)); }
  return [x + w / 2, top];
}

function coolingTower(x, base, hgt, w) {
  const yt = base - Math.round(hgt * 0.8);
  for (let y = base - hgt; y < base; y++) {
    const k = y < yt ? (yt - y) / (hgt * 0.2) : (y - yt) / (hgt * 0.8);
    const half = Math.round(w / 2 * (y < yt ? 0.6 + 0.04 * k * k : 0.6 + 0.4 * k * k));
    const c = y === base - 1 ? '#6f6d68' : '#c9c6bd';
    r(x - half, y, half * 2, 1, c);
    p(x - half, y, mix(c, '#ffffff', 0.15)); r(x + half - 2, y, 2, 1, mix(c, '#000000', 0.18));
  }
  for (let i = -Math.round(w / 2) + 1; i < w / 2; i += 2) p(x + i, base - 1, '#2b2a28');
  return [x, base - hgt];
}

function pylonSmall(x, base, hgt, c = '#9aa1a7') {
  for (let y = 0; y < hgt; y++) {
    const half = Math.round((1 - y / hgt) * hgt * 0.18) + 1;
    p(x - half, base - y, c); p(x + half, base - y, c);
    if (y % 3 === 0) line(x - half, base - y, x + half, base - y, c);
  }
  r(x - hgt * 0.3, base - hgt * 0.72, hgt * 0.6 + 1, 1, c);
  r(x - hgt * 0.22, base - hgt * 0.88, hgt * 0.44 + 1, 1, c);
}

function tree(x, y, s = 1) {
  r(x, y - 2 * s, 1, 2 * s, '#5b4330');
  r(x - 1 - (s > 1), y - 4 * s, 3 + 2 * (s > 1), 2 * s + 1, '#3a6230');
  p(x - 1, y - 4 * s, '#4c7a3a');
}
function palm(x, y, h = 9) {
  for (let i = 0; i < h; i++) p(x + Math.round(Math.sin(i * 0.25) * 1), y - i, '#6d5a40');
  const tx = x + Math.round(Math.sin(h * 0.25)), ty = y - h;
  for (const [dx, dy] of [[-3, 1], [-2, 0], [-1, -1], [1, -1], [2, 0], [3, 1], [0, -1], [-4, 2], [4, 2]]) p(tx + dx, ty + dy, '#3f7a34');
}

function turbine(x, base, hgt, R, angle, o = {}) {
  const c = o.c || '#eceeef';
  for (let y = 0; y < hgt; y++) { const w = y < hgt * 0.4 ? 2 : 1; r(x - (w > 1 ? 1 : 0), base - y, w, 1, c); if (w > 1) p(x, base - y, mix(c, '#000000', 0.2)); }
  const hy = base - hgt;
  r(x - 1, hy - 1, Math.max(3, R * 0.25), 2, '#dfe2e4');
  for (let b = 0; b < 3; b++) {
    const a = angle + b * Math.PI * 2 / 3;
    const tx = x + Math.cos(a) * R, ty = hy + Math.sin(a) * R;
    line(x, hy, tx, ty, c);
    if (R > 10) line(x + Math.cos(a + 0.5) * 1.5, hy + Math.sin(a + 0.5) * 1.5, x + Math.cos(a + 0.08) * R * 0.55, hy + Math.sin(a + 0.08) * R * 0.55, mix(c, '#000000', 0.12));
    p(tx, ty, '#c8403a');
    if (R > 8) p(x + Math.cos(a) * (R - 1), hy + Math.sin(a) * (R - 1), '#c8403a');
  }
  p(x, hy, '#b9bec2');
}

function gantry(x0, x1, base, hgt) {
  const c = '#9aa1a7';
  for (const x of [x0, x1]) for (let y = 0; y < hgt; y++) { p(x, base - y, c); p(x + 1, base - y, c); if (y % 3 === 1) p(x + (y % 2), base - y, '#6c737a'); }
  for (let x = x0; x <= x1 + 1; x++) { p(x, base - hgt, c); if (x % 2 === 0) p(x, base - hgt + 1, c); }
}

function trafo(x, y, w, h, L, t) {
  block(x, y, w, h, '#5a646b', { roof: '#4a535a' });
  for (let i = x + 1; i < x + w - 1; i += 2) r(i, y + 2, 1, h - 3, '#454e55');
  for (let i = 0; i < 3; i++) { r(x + 2 + i * Math.floor((w - 4) / 2), y - 3, 1, 3, '#8d5b3d'); p(x + 2 + i * Math.floor((w - 4) / 2), y - 4, '#b0b6ba'); }
  r(x + w - 4, y - 2, 4, 2, '#6c767c');
  // hum: little arcs pulsing ∝ load
  if (L > 0.05) {
    const k = Math.floor(t * (2 + 6 * L)) % 3;
    for (let i = 0; i <= k; i++) raw(x + w + 1 + i * 2, y + 1 + i, 1, h - 2 - i * 2 > 0 ? h - 2 - i * 2 : 1, rgba('#ffe27a', 0.45 * L));
  }
}

function hull(x0, x1, deck, wl, c, boot, o = {}) {
  for (let x = x0; x <= x1; x++) {
    const bow = x > x1 - 8 ? (x - (x1 - 8)) / 8 : 0, stern = x < x0 + 3 ? (x0 + 3 - x) / 3 : 0;
    const top = deck - (bow > 0 ? Math.round(bow * 2) : 0), bot = wl - Math.round(bow * bow * 3) - Math.round(stern * 2);
    r(x, top, 1, bot - top, c);
    p(x, bot - 1, boot);
    p(x, top, mix(c, '#ffffff', 0.25));
  }
  if (o.name) for (let i = 0; i < 6; i++) p(x1 - 12 + i, deck + 2, '#e6e2d6');
}

function wake(x, y, t, L) {
  if (L < 0.02) return;
  for (let i = 0; i < 16; i++) {
    const a = ((t * 0.6 + i / 16) % 1);
    if (hash(i, Math.floor(t * 0.6 + i / 16)) > L * 1.1) continue;
    raw(x - a * 40, y + (hash(i, 3) - 0.5) * a * 6, 2, 1, rgba('#e6f3ff', 0.8 * (1 - a)));
  }
}

/* ------------------------------------------------------------------ scenes */
const S = {};

S.coal = (t, L, e, st, s) => {
  const hz = 38;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 4, 1.3);
  ground(hz, '#8f8a78', '#7d786a');
  r(0, 47, W, 2, '#6a6660');
  const seaCooled = st.plant && /sea|once/i.test(`${st.plant.water?.cooling || ''} ${st.plant.water?.source || ''}`) && !(st.plant.structure?.cooling_towers > 0);
  // coal heap + stacker-reclaimer
  for (let x = 1; x < 27; x++) { const h = Math.max(0, Math.round(9 - Math.abs(x - 13) * 0.75)); r(x, 44 - h, 1, h, '#232427'); if (h > 1 && hash(x, 5) > 0.6) p(x, 44 - h, '#3a3b40'); }
  r(0, 44, 28, 1, '#3a3834');
  line(24, 41, 13, 36, '#d67a2c'); r(22, 40, 4, 3, '#d9a72b'); r(11, 35, 3, 3, '#3d3d3d');
  // conveyor gallery up to the bunker bay, coal moving ∝ load
  line(26, 42, 38, 21, '#7d8f9c'); line(27, 42, 39, 21, '#7d8f9c');
  for (let k = 0; k < 4; k++) { const x = 28 + k * 3, y = Math.round(42 - (k * 3 + 2) * 21 / 12); r(x, y, 1, 44 - y, '#4c535b'); }
  s.conv = (s.conv || 0) + (s.dt || 0) * L * 0.25;
  for (let k = 0; k < 5; k++) { const u = (s.conv + k / 5) % 1; p(26 + 12 * u, 41 - 21 * u, '#111'); }
  // boiler house, bunker bay, turbine hall
  block(36, 17, 13, 23, '#6a8296', { roof: '#3f464e' });
  for (let y = 20; y < 40; y += 3) r(37, y, 11, 1, '#546a7d');
  r(35, 15, 15, 2, '#3f464e'); for (let x = 36; x < 49; x += 3) p(x, 14, '#3f464e');
  for (let y = 21; y < 38; y += 4) for (let x = 38; x < 48; x += 3) win(x, y, '#ffa84a');
  block(49, 28, 17, 12, '#8ca2b2', { roof: '#5b646c' });
  r(49, 31, 17, 1, '#93b8cc'); for (let x = 50; x < 65; x += 2) win(x, 34, '#ffe6a8');
  block(66, 31, 6, 7, '#8f959b'); r(66, 38, 1, 2, '#4c535b'); r(71, 38, 1, 2, '#4c535b');
  // chimney with red/white aviation bands, smoke ∝ load
  const [cx, cy] = chimney(73, 40, 4, 4);
  plume(cx, cy - 1, t, L, { ...SMOKE, n: 14, life: 6, rise: 12, drift: 26, grow: 4, spread: 3 });
  if (seaCooled) {
    sea(46, t);
    r(80, 42, 16, 2, '#7f7c74'); r(82, 38, 6, 4, '#8ca2b2');
    if (L > 0.02) for (let i = 0; i < 6; i++) raw(84 + hash(i, Math.floor(t * 2)) * 10, 47 + (i % 3), 2, 1, rgba('#e6f3ff', 0.7 * L));
  } else {
    const [tx, ty] = coolingTower(86, 40, 20, 16);
    plume(tx, ty, t, L, { ...STEAM, seed: 9 });
  }
  pylonSmall(92, 46, 12);
};

S.lignite = (t, L, e, st, s) => {
  const hz = 34;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 3, 2.1);
  ground(hz, '#8f8a78', '#7d786a');
  // open-cast pit in the foreground: benches down to the lignite seam
  const steps = [[0, 38], [8, 41], [14, 44], [20, 47], [26, 50], [42, 50], [46, 47], [50, 44], [54, 41], [58, 38]];
  for (let x = 0; x < 60; x++) {
    let y = 38;
    for (let i = 0; i < steps.length - 1; i++) if (x >= steps[i][0] && x < steps[i + 1][0]) y = x < 42 ? steps[i][1] : steps[i + 1][1];
    r(x, hz, 1, y - hz, '#6a8a4a');
    for (let yy = hz + 1; yy < y; yy++) p(x, yy, yy > 45 ? '#40332a' : yy % 3 === 0 ? '#8f6f4c' : '#9d6445');
    r(x, y, 1, H - y, '#40332a');
    if (hash(x, 3) > 0.7) p(x, y, '#57473a');
  }
  // bucket-wheel excavator on the floor, wheel turning ∝ load
  block(30, 46, 8, 4, '#d9a72b'); r(30, 50, 8, 1, '#3a3a3a');
  line(30, 46, 22, 42, '#d67a2c'); line(37, 46, 44, 43, '#d67a2c');
  s.bwe = (s.bwe || 0) + (s.dt || 0) * (L > 0.02 ? 1.2 + 2 * L : 0);
  for (let k = 0; k < 6; k++) { const a = s.bwe + k * Math.PI / 3; p(22 + Math.cos(a) * 3, 42 + Math.sin(a) * 3, k % 2 ? '#d67a2c' : '#2a2a2a'); }
  p(22, 42, '#3a3a3a');
  // conveyor out of the pit
  line(40, 49, 62, 36, '#6e6a64');
  s.conv = (s.conv || 0) + (s.dt || 0) * L * 0.25;
  for (let k = 0; k < 5; k++) { const u = (s.conv + k / 5) % 1; p(40 + 22 * u, 48 - 13 * u, '#2f261f'); }
  // plant: boilers + three stacks + cooling tower
  block(60, 20, 11, 18, '#6a8296', { roof: '#3f464e' });
  for (let y = 23; y < 36; y += 4) for (let x = 62; x < 70; x += 3) win(x, y, '#ffa84a');
  block(70, 28, 10, 10, '#8ca2b2', { roof: '#5b646c' });
  for (const [x, top] of [[72, 6], [77, 8], [82, 10]]) { const [cx, cy] = chimney(x, 30, top, 3); plume(cx, cy - 1, t, L, { ...SMOKE, n: 10, life: 6, rise: 10, drift: 20, grow: 3, seed: x }); }
  const [tx, ty] = coolingTower(90, 38, 16, 11);
  plume(tx, ty, t, L, { ...STEAM, n: 10, s0: 2, grow: 4, seed: 4 });
};

S.gas = (t, L, e, st, s) => {
  const hz = 38;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 3, 3.3);
  ground(hz, '#8f8a78', '#7d786a');
  // naphtha / HSD tank
  block(2, 30, 12, 10, '#ece9e1', { roof: '#c9c9c4' }); r(3, 29, 10, 1, '#c9c9c4');
  r(0, 42, 62, 1, '#d9a72b'); r(0, 44, 62, 1, '#b0b6ba');
  // GT: air filter house, enclosure, HRSG, stack with heat shimmer
  for (const [x0, k] of [[16, 0], [38, 1]]) {
    block(x0, 28, 6, 10, '#7b93a6', { roof: '#5e6e7a' });
    for (let y = 30; y < 38; y += 2) r(x0 + 1, y, 4, 1, '#6a8193');
    block(x0 + 6, 32, 9, 8, '#c9ccc8', { roof: '#9aa0a4' });
    win(x0 + 8, 35, '#ffe6a8', 2, 1);
    block(x0 + 15, 22, 6, 18, '#8d9499', { roof: '#6a7076' });
    for (let x = x0 + 16; x < x0 + 20; x += 2) r(x, 23, 1, 16, '#6f767c');
    r(x0 + 17, 10, 2, 12, '#8f8f8c'); r(x0 + 16, 10, 4, 1, '#5a5a58');
    plume(x0 + 18, 9, t, L, { cols: ['#e6e3dd', '#d6d3cd'], n: 6, life: 3, rise: 10, drift: 5, s0: 1, grow: 2, alpha: 0.5, seed: k + 3 });
    if (L > 0.05) for (let i = 0; i < 3; i++) { const yy = 8 - i * 2 - Math.floor(t * 4 % 2); raw(x0 + 17 + Math.round(Math.sin(t * 6 + i) * 1), yy, 2, 1, rgba('#ffffff', 0.25 * L)); }
  }
  // steam turbine hall + induced-draft cooling cells
  block(62, 28, 14, 12, '#8ca2b2', { roof: '#5b646c' });
  for (let x = 63; x < 75; x += 2) win(x, 32, '#ffe6a8');
  block(78, 33, 17, 7, '#c9c6bd', { roof: '#9d9a92' });
  for (const x of [80, 86, 92]) { r(x - 1, 31, 3, 2, '#7c7a73'); plume(x, 30, t, L, { ...STEAM, n: 5, s0: 1, grow: 3, rise: 10, drift: 4, spread: 2, seed: x }); }
};

S.diesel = (t, L, e, st, s) => {
  const hz = 38;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 3, 4.1);
  ground(hz, '#8f8a78', '#7d786a');
  block(6, 26, 62, 14, '#e0d5ba', { roof: '#8a8f8c' });
  r(6, 30, 62, 1, '#93b8cc');
  for (let x = 8; x < 66; x += 3) win(x, 34, '#ffe6a8');
  for (let k = 0; k < 6; k++) {
    const x = 9 + k * 10;
    r(x + 2, 24, 5, 2, '#3f4549');
    r(x, 12, 2, 14, '#7d746c'); r(x, 12, 2, 1, '#3a3632'); p(x + 1, 13, '#5f5852');
    plume(x + 1, 11, t, L, { cols: ['#55544f', '#46453f', '#62615c'], n: 7, life: 4, rise: 9, drift: 14, grow: 3, seed: x });
  }
  block(72, 30, 10, 10, '#ece9e1', { roof: '#c7c7c2' }); r(73, 29, 8, 1, '#c7c7c2');
  block(84, 32, 10, 8, '#ece9e1', { roof: '#c7c7c2' }); r(85, 31, 8, 1, '#c7c7c2');
  pylonSmall(90, 50, 12);
};

function reactorShore(t, L, hz) {
  ground(hz, '#a59d88', '#948c78', 42 - hz);
  sea(42, t);
  r(0, 43, 30, 2, '#7f7c74'); for (let x = 0; x < 30; x += 3) p(x, 43, '#9a968c');
  // outfall churn ∝ load
  if (L > 0.02) for (let i = 0; i < 14; i++) {
    const cyc = Math.floor(t * 1.5 + hash(i));
    if (hash(i, cyc) > L) continue;
    raw(60 + hash(i, cyc + 1) * 30, 43 + hash(i, cyc + 2) * 5, 2, 1, rgba('#e6f3ff', 0.8));
  }
}

function dome(x, y0, w, hgt, c) {
  for (let i = 0; i < hgt; i++) {
    const half = Math.round(w / 2 * Math.sqrt(1 - Math.pow((hgt - i) / (hgt + 0.6), 2)));
    r(x + w / 2 - half, y0 - hgt + i, half * 2, 1, c);
    p(x + w / 2 - half, y0 - hgt + i, mix(c, '#ffffff', 0.2));
    p(x + w / 2 + half - 1, y0 - hgt + i, mix(c, '#000000', 0.2));
  }
}

S.nuclear_vver = (t, L, e) => {
  const hz = 30;
  reactorShore(t, L, hz);
  // turbine halls behind, blue band
  block(52, 24, 38, 16, '#dadcd8', { roof: '#8b9196' }); r(52, 26, 38, 1, '#3f6fa6');
  for (let x = 54; x < 88; x += 3) win(x, 32, '#ffe6a8');
  for (const x of [58, 70, 82]) plume(x, 23, t, L, { ...STEAM, n: 5, s0: 1, grow: 3, rise: 8, drift: 5, spread: 3, seed: x });
  // two AES-92 reactor buildings: annex, tall cylinder, shallow dome
  for (const x of [6, 30]) {
    block(x - 3, 32, 22, 9, '#d9d6cc', { roof: '#a7aaa8' });
    for (let xx = x - 1; xx < x + 17; xx += 3) win(xx, 36, '#8fd8ff');
    block(x, 16, 16, 16, '#e5e2d8'); r(x, 30, 16, 1, '#b9bcbc');
    dome(x, 16, 16, 5, '#d3d6d6');
  }
  // ventilation stack
  const [vx, vy] = chimney(26, 41, 6, 2);
  plume(vx, vy, t, L * 0.3, { cols: ['#e6e3dd'], n: 3, life: 3, rise: 5, drift: 4, alpha: 0.4 });
};

S.nuclear_phwr = (t, L) => {
  const hz = 30;
  reactorShore(t, L, hz);
  block(64, 26, 28, 14, '#d7d3c6', { roof: '#8b9196' }); r(64, 29, 28, 1, '#93b8cc');
  for (let x = 66; x < 90; x += 3) win(x, 33, '#ffe6a8');
  plume(76, 25, t, L, { ...STEAM, n: 5, s0: 1, grow: 3, rise: 8, drift: 5, spread: 3 });
  for (const x of [8, 40]) {
    block(x - 2, 34, 20, 7, '#cfcabb', { roof: '#9aa0a4' });
    for (let xx = x; xx < x + 16; xx += 3) win(xx, 37, '#8fd8ff');
    block(x, 21, 16, 13, '#c4c1b8'); r(x, 24, 16, 1, '#b1ada4');
    dome(x, 21, 16, 4, '#b6b4ad');
  }
  chimney(30, 41, 3, 3);
};

S.nuclear_fbr = (t, L) => {
  const hz = 30;
  reactorShore(t, L, hz);
  block(66, 26, 26, 14, '#dadcd8', { roof: '#8b9196' });
  for (let x = 68; x < 90; x += 3) win(x, 32, '#ffe6a8');
  plume(78, 25, t, L, { ...STEAM, n: 5, s0: 1, grow: 3, rise: 8, drift: 5, spread: 3 });
  block(12, 26, 10, 15, '#d6d2c4', { roof: '#8f959a' }); block(48, 26, 10, 15, '#d6d2c4', { roof: '#8f959a' });
  for (let y = 29; y < 40; y += 3) { win(14, y, '#ffb070', 6, 1); win(50, y, '#ffb070', 6, 1); }
  block(22, 12, 26, 29, '#cdc7b6', { roof: '#a9a59a' });
  for (let y = 16; y < 40; y += 5) r(23, y, 24, 1, '#bdb7a6');
  r(24, 11, 22, 1, '#b8b3a6');
  chimney(60, 41, 4, 3);
};

S.hydro_dam = (t, L, e, st, s) => {
  const hz = 30;
  hills(hz, mix('#6d8f5a', '#3f5f3a', 0.4), 10, 0.7);
  hills(hz, mix('#5f7f4a', '#2f4f2a', 0.4), 5, 2.9);
  ground(hz, '#62813e', '#4b6b31');
  for (let x = 56; x < W; x++) { const y = 40 + Math.round(Math.sin(x * 0.3) * 1.5); r(x, y, 1, 48 - y, '#7f7c74'); }
  // reservoir (deep, a cross-section on the left)
  for (let y = 20; y < H; y += 3) raw(0, y, 35, 3, tone(mix('#3f7597', '#1e4460', (y - 20) / 34)));
  for (let i = 0; i < 8; i++) raw((hash(i, 4) * 30 + t * (1 + hash(i, 5))) % 32, 21 + (i % 3), 2, 1, rgba('#9fd0f0', 0.5));
  // gravity dam: vertical upstream face, sloping downstream face, masonry courses
  for (let y = 16; y < H; y++) {
    const x1 = 38 + Math.round((y - 16) * 0.55);
    r(35, y, x1 - 35, 1, y % 3 === 0 ? '#8f8372' : '#a89a84');
    p(x1 - 1, y, '#c9c2b2');
  }
  r(34, 15, 6, 1, '#c9c2b2'); for (let x = 34; x < 40; x += 2) p(x, 14, '#aaa79e');
  // spillway sheet down the face, foam at the toe, river ∝ load
  if (L > 0.02) for (let i = 0; i < 26; i++) {
    const a = ((t * 0.9 + i / 26) % 1);
    if (hash(i, Math.floor(t * 0.9 + i / 26)) > L * 1.05) continue;
    const y = 16 + a * 34, x = 38 + (y - 16) * 0.55 + (hash(i, 2) - 0.2) * 2;
    raw(x, y, 2, 1, rgba(i % 3 ? '#d8ecf5' : '#9fd0f0', 0.95));
  }
  for (let y = 48; y < H; y += 2) raw(56, y, W - 56, 2, tone(y < 50 ? '#4f86a8' : '#3f7597'));
  if (L > 0.02) for (let i = 0; i < 16; i++) {
    const cyc = Math.floor(t * 2 + hash(i));
    if (hash(i, cyc) > L) continue;
    raw(56 + hash(i, cyc + 1) * 12, 47 + hash(i, cyc + 2) * 3, 2, 1, rgba('#f2f8fb', 0.9));
  }
  s.riv = (s.riv || 0) + (s.dt || 0) * (4 + 10 * L);
  for (let i = 0; i < 10; i++) raw(56 + ((s.riv + i * 11) % 40), 50 + (i % 3) * 1.5, 3, 1, rgba('#bfe0f2', 0.5));
  // powerhouse at the toe with a penstock
  line(46, 30, 62, 39, '#8c4f31'); line(46, 31, 62, 40, '#8c4f31');
  block(60, 38, 16, 9, '#e0d5ba'); r(59, 37, 18, 1, '#9a4a36');
  for (let x = 62; x < 75; x += 3) win(x, 42, '#ffe6a8');
  pylonSmall(86, 46, 14);
};

S.hydro_run = (t, L, e, st, s) => {
  const hz = 26;
  hills(hz, mix('#6d8f5a', '#3f5f3a', 0.4), 6, 5.2);
  ground(hz, '#62813e', '#4b6b31');
  // the hillside, rising to the west
  for (let x = 0; x < 72; x++) {
    const top = x < 22 ? 10 + Math.round(Math.sin(x * 0.4)) : 10 + Math.round((x - 22) * 0.68);
    r(x, top, 1, 47 - top, x % 5 === 0 ? '#5b7a3c' : '#62813e');
    if (hash(x, 1) > 0.75) p(x, top + 2 + Math.floor(hash(x, 2) * 20), '#7f7c74');
  }
  for (let i = 0; i < 9; i++) { const x = 4 + Math.floor(hash(i, 5) * 60), top = x < 22 ? 10 : 10 + Math.round((x - 22) * 0.68); if (Math.abs(x - 44) > 6) tree(x, top + 1, 1); }
  // surge tank, valve house, two penstocks with water pulses ∝ load
  block(14, 4, 5, 7, '#aaa79e', { roof: '#807d76' });
  block(22, 7, 7, 4, '#e0d5ba'); r(21, 6, 9, 1, '#9a4a36');
  for (const d of [0, 2]) {
    line(26 + d, 11, 62 + d, 38, '#8c4f31');
    for (let k = 0; k < 6; k++) p(30 + d + k * 6, 14 + k * 4.5, '#aaa79e');
  }
  s.pen = (s.pen || 0) + (s.dt || 0) * L * 0.6;
  if (L > 0.02) for (let k = 0; k < 4; k++) { const u = (s.pen + k / 4) % 1; p(27 + 35 * u, 10 + 27 * u, '#bfe6ff'); }
  // powerhouse, tailrace, river
  block(60, 36, 18, 11, '#e0d5ba'); r(59, 35, 20, 1, '#9a4a36');
  for (let x = 62; x < 77; x += 3) win(x, 40, '#ffe6a8');
  for (let y = 47; y < H; y += 2) raw(0, y, W, 2, tone(y < 49 ? '#4f86a8' : '#3f7597'));
  s.riv = (s.riv || 0) + (s.dt || 0) * (4 + 10 * L);
  for (let i = 0; i < 12; i++) raw(((s.riv + i * 9) % (W + 4)) - 2, 48 + (i % 3) * 2, 3, 1, rgba('#bfe0f2', 0.5));
  if (L > 0.02) for (let i = 0; i < 12; i++) { const cyc = Math.floor(t * 2 + hash(i)); if (hash(i, cyc) > L) continue; raw(62 + hash(i, cyc + 1) * 14, 47 + hash(i, cyc + 2) * 2, 2, 1, rgba('#f2f8fb', 0.9)); }
  pylonSmall(88, 46, 14);
};

S.pumped_storage = (t, L, e, st, s) => {
  const hz = 24;
  hills(hz, mix('#6d8f5a', '#3f5f3a', 0.4), 5, 6.1);
  ground(hz, '#62813e', '#4b6b31');
  // the mountain, cut away to show the waterway
  for (let x = 0; x < 80; x++) {
    const top = x < 34 ? 9 : 9 + Math.round((x - 34) * 0.8);
    r(x, top, 1, H - top, '#62813e');
    for (let y = top + 2; y < H; y++) p(x, y, (y + Math.floor(x / 7)) % 6 === 0 ? '#6a5f55' : '#7a6d60');
  }
  // upper reservoir + dam
  for (let y = 9; y < 15; y++) r(3, y, 26, 1, y === 9 ? '#6fa0bf' : '#3f7597');
  r(29, 7, 3, 8, '#a89a84'); r(2, 15, 28, 1, '#5a5048');
  // headrace, surge shaft, pressure shaft, cavern, tailrace
  const path = [[28, 14], [42, 16], [42, 16], [56, 38], [60, 42], [72, 44], [80, 46]];
  for (let i = 0; i < path.length - 1; i++) { line(path[i][0], path[i][1], path[i + 1][0], path[i + 1][1], '#1c2a33'); line(path[i][0], path[i][1] + 1, path[i + 1][0], path[i + 1][1] + 1, '#1c2a33'); }
  r(41, 7, 3, 10, '#1c2a33'); r(40, 6, 5, 1, '#aaa79e');
  const lvl = 9 + Math.round(Math.sin(t * 0.7) * 1.5 * L);
  r(42, lvl, 1, 16 - lvl, '#3f7597');
  raw(52, 38, 16, 8, tone('#2a2f38'));
  for (const x of [55, 60, 65]) { raw(x - 1, 41, 3, 3, mix('#3a3f48', '#ffa84a', L * (0.6 + 0.4 * Math.sin(t * 8 + x)))); }
  r(52, 37, 16, 1, '#aaa79e');
  s.flow = (s.flow || 0) + (s.dt || 0) * L * 0.35;
  if (L > 0.02) {
    const pts = path, segs = []; let tot = 0;
    for (let i = 0; i < pts.length - 1; i++) { const d = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]); segs.push(d); tot += d; }
    for (let k = 0; k < 10; k++) {
      let d = ((s.flow + k / 10) % 1) * tot, i = 0;
      while (i < segs.length - 1 && d > segs[i]) { d -= segs[i]; i++; }
      const u = segs[i] ? d / segs[i] : 0;
      raw(pts[i][0] + (pts[i + 1][0] - pts[i][0]) * u, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * u, 1, 1, '#9fd8ff');
    }
  }
  // lower reservoir + surface switchyard
  for (let y = 44; y < H; y += 2) raw(78, y, W - 78, 2, tone(y < 46 ? '#4f86a8' : '#3f7597'));
  if (L > 0.02) for (let i = 0; i < 8; i++) { const cyc = Math.floor(t * 2 + hash(i)); if (hash(i, cyc) > L) continue; raw(80 + hash(i, cyc + 1) * 12, 44 + hash(i, cyc + 2) * 2, 2, 1, rgba('#f2f8fb', 0.9)); }
  gantry(82, 92, 40, 7); r(80, 40, 16, 1, '#9d998e');
};

function monsoonHills(hz) {
  hills(hz, mix('#8aa3b8', '#3a4a66', N * 0.5), 16, 0.4, 2);
  hills(hz, mix('#6f8a8a', '#2f3f4a', N * 0.5), 9, 1.9);
}

S.wind_turbine = (t, L, e, st, s) => {
  const hz = 40;
  monsoonHills(hz);
  ground(hz, '#7d8a4e', '#6a7a40');
  s.ang = (s.ang || 0) + (s.dt || 0) * (L > 0.02 ? (0.8 + 2.6 * L) : 0);
  turbine(80, 40, 12, 5, s.ang * 1.1 + 1, {});
  turbine(64, 40, 8, 3.5, s.ang * 0.9 + 2, {});
  palm(12, 48, 10); palm(22, 50, 8); palm(88, 50, 9);
  turbine(40, 50, 36, 17, s.ang, {});
  r(36, 50, 9, 1, '#aaa79e');
  block(48, 46, 4, 4, '#d9d6cc');
};

S.wind_farm = (t, L, e, st, s) => {
  const hz = 38;
  monsoonHills(hz);
  ground(hz, '#7d8a4e', '#6a7a40');
  s.ang = (s.ang || 0) + (s.dt || 0) * (L > 0.02 ? (0.8 + 2.6 * L) : 0);
  const ts = [[10, 36, 10, 5], [30, 35, 12, 6], [56, 37, 9, 4.5], [74, 36, 11, 5.5], [90, 37, 8, 4]];
  ts.forEach(([x, b, h, R], i) => turbine(x, b, h, R, s.ang * (0.9 + 0.1 * i) + i, {}));
  turbine(46, 52, 26, 12, s.ang + 0.3, {});
  palm(20, 51, 8); palm(70, 52, 9); palm(84, 50, 7);
  r(0, 45, W, 1, '#b49b73');
};

S.solar_farm = (t, L, e) => {
  const hz = 32;
  hills(hz, mix('#8aa3b8', '#3a4a66', N * 0.5), 4, 2.2);
  ground(hz, '#b49b73', '#a38a64');
  const u = clamp((e.h - 6.1) / 12.4, 0, 1), sunX = 6 + u * 84;
  const rows = [[34, 1, 6], [37, 1, 7], [40, 2, 8], [44, 2, 10], [49, 3, 12]];
  rows.forEach(([y, th, tw], ri) => {
    for (let x0 = -((ri * 5) % tw); x0 < W; x0 += tw + 1) {
      for (let x = x0; x < x0 + tw; x++) {
        if (x < 0 || x >= W) continue;
        r(x, y, 1, th, '#22385a');
        p(x, y - 1, '#5f86b5');
        if (th > 1 && (x - x0) % 3 === 0) p(x, y + th - 1, '#39587f');
      }
      if (x0 + 1 >= 0) r(x0 + 1, y + th, 1, 1 + (ri > 2), '#7a7f84');
      if (x0 + tw - 2 >= 0) r(x0 + tw - 2, y + th, 1, 1 + (ri > 2), '#7a7f84');
    }
    // glint where the sun reflects toward the viewer
    if (e.day > 0.2) for (let k = 0; k < 3; k++) {
      const gx = Math.round(sunX + (ri - 2) * 4 + (hash(k, Math.floor(t * 3) + ri) - 0.5) * 14);
      if (hash(k + ri * 3, Math.floor(t * 4)) < 0.4 + 0.5 * L) raw(gx, y - 1, 2, 1, rgba('#fff6d8', e.day));
    }
  });
  block(84, 40, 7, 5, '#e5e3dc', { roof: '#c9c7c0' });
  for (let x = 1; x < W; x += 4) r(x, 52, 1, 2, '#80868b');
  r(0, 52, W, 1, rgba('#80868b', 0.6));
};

S.biomass = (t, L, e, st, s) => {
  const hz = 38;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 3, 5.5);
  ground(hz, '#8f8a78', '#7d786a');
  // mill house with a pitched roof, boiler house, chimney
  block(6, 26, 30, 14, '#cfc4a8');
  for (let i = 0; i < 5; i++) r(6 + i, 25 - i, 30 - 2 * i, 1, '#8e6b52');
  for (let x = 8; x < 35; x += 4) win(x, 32, '#ffe6a8');
  plume(20, 21, t, L, { ...STEAM, n: 6, s0: 1, grow: 3, rise: 8, drift: 6, spread: 4 });
  block(36, 20, 11, 20, '#6a8296', { roof: '#3f464e' });
  for (let y = 23; y < 38; y += 4) win(40, y, '#ffa84a', 3, 1);
  const [cx, cy] = chimney(49, 40, 6, 3, { bands: false, color: '#9a5a44' });
  plume(cx, cy - 1, t, L, { cols: ['#c4c3bd', '#b3b2ad', '#d2d1cc'], n: 12, life: 6, rise: 12, drift: 22, grow: 4 });
  // bagasse heap + cane carrier
  for (let x = 58; x < 95; x++) { const h = Math.max(0, Math.round(11 - Math.abs(x - 76) * 0.6)); r(x, 42 - h, 1, h, '#cbb57c'); if (hash(x, 9) > 0.6) p(x, 42 - h, '#d8c690'); }
  line(58, 38, 46, 24, '#6e6a64');
  s.conv = (s.conv || 0) + (s.dt || 0) * L * 0.3;
  for (let k = 0; k < 4; k++) { const u = (s.conv + k / 4) % 1; p(58 - 12 * u, 37 - 14 * u, '#b9a36a'); }
  // tractor with a cane trolley on the road
  r(0, 43, W, 2, '#6a6660');
  s.trx = (s.trx || 0) + (s.dt || 0) * L * 6;
  const tx = W + 10 - (s.trx % (W + 30));
  r(tx, 40, 8, 3, '#6f9a3c'); r(tx + 1, 39, 6, 1, '#7da347');
  r(tx + 9, 40, 4, 3, '#2f5f9a'); r(tx + 11, 38, 2, 2, '#2f5f9a');
  p(tx + 1, 43, '#1e1e1e'); p(tx + 6, 43, '#1e1e1e'); r(tx + 10, 43, 2, 1, '#1e1e1e');
  // sugarcane in the foreground, swaying
  for (let x = 0; x < W; x += 2) {
    const sw = Math.round(Math.sin(t * 1.5 + x * 0.3) * 0.8);
    for (let y = 46; y < H; y++) p(x + (y < 49 ? sw : 0), y, y < 48 ? '#7da347' : (x % 4 ? '#5f8f3a' : '#6f9a3c'));
  }
};

S.substation = (t, L) => {
  const hz = 34;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 3, 6.6);
  ground(hz, '#9d998e', '#8a867c');
  pylonSmall(8, 34, 14); pylonSmall(88, 34, 12);
  gantry(4, 30, 40, 16); gantry(36, 62, 40, 16); gantry(68, 92, 40, 16);
  sag(8, 18, 5, 24, 2, '#6c737a'); sag(88, 20, 92, 24, 1, '#6c737a');
  for (const y of [25, 28]) { sag(5, y, 31, y, 1.5, '#6c737a'); sag(37, y, 63, y, 1.5, '#6c737a'); sag(69, y, 93, y, 1.5, '#6c737a'); }
  for (let x = 8; x < 92; x += 6) { r(x, 36, 1, 4, '#8d5b3d'); p(x, 35, '#b0b6ba'); }
  const t0 = performance.now() / 1000;
  trafo(10, 42, 16, 8, L, t); trafo(54, 42, 16, 8, L, t);
  block(78, 40, 14, 9, '#e0d5ba'); r(77, 39, 16, 1, '#9a4a36');
  win(80, 43, '#ffe6a8', 3, 2); win(86, 43, '#ffe6a8', 3, 2);
  const rate = 0.5 + 3 * L, on = ((t0 * rate) % 1) < 0.5;
  pr(90, 38, on ? '#6dff7a' : '#1f4a24'); pr(28, 41, (t0 * rate + 0.5) % 1 < 0.5 ? '#ff5040' : '#4a1a14');
  for (let x = 0; x < W; x += 3) r(x, 50, 1, 4, '#80868b');
  r(0, 51, W, 1, rgba('#80868b', 0.7));
};

// side view along the line: two double-circuit towers, three phase conductors + earth wire
function lattice(cx, base, top, c = '#9aa1a7') {
  const waist = top + Math.round((base - top) * 0.45);
  const half = y => (y > waist ? Math.round(2 + (y - waist) * 0.2) : 2);
  for (let y = base; y >= top; y--) { p(cx - half(y), y, c); p(cx + half(y), y, c); }
  for (let y = base, f = 1; y > top + 2; y -= 4, f = -f) {
    const k0 = half(y), k1 = half(y - 4);
    line(cx - f * k0, y, cx + f * k1, y - 4, c);
    if (y > waist) line(cx - k1, y - 4, cx + k1, y - 4, c);
  }
  r(cx - 2, top, 5, 1, c);
  const levels = [waist - 2, waist - 10, waist - 18].map(y => Math.max(top + 3, y));
  for (const y of levels) { line(cx - 5, y, cx + 5, y, c); line(cx - 2, y - 2, cx - 5, y, c); line(cx + 2, y - 2, cx + 5, y, c); for (const sx of [-5, 5]) r(cx + sx, y + 1, 1, 2, '#5f8f80'); }
  return { levels: levels.map(y => y + 3), peak: top - 1, half: 5 };
}

S.pylon = (t, L, e, st, s) => {
  const hz = 40;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 4, 7.7);
  ground(hz, '#7d8a4e', '#6a7a40');
  for (let x = 0; x < W; x += 7) r(x, 46 + (x % 3), 4, 1, '#8a9a58');
  const A = lattice(24, 51, 7), B = lattice(76, 51, 7);
  const wire = '#3f454a';
  s.pulse = (s.pulse || 0) + (s.dt || 0) * (0.25 + 0.7 * L);
  A.levels.forEach((y, i) => {
    sag(0, y + 2, 24 - 5, y, 2, wire);
    sag(24 + 5, y, 76 - 5, y, 4, wire);
    sag(76 + 5, y, W, y + 2, 2, wire);
    if (L > 0.02) for (let k = 0; k < 2; k++) {
      const u = (s.pulse + i * 0.23 + k * 0.5) % 1;
      const [px, py] = sagAt(29, y, 71, y, 4, u);
      raw(px, py, 1, 1, rgba('#fff2a0', 0.55 + 0.45 * L));
    }
  });
  sag(24, A.peak, 76, B.peak, 3, wire);
  sag(0, A.peak + 1, 24, A.peak, 1, wire); sag(76, B.peak, W, B.peak + 1, 1, wire);
  // a pair of birds on the earth wire
  for (const u of [0.38, 0.45]) { const [bx, by] = sagAt(24, A.peak, 76, B.peak, 3, u); p(bx, by - 1, '#222'); p(bx + 1, by - 1, '#222'); p(bx, by - 2, '#222'); }
};

S.coal_ship = (t, L, e, st, s) => {
  const hz = 26;
  hills(hz, mix('#8aa3b8', '#3a4a66', N * 0.5), 2, 8.1);
  sea(hz, t);
  const bob = Math.round(Math.sin(t * 0.9));
  const d = 36 + bob, wl = 43 + bob;
  wake(12, wl - 1, t, L);
  hull(10, 86, d, wl, '#2a2d32', '#9c2d25', { name: true });
  // superstructure aft, funnel
  block(13, d - 11, 11, 11, '#ebe8e0'); r(12, d - 9, 13, 1, '#ebe8e0');
  for (let x = 14; x < 23; x += 2) win(x, d - 7, '#ffe6a8');
  r(13, d - 10, 11, 1, '#2d3f55');
  r(16, d - 15, 4, 4, '#1d1d1d'); r(16, d - 13, 4, 1, '#b8342a');
  // hatch covers + cranes
  for (let k = 0; k < 6; k++) { r(28 + k * 9, d - 2, 7, 2, '#8a3b2c'); p(28 + k * 9, d - 2, '#a24a38'); }
  for (const x of [35, 53, 71]) { r(x, d - 10, 1, 10, '#d9a72b'); line(x, d - 9, x + 7, d - 13, '#d9a72b'); }
  r(83, d - 5, 1, 5, '#d9a72b');
  // gulls
  for (let i = 0; i < 2; i++) { const gx = (t * 5 + i * 40) % (W + 10) - 5, gy = 10 + i * 4 + Math.round(Math.sin(t * 2 + i)); const f = Math.floor(t * 4 + i) % 2; p(gx, gy, '#f2f2f2'); p(gx - 1, gy - f, '#f2f2f2'); p(gx + 1, gy - f, '#f2f2f2'); }
};

S.lng_tanker = (t, L, e, st, s) => {
  const hz = 26;
  hills(hz, mix('#8aa3b8', '#3a4a66', N * 0.5), 2, 9.3);
  sea(hz, t);
  const bob = Math.round(Math.sin(t * 0.8));
  const d = 38 + bob, wl = 45 + bob;
  wake(12, wl - 1, t, L);
  hull(10, 88, d, wl, '#27384f', '#9c2d25', { name: true });
  block(12, d - 12, 10, 12, '#ebe8e0');
  for (let x = 13; x < 21; x += 2) win(x, d - 8, '#ffe6a8');
  r(12, d - 11, 10, 1, '#2d3f55'); r(15, d - 16, 4, 4, '#ebe8e0'); r(15, d - 16, 4, 1, '#1d1d1d');
  // four Moss spheres
  for (let k = 0; k < 4; k++) {
    const cx = 32 + k * 14;
    for (let y = 0; y < 7; y++) { const half = Math.round(Math.sqrt(49 - y * y)); r(cx - half, d - y - 1, half * 2, 1, y > 2 ? '#e9e3d3' : '#d6cdb7'); p(cx - half, d - y - 1, '#f4efe2'); p(cx + half - 1, d - y - 1, '#bdb4a0'); }
  }
  r(84, d - 8, 1, 8, '#d9a72b');
};

S.coal_train = (t, L, e, st, s) => {
  const hz = 34;
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 5, 10.1);
  ground(hz, '#7d8a4e', '#6a7a40');
  // overhead catenary masts + contact wire
  for (let x = 4; x < W; x += 24) { r(x, 24, 1, 20, '#80868b'); r(x - 2, 24, 5, 1, '#80868b'); }
  r(0, 27, W, 1, '#4d5358');
  // ballast, sleepers, rails
  r(0, 44, W, 4, '#8a867c'); for (let x = 0; x < W; x += 3) r(x, 45, 2, 1, '#5a5047'); r(0, 44, W, 1, '#3a3a3a');
  // the rake scrolls east->west at a speed ∝ load
  const len = 20 + 8 * 12;
  s.tx = (s.tx || 60) + (s.dt || 0) * L * 14;
  let x = W - (s.tx % (W + len));
  const wheel = Math.floor(s.tx * 1.5) % 2;
  // WAG-9 loco
  block(x, 34, 20, 9, '#a5312b'); r(x, 38, 20, 1, '#e3d3a6'); r(x, 33, 20, 1, '#4a4f55');
  r(x, 35, 2, 2, '#28323c'); win(x, 35, '#ffe6a8', 1, 2);
  line(x + 8, 33, x + 11, 28, '#333'); line(x + 11, 28, x + 14, 33, '#333');
  for (const wx of [x + 2, x + 5, x + 14, x + 17]) { p(wx, 43, '#1c1c1c'); p(wx + 1, 43, wheel ? '#9aa0a5' : '#1c1c1c'); }
  x += 21;
  for (let k = 0; k < 12; k++, x += 8) {
    if (x > W || x + 8 < 0) continue;
    block(x, 36, 7, 7, '#7b4631'); r(x + 1, 35, 5, 1, '#232427'); p(x + 3, 34, '#35363a');
    p(x + 1, 43, '#1c1c1c'); p(x + 5, 43, wheel ? '#9aa0a5' : '#1c1c1c');
  }
};

S.mine = (t, L, e, st, s) => {
  const hz = 20;                                     // the sky runs down into the pit (driver draws it to y 48)
  hills(hz, mix('#7d9aa0', '#4e6a6a', 0.3), 3, 11.7);
  // section through the pit: 6 px benches of overburden stepping down to the coal seam and a black floor
  const y0 = x => clamp(48 - Math.floor(Math.max(0, Math.abs(x - 50) - 12) / 5) * 4, hz, 48);
  // the far wall of the pit, benches receding
  for (let y = hz; y < 48; y++) r(0, y, W, 1, (y - hz) % 4 === 0 ? '#9a8266' : y > 42 ? '#3a342f' : mix('#7d5f45', '#6a5040', (y - hz) / 28));
  for (let i = 0; i < 20; i++) p(Math.floor(hash(i, 41) * W), hz + 1 + Math.floor(hash(i, 42) * 26), '#5f4a3a');
  for (let x = 0; x < W; x++) {
    const top = y0(x);
    for (let y = top; y < H; y++) p(x, y, y >= 42 ? (y > 46 || hash(x, y) > 0.8 ? '#232427' : '#35363a') : (y < hz + 2 ? '#8a6a4a' : y % 4 === 0 ? '#8f6f4c' : (y < 32 ? '#a0603e' : '#9d6445')));
    p(x, top, top === hz ? '#6a8a4a' : top >= 48 ? '#35363a' : '#b5a58a');
  }
  // shovel on the floor, bucket working ∝ load
  s.arm = (s.arm || 0) + (s.dt || 0) * (L > 0.02 ? 1 + 2 * L : 0);
  const ay = Math.round(Math.sin(s.arm) * 2);
  block(40, 43, 8, 5, '#d9a72b'); r(40, 48, 8, 1, '#2a2a2a'); r(44, 41, 3, 2, '#d9a72b'); win(45, 41, '#ffe6a8', 1, 1);
  line(40, 44, 34, 40 + ay, '#d9a72b'); r(32, 40 + ay, 3, 3, '#3a3a3a');
  if (L > 0.05) plume(33, 41 + ay, t, L, { cols: ['#a0805e', '#8f7055'], n: 5, life: 2, rise: 5, drift: 4, alpha: 0.5, s0: 1, grow: 2 });
  // dumper climbing the benches on the east wall
  s.dump = (s.dump || 0) + (s.dt || 0) * L * 0.06;
  const steps = [[54, 48], [62, 48], [67, 44], [72, 40], [77, 36], [82, 32], [87, 28], [92, 24], [W + 8, hz]];
  const f = (s.dump % 1) * (steps.length - 1), i = Math.floor(f), k = f - i;
  const dx = Math.round(steps[i][0] + (steps[i + 1][0] - steps[i][0]) * k), dy = Math.round(steps[i][1] + (steps[i + 1][1] - steps[i][1]) * k);
  block(dx - 3, dy - 4, 7, 3, '#d9a72b'); r(dx - 2, dy - 5, 4, 1, '#232427'); r(dx + 2, dy - 6, 2, 2, '#e0b23a');
  p(dx - 2, dy - 1, '#1c1c1c'); p(dx + 2, dy - 1, '#1c1c1c');
  // conveyor out of the pit to the coal handling plant on the west rim
  line(36, 47, 8, hz - 1, '#6e6a64');
  s.conv = (s.conv || 0) + (s.dt || 0) * L * 0.25;
  for (let q = 0; q < 5; q++) { const v = (s.conv + q / 5) % 1; p(36 - 28 * v, 46 - (47 - hz) * v, '#111'); }
  block(1, hz - 12, 7, 12, '#aaa79e', { roof: '#807d76' });
  block(9, hz - 7, 4, 7, '#aaa79e');
};

/* ------------------------------------------------------------------ driver */
function draw(sc, now) {
  let st = {};
  try { st = sc.getState ? (sc.getState() || {}) : {}; } catch { st = {}; }
  const L = clamp(+st.load || 0, 0, 1);
  const tAnim = now / 1000;
  const tClock = st.t > 1e9 ? st.t : tAnim;
  const e = env(tClock);
  sc.dt = sc.last == null ? 0 : clamp(tAnim - sc.last, 0, 0.25);
  sc.last = tAnim;
  X = sc.ctx; N = e.night; LIT = clamp(L * (0.25 + 0.75 * e.night) + (L > 0 ? 0.05 : 0), 0, 1);
  const hzs = { coal: 38, lignite: 34, gas: 38, diesel: 38, nuclear_vver: 30, nuclear_phwr: 30, nuclear_fbr: 30, hydro_dam: 30, hydro_run: 26, pumped_storage: 24,
    wind_turbine: 40, wind_farm: 38, solar_farm: 32, biomass: 38, substation: 34, pylon: 40, coal_ship: 26, lng_tanker: 26, coal_train: 34, mine: 48 };
  sky(e, tAnim, hzs[sc.arch] || 38);
  (S[sc.arch] || S.coal)(tAnim, L, e, st, sc);
  X = null;
}

function loop(now) {
  raf = scenes.size ? requestAnimationFrame(loop) : 0;
  if (now - last < 1000 / FPS - 2) return;
  last = now;
  for (const sc of scenes) {
    if (!sc.canvas.isConnected) { scenes.delete(sc); io?.unobserve(sc.canvas); continue; }
    if (!sc.visible || (reduced.matches && sc.drawn)) continue;
    draw(sc, now);
    sc.drawn = true;
  }
}

// archetype: one of models.js ARCHETYPES; getState() -> { load 0..1, t?, plant? }. Returns cleanup().
export function mountScene(canvas, archetype, getState) {
  if (!canvas) return () => {};
  canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const sc = { canvas, ctx, arch: S[archetype] ? archetype : 'coal', getState, visible: true, drawn: false, last: null };
  canvas.__scene = sc;
  scenes.add(sc);
  io?.observe(canvas);
  draw(sc, performance.now());
  if (!raf) raf = requestAnimationFrame(loop);
  return () => {
    scenes.delete(sc);
    io?.unobserve(canvas);
    if (canvas.__scene === sc) delete canvas.__scene;
    if (!scenes.size && raf) { cancelAnimationFrame(raf); raf = 0; }
  };
}
