/* Coal Tracker: reads ../data/coal/coal.json (scripts/export_coal.py, refreshed after every collection pass)
   and draws the headline cards, the national stock and flow charts, the supply-chain map, the monthly
   supply series and a table of every coal power station. Charts are plain SVG with a hover layer. */
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const icon = (n, c = '') => `<svg class="i ${c}" aria-hidden="true"><use href="../icons.svg?v=2#${n}"/></svg>`;
const fmt = (v, d = 0) => v == null || Number.isNaN(v) ? '–' : Number(v).toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
const DAY = 864e5;
const tOf = d => Date.parse(`${d}T00:00:00Z`);
const dstr = t => new Date(t).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const mstr = t => new Date(t).toLocaleDateString('en-GB', { month: 'short', year: 'numeric', timeZone: 'UTC' });
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

/* ------------------------------------------------------------------ theme */
function setTheme(dark) {
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  try { localStorage.setItem('pw-theme', dark ? 'dark' : 'light'); } catch { /* private mode */ }
  const b = $('#theme');
  b.setAttribute('aria-pressed', dark);
  b.title = b.ariaLabel = dark ? 'Light mode' : 'Dark mode';
  b.innerHTML = icon(dark ? 'sun' : 'moon');
  document.querySelector('meta[name=theme-color]')?.setAttribute('content', dark ? '#0b0d14' : '#f4f1ea');
}
setTheme(document.documentElement.dataset.theme === 'dark');
$('#theme').onclick = () => { setTheme(document.documentElement.dataset.theme !== 'dark'); redraw(); };

const D = await fetch('../data/coal/coal.json', { cache: 'no-cache' }).then(r => r.json());

/* ------------------------------------------------------------ national series */
const NC = D.national.cols, idx = Object.fromEntries(NC.map((c, i) => [c, i]));
const NAT = D.national.rows.map(r => ({ t: tOf(r[0]), d: r[0], n: r[idx.plants], stock: r[idx.stock_mt], imp: r[idx.import_stock_mt],
  rcpt: r[idx.receipt_kt], cons: r[idx.consumption_kt], req: r[idx.requirement_kt], norm: r[idx.normative_mt], crit: r[idx.critical], cap: r[idx.cap_mw], dq: r[idx.days_req] }));
// 7-day means of receipt and burn (days on either side of gaps are simply what's there)
NAT.forEach((p, i) => {
  // 7-day means of receipt and burn over the days that report them (before Dec 2021 CEA's report has neither)
  const w = NAT.slice(Math.max(0, i - 6), i + 1).filter(q => p.t - q.t < 7 * DAY);
  const mean = k => { const v = w.map(q => q[k]).filter(x => x != null && x > 0); return v.length ? v.reduce((a, x) => a + x, 0) / v.length : null; };
  p.c7 = mean('cons');
  p.r7 = mean('rcpt');
  p.days = p.c7 ? p.stock * 1000 / p.c7 : null;
  p.dreq = p.dq ?? (p.req ? p.stock * 1000 / p.req : null);   // days at CEA's daily requirement: comparable across the whole record
});
const last = NAT.at(-1);
const near = (t, tol = 4 * DAY) => { let b = null; for (const p of NAT) if (Math.abs(p.t - t) <= tol && (!b || Math.abs(p.t - t) < Math.abs(b.t - t))) b = p; return b; };
const ly = last && near(last.t - 365 * DAY);
const ago30 = last && near(last.t - 30 * DAY);
const peak = NAT.reduce((a, p) => (!a || p.stock > a.stock ? p : a), null);
const lowSince = last && [...NAT].reverse().find(p => p.t < last.t - 20 * DAY && p.stock <= last.stock);   // last time it was this low
const lowSinceD = last?.dreq && [...NAT].reverse().find(p => p.t < last.t - 20 * DAY && p.dreq != null && p.dreq <= last.dreq);
const yearPeak = last && NAT.filter(p => p.t > last.t - 365 * DAY).reduce((a, p) => (!a || p.stock > a.stock ? p : a), null);
// CEA widened the daily report on 14 Nov 2021 (no-linkage, coal-block and imported-coal plants): a step in the totals, not in stocks
const BREAKS = [{ t: tOf('2021-11-14'), label: 'Report widened' }];

/* ------------------------------------------------------------ supply series */
const SUP = D.supply?.series || {}, UNITS = D.supply?.units || {}, SMETA = D.supply?.meta || {};
const ser = k => (SUP[k] || []).map(([p, v]) => ({ t: tOf(p.length === 7 ? `${p}-01` : p), p, v })).filter(x => x.v != null);
const lastOf = k => ser(k).at(-1);
const yoy = k => { const s = ser(k), l = s.at(-1); if (!l) return null; const o = s.find(x => Math.abs(x.t - (l.t - 365 * DAY)) < 16 * DAY); return o && o.v ? (l.v / o.v - 1) : null; };
const FY = D.fy || {};
const mRange = m => m ? `${new Date(tOf(`${m[0]}-01`)).toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })}–${mstr(tOf(`${m[1]}-01`))}` : '';

/* ------------------------------------------------------------- hero + alert */
function lede() {
  if (!last) return;
  const drop = ago30 ? (1 - last.stock / ago30.stock) : null;
  const net = last.r7 - last.c7;
  $('#lede').innerHTML = `On ${dstr(last.t)} India's coal power stations held <b>${fmt(last.stock, 1)} million tonnes</b> of coal, about <b>${fmt(last.days, 0)} days</b> at the current burn of ${fmt(last.c7 / 1000, 2)} Mt a day`
    + (last.dreq ? ` and ${fmt(last.dreq, 1)} days of what they need at full load${lowSinceD ? `, the least since <b>${dstr(lowSinceD.t)}</b>` : ', the least in a record that goes back to 2017'}.` : '.')
    + (drop != null ? ` That is <b>${drop > 0 ? 'down' : 'up'} ${fmt(Math.abs(drop) * 100, 0)}%</b> in 30 days` : '')
    + (ly ? ` and ${last.stock < ly.stock ? `<b>${fmt((1 - last.stock / ly.stock) * 100, 0)}% below</b>` : `${fmt((last.stock / ly.stock - 1) * 100, 0)}% above`} the same day last year.` : '.')
    + ` <b>${fmt(last.crit)}</b> of ${fmt(last.n)} stations are critical (under a quarter of the stock they are supposed to keep).`
    + (net < 0 ? ` Stations burn ${fmt(-net, 0)} thousand tonnes a day more than arrives.` : '');
  const bad = last.crit >= 50 || (drop != null && drop > 0.15) || last.days < 10;
  if (bad) {
    const a = $('#alert');
    a.hidden = false;
    a.innerHTML = `${icon('alert')}<p><b>Coal stocks are falling fast.</b> ${lowSince ? `In tonnes, stock at power stations is the lowest since ${dstr(lowSince.t)}` : `In tonnes, stock at power stations is the lowest in the record (since ${dstr(NAT[0].t)})`}${lowSinceD ? `; measured against what the stations need each day, the lowest since ${dstr(lowSinceD.t)}, during the 2021 shortage` : ''}.
      ${yearPeak ? ` It stood at ${fmt(yearPeak.stock, 1)} Mt on ${dstr(yearPeak.t)}.` : ''} ${fmt(last.crit)} stations are critical, up from ${fmt(ago30?.crit ?? NAT[0].crit)} a month earlier.</p>`;
  }
}

/* --------------------------------------------------------------- giant cards */
const spark = (vals, color, w = 240, h = 44) => {
  const v = vals.filter(x => x != null);
  if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), n = vals.length;
  const pts = vals.map((x, i) => x == null ? null : `${(i / (n - 1) * w).toFixed(1)},${(h - 3 - (x - lo) / ((hi - lo) || 1) * (h - 6)).toFixed(1)}`).filter(Boolean);
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px" aria-hidden="true"><polyline fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" points="${pts.join(' ')}"/></svg>`;
};
function giants() {
  const pm = lastOf('production'), P = FY.prod, Dp = FY.dispatch;
  $('#g-prod').innerHTML = `<h3><span class="sw" style="--c:#9a5b00">${icon('mine')}</span>Production</h3>`
    + (P?.ytd ? `<div class="big">${fmt(P.ytd, 0)}<small>Mt since 1 April</small></div>
        <p class="sub">All mines, to ${dstr(tOf(P.ytd_date))}. ${P.yoy != null ? `${mRange(P.months)}: <b>${P.yoy < 0 ? 'down' : 'up'} ${fmt(Math.abs(P.yoy) * 100, 1)}%</b> on last year` : ''}${Dp?.yoy != null ? `, while dispatch was <b>${Dp.yoy < 0 ? 'down' : 'up'} ${fmt(Math.abs(Dp.yoy) * 100, 1)}%</b>${Dp.yoy > 0 && P.yoy < Dp.yoy ? ', drawn from stocks at the mines' : ''}` : ''}.${pm ? ` ${mstr(pm.t)}: ${fmt(pm.v, 1)} Mt.` : ''}</p>`
      : pm ? `<div class="big">${fmt(pm.v, 1)}<small>Mt in ${mstr(pm.t)}</small></div>` : '<div class="big">–</div>')
    + `<div class="spark">${spark(ser('production').slice(-24).map(x => x.v), css('--mine'))}</div>`;
  $('#g-cons').innerHTML = `<h3><span class="sw" style="--c:#e34948">${icon('smoke')}</span>Burnt at power stations</h3>
    <div class="big">${fmt(last.c7 / 1000, 2)}<small>Mt a day</small></div>
    <p class="sub">7-day average across ${fmt(last.n)} stations (${fmt(last.cap / 1000, 0)} GW). Arriving: <b>${fmt(last.r7 / 1000, 2)} Mt a day</b>, so the yards ${last.r7 < last.c7 ? `lose <b>${fmt(last.c7 - last.r7, 0)} kt</b>` : `gain <b>${fmt(last.r7 - last.c7, 0)} kt</b>`} a day.</p>
    <div class="spark">${spark(NAT.slice(-120).map(p => p.c7), css('--cons'))}</div>`;
  const stockBad = last.days < 12 || last.crit >= 50;
  $('#g-stock').classList.toggle('bad', stockBad);
  $('#g-stock').innerHTML = `<h3><span class="sw" style="--c:#1f5fae">${icon('coal')}</span>Stock at power stations</h3>
    <div class="big">${fmt(last.stock, 1)}<small>Mt · ${fmt(last.days, 0)} days</small></div>
    <p class="sub"><b>${fmt(last.stock / last.norm * 100, 0)}%</b> of the ${fmt(last.norm, 1)} Mt they are meant to hold. ${ly ? `A year ago: <b>${fmt(ly.stock, 1)} Mt</b>.` : ''} Imported coal: ${fmt(last.imp, 1)} Mt.</p>
    <div class="spark">${spark(NAT.slice(-365).map(p => p.stock), css('--stock'))}</div>`;
  const R = D.reserves || {}, hc = (R.history?.coal || []).at(-1);
  $('#g-res').innerHTML = `<h3><span class="sw" style="--c:#6b7385">${icon('places')}</span>Reserves in the ground</h3>
    <div class="big">${fmt(R.total?.coal_bt ?? hc?.[4], 0)}<small>billion t of coal</small></div>
    <p class="sub">Geological resources (GSI, 1 April ${hc?.[0] || ''}); <b>${fmt(hc?.[1], 0)} bn t</b> of it measured. Lignite: ${fmt(R.total?.lignite_bt, 1)} bn t. ${ser('production').length >= 12 ? `India mined ${fmt(ser('production').slice(-12).reduce((a, x) => a + x.v, 0) / 1000, 2)} bn t in the last 12 months.` : ''}</p>
    <div class="spark">${spark((R.history?.coal || []).map(r => r[4]), css('--text-2'))}</div>`;
}

/* ---------------------------------------------------------------- rate cards */
function rates() {
  const fyDays = (() => { const n = new Date(); return Math.max(1, (Date.now() - Date.UTC(n.getUTCMonth() >= 3 ? n.getUTCFullYear() : n.getUTCFullYear() - 1, 3, 1)) / DAY); })();
  const pct = v => v == null ? '' : `<span class="${v < 0 ? 'dn' : 'up'}">${v < 0 ? '▼' : '▲'} ${fmt(Math.abs(v) * 100, 1)}%</span> on last year`;
  const card = (ic, h, v, unit, p) => `<div class="rate${v === '–' ? ' na' : ''}"><h4>${icon(ic)}${h}</h4><div class="v">${v}<small> ${unit}</small></div><p>${p}</p></div>`;
  const out = [];
  // daily series: last 7 days' mean against the same 7 days a year earlier
  const week = k => { const s = ser(k); if (!s.length) return null; const e = s.at(-1).t, cur = s.filter(x => x.t > e - 7 * DAY), old = s.filter(x => x.t > e - 372 * DAY && x.t <= e - 365 * DAY);
    const m = a => a.reduce((q, x) => q + x.v, 0) / a.length; return { v: m(cur), t: e, ly: old.length >= 4 ? m(old) : null }; };
  const wk = w => w?.ly ? ` · ${pct(w.v / w.ly - 1)}` : '';
  const dp = week('production_daily'), dd = week('dispatch_daily');
  out.push(dp ? card('mine', 'Mined per day', fmt(dp.v, 2), 'Mt', `CIL + Singareni, 7 days to ${dstr(dp.t)}${wk(dp)}`)
    : card('mine', 'Mined per day', FY.prod?.ytd ? fmt(FY.prod.ytd / fyDays, 2) : '–', 'Mt', FY.prod?.ytd ? `average since 1 April` : 'no data yet'));
  out.push(dd ? card('train', 'Dispatched per day', fmt(dd.v, 2), 'Mt', `CIL + Singareni, 7 days to ${dstr(dd.t)}${wk(dd)}`)
    : card('train', 'Dispatched per day', FY.dispatch?.ytd ? fmt(FY.dispatch.ytd / fyDays, 2) : '–', 'Mt', FY.dispatch?.ytd ? `since 1 April` : 'no data yet'));
  const imk = lastOf('imports') ? 'imports' : 'import_power', im = lastOf(imk);
  out.push(card('ship', imk === 'imports' ? 'Coal imports' : 'Imports to power', im ? fmt(im.v, 1) : '–', im ? `Mt in ${mstr(im.t)}` : 'Mt', im ? pct(yoy(imk)) : 'monthly figures not yet in'));
  const rk = week('rakes');
  out.push(card('train', 'Coal trains a day', rk ? fmt(rk.v, 0) : '–', 'rakes', rk ? `Coal India, 7 days to ${dstr(rk.t)}${wk(rk)}` : 'rake loading not yet in'));
  const net = last.r7 - last.c7;
  out.push(card('chart', 'Net change in stock', `${net < 0 ? '−' : '+'}${fmt(Math.abs(net), 0)}`, 'kt a day', `receipts minus burn, 7-day average`));
  out.push(card('alert', 'Critical stations', fmt(last.crit), `of ${fmt(last.n)}`, ago30 ? `${last.crit - ago30.crit >= 0 ? '+' : ''}${fmt(last.crit - ago30.crit)} in 30 days` : 'under 25% of normative stock'));
  const low = D.plants.filter(p => p.pct != null && p.pct < 50 && p.req > 0).length;
  out.push(card('coal', 'Under half their stock', fmt(low), 'stations', 'below 50% of the normative stock'));
  const ph = lastOf('pithead_stock');
  out.push(ph ? card('mine', 'Stock at the mines', fmt(ph.v, 1), 'Mt', `pithead, ${ph.p.length > 7 ? dstr(ph.t) : mstr(ph.t)} · ${pct(yoy('pithead_stock'))}`)
    : card('ship', 'Imported coal in yards', fmt(last.imp, 2), 'Mt', `${fmt(last.imp / last.stock * 100, 0)}% of the stock at power stations`));
  $('#rates').innerHTML = out.join('');
}

/* ------------------------------------------------------------------- charts */
const tip = $('#tip');
function showTip(e, html) {
  tip.innerHTML = html; tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.left = `${Math.max(8, x)}px`; tip.style.top = `${Math.max(8, y)}px`;
}
const hideTip = () => { tip.hidden = true; };
function niceTicks(lo, hi, n = 4) {
  const span = hi - lo || 1, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => span / s <= n) || mag * 10;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}
function timeTicks(t0, t1, w) {
  const span = (t1 - t0) / DAY, out = [];
  const monthsStep = span > 1500 ? 12 : span > 700 ? 6 : span > 250 ? 3 : span > 100 ? 1 : 0;
  if (!monthsStep) { for (let t = t0; t <= t1; t += Math.ceil(span / Math.max(2, w / 90)) * DAY) out.push([t, dstr(t).replace(/ \d{4}$/, '')]); return out; }
  const d = new Date(t0); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1);
  while (d.getTime() <= t1) {
    if (d.getUTCMonth() % monthsStep === 0) out.push([d.getTime(), monthsStep >= 12 ? `${d.getUTCFullYear()}` : d.toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' }) + (d.getUTCMonth() === 0 || monthsStep >= 6 ? ` ${d.getUTCFullYear()}` : '')]);
    d.setUTCMonth(d.getUTCMonth() + 1);
  }
  return out;
}
/* series: [{name, color, pts:[{t,v}], dash, bars}], opts: {unit, fmtV, y0, h, gap} */
function chart(el, series, o = {}) {
  const W = Math.max(280, el.clientWidth), H = o.h || (W < 520 ? 220 : 280), m = { l: 8, r: 52, t: 14, b: 26 };
  const all = series.flatMap(s => s.pts), ts = all.map(p => p.t);
  if (!all.length) { el.innerHTML = '<p class="note">No data yet.</p>'; return; }
  const t0 = o.t0 ?? Math.min(...ts), t1 = o.t1 ?? Math.max(...ts);
  const vals = all.filter(p => p.t >= t0 && p.t <= t1).map(p => p.v);
  let lo = o.y0 ?? Math.min(0, ...vals), hi = Math.max(...vals) * 1.06;
  const ticks = niceTicks(lo, hi); hi = Math.max(hi, ticks.at(-1)); lo = Math.min(lo, ticks[0]);
  const X = t => m.l + (t - t0) / ((t1 - t0) || 1) * (W - m.l - m.r), Y = v => H - m.b - (v - lo) / ((hi - lo) || 1) * (H - m.t - m.b);
  const f = o.fmtV || (v => fmt(v, 1));
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || series.map(x => x.name).join(', '))}"><g class="ax">`;
  for (const v of ticks) s += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" class="${v === 0 ? 'base' : ''}"/><text x="${W - m.r + 6}" y="${Y(v) + 4}">${f(v)}</text>`;
  for (const [t, l] of timeTicks(t0, t1, W)) s += `<text x="${X(t)}" y="${H - 6}" text-anchor="middle">${l}</text>`;
  s += '</g>';
  const gap = o.gap ?? 10 * DAY;
  for (const se of series) {
    const pts = se.pts.filter(p => p.t >= t0 - gap && p.t <= t1 + gap);
    if (se.bars) {
      const bw = Math.max(1, (W - m.l - m.r) / Math.max(1, (t1 - t0) / (se.step || DAY)) - 1.5);
      for (const p of pts) if (p.t >= t0 && p.t <= t1) s += `<rect x="${X(p.t) - bw / 2}" y="${Math.min(Y(p.v), Y(0))}" width="${bw}" height="${Math.abs(Y(p.v) - Y(0))}" fill="${se.color}" rx="${bw > 6 ? 2 : 0}"/>`;
      continue;
    }
    let d = '', prev = null;
    for (const p of pts) { d += `${!prev || p.t - prev.t > gap ? 'M' : 'L'}${X(p.t).toFixed(1)},${Y(p.v).toFixed(1)}`; prev = p; }
    s += `<path d="${d}" fill="none" stroke="${se.color}" stroke-width="${se.w || 2}" ${se.dash ? 'stroke-dasharray="5 4"' : ''} stroke-linejoin="round" stroke-linecap="round"/>`;
    const lp = pts.filter(p => p.t <= t1).at(-1);
    if (lp && se.label !== false) s += `<circle cx="${X(lp.t)}" cy="${Y(lp.v)}" r="3.5" fill="${se.color}" stroke="${css('--panel')}" stroke-width="2"/>`;
  }
  for (const mk of o.marks || []) if (mk.t > t0 && mk.t < t1) s += `<line x1="${X(mk.t)}" x2="${X(mk.t)}" y1="${m.t}" y2="${H - m.b}" stroke="${css('--text-3')}" stroke-dasharray="2 3"/><text x="${X(mk.t) + 4}" y="${m.t + 10}" style="font-size:11px;fill:var(--text-3)">${esc(mk.label)}</text>`;
  s += `<line class="hair" y1="${m.t}" y2="${H - m.b}" x1="-10" x2="-10"/><rect class="hit" x="${m.l}" y="${m.t}" width="${W - m.l - m.r}" height="${H - m.t - m.b}"/></svg>`;
  el.innerHTML = (o.key ? `<div class="key">${series.filter(x => x.name).map(x => `<span><i class="${x.bars ? 'bar' : ''} ${x.dash ? 'dash' : ''}" style="--c:${x.color}"></i>${esc(x.name)}</span>`).join('')}</div>` : '') + s;
  const svg = el.querySelector('svg'), hair = svg.querySelector('.hair'), hit = svg.querySelector('.hit');
  const move = e => {
    const r = svg.getBoundingClientRect(), x = (e.clientX - r.left) * W / r.width, t = t0 + (x - m.l) / (W - m.l - m.r) * (t1 - t0);
    const rows = series.filter(x => x.name).map(se => { let b = null; for (const p of se.pts) if (!b || Math.abs(p.t - t) < Math.abs(b.t - t)) b = p; return [se, b]; }).filter(([, b]) => b && Math.abs(b.t - t) < (o.snap || 20 * DAY));
    if (!rows.length) return hideTip();
    const tt = rows[0][1].t;
    hair.setAttribute('x1', X(tt)); hair.setAttribute('x2', X(tt));
    showTip(e, `<b>${o.monthly ? mstr(tt) : dstr(tt)}</b>` + rows.map(([se, b]) => `<div class="r"><span><i style="--c:${se.color}"></i>${esc(se.name)}</span><b>${f(b.v)}${o.unit ? ` ${o.unit}` : ''}</b></div>`).join('') + (o.extra ? o.extra(tt) : ''));
  };
  hit.addEventListener('pointermove', move);
  hit.addEventListener('pointerleave', () => { hideTip(); hair.setAttribute('x1', -10); hair.setAttribute('x2', -10); });
}

let RANGE = 365, MEASURE = 'mt';
function stockCharts() {
  const t1 = last.t, t0 = RANGE ? Math.max(NAT[0].t, t1 - RANGE * DAY) : NAT[0].t;
  const days = MEASURE === 'days', val = p => days ? p.dreq : p.stock;
  const pts = NAT.filter(p => val(p) != null).map(p => ({ t: p.t, v: val(p) }));
  const lyPts = pts.map(p => ({ t: p.t + 365 * DAY, v: p.v })).filter(p => p.t <= t1);
  const el = $('#c-stock');
  const ranges = [[90, '3 months'], [365, '1 year'], [1826, '5 years'], [0, 'Everything']];
  chart(el, [{ name: days ? 'Days of coal at the daily requirement' : 'Stock at power stations', color: css('--stock'), pts, w: 2 },
             { name: 'Same day a year earlier', color: css('--stock-ly'), pts: lyPts, dash: true, label: false }],
        { t0, t1, unit: days ? 'days' : 'Mt', key: true, y0: 0, fmtV: v => fmt(v, days ? 0 : 1), marks: BREAKS,
          label: days ? 'Days of coal at India\'s power stations' : 'Coal stock at India\'s power stations, million tonnes',
          extra: t => { const p = near(t, 1 * DAY); return p ? `<div class="r"><span>${days ? 'Stock' : 'Days at requirement'}</span><b>${days ? `${fmt(p.stock, 1)} Mt` : fmt(p.dreq, 0)}</b></div>${p.days ? `<div class="r"><span>Days at the week's burn</span><b>${fmt(p.days, 0)}</b></div>` : ''}<div class="r"><span>Critical stations</span><b>${fmt(p.crit)}</b></div>` : ''; } });
  let bar = document.querySelector('#stock-ranges');
  if (!bar) { bar = document.createElement('div'); bar.className = 'ranges'; bar.id = 'stock-ranges'; el.before(bar); }
  bar.innerHTML = ranges.map(([d, l]) => `<button type="button" data-d="${d}" aria-pressed="${d === RANGE}">${l}</button>`).join('')
    + `<span style="flex:1"></span>` + [['mt', 'Million tonnes'], ['days', 'Days of coal']].map(([k, l]) => `<button type="button" data-m="${k}" aria-pressed="${k === MEASURE}">${l}</button>`).join('');
  bar.onclick = e => { const b = e.target.closest('button'); if (!b) return; if (b.dataset.m) MEASURE = b.dataset.m; else RANGE = +b.dataset.d; stockCharts(); flowChart(); };
  chart($('#c-crit'), [{ name: 'Critical stations', color: css('--crit'), pts: NAT.map(p => ({ t: p.t, v: p.crit })), bars: true }],
        { t0, t1, h: 130, fmtV: v => fmt(v), key: true, label: 'Number of stations with critical coal stock' });
  $('#stock-note').innerHTML = `Total coal at the stations in CEA's daily coal report (${fmt(last.n)} today), ${dstr(NAT[0].t)} to ${dstr(last.t)}. <b>Days of coal</b> divides the stock by what the stations need a day at 85% load, CEA's own yardstick, so it compares across the whole record. The dashed line is the same day a year earlier. On 14 November 2021 CEA added about 27 plants to the report (no-linkage, coal-block and imported-coal stations), so totals step up there. Below: how many stations are <b>critical</b> (under 25% of normative stock; before the December 2021 norms, CEA flagged stations with under 7 days, or 4 at pithead).`;
}
function flowChart() {
  const t1 = last.t, t0 = RANGE ? Math.max(NAT[0].t, t1 - RANGE * DAY) : NAT[0].t;
  chart($('#c-flow'), [{ name: 'Arriving (7-day average)', color: css('--rcpt'), pts: NAT.filter(p => p.r7).map(p => ({ t: p.t, v: p.r7 / 1000 })) },
                       { name: 'Burnt (7-day average)', color: css('--cons'), pts: NAT.filter(p => p.c7).map(p => ({ t: p.t, v: p.c7 / 1000 })) },
                       { name: 'Needed at 85% load', color: css('--stock-ly'), pts: NAT.map(p => ({ t: p.t, v: p.req / 1000 })), dash: true, label: false }],
        { t0, t1, unit: 'Mt/day', key: true, fmtV: v => fmt(v, 2), label: 'Coal received and consumed per day at power stations, million tonnes' });
  const net = NAT.filter(p => p.t >= t0 && p.rcpt != null && p.cons != null).reduce((a, p) => a + (p.rcpt - p.cons), 0);
  $('#flow-note').innerHTML = `Coal reaching the stations and coal burnt, each day, in million tonnes. When the purple line runs under the red one, the yards are emptying. Over this period arrivals fell short of burn by <b>${fmt(-net / 1000, 1)} Mt</b> in the days reported.`;
}

/* ---------------------------------------------------------- monthly supply */
// panels: [title, icon, [[series key, colour var, name?], ...]]; the first series is the headline one, a dashed
// grey line repeats it a year earlier; daily series are drawn as 7-day averages
const SUPPLY = [
  ['At the mines', [
    ['Coal mined per day', 'mine', [['production_daily', '--mine']]],
    ['Coal dispatched per day', 'train', [['dispatch_daily', '--rail']]],
    ['Coal production, all India', 'mine', [['production', '--mine']]],
    ['Coal dispatched, all India and to power', 'train', [['offtake', '--rail', 'All uses'], ['dispatch_power', '--coal', 'To power stations']]],
  ]],
  ['On the move', [
    ['Coal trains loaded per day', 'train', [['rakes', '--rail']]],
    ['Coal trains to power stations', 'train', [['rakes_power', '--rail']]],
    ['Thermal coal through the ports', 'ship', [['port_coal', '--sea']]],
  ]],
  ['Imports', [
    ['Coal imports', 'ship', [['imports', '--imp', 'All coal'], ['imports_thermal', '--sea', 'Steam coal']]],
    ['Imported coal received by power stations', 'ship', [['import_power', '--imp']]],
  ]],
  ['At the power stations, month by month', [
    ['Coal received and burnt', 'coal', [['cea_rcpt', '--rcpt', 'Received'], ['cea_cons', '--cons', 'Burnt']]],
    ['Coal in the yards at month end', 'coal', [['cea_stock', '--stock']]],
  ]],
  ['The other fuels', [
    ['Natural gas burnt for power', 'gas', [['gas_power', '--low']]],
    ['Water in the reservoirs', 'hydro', [['hydro_storage', '--stock', 'This year'], ['hydro_normal', '--stock-ly', '10-year normal']]],
  ]],
];
const avg7 = pts => pts.map((p, i) => { const w = pts.slice(Math.max(0, i - 6), i + 1).filter(q => p.t - q.t < 7 * DAY); return { t: p.t, v: w.reduce((a, q) => a + q.v, 0) / w.length }; });
function supplyCharts() {
  const groups = SUPPLY.map(([g, panels]) => [g, panels.filter(([, , ss]) => ser(ss[0][0]).length > 1)]).filter(([, ps]) => ps.length);
  if (!groups.length) {
    $('#supply-note').innerHTML = 'Production, dispatch, imports and rail figures are being collected; they appear here as they come in.';
    $('#supply').innerHTML = '';
    return;
  }
  $('#supply-note').innerHTML = 'Each chart has its own scale; the dashed grey line is the same series a year earlier. Daily figures are 7-day averages; monthly ones sit at the start of their month.';
  let h = '', n = 0;
  for (const [g, ps] of groups) {
    h += `<h3 class="grp">${esc(g)}</h3>`;
    for (const [t, ic, ss] of ps) {
      const k = ss[0][0], m = SMETA[k] || {};
      h += `<div class="m"><h3>${icon(ic, 'sm')} ${esc(t)}</h3><p>${esc(UNITS[k] || '')}${m.source ? ` · ${esc(m.source)}` : ''}${m.note ? ` · ${esc(m.note)}` : ''}</p><div class="chart" id="s-${n++}"></div></div>`;
    }
  }
  $('#supply').innerHTML = h;
  n = 0;
  for (const [, ps] of groups) for (const [t, , ss] of ps) {
    const lines = [];
    ss.forEach(([k, c, name], i) => {
      let pts = ser(k);
      if (!pts.length) return;
      const daily = pts[0].p.length > 7;
      if (daily) pts = avg7(pts);
      lines.push({ name: name || t, color: css(c), pts, daily });
      if (i === 0 && ss.length === 1) lines.push({ name: 'A year earlier', color: css('--stock-ly'), pts: pts.map(p => ({ t: p.t + 365 * DAY, v: p.v })).filter(p => p.t <= pts.at(-1).t), dash: true, label: false });
    });
    const daily = lines[0].daily, k0 = ss[0][0];
    chart($(`#s-${n++}`), lines, { h: 180, unit: UNITS[k0] || '', key: ss.length > 1, monthly: !daily, gap: daily ? 10 * DAY : 45 * DAY, snap: daily ? 3 * DAY : 20 * DAY,
      fmtV: v => fmt(v, Math.abs(v) < 10 ? 2 : Math.abs(v) < 100 ? 1 : 0) });
  }
}

/* ------------------------------------------------------------------ reserves */
function reserveCharts() {
  const R = D.reserves || {};
  const rows = Object.entries(R.coal || {}).map(([k, v]) => [k, v]).filter(([, v]) => v[3] > 0.5).sort((a, b) => b[1][3] - a[1][3]);
  const el = $('#c-res'), W = Math.max(280, el.clientWidth), rh = 26, H = rows.length * rh + 30, lw = Math.min(150, W * 0.36), mx = rows[0]?.[1][3] || 1;
  const cols = [css('--text'), css('--text-2'), css('--stock-ly')];
  let s = `<div class="key"><span><i class="bar" style="--c:${cols[0]}"></i>Measured</span><span><i class="bar" style="--c:${cols[1]}"></i>Indicated</span><span><i class="bar" style="--c:${cols[2]}"></i>Inferred</span></div><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Coal resources by state, billion tonnes">`;
  rows.forEach(([k, v], i) => {
    const y = i * rh + 4; let x = lw;
    s += `<text class="lbl" x="${lw - 8}" y="${y + 15}" text-anchor="end">${esc(k)}</text>`;
    v.slice(0, 3).forEach((q, j) => { const w = q / mx * (W - lw - 60); if (w > 0.5) s += `<rect x="${x}" y="${y + 3}" width="${Math.max(0, w - 1.5)}" height="16" fill="${cols[j]}"/>`; x += w; });
    s += `<text x="${x + 6}" y="${y + 15}" style="font-size:12px;fill:var(--text-2)">${fmt(v[3], 1)}</text>`;
  });
  el.innerHTML = s + '</svg>';
  const h = (R.history?.coal || []).map(r => ({ t: tOf(`${r[0]}-04-01`), v: r[4] }));
  chart($('#c-res-hist'), [{ name: 'Coal resources, billion t', color: css('--text'), pts: h, w: 2.5 }], { h: 220, fmtV: v => fmt(v, 0), unit: 'bn t', snap: 200 * DAY, gap: 400 * DAY, key: true });
  $('#res-note').innerHTML = `Geological coal resources by state (Geological Survey of India's National Coal Inventory, as published by the Ministry of Coal), in billion tonnes. <b>Measured</b> resources are the best-proven. Right: the national total each 1 April; exploration adds more each year than is mined. Resources are not all mineable reserves.`;
}

/* ----------------------------------------------------------------------- map */
const status = p => p.req > 0 && p.pct != null ? (p.crit ? 'crit' : p.pct < 50 ? 'low' : 'ok') : 'na';
const STATUS = { crit: ['Critical, under 25%', '--crit'], low: ['Under 50% of normative', '--low'], ok: ['50% or more', '--ok'], na: ['Not running / no data', '--text-3'] };
let map;
// the site's 16×16 pixel icons as map images: an icon on a white tile with a coloured frame, like the poster nodes
async function pixelImages(m) {
  const doc = new DOMParser().parseFromString(await fetch('../icons.svg?v=2').then(r => r.text()), 'image/svg+xml');
  const make = (id, col) => new Promise(res => {
    const sym = doc.getElementById(id), s = 22, r = 2;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${s * r}" height="${s * r}" viewBox="0 0 22 22" shape-rendering="crispEdges">
      <rect x="1" y="1" width="20" height="20" fill="#ffffff" stroke="${col}" stroke-width="2"/><g transform="translate(3 3)" fill="${col}">${sym.innerHTML}</g></svg>`;
    const img = new Image(s * r, s * r);
    img.onload = () => { m.addImage(`px-${id}`, img, { pixelRatio: r }); res(); };
    img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  });
  await Promise.all([make('mine', '#8a5200'), make('ship', '#1f6fb5')]);
}
function drawMap() {
  const M = D.map;
  const fc = f => ({ type: 'FeatureCollection', features: f });
  const plantsFC = fc(D.plants.filter(p => p.lat != null).map(p => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
    properties: { k: 'plant', n: p.n, s: status(p), cap: p.cap || 0, days: p.days, pct: p.pct, stock: p.stock, st: p.st, co: (p.co || []).join(', '), rmk: p.rmk || '', c7: p.c7, r7: p.r7, u: p.u, mode: p.mode } })));
  const minesFC = fc(M.mines.map(m => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [m.lon, m.lat] }, properties: { k: 'mine', n: m.name, kind: m.kind, co: m.co || '', st: m.st || '', prod: m.prod, cap: m.cap } })));
  const portsFC = fc([...M.ports.map(p => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] }, properties: { k: 'port', n: p.name, kind: p.kind, role: (p.role || []).join('; ') } })),
    ...(M.gem_terminals || []).map(t => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [t.lon, t.lat] }, properties: { k: 'port', n: t.name, kind: 'terminal',
      role: [t.port, t.owner, t.cap ? `${fmt(t.cap)} Mt a year` : '', t.status !== 'operating' ? t.status : ''].filter(Boolean).join(' · ') } }))]);
  const gemFC = fc((M.gem_mines || []).map(m => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [m.lon, m.lat] },
    properties: { k: 'gem', n: m.name, owner: m.owner, status: m.status, type: m.type || '', cf: m.cf || '', st: m.st || '', cap: m.cap, prod: m.prod ?? 0, py: m.py, url: m.url || '' } })));
  const routesFC = fc(M.routes.map(r => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: r.c }, properties: { k: 'route', mode: r.mode, cargo: r.cargo || '', from: r.from || '', to: r.to || '', km: r.km || null, derived: !!r.derived } })));
  const dark = () => document.documentElement.dataset.theme === 'dark';
  Promise.all([fetch('../data/basemap/positron.json').then(r => r.json()), fetch('../data/basemap/dark-matter.json').then(r => r.json())]).then(([pos, dm]) => {
    map = new maplibregl.Map({ container: 'map', style: { version: 8, glyphs: 'https://tiles.basemaps.cartocdn.com/fonts/{fontstack}/{range}.pbf', sources: {}, layers: [] },
      bounds: [[67.5, 7], [97.5, 33.5]], fitBoundsOptions: { padding: 10 }, attributionControl: false, cooperativeGestures: true, maxBounds: [[40, -15], [130, 45]] });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new maplibregl.AttributionControl({ compact: true, customAttribution: 'CEA · Ministry of Coal · OpenStreetMap' }));
    map.on('load', async () => {
      await pixelImages(map);
      map.addSource('carto', { type: 'vector', url: 'https://tiles.basemaps.cartocdn.com/vector/carto.streets/v1/tiles.json',
        attribution: '© <a href="https://carto.com/attributions">CARTO</a> © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' });
      for (const l of pos.layers) map.addLayer({ ...l, layout: { ...(l.layout || {}), visibility: dark() ? 'none' : 'visible' } });
      for (const l of dm.layers) map.addLayer({ ...l, layout: { ...(l.layout || {}), visibility: dark() ? 'visible' : 'none' } });
      map.addSource('routes', { type: 'geojson', data: routesFC });
      map.addSource('mines', { type: 'geojson', data: minesFC });
      map.addSource('gem', { type: 'geojson', data: gemFC });
      map.addSource('ports', { type: 'geojson', data: portsFC });
      map.addSource('plants', { type: 'geojson', data: plantsFC });
      map.addLayer({ id: 'routes', type: 'line', source: 'routes', paint: {
        'line-color': ['match', ['get', 'mode'], 'sea', css('--sea'), 'rail', css('--rail'), css('--text-2')],
        'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1, 8, 2.2], 'line-opacity': ['case', ['get', 'derived'], 0.45, 0.85],
        'line-dasharray': [2, 1.5] } });
      map.addLayer({ id: 'gem', type: 'circle', source: 'gem', paint: {
        'circle-color': ['case', ['==', ['get', 'status'], 'operating'], css('--mine'), 'rgba(0,0,0,0)'],
        'circle-stroke-color': css('--mine'), 'circle-stroke-width': ['case', ['==', ['get', 'status'], 'operating'], 0.8, 1.4],
        'circle-opacity': 0.8,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['+', 1.5, ['*', 0.55, ['sqrt', ['coalesce', ['get', 'prod'], 0]]]], 9, ['+', 3, ['*', 1.4, ['sqrt', ['coalesce', ['get', 'prod'], 0]]]]] } });
      const iconSize = big => ['interpolate', ['linear'], ['zoom'], 4, big, 9, big * 1.6];
      map.addLayer({ id: 'mines', type: 'symbol', source: 'mines', layout: { 'icon-image': 'px-mine', 'icon-allow-overlap': true, 'icon-ignore-placement': true,
        'icon-size': ['interpolate', ['linear'], ['zoom'], 4, ['case', ['==', ['get', 'kind'], 'coalfield'], 0.8, 0.55], 9, ['case', ['==', ['get', 'kind'], 'coalfield'], 1.3, 1]] } });
      map.addLayer({ id: 'ports', type: 'symbol', source: 'ports', layout: { 'icon-image': 'px-ship', 'icon-allow-overlap': true, 'icon-ignore-placement': true, 'icon-size': iconSize(0.6) } });
      map.addLayer({ id: 'plants', type: 'circle', source: 'plants', paint: {
        'circle-color': ['match', ['get', 's'], 'crit', css('--crit'), 'low', css('--low'), 'ok', css('--ok'), css('--text-3')],
        'circle-stroke-color': dark() ? '#05060a' : '#ffffff', 'circle-stroke-width': 1.5,
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, ['+', 2.5, ['/', ['sqrt', ['get', 'cap']], 12]], 9, ['+', 5, ['/', ['sqrt', ['get', 'cap']], 5]]] } });
      map.addLayer({ id: 'plant-names', type: 'symbol', source: 'plants', minzoom: 6.5, layout: { 'text-field': ['get', 'n'], 'text-font': ['Open Sans Regular'], 'text-size': 11,
        'text-offset': [0, 1.1], 'text-anchor': 'top', 'text-optional': true }, paint: { 'text-color': dark() ? '#f5f1e6' : '#1b1d22', 'text-halo-color': dark() ? '#05060a' : '#ffffff', 'text-halo-width': 1.4 } });
      map.addLayer({ id: 'mine-names', type: 'symbol', source: 'mines', minzoom: 6, layout: { 'text-field': ['get', 'n'], 'text-font': ['Open Sans Regular'], 'text-size': 11,
        'text-offset': [0, 1], 'text-anchor': 'top', 'text-optional': true }, paint: { 'text-color': css('--mine'), 'text-halo-color': dark() ? '#05060a' : '#ffffff', 'text-halo-width': 1.4 } });
      for (const id of ['plants', 'mines', 'gem', 'ports', 'routes']) {
        map.on('mouseenter', id, () => { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', id, () => { map.getCanvas().style.cursor = ''; });
      }
      map.on('click', e => {
        const f = map.queryRenderedFeatures([[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]], { layers: ['plants', 'ports', 'mines', 'gem', 'routes'] })[0];
        if (!f) return;
        const p = f.properties;
        let h = '';
        if (p.k === 'plant') h = `<h4>${esc(p.n)}</h4><p>${esc(p.st || '')}${p.u ? ` · ${esc(p.u)}` : ''}${p.mode ? ` · by ${esc(p.mode.toLowerCase())}` : ''}</p>
          <p><span class="pill ${p.s}">${STATUS[p.s][0]}</span></p><p>Stock <b>${fmt(p.stock, 1)} kt</b> · ${p.days != null && p.days !== 'null' ? `<b>${fmt(+p.days, 0)} days</b> at the current burn` : 'not burning'}</p>
          <p>In ${fmt(+p.r7, 1)} kt/day · burnt ${fmt(+p.c7, 1)} kt/day · ${fmt(+p.pct, 0)}% of normative</p>${p.co ? `<p>Coal from ${esc(p.co)}</p>` : ''}${p.rmk ? `<p style="color:var(--text-2)">${esc(p.rmk)}</p>` : ''}`;
        else if (p.k === 'mine') h = `<h4>${esc(p.n)}</h4><p>${esc(p.kind.replace('_', ' '))}${p.co ? ` · ${esc(p.co)}` : ''}${p.st ? ` · ${esc(p.st)}` : ''}</p>${p.prod && p.prod !== 'null' ? `<p>Produced <b>${fmt(+p.prod, 1)} Mt</b> in the last financial year</p>` : ''}`;
        else if (p.k === 'gem') h = `<h4>${esc(p.n)}</h4><p>${esc([p.owner, p.st].filter(Boolean).join(' · '))}</p><p>${esc(p.status)}${p.type ? ` · ${esc(p.type)}` : ''}${p.cf ? ` · ${esc(p.cf)} coalfield` : ''}</p>
          ${+p.prod ? `<p>Produced <b>${fmt(+p.prod, 1)} Mt</b> in ${esc(p.py)}${p.cap && p.cap !== 'null' ? ` of ${fmt(+p.cap, 1)} Mt capacity` : ''}</p>` : p.cap && p.cap !== 'null' ? `<p>Capacity ${fmt(+p.cap, 1)} Mt a year</p>` : ''}
          ${p.url ? `<p><a href="${esc(p.url)}" target="_blank" rel="noopener">GEM wiki</a></p>` : ''}`;
        else if (p.k === 'port') h = `<h4>${esc(p.n)}</h4>${p.role ? `<p>${esc(p.role)}</p>` : ''}`;
        else h = `<h4>${esc(p.from && p.to ? `${p.from} → ${p.to}` : p.cargo)}</h4><p>${esc(p.mode)}${p.km && p.km !== 'null' ? ` · about ${fmt(+p.km)} km` : ''} · ${esc(p.cargo)}</p>${p.derived === true || p.derived === 'true' ? '<p style="color:var(--text-2)">Linked from the company named in CEA\'s daily coal report; drawn straight, not the rail route.</p>' : ''}`;
        new maplibregl.Popup({ maxWidth: '300px' }).setLngLat(e.lngLat).setHTML(`<div class="pop">${h}</div>`).addTo(map);
      });
    });
    map._themes = { pos, dm };
  });
  $('#map-legend').innerHTML = Object.entries(STATUS).map(([k, [l, c]]) => `<span><i class="dot" style="--c:var(${c})"></i>${l}</span>`).join('')
    + `<span><i class="dot" style="--c:var(--mine)"></i>Mine, sized by output (hollow: proposed)</span><span><i class="sq" style="--c:#8a5200">${icon('mine')}</i>Coalfield in a supply chain</span><span><i class="sq" style="--c:#1f6fb5">${icon('ship')}</i>Port</span>`
    + `<span><i class="ln" style="--c:var(--rail)"></i>Rail</span><span><i class="ln" style="--c:var(--sea)"></i>Sea</span><span><i class="ln" style="--c:var(--text-2)"></i>Conveyor or road</span>`;
}
function mapTheme() {
  if (!map?._themes || !map.isStyleLoaded()) return;
  const dark = document.documentElement.dataset.theme === 'dark';
  for (const l of map._themes.pos.layers) map.setLayoutProperty(l.id, 'visibility', dark ? 'none' : 'visible');
  for (const l of map._themes.dm.layers) map.setLayoutProperty(l.id, 'visibility', dark ? 'visible' : 'none');
  map.setPaintProperty('plants', 'circle-stroke-color', dark ? '#05060a' : '#ffffff');
  for (const id of ['plant-names', 'mine-names']) map.setPaintProperty(id, 'text-halo-color', dark ? '#05060a' : '#ffffff');
  map.setPaintProperty('plant-names', 'text-color', dark ? '#f5f1e6' : '#1b1d22');
}

/* --------------------------------------------------------------------- table */
let SORT = { k: 'days', dir: 1 };
const HD = D.hist_dates || [];
function sparkRow(h) {
  const v = h.filter(x => x != null);
  if (v.length < 2) return '';
  const hi = Math.max(...v, 1), n = h.length, w = 110, hh = 26;
  const d = h.map((x, i) => x == null ? null : `${(i / (n - 1) * w).toFixed(1)},${(hh - 2 - x / hi * (hh - 4)).toFixed(1)}`).filter(Boolean).join(' ');
  return `<svg class="sp" viewBox="0 0 ${w} ${hh}" preserveAspectRatio="none" aria-hidden="true"><polyline fill="none" stroke="var(--stock)" stroke-width="1.6" vector-effect="non-scaling-stroke" points="${d}"/></svg>`;
}
function table() {
  const q = $('#q').value.trim().toLowerCase(), st = $('#f-state').value, fs = $('#f-status').value;
  let rows = D.plants.filter(p => (!q || `${p.n} ${p.st} ${p.u} ${(p.co || []).join(' ')} ${p.rmk || ''}`.toLowerCase().includes(q))
    && (!st || p.st === st) && (!fs || (fs === 'crit' ? p.crit : p.pct != null && p.pct < 50 && p.req > 0)));
  const k = SORT.k, dir = SORT.dir;
  rows.sort((a, b) => { const x = a[k], y = b[k]; if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1; return (typeof x === 'string' ? x.localeCompare(y) : x - y) * dir; });
  document.querySelectorAll('table.plants th').forEach(th => th.setAttribute('aria-sort', th.dataset.k === k ? (dir > 0 ? 'ascending' : 'descending') : 'none'));
  $('#plants tbody').innerHTML = rows.map(p => {
    const s = status(p), c = `var(${STATUS[s][1]})`;
    return `<tr class="${s}"><td class="nm"><b>${esc(p.n)}</b><small>${esc([p.st, p.u, p.mode && p.mode.toLowerCase(), p.co && `coal: ${p.co.join(', ')}`].filter(Boolean).join(' · '))}</small>${p.rmk ? `<small>${esc(p.rmk)}</small>` : ''}</td>
      <td class="num">${p.days != null ? `<b>${fmt(p.days, p.days < 10 ? 1 : 0)}</b>` : '–'}</td>
      <td class="num"><span class="meter" style="--c:${c}"><i style="width:${Math.min(100, p.pct || 0)}%"></i></span>${fmt(p.pct)}% ${s === 'crit' ? '<span class="pill crit">critical</span>' : ''}</td>
      <td class="num">${fmt(p.stock, 1)}</td><td class="num">${fmt(p.r7, 1)}</td><td class="num">${fmt(p.c7, 1)}</td>
      <td>${sparkRow(p.h || [])}</td><td class="num">${fmt(p.gen, 1)}</td></tr>`;
  }).join('');
  $('#table-note').innerHTML = `${fmt(rows.length)} of ${fmt(D.plants.length)} stations in CEA's daily coal report for ${dstr(tOf(D.day))}. <b>Days left</b> is the stock divided by the last 7 days' average burn. The 90-day line is each station's own stock. Tap a column to sort.`;
}
function tableSetup() {
  const states = [...new Set(D.plants.map(p => p.st).filter(Boolean))].sort();
  $('#f-state').innerHTML += states.map(s => `<option>${esc(s)}</option>`).join('');
  for (const id of ['#q', '#f-state', '#f-status']) $(id).addEventListener('input', table);
  document.querySelectorAll('table.plants th[data-k]').forEach(th => th.addEventListener('click', () => {
    SORT = { k: th.dataset.k, dir: SORT.k === th.dataset.k ? -SORT.dir : (['n'].includes(th.dataset.k) ? 1 : th.dataset.k === 'days' || th.dataset.k === 'pct' ? 1 : -1) };
    table();
  }));
}

/* ------------------------------------------------------------------- sources */
function sources() {
  const extra = Object.entries(SMETA).map(([k, m]) => m.url ? `<li>${esc(m.label || k)}: <a href="${esc(m.url)}">${esc(m.source || m.url)}</a></li>` : '').join('');
  $('#sources').innerHTML = `<h2>Sources</h2><ul>
    <li>Stock, receipt and consumption at every station: Central Electricity Authority, <a href="https://npp.gov.in/dailyCoalReports">Daily Coal Stock Report</a> (National Power Portal), every day; archived here since ${dstr(NAT[0].t)}.</li>
    <li>Generation per station: CEA Daily Generation Report (DGR2).</li>
    <li>Production and offtake this financial year, and coal and lignite resources: <a href="https://coal.gov.in/en/major-statistics/production-and-supplies">Ministry of Coal</a>; Geological Survey of India National Coal Inventory.</li>${extra}
    <li>Mine and coal-terminal locations, capacity and output: ${esc(D.map.gem_attribution || 'Global Energy Monitor, Global Coal Mine Tracker (CC BY 4.0)')}</li>
    <li>Daily coal production, dispatch and trains: Coal India's MOC dashboard and Rakes Data (FOIS); National Coal Portal. Monthly: Ministry of Coal, Monthly Coal Statistics; CEA monthly coal and import reports (since 2014); Ministry of Commerce TradeStat (imports by HS code); Ministry of Ports, Shipping and Waterways (coal through ports).</li>
    <li>Other fuels: PPAC sectoral gas consumption; CEA monthly gas reports; Central Water Commission weekly reservoir bulletins.</li>
    <li>Coalfields, ports and routes in supply chains: the power map's research (company records, CEA remarks, OpenStreetMap). Basemap © CARTO © OpenStreetMap contributors.</li>
    <li>Data refreshed ${new Date(D.generated).toLocaleString('en-GB', { timeZone: 'Asia/Kolkata', dateStyle: 'medium', timeStyle: 'short' })} IST. <a href="../data/coal/coal.json">Download the dashboard data</a> or <a href="../data/coal/series.json">every series</a> (JSON).</li></ul>`;
}

function redraw() { if (!last) return; giants(); stockCharts(); flowChart(); supplyCharts(); reserveCharts(); mapTheme(); }
lede(); rates(); tableSetup(); table(); sources(); drawMap(); redraw();
let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(redraw, 200); });
