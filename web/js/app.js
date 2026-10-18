// Power Map of India — map, live panel, cards. Mobile first: the panel is a bottom sheet under
// 821 px and a sidebar above it (same shell as maps.reclaimchennai.city/lighthouses).
import { PowerLayer, modelsReady } from './layer3d.js?v=3';
import { FUELS, FUEL_ORDER, fuel, KV, NEUTRAL, uiDark } from './fuels.js?v=3';
import { sunPosition, sunAt, nightBands, sunTimes } from './sun.js?v=1';

const maplibregl = window.maplibregl;
const $ = s => document.querySelector(s);
const icon = (name, cls = '') => `<svg class="i ${cls}" aria-hidden="true"><use href="icons.svg?v=2#${name}"/></svg>`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (v, d = 0) => v == null || Number.isNaN(+v) ? '–' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: 0 });
const pct = v => v == null ? '–' : `${Math.round(v * 100)}%`;
const desktop = matchMedia('(min-width:821px)').matches;
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
// full resolution (capped at 2× for phones): basemap text stays sharp; the stations are still voxels
const PIXEL_RATIO = Math.min(window.devicePixelRatio || 1, 2);
const SHEET_PEEK = 88;
const IST = { timeZone: 'Asia/Kolkata' };
const istTime = iso => iso ? new Date(iso).toLocaleTimeString('en-IN', { ...IST, hour: '2-digit', minute: '2-digit', hour12: false }) : '–';
const istDate = iso => iso ? new Date(iso.length === 10 ? iso + 'T12:00:00+05:30' : iso).toLocaleDateString('en-IN', { ...IST, day: 'numeric', month: 'short' }) : '–';

const VIEWS = {
  india: { center: [80.0, desktop ? 21.5 : 19.5], zoom: desktop ? 4.3 : 3.45, pitch: 45, bearing: 0 },
  tn: { center: [78.5, 10.7], zoom: desktop ? 6.5 : 5.7, pitch: 52, bearing: -8 },
  chennai: { center: [80.27, 13.13], zoom: 10.2, pitch: 58, bearing: -18 },
};
// fly-to buttons: a station (by name match) or a view
const FLY = [
  ['India', { view: 'india' }], ['Tamil Nadu', { view: 'tn' }], ['Chennai', { view: 'chennai' }],
  ['North Chennai', { match: /north chennai tps stage 2|nctps.?(ii|2)/i, zoom: 14.2 }],
  ['Mettur', { match: /^mettur tps$/i, zoom: 14.4 }], ['Neyveli', { match: /neyveli tps-ii$|neyveli tps.?ii$/i, zoom: 13.2 }],
  ['Kudankulam', { match: /kudankulam/i, zoom: 14.6 }], ['Tuticorin', { match: /^tuticorin tps$/i, zoom: 14.2 }],
  ['Nilgiris hydro', { center: [76.66, 11.38], zoom: 10.6, pitch: 64, bearing: 30 }],
  ['Muppandal wind', { center: [77.55, 8.26], zoom: 12.2, pitch: 66, bearing: 20 }],
];

/* ------------------------------------------------------------------ data */
window.__pwLoad?.(20, 'Loading the fleet…');
const dl = { got: 0, want: 0 };
async function fetchJSON(url, expected) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  dl.want += +r.headers.get('content-length') || expected;
  if (!r.body) return r.json();
  const reader = r.body.getReader(), parts = [];
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value); dl.got += value.length;
    window.__pwLoad?.(20 + 55 * Math.min(1, dl.got / dl.want));
  }
  return JSON.parse(await new Blob(parts).text());
}
const opt = p => p.catch(e => { console.warn(e); return null; });
const [atlas, base, gridIdx, now0, emis, positron, darkMatter] = await Promise.all([
  fetchJSON('data/plants.json', 150e3), fetchJSON('data/basemap.json', 840e3),
  opt(fetchJSON('data/grid/index.json', 1e3)), opt(fetchJSON(`data/live/now.json?t=${Date.now() / 6e4 | 0}`, 150e3)),
  opt(fetchJSON('data/emissions.json', 40e3)),
  fetchJSON('data/basemap/positron.json', 20e3), fetchJSON('data/basemap/dark-matter.json', 20e3),
]);
let NOW = now0 || {};
const PLANTS = atlas.plants;
const byId = new Map(PLANTS.map(p => [p.id, p]));
const loadStep = (text, v) => window.__pwLoad?.(v, text);
loadStep('Raising the stacks…', 80);

/* ------------------------------------------------------------------- map */
const map = new maplibregl.Map({
  container: 'map',
  // CARTO's glyphs: the Positron / Dark Matter basemap and our own map labels share one font server
  style: { version: 8, glyphs: 'https://tiles.basemaps.cartocdn.com/fonts/{fontstack}/{range}.pbf', sources: {},
           layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#f2efe9' } }] },
  ...VIEWS[location.hash.includes('tn') ? 'tn' : 'india'], minZoom: 2.8, maxZoom: 17.5, maxPitch: 85,
  maxBounds: [[55, -2], [105, 40]], renderWorldCopies: false, attributionControl: false,
  pixelRatio: PIXEL_RATIO,
  canvasContextAttributes: { antialias: false, preserveDrawingBuffer: false },
});
map.addControl(new maplibregl.AttributionControl({
  compact: true,
  customAttribution: 'SLDC TANTRANSCO · Vidyut Pravah · NPP/CEA · Open-Meteo · DataMeet',
}), desktop ? 'bottom-right' : 'top-right');
class ViewControl {
  onAdd(m) {
    const el = this.el = document.createElement('div');
    el.className = 'maplibregl-ctrl maplibregl-ctrl-group view-ctrl';
    el.innerHTML = `<button type="button" class="z-in" aria-label="Zoom in" title="Zoom in">+</button>
      <button type="button" class="z-out" aria-label="Zoom out" title="Zoom out">−</button>
      <button type="button" class="v-dim"></button>`;
    el.querySelector('.z-in').onclick = () => m.zoomIn({ duration: reduceMotion ? 0 : 400 });
    el.querySelector('.z-out').onclick = () => m.zoomOut({ duration: reduceMotion ? 0 : 400 });
    const dim = el.querySelector('.v-dim');
    dim.onclick = () => {
      const flat = m.getPitch() < 5;
      if (!flat) this.lastBearing = m.getBearing();
      m.easeTo(flat ? { pitch: 60, bearing: this.lastBearing ?? -15, duration: reduceMotion ? 0 : 1000 }
                    : { pitch: 0, bearing: 0, duration: reduceMotion ? 0 : 1000 });
    };
    const sync = () => {
      const next = m.getPitch() < 5 ? '3D' : '2D';
      if (dim.textContent !== next) { dim.textContent = next; dim.setAttribute('aria-label', `Switch to ${next} view`); dim.title = `Switch to ${next} view`; }
    };
    m.on('pitchend', sync); m.on('moveend', sync); sync();
    return el;
  }
  onRemove() { this.el.remove(); }
}
map.addControl(new ViewControl(), desktop ? 'bottom-right' : 'top-right');
const BASE_PADDING = desktop ? { left: 356, top: 0, right: 0, bottom: 0 } : { left: 0, top: 0, right: 0, bottom: SHEET_PEEK };
map.setPadding(BASE_PADDING);

const layer = new PowerLayer(maplibregl, PLANTS);
window.__pw = { map, layer, PLANTS };

// fuels shown: all by default, remembered per viewer
let shown = new Set(FUEL_ORDER.concat(['waste', 'battery']));
try { const s = JSON.parse(localStorage.getItem('pw-fuels') || 'null'); if (Array.isArray(s) && s.length) shown = new Set(s); } catch { /* private mode */ }
layer.setFilter(shown);

const plantsFC = () => ({ type: 'FeatureCollection', features: PLANTS.map(p => ({
  type: 'Feature', id: PLANTS.indexOf(p),
  properties: { id: p.id, name: p.name, type: p.type, cap: p.cap,
    label: `${p.name}${p.cap ? ` · ${fmt(p.cap)} MW` : ''}${p.status && p.status !== 'operating' ? ` (${p.status.replace('_', ' ')})` : ''}` },
  geometry: { type: 'Point', coordinates: [p.lon, p.lat] } })) });

function fuelFilter() { return ['in', ['get', 'type'], ['literal', [...shown]]]; }

const LINE_MIN = { 765: 3, hvdc: 3, 400: 3.5, 220: 5, 110: 7, dist: 9.5 };
const kvOf = k => KV.find(x => x.key === k) || { dark: '#7a6a55', light: '#b89a78', w: 0.8, label: '≤ 33 kV' };
// the map has its own day/night theme (the sun over the view), separate from the panel's light/dark button
let mapDark = false;
const kvCol = k => mapDark ? kvOf(k).dark : kvOf(k).light;

map.once('style.load', async () => {
  // basemap: CARTO Positron by day, Dark Matter by night (the MTC app's CARTO look), as vector tiles: sharp
  // labels at any zoom and no raster watermark. Both layer sets share one source; the theme flips visibility.
  map.addSource('carto', { type: 'vector', url: 'https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/tiles.json',
    attribution: '© <a href="https://carto.com/attributions">CARTO</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' });
  for (const l of positron.layers) map.addLayer(l);
  for (const l of darkMatter.layers) map.addLayer({ ...l, layout: { ...(l.layout || {}), visibility: 'none' } });
  // satellite ground (optional): Sentinel-2 cloudless 2016 (CC BY 4.0)
  map.addSource('sat', { type: 'raster', tileSize: 256, maxzoom: 14, attribution: 'Sentinel-2 cloudless 2016 © EOX (CC BY 4.0)',
    tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg'] });
  map.addLayer({ id: 'sat', type: 'raster', source: 'sat', minzoom: 5,
    layout: { visibility: $('#l-sat').checked ? 'visible' : 'none' },
    paint: { 'raster-opacity': ['interpolate', ['linear'], ['zoom'], 5, 0.6, 9, 0.9], 'raster-brightness-max': 0.9 } });
  map.addSource('dem-hs', { type: 'raster-dem', encoding: 'terrarium', tileSize: 256, maxzoom: 13,
    tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], attribution: 'Terrain: AWS Terrain Tiles' });
  map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem-hs', minzoom: 5,
    paint: { 'hillshade-exaggeration': 0.25, 'hillshade-shadow-color': '#3b3325', 'hillshade-highlight-color': '#ffffff', 'hillshade-accent-color': '#5a4e3a' } });
  // the night side, minute by minute: pixel blocks of civil twilight, nautical twilight and night
  map.addSource('night', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
  map.addLayer({ id: 'night', type: 'fill', source: 'night',
    paint: { 'fill-color': '#0a1330', 'fill-antialias': false, 'fill-opacity': ['match', ['get', 'b'], 1, 0.2, 2, 0.42, 3, 0.62, 0] } });
  map.addSource('states', { type: 'geojson', data: base.states });
  map.addLayer({ id: 'states', type: 'line', source: 'states',
    paint: { 'line-color': '#6b7385', 'line-opacity': 0.45, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 9, 1.4] } });
  addGrid();
  map.addSource('plants', { type: 'geojson', data: plantsFC() });
  map.addLayer({ id: 'plants-hit', type: 'circle', source: 'plants', filter: fuelFilter(),
    paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 7, 10, 12], 'circle-opacity': 0.01, 'circle-color': '#000' } });
  // station names are HTML labels floated above each 3D object (layer.onLabels), not map symbols
  loadStep('Lighting the boilers…', 92);
  map.addLayer(layer);
  addFeed();
  layer.setLive(NOW);
  applyStateLoads();
  updateSun(true);
  setInterval(() => updateSun(true), 60000);
  map.on('moveend', () => updateSun(false));
  map.once('render', () => requestAnimationFrame(() => {
    loadStep('Ready', 100);
    setTimeout(() => { $('#loading').classList.add('done'); $('#loading').setAttribute('aria-hidden', 'true'); }, 220);
  }));
  map.once('idle', () => { if ($('#l-base').checked) loadBasemap(); });
  if (!desktop) setTimeout(() => document.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show'), 50);
  openFromHash();
});

/* ------------------------------------------------------------------ grid */
const LINE_LAYERS = [];
function addGrid() {
  if (!gridIdx) return;
  // 400 kV and up load at once; 220 and 110 kV (≈2 MB compressed) wait until the camera reaches their zoom
  const order = ['dist', '110', '220', '400', 'hvdc', '765'];
  const addClass = k => {
    const f = gridIdx.lines?.[k];
    if (!f || map.getSource(`ln-${k}`)) return;
    const kv = kvOf(k);
    const higher = order.slice(order.indexOf(k) + 1).map(x => `ln-${x}-glow`).find(id => map.getLayer(id));
    const before = higher || (map.getLayer('subs') ? 'subs' : map.getLayer('plants-hit') ? 'plants-hit' : undefined);
    map.addSource(`ln-${k}`, { type: 'geojson', data: `data/grid/${f.file}` });
    map.addLayer({ id: `ln-${k}-glow`, type: 'line', source: `ln-${k}`, minzoom: LINE_MIN[k],
      paint: { 'line-color': kvCol(k), 'line-opacity': ['765', '400', 'hvdc'].includes(k) ? 0.2 : 0.06, 'line-blur': 2, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, kv.w * 1.6, 12, kv.w * 4] } }, before);
    map.addLayer({ id: `ln-${k}`, type: 'line', source: `ln-${k}`, minzoom: LINE_MIN[k],
      layout: { 'line-cap': 'butt', 'line-join': 'miter' },
      // close up the 3D pylons and conductors take over; the ground line stays as their shadow
      paint: { 'line-color': kvCol(k), 'line-opacity': ['interpolate', ['linear'], ['zoom'], 4, ({ dist: 0.35, 110: 0.42, 220: 0.55 }[k] ?? 0.8) * 0.5,
                 6.5, { dist: 0.35, 110: 0.42, 220: 0.55 }[k] ?? 0.8, 12.5, { dist: 0.35, 110: 0.42, 220: 0.55 }[k] ?? 0.8, 15.5, 0.18],
               'line-width': ['interpolate', ['linear'], ['zoom'], 4, kv.w * 0.45, 9, kv.w, 14, kv.w * 1.8] } }, before);
    // "energised" shimmer: dashes stepped along the line (flow direction is not published)
    if (!['dist', '110'].includes(k)) map.addLayer({ id: `ln-${k}-flow`, type: 'line', source: `ln-${k}`, minzoom: Math.max(5, LINE_MIN[k]),
      paint: { 'line-color': mapDark ? '#fffbe0' : '#ffffff', 'line-opacity': k === '220' ? 0.3 : 0.6, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, kv.w * 0.5, 14, kv.w * 1.2],
               'line-dasharray': [0, 4, 3] } }, before);
    LINE_LAYERS.push(`ln-${k}-glow`, `ln-${k}`, `ln-${k}-flow`);
    if (!$('#l-lines').checked) vis([`ln-${k}-glow`, `ln-${k}`, `ln-${k}-flow`], false);
  };
  const addLines = () => { for (const k of [...order].reverse()) if (map.getZoom() >= LINE_MIN[k] - 0.8) addClass(k); };
  addLines();
  map.on('zoomend', addLines);
  if (gridIdx.substations) {
    map.addSource('subs', { type: 'geojson', data: `data/grid/${gridIdx.substations.file}` });
    map.addLayer({ id: 'subs', type: 'circle', source: 'subs', minzoom: 6,
      filter: ['any', ['>=', ['zoom'], 8.5], ['>=', ['coalesce', ['get', 'kv'], 0], 200]],
      paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, ['step', ['coalesce', ['get', 'kv'], 0], 1.2, 200, 2.2, 380, 3.2], 13, ['step', ['coalesce', ['get', 'kv'], 0], 4, 200, 6, 380, 8]],
               'circle-color': mapDark ? '#0b0d14' : '#ffffff', 'circle-stroke-color': subsCol(), 'circle-stroke-width': ['interpolate', ['linear'], ['zoom'], 6, 1, 12, 2.2] } });
    map.addLayer({ id: 'subs-label', type: 'symbol', source: 'subs', minzoom: 10.5,
      layout: { 'text-field': ['concat', ['coalesce', ['get', 'name'], ''], ['case', ['has', 'ratio'], ['concat', ' ', ['get', 'ratio'], ' kV'], '']],
                'text-font': ['Open Sans Regular', 'Noto Sans Regular'], 'text-size': 11, 'text-anchor': 'left', 'text-offset': [0.9, 0], 'text-padding': 3 },
      paint: { 'text-color': mapDark ? '#cdbf8e' : '#5b4a2a', 'text-halo-color': mapDark ? '#05080c' : '#ffffff', 'text-halo-width': 1.4 } });
    $('#subs-note').textContent = `${fmt(gridIdx.substations.n)} mapped`;
  }
  // close-zoom context (1.6 MB together): fetched the first time the camera comes below z 10
  const addContext = () => {
    if (map.getZoom() < 10 || map.getSource('footprints') || map.getSource('solar-arrays')) return;
    const under = map.getLayer('plants-hit') ? 'plants-hit' : undefined;
    if (gridIdx.footprints) {
      map.addSource('footprints', { type: 'geojson', data: `data/grid/${gridIdx.footprints.file}` });
      map.addLayer({ id: 'footprints', type: 'line', source: 'footprints', minzoom: 10.5,
        paint: { 'line-color': '#c9ced3', 'line-opacity': 0.45, 'line-width': 1.2, 'line-dasharray': [2, 2] } }, under);
    }
    if (gridIdx.solar_arrays) {
      map.addSource('solar-arrays', { type: 'geojson', data: `data/grid/${gridIdx.solar_arrays.file}` });
      // panels as low dark-blue blocks, lit by the map light: reads as rows of modules from the satellite ground up
      map.addLayer({ id: 'solar-arrays', type: 'fill-extrusion', source: 'solar-arrays', minzoom: 11,
        paint: { 'fill-extrusion-color': '#1f3552', 'fill-extrusion-height': 2.5, 'fill-extrusion-opacity': 0.9, 'fill-extrusion-vertical-gradient': true } }, under);
    }
  };
  map.on('zoomend', addContext);
  addContext();
  if (gridIdx.schematic) $('#lines-note').textContent = 'TN only, schematic (OSM routes loading in the next build)';
  if (gridIdx.turbines) fetch(`data/grid/${gridIdx.turbines.file}`).then(r => r.json()).then(pts => layer.setTurbines(pts)).catch(() => {});
  renderLineLegend();
  // stepped dash animation (6 fps, pixel-art pace)
  const SEQ = [[0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0], [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5]];
  let step = 0;
  if (!reduceMotion) setInterval(() => {
    step = (step + 1) % SEQ.length;
    for (const id of LINE_LAYERS) if (id.endsWith('-flow') && map.getLayer(id) && map.getLayoutProperty(id, 'visibility') !== 'none') map.setPaintProperty(id, 'line-dasharray', SEQ[step]);
  }, 160);
}

/* ------------------------------------------------------ sun and map theme */
// The map follows the real sun: light CARTO tiles with the night side drawn in pixel blocks (twilight
// bands sweep east to west, north-east India first) and dark CARTO tiles once the whole view is past
// civil dusk. With "Map follows the sun" off, the map takes the panel's light/dark theme.
const subsCol = () => ['step', ['coalesce', ['get', 'kv'], 0], mapDark ? '#7a6a55' : '#b89a78', 60, kvCol('110'), 200, kvCol('220'), 380, kvCol('400'), 700, kvCol('765')];
function renderLineLegend() {
  const lines = gridIdx ? KV.filter(k => gridIdx.lines?.[k.key]).map(k => `<span class="k"><i class="line" style="--c:${uiDark() ? k.dark : k.light}"></i>${k.label}</span>`).join('') : '';
  const feed = FEED ? Object.entries(FEED_MODE).filter(([k]) => FEED_MODES_USED.has(k)).map(([, m]) => `<span class="k"><i class="line" style="--c:${uiDark() ? m.dark : m.light}"></i>${icon(m.icon, 'sm')}${m.label}</span>`).join('') : '';
  $('#line-legend').innerHTML = lines + feed + `<span class="full">Lines shimmer when energised; the direction of flow is not published.${FEED ? ' Supply routes are drawn between the documented mines, junctions and ports. Ships and trains move at one simulated hour per second.' : ''}</span>`;
}
let nightMinute = -1;
// ?sun=18:10 previews the sky at that IST time today (the rest of the page stays live)
const SIM = new URLSearchParams(location.search).get('sun');
const simNow = () => { if (!SIM) return new Date(); const [h, m] = SIM.split(':').map(Number); const d = new Date(); const ist = new Date(d.getTime() + 330 * 60000);
  ist.setUTCHours(h, m || 0, 0, 0); return new Date(ist.getTime() - 330 * 60000); };
function updateSun(tick) {
  if (!map.getLayer('night')) return;
  const now = simNow(), pos = sunPosition(now);
  const follow = $('#l-sun').checked;
  const b = map.getBounds(), c = map.getCenter();
  const pts = [[c.lat, c.lng], [b.getNorth(), b.getWest()], [b.getNorth(), b.getEast()], [b.getSouth(), b.getWest()], [b.getSouth(), b.getEast()]];
  const alts = pts.map(([la, lo]) => sunAt(Math.max(-60, Math.min(60, la)), lo, pos).alt);
  const dark = follow ? Math.max(...alts) < -6 : uiDark();
  const minute = Math.floor(now.getTime() / 60000);
  if (follow && minute !== nightMinute) { map.getSource('night').setData(nightBands([40, -20, 125, 52], 0.25, pos)); nightMinute = minute; }
  map.setLayoutProperty('night', 'visibility', follow && !dark ? 'visible' : 'none');
  if (dark !== mapDark) applyMapTheme(dark);
  const here = sunAt(c.lat, c.lng, pos);
  layer.setSun(here.alt, here.az);
  // watermark: what the sun is doing over the view
  const t = sunTimes(c.lat, c.lng, now), hm = d => d ? d.toLocaleTimeString('en-IN', { ...IST, hour: '2-digit', minute: '2-digit', hour12: false }) : '–';
  const east = sunAt(26.1, 91.7, pos).alt, west = sunAt(19.1, 72.9, pos).alt;
  let msg = here.alt > 0 ? `Sun ${Math.round(here.alt)}° up · sets ${hm(t.set)}` : here.alt > -6 ? `Dusk · sun ${Math.round(-here.alt)}° down` : `Night · sunrise ${hm(t.rise)}`;
  if (east < -0.8 && west > -0.8) msg += ' · sunset crossing India';
  $('#wm-sun').textContent = msg;
  $('#sun-note').textContent = follow ? `${dark ? 'night map' : 'day map'} · ${msg.toLowerCase()}` : 'off: the map follows the panel theme';
}
function applyMapTheme(dark) {
  mapDark = dark;
  for (const l of positron.layers) map.setLayoutProperty(l.id, 'visibility', dark ? 'none' : 'visible');
  for (const l of darkMatter.layers) map.setLayoutProperty(l.id, 'visibility', dark ? 'visible' : 'none');
  map.setPaintProperty('bg', 'background-color', dark ? '#0b0d14' : '#f2efe9');
  map.setPaintProperty('states', 'line-color', dark ? '#9fb4c8' : '#6b7385');
  map.setPaintProperty('hillshade', 'hillshade-shadow-color', dark ? '#000000' : '#3b3325');
  map.setPaintProperty('hillshade', 'hillshade-highlight-color', dark ? '#3a4a5e' : '#ffffff');
  for (const k of ['765', 'hvdc', '400', '220', '110', 'dist']) {
    if (map.getLayer(`ln-${k}`)) { map.setPaintProperty(`ln-${k}`, 'line-color', kvCol(k)); map.setPaintProperty(`ln-${k}-glow`, 'line-color', kvCol(k)); }
    if (map.getLayer(`ln-${k}-flow`)) map.setPaintProperty(`ln-${k}-flow`, 'line-color', dark ? '#fffbe0' : '#ffffff');
  }
  if (map.getLayer('subs')) {
    map.setPaintProperty('subs', 'circle-stroke-color', subsCol());
    map.setPaintProperty('subs', 'circle-color', dark ? '#0b0d14' : '#ffffff');
    map.setPaintProperty('subs-label', 'text-color', dark ? '#cdbf8e' : '#5b4a2a');
    map.setPaintProperty('subs-label', 'text-halo-color', dark ? '#05080c' : '#ffffff');
  }
  for (const [mode, m] of Object.entries(FEED_MODE)) if (map.getLayer(`feed-${mode}`)) map.setPaintProperty(`feed-${mode}`, 'line-color', dark ? m.dark : m.light);
  if (map.getLayer('feed-nodes')) {
    map.setPaintProperty('feed-nodes', 'circle-color', dark ? '#0b0d14' : '#ffffff');
    map.setPaintProperty('feed-nodes', 'circle-stroke-color', nodeCol());
    map.setPaintProperty('feed-node-labels', 'text-color', dark ? '#9fc6e0' : '#1f4f7a');
    map.setPaintProperty('feed-node-labels', 'text-halo-color', dark ? '#05080c' : '#ffffff');
    map.setPaintProperty('feed-hi', 'line-color', dark ? '#ffd84a' : '#d18a00');
  }
  if (map.getLayer('footprints')) map.setPaintProperty('footprints', 'line-color', dark ? '#c9ced3' : '#5b6070');
  if (map.getLayer('omt-buildings')) map.setPaintProperty('omt-buildings', 'fill-extrusion-color', dark ? '#5a6474' : '#d8d2c6');
  map.setLight({ anchor: 'map', position: [1.4, 210, 35], color: dark ? '#b9c6dd' : '#ffffff', intensity: dark ? 0.35 : 0.5 });
  layer.setMapTheme(dark);
  $('#labels').classList.toggle('night', dark);
}
$('#l-sun').onchange = () => updateSun(true);

/* ------------------------------------------------- pylons for lines in view */
// Close up (z >= 12.8) every line in view gets voxel pylons and sagging conductors. The line files are
// fetched once (the browser cache already holds them from the map) and clipped to the view here.
const LINE_DATA = {};
let spanKey = '';
async function updateSpans() {
  if (map.getZoom() < 12.8 || !gridIdx || !$('#l-lines').checked) return;
  const b = map.getBounds(), pad = 0.02;
  const [w, s, e, n] = [b.getWest() - pad, b.getSouth() - pad, b.getEast() + pad, b.getNorth() + pad];
  const detail = map.getZoom() >= 15.2;
  const key = [w, s, e, n].map(x => x.toFixed(2)).join() + detail;
  if (key === spanKey) return;
  spanKey = key;
  const out = [];
  for (const k of ['765', '400', '220', '110']) {
    const f = gridIdx.lines?.[k];
    if (!f) continue;
    LINE_DATA[k] ||= fetch(`data/grid/${f.file}`).then(r => r.json()).catch(() => null);
    const fc = await LINE_DATA[k];
    for (const ft of fc?.features || []) {
      const g = ft.geometry, parts = g.type === 'MultiLineString' ? g.coordinates : [g.coordinates];
      for (const c of parts) {
        if (!c.some(([x, y]) => x > w && x < e && y > s && y < n)) continue;
        out.push({ kv: ft.properties.voltage_kv || +k, coords: c });
      }
    }
  }
  await modelsReady;
  layer.setSpans(out, detail);
}
map.on('moveend', updateSpans);

/* ---------------------------------------------------- 3D buildings (close up) */
// OpenFreeMap / OpenMapTiles building heights (OSM render_height), only fetched once the camera is at z 14
const BASE_LAYERS = [];
function loadBasemap() {
  if (map.getSource('omt')) return setBasemap(true);
  map.addSource('omt', { type: 'vector', url: 'https://tiles.openfreemap.org/planet',
    attribution: '<a href="https://openfreemap.org" target="_blank">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank">OpenMapTiles</a>' });
  map.addLayer({ id: 'omt-buildings', type: 'fill-extrusion', source: 'omt', 'source-layer': 'building', minzoom: 14,
    paint: { 'fill-extrusion-color': mapDark ? '#5a6474' : '#d8d2c6', 'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 6],
             'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0], 'fill-extrusion-opacity': 0.85 } }, 'plants-hit');
  BASE_LAYERS.push('omt-buildings');
}
function setBasemap(on) { for (const id of BASE_LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'); }

/* ---------------------------------------------------------------- toggles */
const vis = (ids, on) => ids.forEach(id => map.getLayer(id) && map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none'));
$('#l-lines').onchange = e => vis(LINE_LAYERS, e.target.checked);
$('#l-subs').onchange = e => vis(['subs', 'subs-label'], e.target.checked);
$('#l-smoke').onchange = e => layer.setVisible({ smoke: e.target.checked });
$('#l-models').onchange = e => layer.setVisible({ models: e.target.checked, turbines: e.target.checked });
$('#l-sat').onchange = e => vis(['sat'], e.target.checked);
$('#l-base').onchange = e => e.target.checked ? loadBasemap() : setBasemap(false);
$('#l-feed').onchange = e => { vis(FEED_LAYERS, e.target.checked); layer.setVisible({ feed: e.target.checked }); };
$('#l-terrain').onchange = e => {
  if (e.target.checked) {
    if (!map.getSource('dem')) map.addSource('dem', { type: 'raster-dem', encoding: 'terrarium', tileSize: 256, maxzoom: 14,
      tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'] });
    map.setTerrain({ source: 'dem', exaggeration: 1.4 });
  } else map.setTerrain(null);
};

/* ------------------------------------------------------------ fuel chips */
function renderFuels() {
  const tally = {};
  // named wind farms sit inside the belt clusters (part_of): count their capacity once, via the belt
  for (const p of PLANTS) { const t = tally[p.type] ||= { n: 0, mw: 0 }; t.n++; if (!p.part_of) t.mw += p.cap || 0; }
  $('#fuels').innerHTML = FUEL_ORDER.filter(t => tally[t]).map(t => {
    const f = FUELS[t];
    return `<button class="fuel" data-t="${t}" aria-pressed="${shown.has(t)}" style="--c:${f.color}">
      <span class="sw">${icon(f.icon)}</span><span class="nm">${f.label}<small>${fmt(tally[t].n)} · ${fmt(tally[t].mw / 1000, 1)} GW</small></span></button>`;
  }).join('');
  const tot = PLANTS.reduce((a, p) => a + (p.part_of ? 0 : p.cap || 0), 0);
  $('#fleet-count').textContent = `${fmt(PLANTS.length)} · ${fmt(tot / 1000)} GW`;
}
renderFuels();
$('#fuels').addEventListener('click', e => {
  const b = e.target.closest('.fuel'); if (!b) return;
  const t = b.dataset.t, on = !shown.has(t);
  on ? shown.add(t) : shown.delete(t);
  b.setAttribute('aria-pressed', on);
  try { localStorage.setItem('pw-fuels', JSON.stringify([...shown])); } catch { /* ignore */ }
  layer.setFilter(shown);
  if (map.getLayer('plants-hit')) map.setFilter('plants-hit', fuelFilter());
});

/* -------------------------------------------------------- TN live panel */
// SLDC rows -> the stack. Central share includes nuclear (Kudankulam, MAPS, Kaiga) and NTPC/NLC coal.
const TN_GROUPS = [
  { k: 'coal', label: 'Coal & lignite', f: 'coal', icon: 'coal', rows: ['thermal', 'ipp_taqa', 'ipp_sepc'], note: 'TNPGCL thermal + TAQA + SEPC' },
  { k: 'wind', label: 'Wind', f: 'wind', icon: 'wind', rows: ['wind'] },
  { k: 'gas', label: 'Gas', f: 'gas', icon: 'gas', rows: ['gas', 'ipp_ppn'] },
  { k: 'hydro', label: 'Hydro', f: 'hydro', icon: 'hydro', rows: ['hydro'] },
  { k: 'solar', label: 'Solar', f: 'solar', icon: 'solar', rows: ['solar'] },
  { k: 'bio', label: 'Cogen & biomass', f: 'biomass', icon: 'biomass', rows: ['cogen', 'biomass'] },
  { k: 'cpp', label: 'Captive', f: null, icon: 'diesel', rows: ['cpp'] },
  { k: 'cgs', label: 'Central share', f: null, icon: 'nuclear', rows: ['cgs'], hatch: true, note: 'NTPC, NLC, NTECL Vallur, NTPL, Kudankulam, MAPS, Kaiga' },
  { k: 'buy', label: 'Bought in', f: null, icon: 'pylon', rows: ['ltoa', 'mtoa_tnpdcl', 'stoa', 'remc', 'dsm', 'exchange_tnpdcl'], hatch: true, note: 'long/medium/short-term open access, REMC, exchange, DSM' },
];
let moment = 'morning_mw';
const rowv = (r, k, m) => r?.[k]?.[m] ?? 0;

function applyStateLoads() {
  const r = NOW.tn?.rows;
  if (!r) return;
  // the freshest SLDC moment: morning peak if issued today, else evening
  const m = 'morning_mw';
  const f = (k) => r[k]?.capacity_mw ? Math.max(0, rowv(r, k, m)) / r[k].capacity_mw : null;
  layer.setStateLoad({ wind: f('wind'), solar: f('solar'), hydro: f('hydro'), cogen: f('cogen'), biomass: f('biomass') });
}

function renderTN() {
  const tn = NOW.tn;
  if (!tn) { $('#tn-note').textContent = 'SLDC statement not available right now.'; return; }
  const r = tn.rows, v = tn.version;
  const whenOf = { min_mw: [v.min_date, v.min_time, v.min_hz], morning_mw: [v.morning_date, v.morning_time, v.morning_hz], lighting_mw: [v.lighting_date, v.lighting_time, v.lighting_hz] };
  const [d, tm, hz] = whenOf[moment];
  $('#tn-when').textContent = `${tm || ''} · ${istDate(d)}`;
  const colOf = g => g.f ? FUELS[g.f].color : g.k === 'cgs' ? NEUTRAL.import : g.k === 'buy' ? (uiDark() ? '#7d86a8' : '#a3a9c2') : NEUTRAL.other;
  const vals = TN_GROUPS.map(g => ({ ...g, c: colOf(g), v: g.rows.reduce((a, k) => a + rowv(r, k, moment), 0) }));
  // exports are negative in the exchange row: keep the stack positive, report the net export apart
  const exp = Math.min(0, rowv(r, 'exchange_tnpdcl', moment)) + Math.min(0, rowv(r, 'dsm', moment));
  vals.find(g => g.k === 'buy').v -= exp;
  const total = rowv(r, 'total', moment);
  const re = ['wind', 'solar', 'hydro', 'bio'].reduce((a, k) => a + vals.find(g => g.k === k).v, 0);
  // Vidyut Pravah: demand met in the current 15-minute block (fresher than the SLDC statement)
  const vp = NOW.vp?.states?.['Tamil Nadu'], blk = vp?.block?.slice(11) || '';
  $('#tn-stats').innerHTML = [
    ['live', fmt(vp?.mw ?? total), vp ? `MW demand now · ${esc(blk)}` : 'MW demand met'],
    ['', hz ? hz.toFixed(2) : '–', `Hz at ${esc(tm || '')}`],
    ['', pct(total ? re / total : null), `from renewables at ${esc(tm || '')}`],
    ['', vp?.exch != null ? fmt(vp.exch) : '–', vp?.price != null ? `MW bought on the exchange · ₹${vp.price}/unit` : 'MW bought on the exchange'],
    ['', fmt(vp?.yday), 'MW peak demand yesterday'],
    ['', fmt(tn.records?.alltime_mw), `MW all-time record · ${esc(tn.records?.alltime_mw_date || '')}`],
  ].map(([k, n, l]) => `<div class="stat ${k}"><b>${n}</b><span>${l}</span></div>`).join('');
  $('#peek').innerHTML = `TN ${fmt(vp?.mw ?? total)} MW now · ${pct(total ? re / total : null)} renewable <span>${esc(vp ? blk : tm || '')}</span>`;
  const today = NOW.vp?.today?.['Tamil Nadu'] || [];
  $('#tn-today').innerHTML = today.length > 1 ? `<div class="sp-row"><span class="kind">Demand today, every 15 minutes</span><b class="v">${fmt(today.at(-1)[1])} MW</b><canvas class="sp"></canvas></div>` : '';
  if (today.length > 1) spark($('#tn-today canvas'), today.map(x => `${NOW.vp.block.slice(0, 10)} ${x[0]}`), today.map(x => x[1]), uiDark() ? '#7ed98b' : '#2e7d32', { unit: 'MW', floor: 0.85 });
  const pos = vals.filter(g => g.v > 0), sum = pos.reduce((a, g) => a + g.v, 0);
  $('#tn-mix').innerHTML = pos.map(g => `<i class="${g.hatch ? 'hatch' : ''}" style="--c:${g.c};flex:${g.v}" data-k="${g.k}" title="${esc(g.label)}: ${fmt(g.v)} MW"></i>`).join('');
  $('#tn-mix').setAttribute('aria-label', `Tamil Nadu supply at ${tm}: ` + pos.map(g => `${g.label} ${fmt(g.v)} MW`).join(', '));
  $('#tn-legend').innerHTML = vals.filter(g => g.v > 0).map(g => `<span class="k"><span class="sw ${g.hatch ? 'hatch' : ''}" style="--c:${g.c}">${g.hatch ? '' : icon(g.icon)}</span>${g.label} <b>${fmt(g.v)}</b></span>`).join('');
  const issued = (vp ? `Demand now: Vidyut Pravah (Ministry of Power), ${esc(blk)} block. ` : '') + (v.pdf_modified ? `Source mix: SLDC statement issued ${istTime(v.pdf_modified)} IST ${istDate(v.pdf_modified)} (SLDC issues it about once a day, around noon)` : '');
  $('#tn-note').innerHTML = `${issued}. Instantaneous MW at the ${moment === 'min_mw' ? 'night minimum' : moment === 'morning_mw' ? 'morning peak' : 'evening lighting peak'} (${esc(tm || '')}).`
    + (exp < 0 ? ` Tamil Nadu was <b>exporting ${fmt(-exp)} MW</b> through the exchange/DSM at that moment.` : '')
    + ` Central share covers ${esc(TN_GROUPS[7].note)}.`;
  const order = ['hydro', 'thermal', 'gas', 'ipp_ppn', 'ipp_taqa', 'ipp_sepc', 'cpp', 'cpp_purchase', 'cpp_wheeling', 'nces', 'cogen', 'biomass', 'wind', 'solar', 'cgs',
    ...Object.keys(r).filter(k => k.startsWith('cgs_')), 'ltoa', 'mtoa', 'mtoa_tnpdcl', 'mtoa_others', 'stoa', 'exchange', 'exchange_tnpdcl', 'exchange_others', 'remc', 'urs', 'dsm', 'total', 'load_shedding', 'ht_relief'];
  $('#tn-table').innerHTML = `<table class="sldc"><thead><tr><th>Item</th><th>Cap MW</th><th>Night</th><th>Morn</th><th>Eve</th><th>MU</th></tr></thead><tbody>${
    order.filter(k => r[k]).map(k => { const x = r[k]; const cls = k === 'total' ? 'tot' : k.startsWith('cgs_') || ['cpp_purchase', 'cpp_wheeling', 'cogen', 'biomass', 'mtoa_tnpdcl', 'mtoa_others', 'exchange_tnpdcl', 'exchange_others'].includes(k) ? 'sub' : '';
      return `<tr class="${cls}"><td>${esc(x.label)}</td><td>${fmt(x.capacity_mw)}${x.capacity_excluded ? '*' : ''}</td><td>${fmt(x.min_mw)}</td><td>${fmt(x.morning_mw)}</td><td>${fmt(x.lighting_mw)}</td><td>${fmt(x.mu, 1)}</td></tr>`; }).join('')
  }</tbody></table><p class="note fine">* not in total installed capacity (renewables, captive, REMC). Night = minimum load, Morn = morning peak (today), Eve = evening lighting peak (yesterday), MU = yesterday's energy.</p>`;
}
$('#tn-moment').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  moment = b.dataset.v;
  for (const x of $('#tn-moment').children) { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', x === b); }
  renderTN();
});

// every archived SLDC reading (night minimum, morning peak, evening peak of each statement), oldest first
async function renderTNReadings() {
  const h = await fetch(`data/live/tn_history.json?t=${Date.now() / 6e4 | 0}`).then(r => r.json()).catch(() => null);
  if (!h?.versions?.length) return;
  const pts = new Map();
  for (const v of h.versions) for (const [slot, idx] of [['min', 1], ['morning', 2], ['lighting', 0]]) {
    const [d, t] = v[slot] || [];
    const tot = v.mw.total?.[idx];
    if (!d || !t || tot == null) continue;
    const key = `${d} ${t}`;
    const re = ['wind', 'solar', 'hydro'].reduce((a, k) => a + (v.mw[k]?.[idx] || 0), 0);
    pts.set(key, { key, d, t, tot, re, slot });
  }
  const list = [...pts.values()].sort((a, b) => a.key.localeCompare(b.key));
  if (list.length < 2) return;
  const el = $('#tn-readings');
  el.innerHTML = `<div class="sp-row"><span class="kind">Demand at each reading</span><b class="v">${list.length} readings</b><canvas class="sp"></canvas></div>
    <div class="sp-row"><span class="kind" style="--c:${FUELS.wind.color}">Wind + solar + hydro</span><b class="v"></b><canvas class="sp"></canvas></div>`;
  const cv = el.querySelectorAll('canvas');
  const dates = list.map(x => x.key), lab = x => `${x.slot === 'min' ? 'night min' : x.slot === 'morning' ? 'morning peak' : 'evening peak'}`;
  spark(cv[0], dates, list.map(x => x.tot), uiDark() ? '#ffd84a' : '#c28a00', { unit: 'MW', floor: 0.8 });
  spark(cv[1], dates, list.map(x => x.re), FUELS.wind.color, { unit: 'MW' });
  for (const c of cv) c.style.imageRendering = 'pixelated';
  el.querySelectorAll('.v')[1].textContent = `${fmt(list.at(-1).re)} MW now`;
}

/* ----------------------------------------------------------- India panel */
function renderIndia() {
  const ind = NOW.india;
  if (!ind) return;
  $('#india-when').textContent = istDate(ind.date);
  const z = ind.zones, tot = Object.values(z).reduce((a, v) => [a[0] + v[0], a[1] + v[1], a[2] + v[2]], [0, 0, 0]);
  const vi = NOW.vp?.india;
  $('#india-stats').innerHTML = [
    ...(vi ? [[fmt(vi.mw / 1000), `GW demand now · ${esc(vi.block.slice(11))}`, 'live']] : []),
    [fmt(tot[1]), 'MU generated'], [`${tot[2] ? (tot[1] / tot[2] * 100 - 100).toFixed(1) : '–'}%`, 'vs same day last year'],
    ...(vi ? [[`₹${vi.price}`, 'per unit, exchange clearing price'], [fmt(vi.exch), 'MW surplus on the exchange']] : []),
    [fmt(tot[1] * 1000 / 24 / 1000, 0), 'GW average yesterday'],
  ].map(([n, l, k]) => `<div class="stat ${k || ''}"><b>${n}</b><span>${l}</span></div>`).join('');
  const max = Math.max(...Object.values(z).map(v => Math.max(v[0], v[1])));
  $('#india-regions').innerHTML = Object.entries(z).sort((a, b) => b[1][1] - a[1][1]).map(([k, v]) =>
    `<div class="row" title="${esc(k)}: ${fmt(v[1], 1)} MU actual, ${fmt(v[0], 1)} MU programme"><span>${esc(k)}</span>
      <span class="track"><i class="fill" style="width:${v[1] / max * 100}%"></i><i class="tick" style="left:${v[0] / max * 100}%"></i></span><span class="v">${fmt(v[1])}</span></div>`).join('');
}

/* ------------------------------------------------ India right now (merit) */
// NPP merit chart: all-India demand and generation by source, ~4-minute step
const MERIT = [['thermal', 'coal', 'Coal & lignite'], ['wind', 'wind', 'Wind'], ['gas', 'gas', 'Gas'], ['hydro', 'hydro', 'Hydro'],
               ['solar', 'solar', 'Solar'], ['nuclear', 'nuclear', 'Nuclear']];
function renderIndiaNow() {
  const m = NOW.merit;
  if (!m) return;
  const L = m.latest, gen = MERIT.reduce((a, [k]) => a + (L[k] || 0), 0);
  $('#india-now-h').innerHTML = `<b>Right now, ${esc(istTime(m.ts))} IST:</b> India is drawing ${fmt((L.demand || 0) / 1000, 1)} GW; ${pct(((L.solar || 0) + (L.wind || 0) + (L.hydro || 0)) / gen)} of generation is solar, wind and hydro.`;
  $('#india-mix').innerHTML = MERIT.filter(([k]) => L[k] > 0).map(([k, f, l]) => `<i style="--c:${FUELS[f].color};flex:${L[k]}" title="${esc(l)}: ${fmt(L[k] / 1000, 1)} GW"></i>`).join('');
  $('#india-mix').setAttribute('aria-label', 'India generation right now: ' + MERIT.map(([k, , l]) => `${l} ${fmt((L[k] || 0) / 1000, 1)} GW`).join(', '));
  $('#india-legend').innerHTML = MERIT.filter(([k]) => L[k] > 0).map(([k, f, l]) => `<span class="k"><span class="sw" style="--c:${FUELS[f].color}">${icon(FUELS[f].icon)}</span>${l} <b>${fmt(L[k] / 1000, 1)} GW</b></span>`).join('');
  const t = m.today || [];
  if (t.length > 2) {
    $('#india-today').innerHTML = `<div class="sp-row"><span class="kind">Demand today, 15-minute steps</span><b class="v">peak ${fmt(Math.max(...t.map(x => x.demand || 0)) / 1000, 1)} GW</b><canvas class="sp"></canvas></div>
      <div class="sp-row"><span class="kind" style="--c:${FUELS.solar.color}"><span class="sw">${icon('solar')}</span>Solar today</span><b class="v">peak ${fmt(Math.max(...t.map(x => x.solar || 0)) / 1000, 1)} GW</b><canvas class="sp"></canvas></div>`;
    const cv = $('#india-today').querySelectorAll('canvas'), day = m.ts.slice(0, 10);
    spark(cv[0], t.map(x => `${day} ${x.t}`), t.map(x => x.demand), uiDark() ? '#ffd84a' : '#c28a00', { unit: 'MW', floor: 0.8 });
    spark(cv[1], t.map(x => `${day} ${x.t}`), t.map(x => x.solar), FUELS.solar.color, { unit: 'MW' });
  }
}

/* ------------------------------------------------- supply to consumers (NFMS) */
function renderNFMS() {
  const n = NOW.nfms;
  if (!n) return;
  const hrs = h => { if (h == null) return '–'; const H = Math.floor(h), M = Math.round((h - H) * 60); return `${H}:${String(M).padStart(2, '0')}`; };
  const tn = n.states.TN, all = n.states.ALL;
  $('#nfms-when').textContent = istDate((all?.data_refresh || n.date).slice(0, 10));
  $('#nfms-stats').innerHTML = [
    [hrs(all?.hrs_inc_ag), 'h/day India, all feeders'], [hrs(all?.urban), 'h/day urban'], [hrs(all?.rural), 'h/day rural'],
    [hrs(all?.agri), 'h/day farm feeders'], [hrs(tn?.hrs_inc_ag), 'h/day Tamil Nadu'], [`${fmt(n.feeders?.IntegrationPercent, 1)}%`, `of ${fmt(+n.feeders?.totalFeeders)} feeders metered`],
  ].map(([v, l], i) => `<div class="stat ${i === 4 ? 'live' : ''}"><b>${v}</b><span>${l}</span></div>`).join('');
  const list = Object.entries(n.states).filter(([k, v]) => k !== 'ALL' && v.hrs_inc_ag != null).sort((a, b) => a[1].hrs_inc_ag - b[1].hrs_inc_ag);
  $('#nfms-states').innerHTML = list.map(([k, v]) => `<div class="row${k === 'TN' ? ' me' : ''}" tabindex="0" title="${esc(v.state)}: ${hrs(v.hrs_inc_ag)} h all feeders · urban ${hrs(v.urban)} · rural ${hrs(v.rural)} · farm ${hrs(v.agri)} · ${fmt(v.feeders_total)} feeders, ${fmt(v.integration_pct, 1)}% metered · data for ${esc((v.data_refresh || '').slice(0, 10))}">
      <span>${esc(v.state)}</span><span class="track"><i class="fill" style="width:${v.hrs_inc_ag / 24 * 100}%;--c:${k === 'TN' ? FUELS.hydro.color : 'var(--stone-hi)'}"></i></span><span class="v">${hrs(v.hrs_inc_ag)}</span></div>`).join('');
  $('#nfms-states').onclick = e => { const r = e.target.closest('.row'); if (r) tipAt({ x: 380, y: r.getBoundingClientRect().top }, esc(r.title).replace(/ · /g, '<br>')); };
  const cities = [...n.cities].sort((a, b) => b.saidi - a.saidi);
  $('#nfms-cities').innerHTML = `<table class="sldc"><thead><tr><th>City</th><th>Discom</th><th>SAIFI</th><th>SAIDI h</th></tr></thead><tbody>${
    cities.map(c => `<tr class="${c.state === 'Tamil Nadu' ? 'tot' : ''}"><td>${esc(c.city)}</td><td>${esc(c.discom)}</td><td>${fmt(c.saifi, 3)}</td><td>${fmt(c.saidi, 2)}</td></tr>`).join('')}</tbody></table>`;
}

/* ------------------------------------------------------------- coal list */
function renderCoal() {
  const rows = PLANTS.filter(p => (p.type === 'coal' || p.type === 'lignite') && NOW.plants?.[p.id]?.stock_pct != null)
    .map(p => ({ p, l: NOW.plants[p.id] }));
  const tn = rows.filter(x => x.p.state === 'Tamil Nadu').sort((a, b) => a.l.stock_pct - b.l.stock_pct);
  const crit = rows.filter(x => x.l.crit).length;
  const d = rows[0]?.l.coal_date;
  $('#coal-when').textContent = d ? istDate(d) : '';
  $('#coal-list').innerHTML = tn.map(({ p, l }) => `<button class="coal-row ${l.crit ? 'crit' : ''}" data-id="${p.id}">
      <span class="nm">${esc(p.name)}</span><span class="d">${l.crit ? `${icon('alert', 'sm')} ` : ''}${fmt(l.stock_pct)}% · ${fmt(l.coal_d ?? (l.req_kt ? l.stock_kt / l.req_kt : null), 1)} d</span>
      <span class="meter"><i style="width:${Math.min(100, l.stock_pct)}%"></i><b title="critical: 25%"></b></span>
      <small>${fmt(l.stock_kt, 1)} kt in yard · ${esc((l.coal_mode || '').toLowerCase())}</small></button>`).join('')
    + `<p class="note fine">${crit} of ${rows.length} coal and lignite plants across India are critical today. The red mark is the critical line (25% of normative stock).</p>`;
}
$('#coal-list').addEventListener('click', e => { const b = e.target.closest('.coal-row'); if (b) openPlant(b.dataset.id, true); });

/* ----------------------------------------------------------------- find */
$('#names').innerHTML = PLANTS.map(p => `<option value="${esc(p.name)}">`).join('');
$('#search').addEventListener('change', e => {
  const q = e.target.value.trim().toLowerCase();
  const p = PLANTS.find(x => x.name.toLowerCase() === q) || PLANTS.find(x => x.name.toLowerCase().includes(q));
  if (p) openPlant(p.id, true);
});
$('#fly').innerHTML = FLY.map(([l], i) => `<button class="btn" data-i="${i}">${esc(l)}</button>`).join('');
$('#fly').addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  const f = FLY[+b.dataset.i][1];
  if (f.view) return map.flyTo({ ...VIEWS[f.view], duration: reduceMotion ? 0 : 2600, essential: true });
  if (f.center) return map.flyTo({ ...f, duration: reduceMotion ? 0 : 3000, essential: true });
  const p = PLANTS.find(x => f.match.test(x.name) || f.match.test(x.npp_name || ''));
  if (p) openPlant(p.id, true, f.zoom);
});

/* ------------------------------------------------------------ sparklines */
// One pixel per day, drawn at native size and scaled up unsmoothed; hover reads the day.
function spark(canvas, dates, vals, color, { ref = null, unit = 'MU', floor = 0 } = {}) {
  const n = vals.length, H = 34;
  canvas.width = n; canvas.height = H;
  const g = canvas.getContext('2d');
  const max = Math.max(ref || 0, ...vals.filter(v => v != null)) || 1;
  const lo = floor ? Math.min(...vals.filter(v => v != null)) * floor : 0;
  g.clearRect(0, 0, n, H);
  const css = getComputedStyle(document.documentElement);
  g.fillStyle = css.getPropertyValue('--cell-2').trim() || '#999';
  for (let i = 0; i < n; i++) if (vals[i] == null) g.fillRect(i, H - 1, 1, 1);
  g.fillStyle = color;
  for (let i = 0; i < n; i++) if (vals[i] != null) { const h = Math.max(1, Math.round((vals[i] - lo) / (max - lo || 1) * (H - 2))); g.fillRect(i, H - h, 1, h); }
  if (ref) { g.fillStyle = css.getPropertyValue('--tick').trim() || '#000'; const y = H - Math.round(ref / max * (H - 2)); for (let i = 0; i < n; i += 2) g.fillRect(i, y, 1, 1); }
  canvas.onmousemove = e => {
    const i = Math.min(n - 1, Math.max(0, Math.floor(e.offsetX / canvas.clientWidth * n)));
    tipAt({ x: e.clientX - map.getCanvas().getBoundingClientRect().left, y: e.clientY - map.getCanvas().getBoundingClientRect().top },
      `<b>${esc(istDate(dates[i]))} ${esc(dates[i].slice(0, 4))}</b>${vals[i] == null ? 'no report' : `${fmt(vals[i], 1)} ${unit}`}`);
  };
  canvas.onmouseleave = () => { $('#tip').hidden = true; };
}
let HIST = null;
const loadHistory = () => (HIST ||= fetch('data/live/history.json').then(r => r.json()).catch(() => null));

async function renderIndiaHistory() {
  const h = await fetch('data/live/history_totals.json').then(r => r.json()).catch(() => null);
  if (!h) return;
  const sum = (...ks) => h.dates.map((_, i) => ks.reduce((a, k) => a + (h.by_type[k]?.[i] || 0), 0));
  const rows = [['Coal & lignite', 'coal', sum('coal', 'lignite')], ['Hydro', 'hydro', sum('hydro', 'pumped_storage')],
                ['Gas & diesel', 'gas', sum('gas', 'diesel')], ['Nuclear', 'nuclear', sum('nuclear')]];
  const el = $('#india-history');
  el.innerHTML = `<p class="note fine">Daily generation, ${esc(istDate(h.dates[0]))} ${h.dates[0].slice(0, 4)} → ${esc(istDate(h.dates.at(-1)))}. One pixel per day; hover for the day.</p>`
    + rows.map(([l, k]) => `<div class="sp-row"><span class="kind" style="--c:${FUELS[k].color}"><span class="sw">${icon(FUELS[k].icon)}</span>${l}</span><b class="v"></b><canvas class="sp" data-k="${k}"></canvas></div>`).join('');
  rows.forEach(([, k, vals], i) => {
    const row = el.querySelectorAll('.sp-row')[i];
    row.querySelector('.v').textContent = `${fmt(vals.at(-1))} MU`;
    spark(row.querySelector('canvas'), h.dates, vals.map(v => v || null), FUELS[k].color);
  });
}

/* ---------------------------------------------------------- time machine */
let TM = null, tmTimer = null;
async function initTimeMachine() {
  const hh = await loadHistory();
  if (!hh?.dates?.length) { $('#tm').disabled = true; return; }
  TM = hh;
  const r = $('#tm');
  r.max = hh.dates.length - 1; r.value = r.max;
  $('#tm-day').textContent = istDate(hh.dates.at(-1));
  r.oninput = () => setDay(+r.value);
  $('#tm-play').onclick = () => {
    if (tmTimer) return stopPlay();
    if (+r.value >= +r.max) r.value = 0;
    $('#tm-play').innerHTML = icon('pause');
    tmTimer = setInterval(() => { const v = +r.value + 1; if (v > +r.max) return stopPlay(); r.value = v; setDay(v); }, reduceMotion ? 600 : 180);
  };
}
function stopPlay() { clearInterval(tmTimer); tmTimer = null; $('#tm-play').innerHTML = icon('play'); }
function setDay(i) {
  const d = TM.dates[i], latest = i === TM.dates.length - 1;
  $('#tm-day').textContent = latest ? `${istDate(d)} (latest)` : `${istDate(d)} ${d.slice(0, 4)}`;
  if (latest) { layer.setDay(null); $('#tm-note').textContent = 'Latest day. Drag back to replay any day of the last year.'; return; }
  const loads = {};
  let mu = 0;
  for (const p of PLANTS) {
    const v = TM.plants[p.id]?.[i];
    if (v != null && p.cap) { loads[p.id] = v * 1000 / 24 / p.cap; mu += v; }
  }
  layer.setDay(loads);
  $('#tm-note').textContent = `${istDate(d)} ${d.slice(0, 4)}: ${fmt(mu)} MU from the stations in CEA's daily report. Stations with no report that day show no output.`;
}

/* ----------------------------------------------------------------- card */
const card = $('#card');
let cardScene = null, lastFocus = null;
const EF = { coal: 0.98, lignite: 1.27, gas: 0.46, diesel: 0.75 };   // tCO2/MWh defaults (CEA CO2 baseline database averages)

async function openPlant(id, fly = false, zoom) {
  const p = byId.get(id);
  if (!p) return;
  lastFocus = document.activeElement;
  layer.select(id);
  highlightFeed(id);
  history.replaceState(null, '', `#p=${encodeURIComponent(id)}`);
  renderCard(p);
  if (fly) {
    const pad = desktop ? { ...BASE_PADDING, right: 400 } : { ...BASE_PADDING, bottom: Math.round(innerHeight * 0.5) };
    map.flyTo({ center: [p.lon, p.lat], zoom: zoom || Math.max(map.getZoom(), 13.2), pitch: 62, bearing: map.getBearing() || -20,
      padding: pad, duration: reduceMotion ? 0 : 3200, essential: true });
  }
  if (p.dossier) {
    try { const d = await fetch(`data/dossier/${encodeURIComponent(id)}.json`).then(r => r.json()); if (layer.selected === id) renderCard(p, d); } catch { /* none */ }
  }
}

let lastDossier = null;
function renderCard(p, dos) {
  lastDossier = dos || null;
  const f = fuel(p.type), l = NOW.plants?.[p.id] || {};
  const w = layer.windAt(p.lat, p.lon);
  const e = emis?.stations?.[p.id];
  const cap = p.cap || dos?.capacity_mw;
  const avg = l.mw, lf = l.lf;
  const sec = s => `<div class="spec">${s}</div>`;
  let h = `<button class="close" aria-label="Close">${icon('close')}</button>
    <canvas class="scene card-scene" aria-hidden="true"></canvas><div class="body">
    <h2 id="card-title">${esc(p.name)}</h2>
    <span class="kind" style="--c:${f.color}"><span class="sw">${icon(f.icon)}</span>${esc(f.label)}${p.status && p.status !== 'operating' ? ` · ${esc(p.status.replace('_', ' '))}` : ''}${p.cluster ? ' · cluster' : ''}</span>
    <div class="region">${esc([dos?.operator, p.sector && `${p.sector} sector`, dos?.district, p.state].filter(Boolean).join(' · '))}</div>
    ${cap ? `<p class="note" style="margin-top:8px">${p.cap_est ? 'about ' : ''}${fmt(cap)} MW installed${p.cap_est ? ' <span class="est">ESTIMATE</span> from the mapped array area (about 2 ha per MW)' : ''}${p.osm ? ` · <a href="https://www.openstreetmap.org/${esc(p.osm)}" target="_blank" rel="noopener">OSM ${esc(p.osm)}</a>` : ''}</p>` : ''}`;
  // output
  if (l.mu != null) {
    h += sec(`<h3 class="spec-h">${icon('bolt')}Output ${esc(istDate(l.d))} <span class="hint">${pct(lf)}</span></h3>
      <p class="big">${fmt(avg)}<small> MW average of ${fmt(cap)} MW</small></p>
      <div class="meter-lg" style="--c:${f.color}"><i style="width:${Math.min(100, (lf || 0) * 100)}%"></i>${l.prog != null && cap ? `<span class="tick" style="left:${Math.min(100, l.prog * 1000 / 24 / cap * 100)}%" title="programme"></span>` : ''}</div>
      <div class="meter-cap"><span>0 MW</span>${l.prog != null ? '<span><i class="tk"></i>CEA programme</span>' : ''}<span>${fmt(cap)} MW</span></div>
      <dl class="facts"><dt>Energy</dt><dd>${fmt(l.mu, 2)} MU (programme ${fmt(l.prog, 2)})</dd>
      ${l.ly != null ? `<dt>Same day 2025</dt><dd>${fmt(l.ly, 2)} MU</dd>` : ''}
      ${l.cum != null ? `<dt>Since 1 April</dt><dd>${fmt(l.cum)} MU${l.cum_ly ? ` (${l.cum_ly ? ((l.cum / l.cum_ly - 1) * 100).toFixed(0) : ''}% vs last year)` : ''}</dd>` : ''}
      ${l.out_mw ? `<dt>Under outage</dt><dd>${fmt(l.out_mw)} MW${l.rmk ? ` · ${esc(l.rmk)}` : ''}</dd>` : ''}</dl>`);
  } else if (p.state === 'Tamil Nadu' && layer.stateLoad[p.type] != null) {
    h += sec(`<h3 class="spec-h">${icon('bolt')}Output</h3><p class="note">Station-level output isn't published for ${esc(f.label.toLowerCase())}. Statewide, Tamil Nadu's ${esc(f.label.toLowerCase())} fleet was running at <b>${pct(layer.stateLoad[p.type])}</b> of capacity at the SLDC's last reading; the 3D model runs at that rate.</p>`);
  }
  h += `<div class="spec hist-slot" hidden><h3 class="spec-h">${icon('history')}Daily generation<span class="hint"></span></h3><canvas class="sp"></canvas><p class="note fine">One pixel per day from CEA's daily reports; dotted line = full capacity for 24 h.</p></div>`;
  // coal
  if (l.stock_pct != null) {
    h += sec(`<h3 class="spec-h">${icon('coal')}Coal in the yard ${l.crit ? '<span class="status-crit">' + icon('alert', 'sm') + 'CRITICAL</span>' : ''}<span class="hint">${fmt(l.stock_pct)}%</span></h3>
      <div class="meter-lg" style="--c:${l.crit ? 'var(--crit)' : 'var(--stone-hi)'}"><i style="width:${Math.min(100, l.stock_pct)}%"></i><span class="tick crit" style="left:25%" title="critical: 25% of normative stock"></span></div>
      <div class="meter-cap"><span>0%</span><span class="crit-l"><i class="tk crit"></i>critical 25%</span><span>100% = ${fmt(l.norm_days)} days' normative stock</span></div>
      <dl class="facts"><dt>Stock</dt><dd>${fmt(l.stock_kt, 1)} thousand t · ${fmt(l.coal_d ?? (l.req_kt ? l.stock_kt / l.req_kt : null), 1)} days</dd>
      <dt>Burns</dt><dd>${fmt(l.req_kt, 1)} kt/day at normative load</dd>
      <dt>Yesterday</dt><dd>received ${fmt(l.rcpt_kt, 1)} kt · burnt ${fmt(l.cons_kt, 1)} kt</dd>
      <dt>Arrives by</dt><dd>${esc((l.coal_mode || '–').toLowerCase())}</dd>${l.coal_rmk ? `<dt>CEA remark</dt><dd>${esc(l.coal_rmk)}</dd>` : ''}</dl>`);
  } else if (l.coal_d != null) {
    h += sec(`<h3 class="spec-h">${icon('coal')}Coal</h3><dl class="facts"><dt>Stock</dt><dd>${fmt(l.coal_d)} days (CEA daily report)</dd></dl>`);
  }
  // emissions: CEA CO2 database / FGD / fly ash / measured SO2 / CAAQMS where joined, labelled estimates otherwise
  if (f.thermal && (l.mu != null || e)) {
    const ef = e?.co2_t_per_mwh ?? EF[p.type];
    const rows = [];
    if (l.mu != null && ef) rows.push(['CO₂ yesterday', `${fmt(l.mu * 1000 * ef)} t <small>(${ef} t/MWh${e?.co2_t_per_mwh ? `, CEA ${esc(e.co2_fy || '')}` : ', fuel average'})</small>`]);
    if (e?.co2_t) rows.push([`CO₂ FY ${esc(e.co2_fy || '')}`, `${fmt(e.co2_t / 1e6, 2)} million t`]);
    if (e?.fgd) rows.push(['SO₂ scrubber (FGD)', `${esc(e.fgd)}${e.so2_deadline ? ` · SO₂ limit due ${esc(e.so2_deadline)}` : ''}`]);
    if (e?.so2_norm?.length) rows.push(['SO₂ limit', `${e.so2_norm.map(fmt).join(' / ')} mg/Nm³ (2015 norms)`]);
    if (e?.so2_measured?.length) rows.push(['SO₂ measured 2021', e.so2_measured.map(u => `${esc(u.unit)}: <b class="${u.limit && u.mean > u.limit ? 'warn-text' : ''}">${fmt(u.mean)}</b>${u.limit ? `/${fmt(u.limit)}` : ''}`).join('<br>')]);
    if (e?.fly_ash?.fly_ash_generated_mt != null) rows.push(['Fly ash 2021-22', `${fmt(e.fly_ash.fly_ash_generated_mt, 2)} Mt made · ${fmt(e.fly_ash.utilisation_pct)}% used${e.fly_ash.ash_content_pct ? ` · ash ${fmt(e.fly_ash.ash_content_pct, 1)}%` : ''}`]);
    if (e?.est) rows.push(['This year, annualised <span class="est">ESTIMATE</span>', `CO₂ ${fmt((e.est.co2_t || 0) / 1e6, 2)} Mt · SO₂ ${fmt(e.est.so2_t_best)} t · NOx ${fmt(e.est.nox_t)} t · PM ${fmt(e.est.pm_t)} t`]);
    if (w) rows.push(['Plume heading', `towards ${Math.round(((w.wind_direction_10m ?? 0) + 180) % 360)}° at ${fmt(w.wind_speed_10m, 1)} m/s`]);
    if (e?.caaqms?.length) rows.push(['Air monitors', e.caaqms.map(c => `${esc(c.name)} (${fmt(c.distance_km, 1)} km)`).join('<br>')]);
    if (e?.incidents?.length) rows.push(['On record', e.incidents.map(x => esc(String(x).replace(/-/g, ' '))).join('; ')]);
    if (rows.length) h += sec(`<h3 class="spec-h">${icon('smoke')}Emissions${e?.co2_t_per_mwh ? '' : '<span class="est">ESTIMATE</span>'}</h3>
      ${e?.co2_hist ? '<canvas class="sp co2-sp"></canvas>' : ''}
      <dl class="facts stack">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${e?.est_caveats ? `<details class="more"><summary>${icon('info', 'sm')}How the estimates are made</summary><p class="note fine">${esc(e.est_method || '')}</p><ul class="srcs">${e.est_caveats.map(c => `<li>${esc(c)}</li>`).join('')}</ul></details>` : ''}`);
  }
  // dossier
  if (dos) {
    if (dos.units?.length) h += sec(`<h3 class="spec-h">${icon('list')}Units<span class="hint">${dos.units.length}</span></h3><table class="units"><thead><tr><th>#</th><th>MW</th><th>Since</th><th>Make</th><th>Status</th></tr></thead><tbody>${
      dos.units.map(u => `<tr><td>${esc(u.no ?? '')}</td><td class="n">${fmt(u.mw)}</td><td>${esc(u.commissioned || '–')}</td><td>${esc(u.make || '–')}</td><td>${esc(u.status || '')}</td></tr>`).join('')}</tbody></table>`);
    const fu = dos.fuel || {};
    const chain = [...(fu.sources || []).map(s => `${s.kind ? `${s.kind}: ` : ''}${s.name}${s.share ? ` (${s.share})` : ''}`), ...(fu.route || [])];
    if (chain.length || fu.annual_requirement) h += sec(`<h3 class="spec-h">${icon('route')}Fuel sources</h3><ul class="chain">${chain.map(c => `<li>${icon('route')}${esc(c)}</li>`).join('')}</ul>${fu.annual_requirement ? `<p class="note">Needs ${esc(fu.annual_requirement)}.</p>` : ''}`);
    const facts = [['Water', dos.water && [dos.water.source, dos.water.cooling].filter(Boolean).join(' · ')], ['Evacuation', (dos.evacuation || []).join('; ')],
      ['Emissions', dos.emissions && [dos.emissions.fgd && `FGD: ${dos.emissions.fgd}`, dos.emissions.notes].filter(Boolean).join(' · ')]].filter(x => x[1]);
    if (facts.length) h += sec(`<dl class="facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`);
    if (dos.history) h += sec(`<p class="note" style="margin:0">${esc(dos.history)}</p>`);
  }
  // fuel supply chains (feed.json): each one a button that opens its schematic
  const chains = FEED?.chains?.[p.id] || [];
  if (chains.length) {
    h += sec(`<h3 class="spec-h">${icon('route')}Fuel supply chains<span class="hint">${chains.length}</span></h3><div class="chain-list">${chains.map(ch => {
      const c = chainSummary(ch);
      return `<button class="chain-btn" data-chain="${esc(ch.id)}"><b>${esc(cap1(ch.fuel || 'fuel'))} from ${esc(shortName(c.first))}</b><span>${esc(c.steps)}${c.km ? ` · about ${fmt(c.km)} km` : ''}${typeof ch.share === 'number' ? ` · ${pct(ch.share)} of receipts` : ''}${ch.status === 'planned' ? ' · planned' : ''}</span></button>`;
    }).join('')}</div><p class="note fine">Tap a chain for its schematic; the station's routes are in gold on the map.</p>`);
  }
  if (w) h += sec(`<h3 class="spec-h">${icon('cloud')}Weather at site</h3><dl class="facts"><dt>Wind</dt><dd>from ${fmt(w.wind_direction_10m)}° · ${fmt(w.wind_speed_10m, 1)} m/s (${fmt(w.wind_speed_80m, 1)} m/s at 80 m)</dd><dt>Air</dt><dd>${fmt(w.temperature_2m, 1)} °C · cloud ${fmt(w.cloud_cover)}%</dd></dl>`);
  const srcs = [...(dos?.sources || [])];
  h += `<div class="links"><a href="https://npp.gov.in/dashBoard/gc-map-dashboard" target="_blank" rel="noopener">${icon('external')}NPP</a>
    <a href="https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=15/${p.lat}/${p.lon}" target="_blank" rel="noopener">${icon('places')}OSM</a></div>
    <p class="note fine">Position: ${esc({ exact: 'checked', npp: 'National Power Portal', osm: 'OpenStreetMap', approx: 'approximate', dossier: 'dossier' }[p.q] || p.q)}. ${p.npp ? `NPP station ${p.npp}.` : ''}</p>
    ${srcs.length ? `<details class="more"><summary>${icon('book', 'sm')}Sources</summary><ul class="srcs">${srcs.map(s => `<li>${/^https?:/.test(s) ? `<a href="${esc(s)}" target="_blank" rel="noopener">${esc(s)}</a>` : esc(s)}</li>`).join('')}</ul></details>` : ''}
    </div>`;
  card.innerHTML = h;
  card.hidden = false;
  document.body.classList.add('card-open');
  card.querySelector('.close').onclick = closeCard;
  card.querySelectorAll('[data-chain]').forEach(b => { b.onclick = () => { const c = CHAIN_BY_ID.get(b.dataset.chain); if (c) openChains([c], `${cap1(c.ch.fuel || 'fuel')} supply chain`, p.name); }; });
  cardScene?.();
  cardScene = null;
  mountCardScene(p, card.querySelector('.card-scene'));
  const cs = card.querySelector('.co2-sp');
  if (cs && e?.co2_hist) { const ks = Object.keys(e.co2_hist).sort(); spark(cs, ks.map(k => `${k.slice(0, 4)}-04-01`), ks.map(k => e.co2_hist[k]), uiDark() ? '#b9bcc2' : '#5b6070', { unit: 't CO₂/MWh', floor: 0.9 }); }
  loadHistory().then(hh => {
    const v = hh?.plants?.[p.id], slot = card.querySelector('.hist-slot');
    if (!v || !slot || layer.selected !== p.id) return;
    slot.hidden = false;
    const got = v.filter(x => x != null).length;
    slot.querySelector('.hint').textContent = `${got} days`;
    spark(slot.querySelector('canvas'), hh.dates, v, f.color, { ref: cap ? cap * 24 / 1000 : null });
  });
}
function closeCard() {
  card.hidden = true;
  cardScene?.(); cardScene = null;
  layer.select(null);
  highlightFeed(null);
  document.body.classList.remove('card-open');
  history.replaceState(null, '', location.pathname);
  lastFocus?.focus?.();
}
addEventListener('keydown', e => { if (e.key === 'Escape' && !card.hidden) closeCard(); });

let SCENES = null;
const scenesReady = import('./scenes.js?v=2').then(m => (SCENES = m)).catch(e => { console.warn('scenes.js unavailable', e); return null; });
async function mountCardScene(p, canvas) {
  await scenesReady; await modelsReady;
  if (!SCENES || !canvas || !canvas.isConnected) { if (canvas) canvas.hidden = true; return; }
  const M = await modelsReady;
  const arch = M?.archetypeFor ? M.archetypeFor(p) : p.type;
  const e = layer.entries?.find(x => x.p.id === p.id);
  cardScene = SCENES.mountScene(canvas, arch, () => ({ load: e?.ld ?? 0, plant: p }));
}

// hero: cycles through Tamil Nadu's fleet, each running at its statewide load
(async () => {
  await scenesReady;
  if (!SCENES) { $('#hero-scene').hidden = true; return; }
  const cycle = [['coal', 'coal'], ['wind_farm', 'wind'], ['solar_farm', 'solar'], ['hydro_dam', 'hydro'], ['nuclear_vver', 'nuclear']];
  let i = 0, stop = null;
  const next = () => {
    stop?.();
    const [arch, key] = cycle[i++ % cycle.length];
    const r = NOW.tn?.rows || {};
    const loadOf = { coal: r.thermal?.capacity_mw ? r.thermal.morning_mw / r.thermal.capacity_mw : 0.6, nuclear: 0.85 };
    stop = SCENES.mountScene($('#hero-scene'), arch, () => ({ load: loadOf[key] ?? layer.stateLoad[key] ?? 0.5 }));
  };
  next();
  if (!reduceMotion) setInterval(next, 9000);
})();

/* --------------------------------------------------------------- clicks */
map.on('click', e => {
  const f = map.queryRenderedFeatures(e.point, { layers: ['plants-hit'].filter(id => map.getLayer(id)) });
  if (f.length) return openPlant(f[0].properties.id, false);
  const s = map.getLayer('subs') && map.queryRenderedFeatures([[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]], { layers: ['subs'] });
  if (s?.length) {
    const pr = s[0].properties;
    return tipAt(e.point, `<b>${esc(pr.name || 'Substation')}</b>${pr.ratio ? `${esc(pr.ratio)} kV` : pr.kv ? `${fmt(pr.kv)} kV` : ''}${pr.mva ? ` · ${fmt(pr.mva)} MVA` : ''}${pr.tx ? ` · ${pr.tx} transformers` : ''}${pr.circle ? `<br><span class="k">Circle</span>${esc(pr.circle)}` : ''}${pr.operator ? `<br>${esc(pr.operator)}` : ''}`);
  }
  const fn = map.getLayer('feed-nodes') && map.queryRenderedFeatures([[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]], { layers: ['feed-nodes'] });
  if (fn?.length) { const pr = fn[0].properties; return tipAt(e.point, `<b>${esc(pr.name)}</b>${esc(pr.kind.replace('_', ' '))}${pr.note ? `<br>${esc(pr.note.slice(0, 220))}` : ''}`); }
  const fr = FEED_LAYERS.filter(id => /^feed-(sea|rail|pipeline|conveyor|air|hi)$/.test(id) && map.getLayer(id));
  const rr = fr.length && map.queryRenderedFeatures([[e.point.x - 7, e.point.y - 7], [e.point.x + 7, e.point.y + 7]], { layers: fr });
  if (rr?.length) {
    // every chain that runs along the tapped route(s), grouped as schematics
    const ids = [...new Set(rr.flatMap(f => f.properties.chains_s.split(',').filter(Boolean)))];
    const items = ids.map(id => CHAIN_BY_ID.get(id)).filter(Boolean).slice(0, 8);
    if (items.length) {
      const r0 = FEED.routes[rr[0].properties.i];
      return openChains(items, `${FEED_MODE[modeOf(r0.mode)].label} route`, `${r0.from_name && r0.to_name ? `${shortName(r0.from_name)} → ${shortName(r0.to_name)} · ` : ''}${items.length} supply chain${items.length > 1 ? 's' : ''} use it`);
    }
    const pr = rr[0].properties;
    return tipAt(e.point, `<b>${esc(FEED_MODE[pr.mode]?.label || pr.mode)}</b>${esc(pr.cargo)}`);
  }
  const ln = LINE_LAYERS.filter(id => !id.endsWith('glow') && map.getLayer(id));
  const l = ln.length && map.queryRenderedFeatures([[e.point.x - 5, e.point.y - 5], [e.point.x + 5, e.point.y + 5]], { layers: ln });
  if (l?.length) { const pr = l[0].properties; return tipAt(e.point, `<b>${fmt(pr.voltage_kv)} kV line</b>${esc(pr.name || '')}${pr.circuits ? ` · ${pr.circuits} circuits` : ''}${pr.operator ? `<br>${esc(pr.operator)}` : ''}`); }
  $('#tip').hidden = true;
});
for (const id of ['plants-hit', 'subs']) {
  map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
}
function tipAt(pt, html) {
  const t = $('#tip');
  t.innerHTML = html; t.hidden = false;
  const r = map.getCanvas().getBoundingClientRect();
  t.style.left = `${Math.min(r.left + pt.x + 12, innerWidth - 270)}px`;
  t.style.top = `${Math.max(8, r.top + pt.y - 20)}px`;
  clearTimeout(tipAt.h); tipAt.h = setTimeout(() => { t.hidden = true; }, 6000);
}
function openFromHash() {
  const m = location.hash.match(/p=([^&]+)/);
  if (m) openPlant(decodeURIComponent(m[1]), true);
}

/* ---------------------------------------------------------- feed chains */
// Supply routes (sea lanes, rail legs, pipelines, conveyors) and their nodes (mines, ports, gas fields).
// Mode is told by dash pattern and legend icon as well as colour.
const FEED_LAYERS = [];
const FEED_MODE = {
  sea: { dark: '#5fc8ff', light: '#1f6fb5', dash: [2, 2], icon: 'ship', label: 'Sea (coal, LNG)', verb: 'Ship' },
  rail: { dark: '#b79cff', light: '#6b4fc4', dash: [4, 1.5], icon: 'train', label: 'Rail', verb: 'Rail' },
  pipeline: { dark: '#ff9f3a', light: '#d9660b', dash: [1, 0], icon: 'pipe', label: 'Gas pipeline', verb: 'Pipeline' },
  conveyor: { dark: '#c9ced3', light: '#5d6470', dash: [1, 1], icon: 'coal', label: 'Conveyor / road', verb: 'Conveyor / road' },
  air: { dark: '#f5f1e6', light: '#333842', dash: [0.5, 2.5], icon: 'nuclear', label: 'Air (nuclear fuel)', verb: 'Air' },
};
const MODE_ALIAS = { 'on-site': 'conveyor', road: 'conveyor', truck: 'conveyor', river: 'sea', coastal: 'sea' };
const modeOf = m => FEED_MODE[m] ? m : MODE_ALIAS[m] || 'conveyor';
let FEED_MODES_USED = new Set();
const NODE_GROUP = { mine: 'mine', coal_mine: 'mine', lignite_mine: 'mine', coalfield: 'mine', captive_block: 'mine',
  port: 'port', terminal: 'port', foreign_port: 'port', rail_station: 'rail', lng: 'gas', gasfield: 'gas', gas_terminal: 'gas',
  nuclear_fuel: 'nuc', uranium_mine: 'nuc', mill: 'nuc', fuel_fabrication: 'nuc', reprocessing: 'nuc', heavy_water_plant: 'nuc', reactor: 'nuc', plant: 'plant' };
const NODE_COL = { mine: ['#e6a23c', '#9a5b00'], port: ['#5fc8ff', '#1f6fb5'], rail: ['#b79cff', '#6b4fc4'], gas: ['#ff9f3a', '#d9660b'], nuc: ['#d55181', '#b0306a'], plant: ['#f5f1e6', '#1b1d22'] };
const NODE_ICON = { mine: 'mine', port: 'ship', rail: 'train', gas: 'gas', nuc: 'nuclear' };
const nodeCol = () => ['match', ['get', 'grp'], ...Object.entries(NODE_COL).flatMap(([k, v]) => [k, mapDark ? v[0] : v[1]]), mapDark ? '#c9ced3' : '#5d6470'];
let FEED = null;
const CHAIN_BY_ID = new Map();
async function addFeed() {
  FEED = await fetch('data/feed.json').then(r => r.json()).catch(() => null);
  if (!FEED) return;
  for (const [pid, list] of Object.entries(FEED.chains || {})) for (const ch of list) CHAIN_BY_ID.set(ch.id, { pid, ch });
  const routes = { type: 'FeatureCollection', features: FEED.routes.map((r, i) => ({ type: 'Feature', id: i,
    properties: { id: r.id, i, mode: modeOf(r.mode), cargo: r.cargo || '', serves_s: `,${(r.serves || []).join(',')},`, chains_s: `,${(r.chains || []).join(',')},` },
    geometry: { type: 'LineString', coordinates: r.coords } })) };
  const nodes = { type: 'FeatureCollection', features: FEED.nodes.map(n => ({ type: 'Feature',
    properties: { id: n.id, kind: n.kind, grp: NODE_GROUP[n.kind] || 'other', name: n.name, note: n.note || '', serves_s: `,${(n.serves || []).join(',')},` },
    geometry: { type: 'Point', coordinates: [n.lon, n.lat] } })) };
  map.addSource('feed-routes', { type: 'geojson', data: routes });
  map.addSource('feed-nodes', { type: 'geojson', data: nodes });
  const before = map.getLayer('plants-hit') ? 'plants-hit' : undefined;
  for (const [mode, m] of Object.entries(FEED_MODE)) {
    map.addLayer({ id: `feed-${mode}`, type: 'line', source: 'feed-routes', minzoom: 3.5, filter: ['==', ['get', 'mode'], mode],
      layout: { 'line-cap': 'butt' },
      paint: { 'line-color': mapDark ? m.dark : m.light, 'line-opacity': 0.7, 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1.2, 10, 2.6], 'line-dasharray': m.dash } }, before);
    FEED_LAYERS.push(`feed-${mode}`);
  }
  map.addLayer({ id: 'feed-hi', type: 'line', source: 'feed-routes', filter: ['==', ['get', 'id'], '__none__'],
    paint: { 'line-color': mapDark ? '#ffd84a' : '#d18a00', 'line-width': ['interpolate', ['linear'], ['zoom'], 4, 3, 10, 5.5], 'line-opacity': 0.95 } }, before);
  map.addLayer({ id: 'feed-nodes', type: 'circle', source: 'feed-nodes', minzoom: 3.5, filter: ['!=', ['get', 'grp'], 'rail'],
    paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3, 10, 7], 'circle-color': mapDark ? '#0b0d14' : '#ffffff',
             'circle-stroke-color': nodeCol(), 'circle-stroke-width': 2 } }, before);
  map.addLayer({ id: 'feed-node-labels', type: 'symbol', source: 'feed-nodes', minzoom: 6, filter: ['!=', ['get', 'grp'], 'rail'],
    layout: { 'text-field': ['get', 'name'], 'text-font': ['Open Sans Regular', 'Noto Sans Regular'], 'text-size': 12, 'text-anchor': 'left', 'text-offset': [0.8, 0], 'text-optional': true, 'text-max-width': 14 },
    paint: { 'text-color': mapDark ? '#9fc6e0' : '#1f4f7a', 'text-halo-color': mapDark ? '#05080c' : '#ffffff', 'text-halo-width': 1.5 } });
  FEED_LAYERS.push('feed-hi', 'feed-nodes', 'feed-node-labels');
  if (!$('#l-feed').checked) vis(FEED_LAYERS, false);
  for (const id of FEED_LAYERS.filter(x => /^feed-(sea|rail|pipeline|conveyor|air)$/.test(x))) {
    map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
    map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
  }
  if (layer.selected) { highlightFeed(layer.selected); const p = byId.get(layer.selected); if (p && !card.hidden) renderCard(p, lastDossier); }
  FEED_MODES_USED = new Set(FEED.routes.map(r => modeOf(r.mode)));
  renderLineLegend();
  $('#feed-note').textContent = `${FEED.nodes.length} mines, ports, fields & fuel plants · ${Object.keys(FEED.chains || {}).length} stations' chains · tap a route`;
  await modelsReady;
  layer.setRoutes(FEED.routes);
}
function highlightFeed(id) {
  if (!map.getLayer('feed-hi')) return;
  map.setFilter('feed-hi', id ? ['in', `,${id},`, ['get', 'serves_s']] : ['==', ['get', 'id'], '__none__']);
}

/* ------------------------------------------------- supply-chain schematic */
// A chain drawn as a vertical flow: source → each leg (mode, distance) → node → … → the station. Rail
// legs junction-to-junction are merged into one leg, with the junctions listed as "via".
const nodeIcon = kind => NODE_ICON[NODE_GROUP[kind]] || 'pin';
const nodeColour = kind => { const c = NODE_COL[NODE_GROUP[kind]]; return c ? (uiDark() ? c[0] : c[1]) : '#6b7385'; };
function mergeLegs(legs) {
  const out = [];
  for (const lg of legs) {
    const prev = out.at(-1);
    if (prev && prev.mode === lg.mode && prev.to === lg.from && lg.mode === 'rail') {
      prev.via.push(prev.to); prev.to = lg.to; prev.to_kind = lg.to_kind; prev.km = (prev.km || 0) + (lg.km || 0) || null;
    } else out.push({ ...lg, via: [] });
  }
  return out;
}
const cap1 = t => String(t || '').replace(/^./, c => c.toUpperCase());
const shortName = n => String(n || '').replace(/ railway station$/i, '').replace(/ Junction$/i, ' Jn');
function chainSummary(ch) {
  const m = mergeLegs(ch.legs);
  const km = m.reduce((a, l) => a + (l.km || 0), 0);
  const steps = m.map(l => `${(FEED_MODE[l.mode]?.verb || l.mode).toLowerCase()}${l.km ? ` ${fmt(l.km)} km` : ''}`).join(' → ');
  return { first: ch.legs[0]?.from, km, steps };
}
function openChains(items, title, sub) {
  // items: [{pid, ch}]
  document.querySelector('.dialog-back')?.remove();
  const back = document.createElement('div');
  back.className = 'dialog-back';
  const esc2 = esc;
  const body = items.map(({ pid, ch }) => {
    const p = byId.get(pid), m = mergeLegs(ch.legs);
    const km = m.reduce((a, l) => a + (l.km || 0), 0);
    const share = typeof ch.share === 'number' ? ` · ${pct(ch.share)} of receipts` : '';
    let h = `<p class="flow-head">${esc2(cap1(ch.fuel || 'fuel'))} for ${esc2(p?.name || pid)} <span>· about ${fmt(km)} km${share}${ch.status === 'planned' ? ' · planned' : ''}</span></p><ol class="flow">`;
    h += `<li class="node" style="--c:${nodeColour(m[0]?.from_kind)}"><span class="ic">${icon(nodeIcon(m[0]?.from_kind))}</span><span><b>${esc2(m[0]?.from)}</b><small>${esc2((m[0]?.from_kind || '').replace(/_/g, ' '))}</small></span></li>`;
    for (const l of m) {
      const md = FEED_MODE[l.mode] || FEED_MODE.conveyor;
      h += `<li class="leg" style="--c:${uiDark() ? md.dark : md.light}">${icon(md.icon)}<span><b>${esc2(md.verb)}</b>${l.km ? ` · about ${fmt(l.km)} km` : ''}${l.via.length ? ` · via ${esc2(l.via.map(shortName).join(', '))}` : ''}${l.note && !/schematic/i.test(l.note) ? ` · ${esc2(l.note)}` : ''}</span></li>`;
      const last = l === m.at(-1), via = !last && l.to_kind === 'plant';
      const pf = (last || via) && p ? fuel(p.type) : null;
      const kindTxt = last ? `${fmt(p?.cap)} MW station` : via ? 'transfer at this station\'s yard' : (l.to_kind || '').replace(/_/g, ' ');
      h += `<li class="node ${last ? 'plant' : ''}" style="--c:${pf ? pf.color : nodeColour(l.to_kind)}"><span class="ic">${icon(pf ? pf.icon : nodeIcon(l.to_kind))}</span><span><b>${esc2(shortName(l.to))}</b><small>${esc2(kindTxt)}</small></span></li>`;
    }
    return h + `</ol><div class="grid2"><button class="btn" data-show="${esc2(ch.id)}">${icon('route')}Show on map</button>${p ? `<button class="btn" data-open="${esc2(pid)}">${icon('info')}Open station</button>` : ''}</div>`;
  }).join('');
  back.innerHTML = `<section class="dialog" role="dialog" aria-modal="true" aria-labelledby="dlg-t"><header><h2 id="dlg-t">${esc(title)}<small>${esc(sub || '')}</small></h2>
    <button class="close" aria-label="Close">${icon('close')}</button></header>${body}
    <p class="note fine">From CEA coal statements, port, railway and company records. Lines on the map join the documented mines, junctions and ports; they are not traced tracks.</p></section>`;
  document.body.appendChild(back);
  const close = () => { back.remove(); };
  back.addEventListener('click', e => {
    if (e.target === back || e.target.closest('.close')) return close();
    const sh = e.target.closest('[data-show]'), op = e.target.closest('[data-open]');
    if (sh) { showChain(sh.dataset.show); close(); }
    if (op) { close(); openPlant(op.dataset.open, true); }
  });
  back.querySelector('.close').focus();
  addEventListener('keydown', function k(e) { if (e.key === 'Escape') { close(); removeEventListener('keydown', k); } });
}
function showChain(cid) {
  if (!map.getLayer('feed-hi')) return;
  if (!$('#l-feed').checked) { $('#l-feed').checked = true; vis(FEED_LAYERS, true); layer.setVisible({ feed: true }); }
  map.setFilter('feed-hi', ['in', `,${cid},`, ['get', 'chains_s']]);
  const cs = FEED.routes.filter(r => (r.chains || []).includes(cid)).flatMap(r => r.coords);
  if (!cs.length) return;
  const b = cs.reduce((bb, c) => bb.extend(c), new maplibregl.LngLatBounds(cs[0], cs[0]));
  const pad = desktop ? { top: 60, bottom: 60, left: 380, right: card.hidden ? 60 : 420 } : { top: 80, bottom: Math.round(innerHeight * 0.45), left: 30, right: 30 };
  map.fitBounds(b, { padding: pad, pitch: 30, duration: reduceMotion ? 0 : 2400, maxZoom: 9 });
}

/* ---------------------------------------------------------- station labels */
// HTML labels floated just above each pillar or model top (the layer projects the anchors every frame), so
// a name never sits on the object it names. Size follows zoom; below z 4.8 there are none, then the
// biggest stations first; overlapping labels give way to the larger station.
const labelsEl = $('#labels');
const labelPool = new Map();
const clampN = (v, a, b) => Math.max(a, Math.min(b, v));
// Station names as on the posters (scripts/render_poster.py clean_name): the fuel icon says what kind of
// station it is, so type suffixes and shorthand (TPS, STPS, Thermal Power Station...) are dropped.
const SUFFIX_RX = new RegExp([
  'super thermal power (station|project|plant)', 'thermal power (station|project|plant)( project)?', 'atomic power (station|project|plant)',
  'nuclear power (station|project|plant)', 'gas turbine power (station|plant)', 'combined cycle (power )?(plant|station|project)',
  'hydro ?electric (power )?(station|project|plant)', 'hydel (power )?(station|project)', 'pumped storage (power )?(station|project|plant|house)?',
  'solar (power )?(park|project|plant|station)', '(offshore )?wind (farm|park|belt|zone|power project)', 'power (station|plant|project|house|generation)',
  'gas engine power plant', 'gas engine plant', 'gas plant', 'diesel power plant', 'captive power (plant|station)', 'captive',
  'thermal plant', 'thermal power', 'power house', '\\bproject\\b',
  '\\b(u?mtpp|umtpp|stpp|stps|sctpp|ctpp|tpp|tps|ccpp|ccgt|gtps|gps|hps|pshep|shep|hep|aps|npp|psp|gt|dg|pp)\\b',
  '\\b(limited|ltd|pvt|private|company|corporation|co)\\b\\.?', '\\b\\d+(\\.\\d+)? ?mw\\b', '\\bists\\b'].join('|'), 'gi');
function cleanName(n) {
  let s = n.replace(/\s+—.*$/, '').replace(/\s*\([^)]*\)/g, '').replace(SUFFIX_RX, ' ');
  s = s.replace(/\s+,/g, ',').replace(/\s{2,}/g, ' ').trim().replace(/^[\s,.–-]+|[\s,.–-]+$/g, '');
  return s.replace(/\s+-\s*(?=[IVX\d])/g, ' ');
}
const LABEL_NAME = (() => {
  const out = new Map(), by = new Map();
  for (const p of PLANTS) {
    const c = cleanName(p.name) || p.name;
    out.set(p.id, c);
    const k = `${c.toLowerCase()}|${p.state}`;
    if (!by.has(k)) by.set(k, []);
    by.get(k).push(p);
  }
  for (const g of by.values()) if (g.length > 1) for (const p of g) {    // two stations in one town: "Suratgarh" / "Suratgarh Super"
    if (/\bstps\b|super thermal|\bstpp\b/i.test(p.name)) out.set(p.id, `${out.get(p.id)} Super`);
    else if (p.type === 'gas' && /\b(ccgt|ccpp|gas)\b/i.test(p.name)) out.set(p.id, `${out.get(p.id)} Gas`);
  }
  return out;
})();
function wrapName(s, max) {
  const lines = [];
  let line = '';
  for (const w of s.split(' ')) {
    const t = line ? `${line} ${w}` : w;
    if (t.length > max && line) { lines.push(line); line = w; } else line = t;
  }
  if (line) lines.push(line);
  return lines;
}
function labelText(a) {
  const p = a.p, cap = p.cap || 0;
  const pre = p.status && p.status !== 'operating' ? `${p.status.replace('_', ' ')} · ` : '';
  if (a.ld != null && cap && (!p.status || p.status === 'operating')) {
    const live = NOW.plants?.[p.id]?.mw != null && !layer.dayLoads;
    return `${fmt(a.ld * cap)} of ${fmt(cap)} MW ${live ? 'yesterday' : p.state === 'Tamil Nadu' && layer.stateLoad[p.type] != null ? 'now' : ''}`.trim();
  }
  return `${pre}${p.cap_est ? 'about ' : ''}${fmt(cap)} MW`;
}
let labelFrame = 0;
layer.onLabels = (anchors, zoom) => {
  if (labelFrame++ % 2) return;                    // every other frame is plenty for text
  const fs = clampN(10.5 + (zoom - 5) * 0.42, 11, 14), max = desktop ? 60 : 26;
  anchors.sort((a, b) => (b.p.id === layer.selected) - (a.p.id === layer.selected) || (b.p.cap || 0) - (a.p.cap || 0));
  const placed = [], keep = new Set();
  for (const a of anchors) {
    if (placed.length >= max) break;
    const sub = labelText(a);
    const lines = wrapName(LABEL_NAME.get(a.p.id) || a.p.name, desktop ? 24 : 20);
    const w = Math.max(...lines.map(l => l.length * fs * 0.58), sub.length * fs * 0.5) + fs * 1.6 + 22;
    const hgt = lines.length * fs * 1.2 + fs * 1.05 + 12;
    const x = a.sx - w / 2, y = a.sy - hgt - 8;
    if (x + w < 0 || x > innerWidth || y + hgt < 0) continue;
    if (placed.some(r => x < r[0] + r[2] && x + w > r[0] && y < r[1] + r[3] && y + hgt > r[1])) continue;
    placed.push([x, y, w, hgt]);
    keep.add(a.p.id);
    let el = labelPool.get(a.p.id);
    if (!el) {
      el = document.createElement('button');
      el.className = 'lab';
      el.tabIndex = -1;
      el.onclick = () => openPlant(el.dataset.id, false);
      el.dataset.id = a.p.id;
      labelsEl.appendChild(el);
      labelPool.set(a.p.id, el);
    }
    const f = fuel(a.p.type);
    const txt = `<span class="sw">${icon(f.icon)}</span><span class="t">${lines.map(esc).join('<br>')}<small>${esc(sub)}</small></span>`;
    if (el._t !== txt) { el.innerHTML = txt; el._t = txt; el.title = `${a.p.name} (${f.label}) · ${sub}`; }
    el.style.setProperty('--c', mapDark ? f.dark : f.light);
    el.style.setProperty('--fs', `${fs.toFixed(1)}px`);
    el.style.transform = `translate(${Math.round(a.sx)}px, ${Math.round(a.sy - 8)}px) translate(-50%, -100%)`;
    el.classList.toggle('sel', a.p.id === layer.selected);
    el.hidden = false;
  }
  for (const [id, el] of labelPool) if (!keep.has(id)) el.hidden = true;
};

/* ------------------------------------------------------------ theme button */
function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  try { localStorage.setItem('pw-theme', dark ? 'dark' : 'light'); } catch { /* ignore */ }
  const b = $('#theme-toggle');
  b.setAttribute('aria-pressed', dark);
  b.title = b.ariaLabel = dark ? 'Light mode' : 'Dark mode';
  b.innerHTML = icon(dark ? 'sun' : 'moon');
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', dark ? '#0b0d14' : '#f4f1ea');
  renderFuels(); renderAll(); renderLineLegend();
  if (!card.hidden && layer.selected) renderCard(byId.get(layer.selected), lastDossier);
  if (!$('#l-sun').checked) updateSun(false);
}
$('#theme-toggle').onclick = () => setTheme(!uiDark());

/* ---------------------------------------------------------------- panel */
const panel = $('#panel'), toggle = $('#panel-toggle');
function setSheet(open) {
  panel.classList.toggle('collapsed', !open);
  toggle.setAttribute('aria-expanded', open);
  document.body.classList.toggle('sheet-open', open && !desktop);
}
if (!desktop) setSheet(false);
panel.querySelector('header').addEventListener('click', e => { if (desktop || e.target.closest('a')) return; setSheet(panel.classList.contains('collapsed')); });

/* ------------------------------------------------------------ live loop */
function renderAll() {
  renderTN(); renderIndia(); renderIndiaNow(); renderNFMS(); renderCoal(); renderIndiaHistory(); renderTNReadings();
  const src = NOW.sources || {};
  $('#built').textContent = `Atlas built ${atlas.meta.built.slice(0, 10)}; live data refreshed ${istTime(NOW.generated)} IST.`;
}
renderAll();
initTimeMachine();
setInterval(async () => {
  try {
    const n = await fetch(`data/live/now.json?t=${Date.now() / 6e4 | 0}`).then(r => r.json());
    if (n.generated !== NOW.generated) { NOW = n; layer.setLive(NOW); applyStateLoads(); renderAll(); const id = layer.selected; if (id && !card.hidden) renderCard(byId.get(id)); }
  } catch { /* offline: keep the last data */ }
}, 5 * 60 * 1000);
const clock = () => { $('#wm-clock').textContent = simNow().toLocaleTimeString('en-IN', { ...IST, hour: '2-digit', minute: '2-digit', hour12: false }) + ' IST' + (SIM ? ' (preview)' : ''); };
clock(); setInterval(clock, 20000);
{ const d = uiDark(); const b = $('#theme-toggle'); b.innerHTML = icon(d ? 'sun' : 'moon'); b.setAttribute('aria-pressed', d); b.title = b.ariaLabel = d ? 'Light mode' : 'Dark mode'; }
