// Voxel power infrastructure, Minecraft / Dangerous Dave style (after lighthouses/web/js/models.js).
// Every asset is built from cubes into ONE static InstancedMesh (shell only: hidden cells are culled,
// per-block shade jitter), plus a few small instanced meshes for the moving parts:
//   'smoke' / 'steam'  voxel puffs rising from stacks and cooling towers (density ∝ load)
//   'glow'             boiler / hall windows (MeshBasicMaterial, brightness ∝ load)
//   'blink'            aviation lights, substation indicators
//   'flow'             conveyor coal, spillway water, dumpers, wakes
//   'spin'             wind rotors, bucket wheels, wagon wheels
// Local metres, Y up, origin at the ground centre of the site, +X east, -Z north.
// group.userData = { archetype, h, radius, anim(tSeconds, load0to1), wind:{x,z}, emitters }
import * as THREE from 'three';

export const ARCHETYPES = ['coal', 'lignite', 'gas', 'diesel', 'nuclear_vver', 'nuclear_phwr', 'nuclear_fbr', 'hydro_dam', 'hydro_run',
  'pumped_storage', 'wind_turbine', 'wind_farm', 'solar_farm', 'biomass', 'substation', 'pylon', 'coal_ship', 'coal_train', 'lng_tanker', 'mine'];

/* ---------------------------------------------------------------- palette */
const C = {
  dust: 0x9a927f, dust2: 0x8c8574, gravel: 0x9d998e, road: 0x55555a, grass: 0x62813e, grassDk: 0x4b6b31, tree: 0x3a6230, treeDk: 0x2c4d25,
  trunk: 0x5b4330, soil: 0x8a6a4a, laterite: 0xa0603e, rock: 0x7f7c74, rockDk: 0x5f5d58, sand: 0xc2ad83,
  concrete: 0xaaa79e, concreteDk: 0x807d76, concreteLt: 0xc9c6bd, stone: 0x9c8f7c, stoneDk: 0x7d7162,
  clad: 0x6a8296, cladDk: 0x546a7d, cladLt: 0x8ca2b2, roof: 0x5b646c, glass: 0x93b8cc, frame: 0x3f464e,
  steel: 0x4c535b, steelLt: 0x858d95, rust: 0x8c4f31, red: 0xb8342a, white: 0xece9e1, cream: 0xe0d5ba, buff: 0xc8b48e,
  coal: 0x232427, coalHi: 0x35363a, lignite: 0x40332a, ash: 0xc3bfb4, ashDk: 0xa9a59a,
  water: 0x3f7597, waterDk: 0x2d5a78, waterLt: 0x6fa0bf, foam: 0xe4f1f7,
  yellow: 0xd9a72b, orange: 0xd67a2c, trafo: 0x5a646b, insul: 0x8d5b3d, insGlass: 0x5f8f80,
  bagasse: 0xcbb57c, cane: 0x6f9a3c, panel: 0x22385a, panelLt: 0x39587f, panelFr: 0xa7adb2,
  hull: 0x2a2d32, hullRed: 0x9c2d25, deck: 0x7b5040, hatch: 0x8a3b2c, superW: 0xebe8e0, navy: 0x27384f,
  nukeW: 0xe5e2d8, dome: 0xc3c6c6, nukeBlue: 0x3f6fa6, loco: 0xa5312b, locoCream: 0xe3d3a6, wagon: 0x7b4631,
};
const GLOW = 0xffa84a, GLOW_W = 0xffe6a8, GLOW_B = 0x8fd8ff;

/* ---------------------------------------------------------------- helpers */
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const hash = (x, y = 0, z = 0) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
const lc = s => String(s || '').toLowerCase();
const BOX = new THREE.BoxGeometry(1, 1, 1);
const MAT = new THREE.MeshStandardMaterial({ roughness: 0.92, metalness: 0, flatShading: true });
const PUFF = new THREE.MeshStandardMaterial({ roughness: 1, metalness: 0, flatShading: true, emissive: 0x1c1c1c });
const STEAM = new THREE.MeshStandardMaterial({ roughness: 1, metalness: 0, flatShading: true, emissive: 0x565656 });

function shade(hex, g, x, y, z) {
  const col = new THREE.Color(hex);
  const k = 1 + (hash(x, y, z) - 0.5) * 2 * g;
  return col.setRGB(Math.min(1, col.r * k), Math.min(1, col.g * k), Math.min(1, col.b * k));
}

// Sun: tSeconds > 1e9 is taken as epoch seconds (a simulated clock), otherwise the wall clock. IST.
export function sunAt(t) {
  const d = t > 1e9 ? new Date(t * 1000) : new Date();
  const h = ((d.getUTCHours() + d.getUTCMinutes() / 60 + 5.5) % 24);
  const elev = Math.sin(Math.PI * (h - 6.1) / 12.4);          // ~6:06 sunrise, ~18:30 sunset
  return { h, elev, day: clamp(elev * 4 + 0.15, 0, 1) };
}

/* ------------------------------------------------------------------ voxels */
const key = (x, y, z) => ((x + 4096) * 8192 + (z + 4096)) * 2048 + (y + 512);

class Voxels {
  constructor(vox) { this.vox = vox; this.cells = new Map(); this.free = []; }
  set(x, y, z, c, g = 0.08) {
    if (c == null) return;
    x = Math.round(x); y = Math.round(y); z = Math.round(z);
    this.cells.set(key(x, y, z), [x, y, z, c, g]);
  }
  get(x, y, z) { return this.cells.get(key(Math.round(x), Math.round(y), Math.round(z))); }
  has(x, y, z) { return this.cells.has(key(x, y, z)); }
  del(x, y, z) { this.cells.delete(key(Math.round(x), Math.round(y), Math.round(z))); }
  box(x0, y0, z0, x1, y1, z1, c, g = 0.08) {
    [x0, x1] = [Math.min(x0, x1), Math.max(x0, x1)]; [y0, y1] = [Math.min(y0, y1), Math.max(y0, y1)]; [z0, z1] = [Math.min(z0, z1), Math.max(z0, z1)];
    for (let x = Math.round(x0); x <= Math.round(x1); x++) for (let y = Math.round(y0); y <= Math.round(y1); y++) for (let z = Math.round(z0); z <= Math.round(z1); z++) {
      this.set(x, y, z, typeof c === 'function' ? c(x, y, z) : c, g);
    }
  }
  // free block in voxel units: centre x/z, bottom y, size sx/sy/sz (not culled, not in the neighbour map)
  block(x, y, z, sx, sy, sz, c, g = 0.08) { this.free.push([x, y, z, sx, sy, sz, c, g]); }
  // flat tiles over cells x0..x1, z0..z1 (tile = cells per tile edge), top at y + t
  slab(x0, z0, x1, z1, y, t, c, g = 0.08, tile = 2) {
    [x0, x1] = [Math.min(x0, x1), Math.max(x0, x1)]; [z0, z1] = [Math.min(z0, z1), Math.max(z0, z1)];
    for (let x = x0; x <= x1; x += tile) for (let z = z0; z <= z1; z += tile) {
      const w = Math.min(tile, x1 - x + 1), d = Math.min(tile, z1 - z + 1);
      const col = typeof c === 'function' ? c(x, z) : c;
      if (col == null) continue;
      this.block(x - 0.5 + w / 2, y, z - 0.5 + d / 2, w, t, d, col, g);
    }
  }
  // 3D line of cells
  line(a, b, c, g = 0.08, thick = 0) {
    const n = Math.max(1, Math.round(Math.max(Math.abs(b[0] - a[0]), Math.abs(b[1] - a[1]), Math.abs(b[2] - a[2]))));
    for (let i = 0; i <= n; i++) {
      const x = a[0] + (b[0] - a[0]) * i / n, y = a[1] + (b[1] - a[1]) * i / n, z = a[2] + (b[2] - a[2]) * i / n;
      this.set(x, y, z, c, g);
      if (thick) this.set(x, y - 1, z, c, g);
    }
  }
  // heightfield columns: hf(x,z) -> integer height, cf(x,y,z,top,h) -> colour (null = skip)
  cols(x0, x1, z0, z1, hf, cf, g = 0.12) {
    const H = (x, z) => (x < x0 || x > x1 || z < z0 || z > z1) ? 0 : Math.max(0, Math.round(hf(x, z)));
    for (let x = x0; x <= x1; x++) for (let z = z0; z <= z1; z++) {
      const h = H(x, z);
      if (h <= 0) continue;
      const hn = Math.min(H(x + 1, z), H(x - 1, z), H(x, z + 1), H(x, z - 1));
      for (let y = Math.max(0, Math.min(hn, h - 1)); y < h; y++) this.set(x, y, z, cf(x, y, z, y === h - 1, h), g);
    }
  }
  bounds() {
    let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity, y1 = 0;
    for (const [x, y, z] of this.cells.values()) { x0 = Math.min(x0, x - 0.5); x1 = Math.max(x1, x + 0.5); z0 = Math.min(z0, z - 0.5); z1 = Math.max(z1, z + 0.5); y1 = Math.max(y1, y + 1); }
    for (const [x, y, z, sx, sy, sz] of this.free) { x0 = Math.min(x0, x - sx / 2); x1 = Math.max(x1, x + sx / 2); z0 = Math.min(z0, z - sz / 2); z1 = Math.max(z1, z + sz / 2); y1 = Math.max(y1, y + sy); }
    const v = this.vox;
    if (x0 === Infinity) return { x0: 0, x1: 0, z0: 0, z1: 0, y1: 0 };
    return { x0: x0 * v, x1: x1 * v, z0: z0 * v, z1: z1 * v, y1: y1 * v };
  }
  mesh(material = MAT, yOff = 0.5) {
    const list = [];
    for (const cell of this.cells.values()) {
      const [x, y, z] = cell;
      const hidden = this.has(x + 1, y, z) && this.has(x - 1, y, z) && this.has(x, y + 1, z) && (y === 0 || this.has(x, y - 1, z)) && this.has(x, y, z + 1) && this.has(x, y, z - 1);
      if (!hidden) list.push(cell);
    }
    const m = new THREE.InstancedMesh(BOX, material, Math.max(1, list.length + this.free.length));
    m.count = list.length + this.free.length;
    const mat = new THREE.Matrix4(), v = this.vox;
    let i = 0;
    for (const [x, y, z, c, g] of list) {
      mat.makeScale(v, v, v).setPosition(x * v, (y + yOff) * v, z * v);
      m.setMatrixAt(i, mat); m.setColorAt(i, shade(c, g, x, y, z)); i++;
    }
    for (const [x, y, z, sx, sy, sz, c, g] of this.free) {
      mat.makeScale(sx * v, sy * v, sz * v).setPosition(x * v, (y + sy / 2) * v, z * v);
      m.setMatrixAt(i, mat); m.setColorAt(i, shade(c, g, x * 3.1, y * 7.3, z * 1.7)); i++;
    }
    m.frustumCulled = false;
    m.userData.cells = m.count;
    return m;
  }
}

function inDisk(x, z, r) { return x * x + z * z <= (r + 0.45) * (r + 0.45); }
function ringEdge(x, z, r) {
  if (!inDisk(x, z, r)) return false;
  for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) if (!inDisk(x + i, z + j, r)) return true;
  return false;
}

/* --------------------------------------------------------------------- kit */
// A Kit collects the static voxels plus every moving part, then assembles the Group.
const ZERO = new THREE.Matrix4().makeScale(0, 0, 0);
const _m = new THREE.Matrix4(), _q = new THREE.Quaternion(), _p = new THREE.Vector3(), _s = new THREE.Vector3(), _v = new THREE.Vector3();

class Kit {
  constructor(vox) {
    this.vox = vox; this.v = new Voxels(vox);
    this.glows = []; this.blinks = []; this.emitters = []; this.flows = []; this.spins = []; this.fns = []; this.extra = [];
  }
  M(m) { return Math.round(m / this.vox); }
  glow(x, y, z, c = GLOW) { this.v.del(x, y, z); this.glows.push([x, y, z, c]); }
  blink(x, y, z, c = 0xff2a1a, size = 0.6) { this.blinks.push([x, y, z, c, size]); }
  // metres: x, y (top of stack), z; r = outlet radius
  emit(x, y, z, r, kind = 'smoke', extra = {}) { this.emitters.push({ x, y, z, r, kind, seed: hash(x, y, z) * 10, ...extra }); }
  // path in metres [[x,y,z],...]; mode: 'belt' (moves ∝ load, always shown) | 'water' (count ∝ load) | 'churn'
  flow(path, o = {}) { this.flows.push({ path, n: 12, size: this.vox * 0.6, speed: 6, colors: [C.coal], mode: 'belt', spread: 0, ...o }); }
  // cells: [[x,y,z,colour]] in metres relative to pivot; pivots [[x,y,z]]; axis Vector3; rpm at full load
  spin(cells, pivots, axis, o = {}) { this.spins.push({ cells, pivots, axis, rpm: 15, size: this.vox, min: 0, ...o }); }

  finish(archetype, o = {}) {
    const group = new THREE.Group(), inner = new THREE.Group();
    group.add(inner);
    const b = this.v.bounds();
    const cx = o.centre ? o.centre[0] : (b.x0 + b.x1) / 2, cz = o.centre ? o.centre[1] : (b.z0 + b.z1) / 2;
    inner.position.set(-cx, 0, -cz);
    const stat = this.v.mesh();
    stat.name = 'voxels';
    inner.add(stat);
    let count = stat.count;
    const vox = this.vox, updates = [];
    const fx = o.focus ? o.focus[0] - cx : 0, fz = o.focus ? o.focus[1] - cz : 0;
    const ud = { archetype, wind: { x: 0.94, z: 0.34 }, focus: [fx, fz], seaward: o.seaward || null, emitters: this.emitters.map(e => ({ x: e.x - cx, y: e.y, z: e.z - cz, r: e.r, kind: e.kind })) };

    if (this.glows.length) {
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const m = new THREE.InstancedMesh(BOX, mat, this.glows.length);
      this.glows.forEach(([x, y, z, c], i) => { m.setMatrixAt(i, _m.makeScale(vox, vox, vox).setPosition(x * vox, (y + 0.5) * vox, z * vox)); m.setColorAt(i, new THREE.Color(c)); });
      m.name = 'glow'; m.frustumCulled = false; inner.add(m); count += m.count;
      updates.push((t, L) => mat.color.setScalar(0.1 + 0.9 * L * (0.94 + 0.06 * Math.sin(t * 11.3) * Math.sin(t * 3.7))));
    }
    if (this.blinks.length) {
      const mat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const m = new THREE.InstancedMesh(BOX, mat, this.blinks.length);
      this.blinks.forEach(([x, y, z, c, s], i) => { m.setMatrixAt(i, _m.makeScale(vox * s, vox * s, vox * s).setPosition(x * vox, (y + 0.5) * vox, z * vox)); m.setColorAt(i, new THREE.Color(c)); });
      m.name = 'blink'; m.frustumCulled = false; inner.add(m); count += m.count;
      const rate = o.blinkRate || 0;
      updates.push((t, L) => {
        const period = rate ? 1 / (0.4 + rate * L) : 1.5;
        mat.color.setScalar(((t % period) / period) < (rate ? 0.5 : 0.18) ? 1 : 0.12);
      });
    }
    if (this.emitters.length) {
      for (const kind of ['smoke', 'steam']) {
        const es = this.emitters.filter(e => (kind === 'steam') === (e.kind === 'steam'));
        if (!es.length) continue;
        let n = 0;
        for (const e of es) {
          Object.assign(e, {
            smoke: { n: 16, life: 9, sz: 1.4, grow: 2.2, rise: 25, drift: 45, spread: 1.0, cols: [0x9a9a96, 0x8a8a87, 0xaaa9a4, 0x7d7c79] },
            dark: { n: 12, life: 7, sz: 1.6, grow: 2.0, rise: 22, drift: 35, spread: 1.0, cols: [0x55544f, 0x46453f, 0x62615c] },
            light: { n: 12, life: 8, sz: 1.4, grow: 2.0, rise: 22, drift: 40, spread: 1.0, cols: [0xc4c3bd, 0xb3b2ad, 0xd2d1cc] },
            heat: { n: 6, life: 4, sz: 1.1, grow: 1.2, rise: 10, drift: 10, spread: 0.6, cols: [0xd9d6d0, 0xc9c6c0] },
            steam: { n: 18, life: 10, sz: 0.55, grow: 1.2, rise: 4.5, drift: 3, spread: 1.3, cols: [0xf4f5f6, 0xe6e8ea, 0xffffff, 0xdcdfe2] },
            wisp: { n: 5, life: 5, sz: 1.0, grow: 1.2, rise: 8, drift: 8, spread: 0.8, cols: [0xf2f3f4, 0xe2e4e6] },
          }[e.kind] || {}, e.o || {});
          e.i0 = n; n += e.n;
        }
        const m = new THREE.InstancedMesh(BOX, kind === 'steam' ? STEAM : PUFF, n);
        for (const e of es) for (let i = 0; i < e.n; i++) { m.setMatrixAt(e.i0 + i, ZERO); m.setColorAt(e.i0 + i, new THREE.Color(e.cols[i % e.cols.length])); }
        m.name = kind; m.frustumCulled = false; inner.add(m); count += n;
        const q = vox / 2;
        updates.push((t, L) => {
          const W = group.userData.wind || { x: 1, z: 0 };
          for (const e of es) {
            for (let i = 0; i < e.n; i++) {
              const ph = t / e.life + i / e.n + e.seed, cyc = Math.floor(ph), a = ph - cyc;
              if (L < 0.02 || hash(e.seed * 13.1 + i, cyc, 7.7) > L * 1.08) { m.setMatrixAt(e.i0 + i, ZERO); continue; }
              const R = e.r;
              const s = Math.max(q, Math.round(R * e.sz * (1 + e.grow * a) * (0.75 + 0.25 * L) / q) * q);
              const rise = R * e.rise * a * (0.6 + 0.4 * L);
              const drift = R * e.drift * Math.pow(a, 1.5);
              const sp = R * e.spread * (0.5 + a);
              const jx = (hash(i, cyc, 1) - 0.5) * 2 * sp, jz = (hash(i, cyc, 2) - 0.5) * 2 * sp;
              const x = Math.round((e.x + W.x * drift + jx) / q) * q, z = Math.round((e.z + W.z * drift + jz) / q) * q;
              const y = Math.round((e.y + rise) / q) * q;
              m.setMatrixAt(e.i0 + i, _m.makeScale(s, s, s).setPosition(x, y + s / 2, z));
            }
          }
          m.instanceMatrix.needsUpdate = true;
        });
      }
    }
    if (this.flows.length) {
      let n = 0;
      for (const f of this.flows) {
        f.i0 = n; n += f.n; f.pos = 0; f.seed = hash(f.path[0][0], f.path[0][2], f.n);
        f.cum = [0];
        for (let i = 1; i < f.path.length; i++) f.cum.push(f.cum[i - 1] + Math.hypot(f.path[i][0] - f.path[i - 1][0], f.path[i][1] - f.path[i - 1][1], f.path[i][2] - f.path[i - 1][2]));
        f.len = f.cum[f.cum.length - 1] || 1;
      }
      const m = new THREE.InstancedMesh(BOX, MAT, n);
      for (const f of this.flows) for (let i = 0; i < f.n; i++) { m.setMatrixAt(f.i0 + i, ZERO); m.setColorAt(f.i0 + i, shade(f.colors[i % f.colors.length], 0.08, i, f.i0, 3)); }
      m.name = 'flow'; m.frustumCulled = false; inner.add(m); count += n;
      const at = (f, s) => {
        let k = 1; while (k < f.cum.length - 1 && f.cum[k] < s) k++;
        const a = f.path[k - 1], b = f.path[k], u = (s - f.cum[k - 1]) / ((f.cum[k] - f.cum[k - 1]) || 1);
        return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
      };
      updates.push((t, L, dt) => {
        for (const f of this.flows) {
          const water = f.mode !== 'belt';
          f.pos += f.speed * (water ? 0.5 + 0.5 * L : L) * dt;
          for (let i = 0; i < f.n; i++) {
            if (water && (L < 0.02 || hash(i, f.seed, 5) > L * 1.05)) { m.setMatrixAt(f.i0 + i, ZERO); continue; }
            let p, s = f.size;
            if (f.mode === 'churn') {
              const cyc = Math.floor(t * 1.3 + hash(i, f.seed));
              p = [...f.path[0]];
              p[0] += (hash(i, cyc, 1) - 0.5) * f.spread; p[2] += (hash(i, cyc, 2) - 0.5) * f.spread;
              p[1] += Math.abs(Math.sin(t * 4 + i * 1.7)) * f.size * 0.8;
              s *= 0.6 + 0.6 * hash(i, cyc, 3);
            } else {
              const d = ((f.pos + i * f.len / f.n) % f.len + f.len) % f.len;
              p = at(f, d);
              if (f.spread) { p[0] += (hash(i, f.seed, 1) - 0.5) * f.spread; p[2] += (hash(i, f.seed, 2) - 0.5) * f.spread; }
            }
            m.setMatrixAt(f.i0 + i, _m.makeScale(s, s * (f.flat || 1), s).setPosition(p[0], p[1] + s * (f.flat || 1) / 2, p[2]));
          }
        }
        m.instanceMatrix.needsUpdate = true;
      });
    }
    if (this.spins.length) {
      let n = 0;
      for (const sp of this.spins) { sp.i0 = n; n += sp.cells.length * sp.pivots.length; sp.angle = 0; }
      const m = new THREE.InstancedMesh(BOX, MAT, n);
      for (const sp of this.spins) {
        let i = sp.i0;
        for (let k = 0; k < sp.pivots.length; k++) for (const c of sp.cells) m.setColorAt(i++, shade(c[3], 0.06, c[0] * 3, c[1] * 3, c[2] * 3 + k));
      }
      m.name = 'spin'; m.frustumCulled = false; inner.add(m); count += n;
      updates.push((t, L, dt) => {
        for (const sp of this.spins) {
          const rpm = L < 0.02 ? sp.min : sp.rpm * (0.25 + 0.75 * L);
          sp.angle += rpm / 60 * Math.PI * 2 * dt;
          let i = sp.i0;
          sp.pivots.forEach((pv, k) => {
            _q.setFromAxisAngle(sp.axis, sp.angle + k * 1.3);
            for (const c of sp.cells) {
              _v.set(c[0], c[1], c[2]).applyQuaternion(_q);
              _p.set(pv[0] + _v.x, pv[1] + _v.y, pv[2] + _v.z);
              m.setMatrixAt(i++, _m.compose(_p, _q, _s.setScalar(sp.size)));
            }
          });
        }
        m.instanceMatrix.needsUpdate = true;
      });
    }
    for (const e of this.extra) { inner.add(e); }
    for (const f of this.fns) updates.push(f);

    let last = null;
    const h = Math.max(b.y1, o.h || 0);
    const radius = Math.max(Math.hypot(b.x0 - cx, b.z0 - cz), Math.hypot(b.x1 - cx, b.z0 - cz), Math.hypot(b.x0 - cx, b.z1 - cz), Math.hypot(b.x1 - cx, b.z1 - cz));
    group.userData = Object.assign(ud, {
      h, radius, instances: count, voxel: vox,
      anim(t, load = 1) {
        const L = clamp(+load || 0, 0, 1);
        const dt = last == null ? 0 : clamp(t - last, 0, 0.25);
        last = t;
        for (const u of updates) u(t, L, dt);
      },
    }, o.userData || {});
    group.userData.anim(0, 0.8);
    return group;
  }
}

/* ------------------------------------------------------------- components */
function building(v, x0, z0, x1, z1, y0, h, wall, roof = C.roof, o = {}) {
  const y1 = y0 + h - 1;
  v.box(x0, y0, z0, x1, y1, z1, (x, y, z) => {
    if (y === y1) return roof;
    if (o.band && y === y0 + Math.floor(h * o.band)) return o.bandC || C.glass;
    if (o.stripes && (y - y0) % o.stripes === o.stripes - 1) return o.stripeC || C.cladDk;
    return wall;
  }, o.g ?? 0.07);
}

function chimney(K, cx, cz, Hm, o = {}) {
  const v = K.v, vox = K.vox, H = Math.max(4, K.M(Hm));
  const Rb = clamp(Hm * (o.slim ? 0.035 : 0.05), 2.5, 15) / vox, Rt = Rb * 0.62;
  const bands = o.bands !== false && Hm >= 60;
  const y3 = Math.floor(H * 2 / 3);
  const nb = clamp(Math.round((H - y3) / 2) | 1, 3, 7), bh = (H - y3) / nb;
  const body = o.color || C.concrete;
  for (let y = 0; y < H; y++) {
    const r = Rb + (Rt - Rb) * y / H, ri = Math.ceil(r) + 1;
    for (let x = -ri; x <= ri; x++) for (let z = -ri; z <= ri; z++) {
      if (!inDisk(x, z, r)) continue;
      const top = y === H - 1;
      let c = body;
      if (bands && y >= y3) c = Math.floor((H - 1 - y) / bh) % 2 === 0 ? C.red : C.white;
      if (top) c = ringEdge(x, z, r) ? 0x3a3836 : 0x141414;
      v.set(cx + x, y, cz + z, c, 0.06);
    }
    if ((y === y3 && bands) || y === H - 2) {                       // galleries
      const rr = r + 1;
      for (let x = -Math.ceil(rr); x <= Math.ceil(rr); x++) for (let z = -Math.ceil(rr); z <= Math.ceil(rr); z++) if (ringEdge(x, z, rr) && !inDisk(x, z, r)) v.set(cx + x, y, cz + z, C.steel, 0.04);
    }
  }
  const rt = Math.max(1, Math.round(Rt));
  if (Hm >= 45) for (const [dx, dz] of [[rt + 1, 0], [-rt - 1, 0], [0, rt + 1], [0, -rt - 1]]) {
    K.blink(cx + dx, H - 1, cz + dz);
    if (bands) K.blink(cx + dx * 1.1, y3, cz + dz * 1.1);
  }
  const fl = o.flues || 1, fr = Math.max(vox * 0.5, Rt * vox * (fl > 1 ? 0.45 : 0.7));
  for (let i = 0; i < fl; i++) {
    const a = i / fl * Math.PI * 2 + 0.4, d = fl > 1 ? Rt * vox * 0.45 : 0;
    K.emit(cx * vox + Math.cos(a) * d, H * vox, cz * vox + Math.sin(a) * d, fr, o.kind || 'smoke');
  }
  return { H, Rb };
}

function coolingTower(K, cx, cz, Hm) {
  const v = K.v, vox = K.vox, H = K.M(Hm), Rb = Hm * 0.4 / vox;
  const yt = 0.8 * H, Rt = Rb * 0.6, Rtop = Rb * 0.64;
  for (let y = 0; y < H; y++) {
    const r = y < yt ? Rt + (Rb - Rt) * Math.pow((yt - y) / yt, 2) : Rt + (Rtop - Rt) * Math.pow((y - yt) / (H - yt), 2);
    const ri = Math.ceil(r) + 1;
    for (let x = -ri; x <= ri; x++) for (let z = -ri; z <= ri; z++) {
      if (!inDisk(x, z, r) || inDisk(x, z, r - 1.2)) continue;
      if (y === 0 && (x + z) % 2 !== 0) continue;                 // raker columns, air inlet between
      let c = y === 0 ? C.concreteDk : y > H - 3 ? 0x9d9a92 : C.concreteLt;
      if (y > H * 0.55 && hash(x, 1, z) > 0.82) c = 0xb4b0a7;       // weathering streaks
      v.set(cx + x, y, cz + z, c, 0.05);
    }
  }
  // basin water inside
  v.slab(cx - Math.floor(Rb * 0.8), cz - Math.floor(Rb * 0.8), cx + Math.floor(Rb * 0.8), cz + Math.floor(Rb * 0.8), 0, 0.3, (x, z) => inDisk(x - cx, z - cz, Rb - 1) ? C.waterDk : null, 0.05, 2);
  K.emit(cx * vox, H * vox, cz * vox, Rtop * vox * 0.75, 'steam');
  return H;
}

function tank(v, cx, cz, r, h, c = C.white, roof = null) {
  for (let y = 0; y < h; y++) for (let x = -Math.ceil(r); x <= Math.ceil(r); x++) for (let z = -Math.ceil(r); z <= Math.ceil(r); z++) {
    if (inDisk(x, z, r)) v.set(cx + x, y, cz + z, y === h - 1 ? (roof || c) : (y === 0 ? C.concreteDk : c), 0.05);
  }
}

function tree(v, x, z, s = 1) {
  const t = hash(x, z, 9) > 0.5 ? C.tree : C.treeDk;
  v.set(x, 0, z, C.trunk, 0.1);
  if (s >= 2) { v.box(x - 1, 1, z - 1, x + 1, 2, z + 1, t, 0.18); v.set(x, 3, z, t, 0.18); }
  else { v.set(x, 1, z, t, 0.2); v.set(x, 2, z, t, 0.2); }
}

function trafo(K, x, z, s = 1, y = 0) {
  const v = K.v;
  v.box(x - s, y, z - s, x + s, y + s, z + s, C.trafo, 0.06);
  for (let i = -s; i <= s; i += 2) v.set(x + i, y, z + s + 1, 0x49525a, 0.04);  // radiator bank
  for (let i = -s; i <= s; i++) v.set(x + i, y + s + 1, z, C.insul, 0.1);         // bushings
  v.set(x - s, y + s + 1, z - s, 0x6c767c, 0.05);                                    // conservator
}

function gantryRow(K, x0, x1, z, hCells, step = 4) {
  const v = K.v;
  for (let x = x0; x <= x1; x += step) for (let y = 0; y < hCells; y++) v.set(x, y, z, C.steelLt, 0.05);
  for (let x = x0; x <= x1; x++) v.set(x, hCells, z, C.steelLt, 0.05);
}

function switchyard(K, x0, z0, x1, z1, kv = 400) {
  const v = K.v, vox = K.vox;
  v.slab(x0, z0, x1, z1, 0, 0.12, C.gravel, 0.06, 4);
  const hG = Math.max(2, K.M(kv >= 400 ? 22 : kv >= 220 ? 16 : 11));
  const pitch = Math.max(3, K.M(kv >= 400 ? 28 : 18));
  for (let z = z0 + 1; z <= z1 - 1; z += pitch) {
    gantryRow(K, x0 + 1, x1 - 1, z, hG, Math.max(3, K.M(20)));
    for (let x = x0 + 2; x <= x1 - 2; x += 2) {                  // breakers, isolators, CTs between gantries
      const zz = z + Math.floor(pitch / 2);
      if (zz >= z1) continue;
      v.set(x, 0, zz, 0x8e959b, 0.05);
      if (hG > 3) v.set(x, 1, zz, C.insul, 0.1);
      if ((x & 3) === 0) v.set(x, 0, zz + 1, C.steelLt, 0.05);
    }
  }
  // perimeter fence posts
  for (let x = x0; x <= x1; x += 2) { v.set(x, 0, z0, 0x70767b, 0.05); v.set(x, 0, z1, 0x70767b, 0.05); }
  for (let z = z0; z <= z1; z += 2) { v.set(x0, 0, z, 0x70767b, 0.05); v.set(x1, 0, z, 0x70767b, 0.05); }
  return hG;
}

function pad(v, x0, z0, x1, z1, tile = 4, c = C.dust) {
  v.slab(x0, z0, x1, z1, -0.1, 0.1, (x, z) => (hash(x, z, 4) > 0.85 ? C.dust2 : c), 0.07, tile);
}

// coal / lignite windrow along Z
function heap(v, x0, x1, z0, z1, h, c, hi) {
  v.cols(x0, x1, z0, z1, (x, z) => Math.min(h, x - x0 + 1, x1 - x + 1, z - z0 + 1, z1 - z + 1), (x, y, z, top) => top && hash(x, y, z) > 0.8 ? hi : c, 0.3);
}

/* -------------------------------------------------------------- plant data */
function unitList(p, fallback = 210, sizes = [800, 660, 600, 525, 500, 300, 250, 210, 200, 150, 125, 110, 60, 30]) {
  const us = (p.units || []).filter(u => u && +(u.mw ?? u.capacity_mw) > 0 && !/retired|decommission|dismantl/i.test(u.status || ''));
  if (us.length) return us.slice(0, 10).map(u => +(u.mw ?? u.capacity_mw));
  const cap = +p.capacity_mw || 0, st = p.structure || {};
  if (st.boiler_units > 0 && cap) return Array(Math.min(10, st.boiler_units)).fill(cap / st.boiler_units);
  if (!cap) return [fallback, fallback];
  for (const m of sizes) {
    const k = cap / m;
    if (k >= 1 && k <= 8 && Math.abs(k - Math.round(k)) < 0.02) return Array(Math.round(k)).fill(m);
  }
  const k = clamp(Math.round(cap / 210), 1, 6);
  return Array(k).fill(cap / k);
}

const COASTAL = /north chennai|nctps|ennore|vallur|ntecl|tuticorin|thoothukudi|ntpl|muthiara|udangudi|cuddalore|itpcl|sepc|ppn|kudankulam|kalpakkam|maps|pfbr|mundra|krishnapatnam|simhapuri|painampuram|trombay|dahanu|ratnagiri|udupi|simhadri|hinduja|paradip|kakinada|nagapattinam/i;
function seaCooled(p) {
  const w = p.water || {};
  const s = lc(w.cooling) + ' ' + lc(w.source);
  if (/sea|once.?through|ocean|bay of bengal|arabian|backwater/.test(s)) return true;
  if (/tower|ndct|reservoir|river|canal|dam/.test(s)) return false;
  if ((p.structure?.cooling_towers || 0) > 0) return false;
  return COASTAL.test(`${p.name || ''} ${p.id || ''} ${(p.aliases || []).join(' ')}`);
}

function boilerDims(mw, lig) {
  const d = mw < 100 ? [26, 24, 42] : mw < 180 ? [34, 32, 55] : mw < 300 ? [44, 40, 70] : mw < 550 ? [54, 48, 85] : mw < 700 ? [62, 54, 95] : [70, 60, 105];
  return { w: d[0], d: d[1], h: d[2] * (lig ? 1.12 : 1) };
}

/* ------------------------------------------------------------ coal/lignite */
function thermal(p, kind) {
  const lig = kind === 'lignite';
  const st = p.structure || {};
  const mws = unitList(p);
  const n = mws.length;
  const K = new Kit(n <= 3 ? 4 : 5), v = K.v, M = m => K.M(m), vox = K.vox;
  const sea = seaCooled(p);
  const D = mws.map(mw => boilerDims(mw, lig));
  const maxMw = Math.max(...mws), maxH = Math.max(...D.map(d => d.h)), maxD = Math.max(...D.map(d => d.d));
  const gap = 22;
  const xs = []; let cur = 0;
  for (const d of D) { xs.push(cur + gap / 2 + d.w / 2); cur += d.w + gap; }
  const X0 = 0, X1 = cur;
  const thD = maxMw >= 500 ? 45 : 38, thH = maxMw >= 500 ? 38 : 30;
  const zBun = -15, zBoil1 = zBun, zBoil0 = zBun - maxD;
  const zEsp1 = zBoil0 - 12, zEsp0 = zEsp1 - (maxMw >= 500 ? 55 : 42);

  // turbine hall + bunker bay (continuous across units)
  const tx0 = M(X0 + gap / 2), tx1 = M(X1 - gap / 2) - 1;
  building(v, tx0, M(0), tx1, M(thD) - 1, 0, M(thH), C.cladLt, C.roof, { band: 0.62, bandC: C.glass });
  for (let x = tx0 + 1; x < tx1; x += 3) K.glow(x, Math.floor(M(thH) * 0.35), M(thD) - 1, GLOW_W);
  const bunH = M(maxH * 0.62);
  building(v, tx0, M(zBun), tx1, -1, 0, bunH, C.clad, C.roof, { stripes: 4 });

  // boilers, ESPs, flue ducts, generator transformers
  D.forEach((d, i) => {
    const x0 = M(xs[i] - d.w / 2), x1 = M(xs[i] + d.w / 2) - 1, z0 = M(zBun - d.d), z1 = M(zBun) - 1;
    const H = M(d.h), yc = Math.floor(H * 0.84);
    v.box(x0, 0, z0, x1, yc - 1, z1, (x, y, z) => (y % 4 === 3 ? C.cladDk : (y > H * 0.5 && (x + z) % 7 === 0 ? C.cladLt : C.clad)), 0.06);
    for (let y = yc; y < H; y++) for (let x = x0; x <= x1; x++) for (let z = z0; z <= z1; z++) {   // open steel crown
      const edgeX = x === x0 || x === x1, edgeZ = z === z0 || z === z1;
      if (y === H - 1) v.set(x, y, z, C.roof, 0.05);
      else if ((edgeX && edgeZ) || ((edgeX || edgeZ) && ((x + z) % 3 === 0 || y === yc + 1))) v.set(x, y, z, C.frame, 0.05);
    }
    v.box(x0 - 1, 0, z1 - 1, x0, H, z1, C.concrete, 0.05);                 // lift / stair tower
    for (const yy of [0.3, 0.45, 0.6].map(k => Math.floor(H * k))) for (let z = z0 + 1; z < z1; z += 3) { K.glow(x1, yy, z); K.glow(x0 + (z === z1 - 1 ? 1 : 0), yy, z); }
    for (let x = x0 + 1; x < x1; x += 3) K.glow(x, Math.floor(H * 0.7), z0);
    // ESP on legs with hoppers
    const ex0 = M(xs[i] - d.w * 0.45), ex1 = M(xs[i] + d.w * 0.45) - 1, ez0 = M(zEsp0), ez1 = M(zEsp1) - 1;
    v.box(ex0, M(9), ez0, ex1, M(33), ez1, (x, y, z) => (z - ez0) % 3 === 2 ? 0x7a8086 : 0x8f959b, 0.05);
    for (let x = ex0; x <= ex1; x += 2) for (let z = ez0; z <= ez1; z += 2) v.set(x, M(9) - 1, z, 0x6e747a, 0.05);
    for (const x of [ex0, ex1]) for (const z of [ez0, ez1]) v.box(x, 0, z, x, M(9) - 1, z, C.steel, 0.04);
    v.box(M(xs[i]) - 1, M(22), ez1 + 1, M(xs[i]) + 1, M(30), z0 - 1, C.steelLt, 0.05);       // boiler -> ESP duct
    trafo(K, M(xs[i]), M(thD + 12), 1);
  });

  // chimneys: stacks[] from the record, else one per 2 units (one per 3 for >= 500 MW)
  let stacks = Array.isArray(st.stacks) && st.stacks.length ? st.stacks.map(s => ({ h: +s.h_m || 0, flues: +s.flues || 0 })) : null;
  if (!stacks) {
    const ns = lig ? Math.min(n, 7) : Math.ceil(n / (maxMw >= 500 ? 3 : 2));
    stacks = Array.from({ length: ns }, () => ({ h: 0, flues: 0 }));
  }
  const defH = maxMw >= 500 ? 275 : maxMw >= 200 ? 220 : maxMw >= 100 ? 150 : 100;
  const ns = stacks.length;
  let topH = 0;
  stacks.forEach((s, j) => {
    const a = Math.floor(j * n / ns), b = Math.max(a + 1, Math.floor((j + 1) * n / ns));
    const served = xs.slice(a, b), cxm = served.length ? (served[0] + served[served.length - 1]) / 2 : xs[0];
    const Hm = s.h || defH;
    const R = clamp(Hm * 0.05, 2.5, 15);
    const czm = zEsp0 - 22 - R;
    const { H } = chimney(K, M(cxm), M(czm), Hm, { flues: s.flues || Math.max(1, b - a) });
    topH = Math.max(topH, H);
    for (let u = a; u < b; u++) {                                              // ID fan duct ESP -> chimney
      const ux = M(xs[u]);
      v.box(ux, M(4), M(czm + R), ux, M(12), M(zEsp0) - 1, C.steelLt, 0.05);
      if (ux !== M(cxm)) v.box(Math.min(ux, M(cxm)), M(4), M(czm + R) , Math.max(ux, M(cxm)), M(8), M(czm + R), C.steelLt, 0.05);
    }
  });
  const zChim = zEsp0 - 22 - clamp(defH * 0.05, 2.5, 15) * 2;

  // west: coal yard (coal) or the lignite mine
  let yardX1 = X0 - (lig ? 30 : 130), yardX0, yardZ0 = zEsp0, yardZ1 = thD + 20;
  const yZ0 = M(yardZ0), yZ1 = M(yardZ1);
  if (lig) {
    const w = M(n > 4 ? 420 : 320);
    yardX0 = yardX1 - w * vox;
    mineInto(K, M(yardX0), M(zChim - 120), M(yardX1), M(yardZ1 + 60), { lignite: true, conveyorTo: [M(yardX1), M(zBun) + 1] });
    heap(v, M(yardX1 + 10) - 1, M(yardX1 + 10) + 3, yZ0, yZ0 + 12, 3, C.lignite, 0x55463a);
  } else {
    const rows = clamp(1 + Math.ceil(n / 2), 2, 4), rw = 44, rg = 16;
    yardX0 = yardX1 - rows * (rw + rg);
    for (let r = 0; r < rows; r++) {
      const hx1 = yardX1 - r * (rw + rg) - rg, hx0 = hx1 - rw;
      heap(v, M(hx0), M(hx1) - 1, yZ0 + 1, yZ1 - 1, M(14), C.coal, C.coalHi);
      // stacker-reclaimer on rails in the gap east of each windrow
      const rx = M(hx1 + rg / 2);
      for (let z = yZ0; z <= yZ1; z += 2) v.set(rx, 0, z, 0x5a5047, 0.05);
      const sz = yZ0 + Math.floor((yZ1 - yZ0) * (0.3 + 0.4 * hash(r, n))), sy = 1;
      v.box(rx - 1, sy, sz - 1, rx + 1, sy + 1, sz + 1, C.yellow, 0.06);
      v.set(rx, sy + 2, sz, C.yellow, 0.06);
      v.line([rx, sy + 3, sz], [rx - M(rw * 0.7), sy + 1, sz], C.orange, 0.05);
      v.box(rx - M(rw * 0.7) - 1, sy, sz - 1, rx - M(rw * 0.7), sy + 1, sz + 1, 0x3d3d3d, 0.1);
    }
  }
  // conveyor: yard -> crusher house -> up to the bunker bay roof -> along the bunker bay
  const cy0 = 1, junc = [M(yardX1 + 14), M(18), M(zBun / 2)];
  const bunTop = bunH + 1;
  const pts = [[M(yardX1), cy0, M((yardZ0 + yardZ1) / 2)], [junc[0], cy0 + 1, M((yardZ0 + yardZ1) / 2)], [junc[0], junc[1], junc[2]], [tx0, bunTop, junc[2]], [tx1, bunTop, junc[2]]];
  v.box(junc[0] - 1, 0, M((yardZ0 + yardZ1) / 2) - 1, junc[0] + 1, 4, M((yardZ0 + yardZ1) / 2) + 1, C.cladDk, 0.06);   // crusher house
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    v.line(a, b, i === 2 ? 0x7d8f9c : 0x6e6a64, 0.05, i === 2 ? 1 : 0);
    const nseg = Math.max(Math.abs(b[0] - a[0]), Math.abs(b[2] - a[2]));
    if (i === 2) for (let k = 0; k <= nseg; k += 6) {                           // trestles
      const x = Math.round(a[0] + (b[0] - a[0]) * k / nseg), y = Math.round(a[1] + (b[1] - a[1]) * k / nseg);
      for (let yy = 0; yy < y; yy++) v.set(x, yy, a[2], C.steel, 0.04);
    }
  }
  v.box(junc[0] - 1, 0, junc[2] - 1, junc[0] + 1, junc[1], junc[2] + 1, C.cladDk, 0.06);                     // transfer tower
  K.flow(pts.map(([x, y, z]) => [x * vox, (y + 1) * vox, z * vox]), { n: 60, size: vox * 0.55, speed: 14, colors: lig ? [C.lignite, 0x2f261f] : [C.coal, C.coalHi], flat: 0.6 });

  // switchyard south
  const syZ0 = M(thD + 30), syZ1 = syZ0 + M(maxMw >= 500 ? 75 : 55);
  const kv = maxMw >= 500 ? 400 : 230;
  switchyard(K, tx0, syZ0, tx1, syZ1, kv);

  // cooling: towers east (inland) or CW pump house + intake/outfall canals (sea)
  let eastX = X1 + 30;
  const ctN = st.cooling_towers ?? (sea ? 0 : clamp(Math.ceil(n / (maxMw >= 300 ? 1 : 2)), 1, 6));
  if (ctN > 0) {
    const Hm = maxMw >= 500 ? 150 : maxMw >= 200 ? 125 : 95, R = Hm * 0.4;
    const rowsCT = ctN > 3 ? 2 : 1, perRow = Math.ceil(ctN / rowsCT);
    for (let k = 0; k < ctN; k++) {
      const c = Math.floor(k / rowsCT), r = k % rowsCT;
      coolingTower(K, M(X1 + 40 + R + c * (2 * R + 30)), M(zBoil0 + 20 - r * (2 * R + 30)), Hm);
    }
    eastX = X1 + 40 + perRow * (2 * R + 30);
    // raw water reservoir
    v.slab(M(X1 + 40), M(thD + 40), M(eastX - 30), M(thD + 110), 0, 0.3, C.water, 0.05, 3);
    for (let x = M(X1 + 39); x <= M(eastX - 29); x++) { v.set(x, 0, M(thD + 39), C.concreteDk, 0.05); v.set(x, 0, M(thD + 111), C.concreteDk, 0.05); }
  } else {
    const px0 = tx1 + 2, pz = M(thD / 2);
    building(v, px0, pz - 2, px0 + M(30), pz + 3, 0, M(14), C.cladLt, C.roof);                        // CW pump house
    const cx1 = px0 + M(260);
    v.slab(px0 + M(30) + 1, pz - 1, cx1, pz + 2, 0, 0.25, C.water, 0.05, 3);                             // intake channel
    v.slab(px0, pz + 6, cx1, pz + 9, 0, 0.25, C.waterLt, 0.05, 3);                                       // outfall
    for (let x = px0 + M(30) + 1; x <= cx1; x += 1) { v.set(x, 0, pz - 2, C.stoneDk, 0.1); v.set(x, 0, pz + 3, C.stoneDk, 0.1); }
    K.flow([[(px0 + 2) * vox, 0.3 * vox, (pz + 7.5) * vox], [cx1 * vox, 0.3 * vox, (pz + 7.5) * vox]], { mode: 'water', n: 24, size: vox * 0.7, speed: 8, colors: [C.foam, C.waterLt], spread: vox * 2, flat: 0.4 });
    eastX = X1 + 60;
  }

  // ash dyke north of the chimneys
  const ax0 = M(X0 + (X1 - X0) * 0.1), ax1 = M(X1 + 60), az1 = M(zChim - 40), az0 = az1 - M(lig ? 140 : 170);
  for (let x = ax0; x <= ax1; x++) for (const z of [az0, az1]) { v.set(x, 0, z, C.soil, 0.15); v.set(x, 1, z, C.soil, 0.15); }
  for (let z = az0; z <= az1; z++) for (const x of [ax0, ax1]) { v.set(x, 0, z, C.soil, 0.15); v.set(x, 1, z, C.soil, 0.15); }
  v.slab(ax0 + 1, az0 + 1, ax1 - 1, az1 - 1, 0, 1.4, (x, z) => (x - ax0) / (ax1 - ax0) + 0.3 * hash(x, z) > 0.75 ? 0x8fa3a0 : (hash(x, z, 1) > 0.5 ? C.ash : C.ashDk), 0.06, 3);
  // ash slurry pipes
  v.line([M(xs[0]), 0, M(zEsp0) - 1], [M(xs[0]), 0, az1 + 1], C.steelLt, 0.04);

  // site pad, roads, trees
  const px0 = Math.min(M(yardX0 ?? yardX1) - 6, ax0 - 4), px1 = Math.max(M(eastX) + 6, ax1 + 4), pz0 = az0 - 4, pz1 = syZ1 + 8;
  pad(v, px0, pz0, px1, pz1, 4);
  v.slab(px0, syZ0 - 3, px1, syZ0 - 2, 0, 0.14, C.road, 0.04, 4);
  for (let k = 0; k < 40; k++) {
    const x = Math.round(px0 + 2 + hash(k, 1) * (px1 - px0 - 4)), z = hash(k, 2) > 0.5 ? pz1 - 2 - Math.floor(hash(k, 3) * 3) : pz0 + 2 + Math.floor(hash(k, 3) * 3);
    if (!v.has(x, 0, z)) tree(v, x, z, vox < 5 ? 1 : 1);
  }
  return K.finish(kind, { h: topH * vox, focus: [(xs[0] + xs[n - 1]) / 2, zBun - maxD / 2], seaward: sea ? [1, 0] : null });
}

/* ------------------------------------------------------------------- mine */
// Open-cast pit: benches stepping up from the floor, overburden dumps, haul ramp with dumpers,
// bucket-wheel excavator (lignite) or shovel + dragline (coal), conveyor out of the pit.
function mineInto(K, x0, z0, x1, z1, o = {}) {
  const v = K.v, vox = K.vox;
  const W = x1 - x0, Dd = z1 - z0;
  const lig = o.lignite;
  const levels = o.levels || Math.max(4, Math.round(40 / vox));
  const bw = Math.max(2, Math.round(Math.min(W, Dd) * 0.07));
  const fx0 = x0 + levels * bw + 2, fx1 = x1 - levels * bw - 2, fz0 = z0 + levels * bw + 2, fz1 = z1 - levels * bw - 2;
  const seam = lig ? C.lignite : C.coal, seamHi = lig ? 0x57473a : C.coalHi;
  const hf = (x, z) => {
    const dx = Math.max(fx0 - x, x - fx1, 0), dz = Math.max(fz0 - z, z - fz1, 0);
    const d = Math.max(dx, dz);
    return d === 0 ? 1 : Math.min(levels + 1, 1 + Math.ceil(d / bw));
  };
  v.cols(x0, x1, z0, z1, hf, (x, y, z, top, h) => {
    if (h <= 2 || y <= 1) return top && hash(x, z) > 0.7 ? seamHi : seam;
    if (y === 2) return 0x6f6a60;
    if (top && h === levels + 1) return hash(x, z, 2) > 0.6 ? C.grassDk : 0x8b7a55;
    if (top) return hash(x, z, 3) > 0.85 ? 0x7d6a55 : 0x9a7a58;
    return y > levels - 1 ? C.laterite : (y % 2 ? 0x8f6f4c : 0x9d6445);
  }, 0.12);
  // sump water in a floor corner
  v.slab(fx0, fz0, fx0 + Math.floor((fx1 - fx0) * 0.18), fz0 + Math.floor((fz1 - fz0) * 0.3), 1, 0.25, 0x3f7f8f, 0.05, 2);
  // haul ramp: switchbacks up the east wall, dumpers along it
  const path = [];
  let x = fx1 - 2, z = fz1 - 1, y = 1;
  path.push([x, y, z]);
  for (let k = 0; k < levels; k++) {
    const nx = fx1 + (k + 1) * bw - Math.floor(bw / 2);
    const nz = k % 2 ? fz1 - 1 : fz0 + 1;
    path.push([nx, k + 2, nz]);
  }
  for (const [px, py, pz] of path) v.set(px, py, pz, 0xb5a58a, 0.05);
  K.flow(path.map(([a, b, c]) => [a * vox, b * vox, c * vox]), { mode: 'belt', n: 5, size: vox * 0.9, speed: 12, colors: [C.yellow, 0xe0b23a] });
  // conveyor out of the pit to the plant / CHP
  const cz = Math.round((fz0 + fz1) / 2), to = o.conveyorTo;
  const cp = [[fx0 + 2, 2, cz], [x1, levels + 3, cz]];
  if (to) cp.push([to[0], levels + 3, to[1]]);
  for (let i = 0; i < cp.length - 1; i++) v.line(cp[i], cp[i + 1], 0x6e6a64, 0.05);
  for (let i = 0; i < cp.length - 1; i++) {
    const a = cp[i], b = cp[i + 1], ns = Math.max(Math.abs(b[0] - a[0]), Math.abs(b[2] - a[2]));
    for (let k = 0; k <= ns; k += 5) { const xx = Math.round(a[0] + (b[0] - a[0]) * k / ns), yy = Math.round(a[1] + (b[1] - a[1]) * k / ns), zz = Math.round(a[2] + (b[2] - a[2]) * k / ns); for (let q = hf(xx, zz); q < yy; q++) v.set(xx, q, zz, C.steel, 0.04); }
  }
  K.flow(cp.map(([a, b, c]) => [a * vox, (b + 1) * vox, c * vox]), { n: 40, size: vox * 0.55, speed: 10, colors: [seam, seamHi], flat: 0.6 });
  // excavator on the floor
  const ex = Math.round(fx0 + (fx1 - fx0) * 0.55), ez = Math.round(fz0 + (fz1 - fz0) * 0.35);
  if (lig) {
    v.box(ex - 2, 1, ez - 1, ex + 2, 3, ez + 1, (xx, yy) => yy === 1 ? 0x3a3a3a : C.yellow, 0.06);
    v.box(ex - 1, 4, ez, ex + 1, 5, ez, 0xb9b3a6, 0.06);
    v.line([ex - 2, 4, ez], [ex - 8, 3, ez], C.orange, 0.05);
    v.line([ex + 2, 4, ez], [ex + 7, 3, ez], C.orange, 0.05);
    const cells = [];
    const R = 2.2 * vox;
    for (let a = 0; a < 12; a++) { const t = a / 12 * Math.PI * 2; cells.push([Math.cos(t) * R, Math.sin(t) * R, 0, a % 2 ? C.orange : 0x3a3a3a]); }
    K.spin(cells, [[(ex - 9) * vox, 3.5 * vox, ez * vox]], new THREE.Vector3(0, 0, 1), { rpm: 6, size: vox * 0.8 });
  } else {
    v.box(ex - 1, 1, ez - 1, ex + 1, 2, ez + 1, C.yellow, 0.06);
    v.set(ex + 1, 3, ez, 0x333333, 0.06);
    v.line([ex + 1, 3, ez], [ex + 5, 5, ez], C.yellow, 0.05);
    v.box(ex + 5, 3, ez, ex + 6, 4, ez, 0x3a3a3a, 0.06);
    // dragline on a bench
    const dx = fx0 - Math.floor(bw * 1.5), dz = Math.round((fz0 + fz1) / 2) - 4, dy = hf(dx, dz);
    v.box(dx - 1, dy, dz - 1, dx + 1, dy + 2, dz + 1, C.yellow, 0.06);
    v.line([dx, dy + 3, dz], [dx + 12, dy + 7, dz + 3], 0xb0561f, 0.05);
  }
  return { fx0, fx1, fz0, fz1, levels };
}

function mine(p) {
  const lig = /lignite/.test(lc(p.fuel?.primary || p.fuel)) || /neyveli|lignite|nlc/i.test(p.name || '');
  const area = +(p.structure?.area_ha) || 0;
  const side = clamp(area ? Math.sqrt(area) * 100 : 600, 400, 1200);
  const K = new Kit(side > 800 ? 8 : 6), vox = K.vox, v = K.v;
  const W = K.M(side), Dd = K.M(side * 0.75);
  const r = mineInto(K, 0, 0, W, Dd, { lignite: lig, levels: Math.round(48 / vox) });
  // coal handling plant: silos + rail loading loop east
  const sx = W + 6, sz = Math.round(Dd / 2);
  tank(v, sx, sz - 3, 2, K.M(40), C.concrete, C.concreteDk);
  tank(v, sx, sz + 3, 2, K.M(40), C.concrete, C.concreteDk);
  v.line([W, r.levels + 3, sz], [sx, K.M(40), sz], 0x6e6a64, 0.05);
  for (let z = -4; z <= Dd + 4; z++) v.set(sx + 4, 0, z, 0x5a5047, 0.05);
  for (let k = 0; k < 6; k++) v.box(sx + 4, 0, sz - 16 + k * 5, sx + 4, 1, sz - 13 + k * 5, C.wagon, 0.08);
  pad(v, -2, -2, W + 12, Dd + 2, 4, 0x8f8068);
  return K.finish('mine');
}

/* -------------------------------------------------------------------- gas */
function gas(p) {
  const name = `${p.name || ''} ${p.id || ''}`;
  const cap = +p.capacity_mw || 100;
  const open = /basin bridge|ocgt|open.?cycle|peaking/i.test(name) || p.structure?.open_cycle === true;
  const nGT = open ? ((p.units || []).length || clamp(Math.round(cap / 30), 1, 6)) : clamp(Math.round(cap / 150), 1, 4);
  const K = new Kit(3), v = K.v, M = m => K.M(m), vox = K.vox;
  const big = cap / nGT > 150;
  const L = M(big ? 42 : 30), Wd = M(big ? 14 : 11), gh = M(big ? 13 : 10);
  const pitch = M(open ? 34 : 60);
  let zTop = 0;
  for (let i = 0; i < nGT; i++) {
    const z0 = i * pitch, x0 = 0;
    building(v, x0, z0, x0 + L, z0 + Wd, 0, gh, 0xc9ccc8, 0x9aa0a4);                                    // GT enclosure
    building(v, x0 - M(12), z0 - 1, x0 - 1, z0 + Wd + 1, 0, M(20), 0x7b93a6, 0x5e6e7a, { stripes: 2, stripeC: 0x6a8193 });   // air filter house
    K.glow(x0 + 2, 1, z0 + Wd, GLOW_W);
    if (open) {
      const sx = x0 + L + M(6), sz = z0 + Math.floor(Wd / 2);
      v.box(x0 + L + 1, 0, sz - 1, sx - 1, M(8), sz + 1, C.steelLt, 0.05);
      chimney(K, sx, sz, 32, { bands: false, color: 0x8a8580, kind: 'heat', slim: true });
      zTop = Math.max(zTop, 32);
    } else {
      const hx0 = x0 + L + 1, hx1 = hx0 + M(30), hz0 = z0 - 2, hz1 = z0 + Wd + 2;
      v.box(hx0, 0, hz0, hx1, M(28), hz1, (x, y, z) => (x - hx0) % 3 === 0 ? C.steel : 0x8d9499, 0.05);  // HRSG
      chimney(K, hx1 + M(6), Math.floor((hz0 + hz1) / 2), 55, { bands: false, color: 0x8f8f8c, kind: 'heat', slim: true });
      zTop = 55;
    }
    trafo(K, x0 - M(18), z0 + Math.floor(Wd / 2), 1);
  }
  const zEnd = (nGT - 1) * pitch + Wd;
  if (!open) {
    building(v, 0, zEnd + M(20), L + M(20), zEnd + M(45), 0, M(26), C.cladLt, C.roof, { band: 0.6 });   // steam turbine hall
    // induced-draft cooling tower cells with fan stacks
    const cz0 = zEnd + M(60), cells = Math.max(3, nGT * 3);
    building(v, 0, cz0, cells * 4, cz0 + 4, 0, M(12), C.concreteLt, 0x7d7a73);
    for (let c = 0; c < cells; c++) {
      const cx = c * 4 + 2, cz = cz0 + 2;
      for (let x = -1; x <= 1; x++) for (let z = -1; z <= 1; z++) if (x || z) v.set(cx + x, M(12), cz + z, C.concreteDk, 0.05);
      v.set(cx, M(12) - 1, cz, 0x222222, 0);
      K.emit(cx * vox, (M(12) + 1) * vox, cz * vox, vox * 1.2, 'steam', { o: { n: 4, life: 6, sz: 0.8, rise: 8, drift: 6, grow: 1.2, spread: 0.6 } });
    }
  }
  // fuel: gas receiving station pipes + naphtha / HSD tanks
  const tx = -M(40);
  tank(v, tx, -M(25), M(10), M(14), C.white, 0xc9c9c4);
  tank(v, tx + M(28), -M(25), M(10), M(14), C.white, 0xc9c9c4);
  v.line([tx, 1, -M(10)], [L, 1, -M(10)], C.yellow, 0.04);
  v.line([tx, 2, -M(8)], [L, 2, -M(8)], 0xb0b6ba, 0.04);
  // switchyard
  const syX0 = -M(80), syX1 = -M(40);
  switchyard(K, syX0, 0, syX1, Math.max(M(60), zEnd), cap >= 300 ? 400 : 230);
  const padX1 = Math.max(L + M(open ? 25 : 60), 4 * Math.max(3, nGT * 3)) + 4;
  pad(v, syX0 - 4, -M(40), padX1, zEnd + M(open ? 24 : 80), 4);
  for (let k = 0; k < 16; k++) tree(v, syX0 - 2 + Math.floor(hash(k, 3) * (padX1 - syX0)), zEnd + M(open ? 20 : 76), 1);
  return K.finish('gas', { h: zTop });
}

/* ----------------------------------------------------------------- diesel */
function diesel(p) {
  const cap = +p.capacity_mw || 100;
  const nE = clamp((p.units || []).length || Math.round(cap / 18), 2, 10);
  const K = new Kit(3), v = K.v, M = m => K.M(m), vox = K.vox;
  const bay = M(14), L = nE * bay, Wd = M(30);
  building(v, 0, 0, L, Wd, 0, M(18), C.cream, 0x8a8f8c, { band: 0.55, bandC: C.glass });
  for (let x = 1; x < L; x += 3) K.glow(x, M(5), Wd, GLOW_W);
  for (let i = 0; i < nE; i++) {                                                   // radiators on the roof, a stack per engine
    const x = i * bay + Math.floor(bay / 2);
    v.box(x - 1, M(18), 2, x + 1, M(18), Wd - 8, 0x3f4549, 0.05);
    chimney(K, x, -3, 35, { bands: false, color: 0x7d746c, kind: 'dark', slim: true });
    v.box(x, M(8), -2, x, M(10), -1, C.steelLt, 0.05);
  }
  tank(v, -M(30), M(10), M(9), M(12), C.white, 0xc7c7c2);
  tank(v, -M(30), M(36), M(9), M(12), C.white, 0xc7c7c2);
  tank(v, -M(10), M(52), M(5), M(8), 0x8a8f94);
  switchyard(K, 0, Wd + M(20), L, Wd + M(60), 230);
  pad(v, -M(46), -M(20), L + 4, Wd + M(66), 4);
  return K.finish('diesel', { h: 35 });
}

/* ---------------------------------------------------------------- biomass */
// Sugar-mill cogeneration: mill house, boiler, chimney, bagasse yard with cane carrier, godowns,
// molasses tanks, cane trucks and fields.
function biomass(p) {
  const cap = +p.capacity_mw || 20;
  const K = new Kit(3), v = K.v, M = m => K.M(m), vox = K.vox;
  const s = clamp(Math.sqrt(cap / 20), 0.8, 1.8);
  const mL = M(70 * s), mW = M(30);
  building(v, 0, 0, mL, mW, 0, M(22), 0xcfc4a8, 0x8e6b52, { band: 0.55, bandC: 0x6a7a80 });            // mill house
  for (let x = 2; x < mL; x += 4) K.glow(x, M(8), mW, GLOW_W);
  const bx0 = mL + 2, bx1 = bx0 + M(24 * s);
  building(v, bx0, 0, bx1, M(24), 0, M(34 * s), C.clad, C.roof, { stripes: 3 });                       // boiler house
  for (let y = 3; y < M(30 * s); y += 3) K.glow(bx1, y, M(12));
  const stH = cap >= 15 ? 75 : 55;
  chimney(K, bx1 + M(12), M(12), stH, { kind: 'light', bands: stH >= 70, color: cap >= 15 ? C.concrete : 0x9a5a44 });
  for (let x = bx0 + 1; x < bx1; x += 3) K.emit(x * vox, M(34 * s) * vox + vox, M(6) * vox, vox, 'wisp');
  // bagasse yard + cane carrier
  const yx0 = bx0 - M(10), yx1 = bx1 + M(40), yz0 = M(50), yz1 = M(110);
  heap(v, yx0, yx1, yz0, yz1, M(12), C.bagasse, 0xd8c690);
  const cp = [[yx0 - 2, 1, yz0 + 4], [bx0 + 2, M(24), M(24) + 1]];
  v.line(cp[0], cp[1], 0x6e6a64, 0.05);
  K.flow(cp.map(([x, y, z]) => [x * vox, (y + 1) * vox, z * vox]), { n: 16, size: vox * 0.6, speed: 5, colors: [C.bagasse, 0xb9a36a], flat: 0.6 });
  // sugar godown, molasses tanks
  building(v, -M(10), M(45), M(40), M(75), 0, M(12), 0xd9d2c0, 0x8a8f8c);
  tank(v, -M(45), M(95), M(7), M(12), 0x6b4a33, 0x5a3d2a);
  tank(v, -M(25), M(95), M(7), M(12), 0x6b4a33, 0x5a3d2a);
  // cane trucks queued on the road
  for (let k = 0; k < 5; k++) {
    const x = -M(30) - k * 5;
    v.box(x, 0, M(20), x + 2, 1, M(20) + 1, k % 2 ? 0x5f8f3a : 0x6a9a44, 0.15);
    v.box(x + 3, 0, M(20), x + 3, 1, M(20) + 1, k % 2 ? 0xb03a2a : 0x2f5f9a, 0.08);
  }
  switchyard(K, bx1 + M(30), -M(30), bx1 + M(70), -M(4), 110);
  pad(v, -M(60), -M(40), yx1 + 4, yz1 + 4, 4);
  // cane fields around
  v.slab(-M(60), yz1 + 5, yx1 + 4, yz1 + 5 + M(60), 0, 0.5, (x, z) => ((x >> 2) + (z >> 3)) % 3 === 0 ? 0x7da347 : C.cane, 0.1, 2);
  return K.finish('biomass', { h: stH });
}

/* ---------------------------------------------------------------- nuclear */
function containment(K, cx, cz, R, Hc, domeH, wall, dome) {
  const v = K.v;
  for (let y = 0; y < Hc + domeH; y++) {
    const r = y < Hc ? R : R * Math.sqrt(Math.max(0, 1 - Math.pow((y - Hc + 1) / domeH, 2)));
    const ri = Math.ceil(r) + 1;
    for (let x = -ri; x <= ri; x++) for (let z = -ri; z <= ri; z++) {
      if (!inDisk(x, z, r)) continue;
      const nxt = y + 1 < Hc + domeH ? (y + 1 < Hc ? R : R * Math.sqrt(Math.max(0, 1 - Math.pow((y + 2 - Hc) / domeH, 2)))) : -1;
      if (!ringEdge(x, z, r) && inDisk(x, z, nxt)) continue;     // interior below a wider or equal level
      const c = y < Hc ? (y === Hc - 1 ? 0xb9bcbc : (y === 2 ? 0xa9aaa6 : wall)) : dome;
      v.set(cx + x, y, cz + z, c, 0.04);
    }
  }
}

function nuclear(p, kind) {
  const K = new Kit(3), v = K.v, M = m => K.M(m), vox = K.vox;
  const mws = unitList(p, kind === 'nuclear_vver' ? 1000 : 220, kind === 'nuclear_vver' ? [1000] : [700, 540, 500, 220, 160, 100]).slice(0, 6);
  const n = kind === 'nuclear_fbr' ? 1 : mws.length;
  const big = Math.max(...mws) >= 600;
  let xEnd = 0, top = 0;
  if (kind === 'nuclear_vver') {
    // AES-92 VVER-1000: square annex, cylindrical double containment with a shallow dome, turbine hall north
    const pitch = M(185);
    for (let i = 0; i < n; i++) {
      const cx = i * pitch, cz = 0;
      building(v, cx - M(38), cz - M(38), cx + M(38), cz + M(38), 0, M(22), 0xd9d6cc, 0xa7aaa8);
      for (let x = cx - M(36); x <= cx + M(36); x += 3) K.glow(x, M(15), cz + M(38), GLOW_B);
      containment(K, cx, cz, M(24), M(64), M(16), C.nukeW, 0xd3d6d6);
      building(v, cx - M(55), cz - M(38) - M(62), cx + M(55), cz - M(38) - 3, 0, M(42), 0xdadcd8, 0x8b9196, { band: 0.8, bandC: C.nukeBlue });
      for (let x = cx - M(52); x <= cx + M(52); x += 3) K.glow(x, M(18), cz - M(38) - M(62), GLOW_W);
      for (let k = -1; k <= 1; k++) K.emit((cx + k * M(30)) * vox, M(42) * vox + vox, (cz - M(38) - M(30)) * vox, vox * 1.5, 'steam', { o: { n: 5, life: 7, sz: 0.9, rise: 10, drift: 8, grow: 1.4, spread: 0.8 } });
      xEnd = cx;
    }
    top = 80;
    // ventilation stacks between the units
    const vx = n > 1 ? Math.round(pitch / 2) : M(70);
    chimney(K, vx, M(10), 100, { slim: true, kind: 'heat', color: 0xd0d0cc });
    // sea water intake: pump house, channel, breakwaters to the south
    const iz = M(90);
    building(v, -M(40), iz, xEnd + M(40), iz + M(20), 0, M(14), 0xd0d4d6, 0x7d8a93);
    v.slab(-M(60), iz + M(22), xEnd + M(60), iz + M(80), 0, 0.3, C.water, 0.05, 3);
    for (let z = iz + M(22); z <= iz + M(100); z++) { v.set(-M(60), 0, z, C.rock, 0.15); v.set(-M(60), 1, z, C.rockDk, 0.15); v.set(xEnd + M(60), 0, z, C.rock, 0.15); v.set(xEnd + M(60), 1, z, C.rockDk, 0.15); }
    K.flow([[xEnd * vox / 2, 0.3 * vox, (iz + M(50)) * vox]], { mode: 'churn', n: 18, size: vox * 1.1, spread: M(70) * vox, colors: [C.foam, C.waterLt] });
    // desalination + switchyard
    building(v, xEnd + M(90), -M(30), xEnd + M(140), M(20), 0, M(12), 0xd9d6cc, 0x7d8a93);
    switchyard(K, -M(40), -M(200), xEnd + M(40), -M(120), 400);
  } else if (kind === 'nuclear_phwr') {
    // Indian PHWR: concrete double containment with a shallow dome per unit, common 100 m stack
    const R = M(big ? 26 : 21), Hc = M(big ? 50 : 40), dh = M(big ? 12 : 10), pitch = M(big ? 120 : 95);
    for (let i = 0; i < n; i++) {
      const cx = i * pitch;
      containment(K, cx, 0, R, Hc, dh, 0xc4c1b8, 0xb6b4ad);
      building(v, cx - M(35), -R - M(58), cx + M(35), -R - 3, 0, M(32), 0xd7d3c6, 0x8b9196, { band: 0.7, bandC: C.glass });   // turbine building
      for (let x = cx - M(33); x <= cx + M(33); x += 3) K.glow(x, M(12), -R - M(58), GLOW_W);
      building(v, cx - R - 3, R - 2, cx + R + 3, R + M(18), 0, M(18), 0xcfcabb, 0x9aa0a4);                // service building
      for (let x = cx - R; x <= cx + R; x += 3) K.glow(x, M(10), R + M(18), GLOW_B);
      K.emit(cx * vox, (Hc + 1) * vox, (-R - M(30)) * vox, vox * 1.4, 'steam', { o: { n: 5, life: 7, sz: 0.9, rise: 10, drift: 8, grow: 1.4, spread: 0.8 } });
      xEnd = cx;
    }
    top = 100;
    chimney(K, Math.round(xEnd / 2), R + M(40), 100, { color: C.concrete });
    const iz = R + M(70);
    building(v, -R, iz, xEnd + R, iz + M(16), 0, M(12), 0xd0d4d6, 0x7d8a93);
    v.slab(-R - M(10), iz + M(18), xEnd + R + M(10), iz + M(80), 0, 0.3, C.water, 0.05, 3);
    K.flow([[xEnd * vox / 2, 0.3 * vox, (iz + M(45)) * vox]], { mode: 'churn', n: 14, size: vox, spread: M(70) * vox, colors: [C.foam, C.waterLt] });
    switchyard(K, -R - M(10), -R - M(160), xEnd + R + M(10), -R - M(90), 230);
  } else {
    // PFBR: rectangular reactor containment building, two steam-generator buildings, turbine hall, stack
    const rx = M(32), rz = M(30), rh = M(56);
    building(v, -rx, -rz, rx, rz, 0, rh, 0xcdc7b6, 0xa9a59a, { stripes: 6, stripeC: 0xbdb7a6 });
    v.box(-rx + 2, rh, -rz + 2, rx - 2, rh, rz - 2, 0xb8b3a6, 0.05);
    for (const sx of [-1, 1]) {
      const x0 = sx < 0 ? -rx - M(40) : rx + 2, x1 = sx < 0 ? -rx - 2 : rx + M(40);
      building(v, x0, -rz + M(8), x1, rz - M(8), 0, M(38), 0xd6d2c4, 0x8f959a, { band: 0.75 });
      for (let z = -rz + M(10); z < rz - M(10); z += 3) K.glow(sx < 0 ? x0 : x1, M(20), z, 0xffb070);
    }
    building(v, -M(60), -rz - M(70), M(60), -rz - M(10), 0, M(36), 0xdadcd8, 0x8b9196, { band: 0.7 });
    for (let x = -M(58); x <= M(58); x += 3) K.glow(x, M(12), -rz - M(70), GLOW_W);
    K.emit(0, M(36) * vox + vox, (-rz - M(40)) * vox, vox * 1.5, 'steam', { o: { n: 6, life: 7, sz: 0.9, rise: 10, drift: 8, grow: 1.4, spread: 0.8 } });
    chimney(K, rx + M(70), rz + M(30), 100, { color: C.concrete });
    top = 100;
    const iz = rz + M(80);
    building(v, -rx, iz, rx, iz + M(16), 0, M(12), 0xd0d4d6, 0x7d8a93);
    v.slab(-rx - M(20), iz + M(18), rx + M(20), iz + M(80), 0, 0.3, C.water, 0.05, 3);
    K.flow([[0, 0.3 * vox, (iz + M(45)) * vox]], { mode: 'churn', n: 12, size: vox, spread: M(60) * vox, colors: [C.foam, C.waterLt] });
    switchyard(K, -M(60), -rz - M(160), M(60), -rz - M(90), 230);
    xEnd = 0;
  }
  const b = v.bounds();
  pad(v, Math.floor(b.x0 / vox) - 6, Math.floor(b.z0 / vox) - 6, Math.ceil(b.x1 / vox) + 6, Math.ceil(b.z1 / vox) + 2, 4, 0xa59d88);
  for (let k = 0; k < 30; k++) tree(v, Math.floor(b.x0 / vox) - 4 + Math.floor(hash(k, 7) * ((b.x1 - b.x0) / vox + 8)), Math.floor(b.z0 / vox) - 4 + (k % 2), 1);
  return K.finish(kind, { h: top, focus: [xEnd * vox / 2, 0], seaward: [0, 1] });
}

/* ------------------------------------------------------------------ hydro */
function hills(v, x0, x1, z0, z1, hf, rockish = 0.25) {
  v.cols(x0, x1, z0, z1, hf, (x, y, z, top, h) => {
    if (!top) return hash(x, y, z) > 0.5 ? C.rock : 0x8a7560;
    if (hash(x, z, 5) < rockish * (h > 6 ? 1 : 0.3)) return C.rock;
    return hash(x, z, 6) > 0.7 ? C.grassDk : C.grass;
  }, 0.14);
}

function hydroDam(p) {
  const st = p.structure || {};
  const cap = +p.capacity_mw || 50;
  const Lm = clamp(+st.dam_len_m || (300 + cap * 2.5), 150, 2500), Hm = clamp(+st.dam_h_m || (35 + cap * 0.1), 15, 120);
  const K = new Kit(clamp(Math.round(Math.max(Lm / 220, Hm / 14)), 3, 8)), v = K.v, M = m => K.M(m), vox = K.vox;
  const L = M(Lm), H = Math.max(4, M(Hm)), half = Math.floor(L / 2);
  const baseW = Math.max(3, Math.round(H * 0.75)), topW = Math.max(1, M(8));
  const spW = Math.max(4, Math.round(L * 0.18)), spX0 = -Math.round(L * 0.15), spX1 = spX0 + spW;
  const crest = H - Math.max(1, M(6));
  // gravity dam, masonry; upstream face at z = 0, downstream slope to +z
  for (let x = -half; x <= half; x++) {
    const endK = Math.min(1, (half - Math.abs(x)) / Math.max(3, L * 0.08));
    const hx = Math.max(2, Math.round(H * (0.35 + 0.65 * endK)));
    const sp = x >= spX0 && x <= spX1;
    const hTop = sp ? Math.min(hx, crest) : hx;
    for (let y = 0; y < hTop; y++) {
      const w = Math.max(topW, Math.round(topW + (baseW - topW) * (1 - y / hx)));
      for (let z = 0; z < w; z++) {
        const face = z === w - 1 || z === 0 || y === hTop - 1;
        if (!face) continue;
        const c = y === hTop - 1 ? (sp ? 0xb9b4a8 : 0xc9c2b2) : sp && z === w - 1 ? 0xb9b4a8 : (y % 3 === 0 ? 0x8f8372 : (hash(x, y) > 0.8 ? 0xb3a58f : 0xa89a84));
        v.set(x, y, z, c, 0.1);
      }
    }
    if (!sp && x % 3 === 0) v.set(x, hx, 0, C.concreteLt, 0.05);          // parapet
    if (sp && (x - spX0) % 3 === 0) { for (let y = crest; y <= H; y++) v.set(x, y, 1, C.concrete, 0.05); v.set(x, H + 1, 1, C.concreteDk, 0.05); }
    else if (sp) v.set(x, crest + 1, 0, 0x4b4f55, 0.04);                   // gates
  }
  // spillway water down the downstream face (∝ load), stilling basin, river
  const riverZ1 = baseW + Math.min(45, M(Math.min(600, Lm * 0.4)));
  for (let k = 0; k < 6; k++) {
    const x = (spX0 + 1 + k * (spW - 2) / 5) * vox;
    K.flow([[x, crest * vox, 0.5 * vox], [x, crest * vox, topW * vox], [x, 0.2 * vox, baseW * vox], [x, 0.2 * vox, riverZ1 * vox * 0.6]], { mode: 'water', n: 10, size: vox * 0.8, speed: 22, colors: [C.foam, 0xcfe6f2, C.waterLt] });
  }
  v.slab(spX0 - 3, baseW, spX1 + 3, riverZ1, 0, 0.3, (x, z) => z < baseW + 4 ? C.waterLt : C.water, 0.06, 2);
  K.flow([[(spX0 + spX1) / 2 * vox, 0.3 * vox, (baseW + 3) * vox]], { mode: 'churn', n: 16, size: vox, spread: spW * vox, colors: [C.foam, 0xd8ecf5] });
  // powerhouse at the toe with penstocks
  const units = clamp((p.units || []).length || Math.round(cap / 30), 1, 6);
  const phX0 = spX1 + 6, phX1 = phX0 + Math.max(6, units * 3 + 2), phZ0 = baseW + 1, phZ1 = phZ0 + Math.max(4, M(25));
  building(v, phX0, phZ0, phX1, phZ1, 0, Math.max(3, M(22)), C.cream, 0x9a4a36, { band: 0.5, bandC: C.glass });
  for (let x = phX0 + 1; x < phX1; x += 2) K.glow(x, 1, phZ1, GLOW_W);
  for (let u = 0; u < units; u++) {
    const x = phX0 + 2 + u * 3;
    v.line([x, Math.round(H * 0.55), 0], [x, Math.max(3, M(22)), phZ0 - 1], C.rust, 0.06);
  }
  v.slab(spX1 + 4, phZ1 + 1, phX1, riverZ1, 0, 0.3, C.water, 0.06, 2);                              // tailrace joins the river
  K.flow([[(phX0 + phX1) / 2 * vox, 0.3 * vox, (phZ1 + 2) * vox]], { mode: 'churn', n: 12, size: vox * 0.8, spread: (phX1 - phX0) * vox, colors: [C.foam, 0xd8ecf5] });
  switchyard(K, phX1 + 3, phZ0, phX1 + 3 + Math.max(8, M(60)), phZ0 + Math.max(6, M(40)), 110);
  // reservoir (a diorama block of water) and the hills the dam ties into
  const resD = Math.max(8, Math.min(55, M(Math.min(900, Lm * 0.45))));
  v.slab(-half - 2, -resD, half + 2, -1, 0, H - 3, (x, z) => (hash(x, z) > 0.9 ? C.waterLt : C.water), 0.05, 6);
  const hillW = Math.max(8, Math.round(L * 0.07));
  hills(v, -half - hillW, -half + 1, -resD, riverZ1, (x, z) => Math.round(H * 1.15 * Math.min(1, (-half + 2 - x) / hillW * 1.6 + 0.35) - Math.max(0, z - baseW) * 0.15));
  hills(v, half - 1, half + hillW, -resD, riverZ1, (x, z) => Math.round(H * 1.15 * Math.min(1, (x - half + 2) / hillW * 1.6 + 0.35) - Math.max(0, z - baseW) * 0.15));
  // downstream banks
  v.slab(-half, baseW, half, riverZ1, -0.1, 0.1, (x, z) => (x < spX0 - 3 || x > phX1 + Math.max(8, M(60)) + 4) ? (hash(x, z) > 0.6 ? C.grassDk : C.grass) : null, 0.1, 6);
  return K.finish('hydro_dam', { centre: [0, 0], h: H * 1.2 * vox, focus: [(phX0 + phX1) / 2 * vox, (phZ0 + phZ1) / 2 * vox] });
}

function hydroRun(p) {
  const cap = +p.capacity_mw || 50;
  const K = new Kit(3), v = K.v, M = m => K.M(m), vox = K.vox;
  const units = clamp((p.units || []).length || Math.round(cap / 25), 1, 6);
  const hillH = M(clamp(60 + cap * 0.3, 60, 130)), W = M(240), Dz = M(200);
  // hill rising to the north (-z) with a ridge line
  const hf = (x, z) => {
    const t = clamp((-z - M(10)) / (Dz * 0.6), 0, 1);
    return Math.round(hillH * (t * t * (3 - 2 * t)) * (0.85 + 0.15 * Math.sin(x * 0.15)) + 1);
  };
  hills(v, -W / 2, W / 2, -Dz, 0, hf, 0.35);
  for (let k = 0; k < 60; k++) {
    const x = Math.round(-W / 2 + hash(k, 1) * W), z = Math.round(-Dz + hash(k, 2) * (Dz - M(30)));
    if (Math.abs(x) < units * 3 + 4) continue;
    const y = hf(x, z);
    v.set(x, y, z, C.tree, 0.2); v.set(x, y + 1, z, C.treeDk, 0.2);
  }
  // forebay / valve house at the top, surge tank, penstocks down the slope
  const zTop = -Math.round(Dz * 0.72), yTop = hf(0, zTop);
  building(v, -units * 2 - 3, zTop - 4, units * 2 + 3, zTop, yTop, 3, C.cream, 0x9a4a36);
  tank(v, units * 2 + 8, zTop - 2, 2, 0, C.concrete);
  for (let y = 0; y < 8; y++) for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) if (ringEdge(x, z, 2)) v.set(units * 2 + 8 + x, yTop + y, zTop - 2 + z, C.concrete, 0.05);
  const phZ0 = M(6), phZ1 = phZ0 + M(24);
  for (let u = 0; u < units; u++) {
    const x = -units * 2 + 1 + u * 4;
    let prev = null;
    for (let z = zTop + 1; z <= phZ0 - 1; z++) {
      const y = z < 0 ? hf(x, z) : Math.max(1, Math.round(M(12) * (1 - z / phZ0)));
      if (prev != null && prev - y > 1) for (let yy = y + 1; yy < prev; yy++) v.set(x, yy, z, C.rust, 0.06);
      v.set(x, y, z, C.rust, 0.06);
      if (z % 6 === 0) v.set(x, y - 1, z, C.concrete, 0.05);                 // anchor blocks
      prev = y;
    }
  }
  // powerhouse, tailrace, switchyard
  building(v, -units * 2 - 4, phZ0, units * 2 + 4, phZ1, 0, M(20), C.cream, 0x9a4a36, { band: 0.5, bandC: C.glass });
  for (let x = -units * 2 - 3; x < units * 2 + 4; x += 2) K.glow(x, 1, phZ1, GLOW_W);
  const tz1 = phZ1 + M(150);
  v.slab(-units * 2 - 1, phZ1 + 1, units * 2 + 1, tz1, 0, 0.3, C.water, 0.06, 2);
  v.slab(-W / 2, phZ1 + M(80), W / 2, phZ1 + M(110), 0, 0.3, C.water, 0.06, 3);                         // the river
  K.flow([[0, 0.3 * vox, (phZ1 + 1) * vox], [0, 0.3 * vox, (phZ1 + M(95)) * vox], [W / 2 * vox, 0.3 * vox, (phZ1 + M(95)) * vox]], { mode: 'water', n: 30, size: vox * 0.7, speed: 10, colors: [C.foam, C.waterLt], spread: vox * 3, flat: 0.5 });
  K.flow([[0, 0.3 * vox, (phZ1 + 3) * vox]], { mode: 'churn', n: 10, size: vox * 0.8, spread: units * 4 * vox, colors: [C.foam] });
  switchyard(K, units * 2 + 8, phZ0, units * 2 + 8 + M(60), phZ0 + M(45), 110);
  v.slab(-W / 2, 1, W / 2, tz1, -0.1, 0.1, (x, z) => (hash(x, z) > 0.6 ? C.grassDk : C.grass), 0.1, 4);
  return K.finish('hydro_run', { centre: [0, -M(60) * vox], focus: [0, (phZ0 + phZ1) / 2 * vox] });
}

function pumped(p) {
  const K = new Kit(4), v = K.v, M = m => K.M(m), vox = K.vox;
  const Hh = M(90), W = M(420), Dz = M(360);
  const rz0 = -M(320), rz1 = -M(140), rx0 = -M(150), rx1 = M(120);
  const hf = (x, z) => {
    const inRes = x > rx0 && x < rx1 && z > rz0 && z < rz1;
    const t = clamp((-z - M(40)) / M(90), 0, 1);
    const base = Math.round(Hh * (t * t * (3 - 2 * t)));
    return inRes ? Math.max(1, base - M(12)) : base + (base > 2 && hash(x, z) > 0.93 ? 1 : 0);
  };
  hills(v, -W / 2, W / 2, -Dz, 0, hf, 0.2);
  // upper reservoir water and the dam on its south lip
  v.slab(rx0 + 1, rz0 + 1, rx1 - 1, rz1 - 1, Hh - M(14), M(10), (x, z) => hash(x, z) > 0.92 ? C.waterLt : C.water, 0.05, 4);
  for (let x = rx0; x <= rx1; x++) for (let y = Hh - M(16); y <= Hh + 1; y++) v.set(x, y, rz1, (x % 4 === 0 ? C.concreteDk : C.stone), 0.1);
  for (let x = rx0; x <= rx1; x += 2) v.set(x, Hh + 2, rz1, C.concreteLt, 0.05);
  // intake tower + surge shaft on the slope
  const sx = M(40), sz = rz1 + M(40), sy = hf(sx, sz);
  for (let y = 0; y < M(30); y++) for (let x = -3; x <= 3; x++) for (let z = -3; z <= 3; z++) if (ringEdge(x, z, 2.6)) v.set(sx + x, sy + y, sz + z, C.concrete, 0.05);
  v.slab(sx - 2, sz - 2, sx + 2, sz + 2, sy + M(30) - 2.2, 0.2, C.waterDk, 0.05, 1);
  building(v, rx0 + M(20), rz1 - M(20), rx0 + M(40), rz1 - 2, Hh - M(14), M(22), C.concrete, C.concreteDk);
  // tunnel portal at the hill foot, access road, lower pond with churn
  const pz = -M(40);
  v.box(-3, 0, pz - 1, 3, 4, pz, (x, y) => (Math.abs(x) <= 1 && y <= 2) ? 0x151515 : C.concrete, 0.05);
  v.slab(-2, pz + 1, 2, M(120), 0, 0.14, C.road, 0.04, 2);
  v.slab(-M(200), M(60), -M(20), M(150), 0, 0.3, C.water, 0.05, 3);
  K.flow([[-M(110) * vox, 0.3 * vox, M(70) * vox]], { mode: 'churn', n: 16, size: vox, spread: M(120) * vox, colors: [C.foam, C.waterLt] });
  K.flow([[sx * vox, (sy + M(30) - 2) * vox, sz * vox]], { mode: 'churn', n: 6, size: vox * 0.6, spread: 3 * vox, colors: [C.foam] });
  switchyard(K, M(30), M(20), M(170), M(110), 400);
  building(v, M(30), -M(20), M(90), M(5), 0, M(14), C.cream, 0x9a4a36, { band: 0.5, bandC: C.glass });
  for (let x = M(31); x < M(90); x += 2) K.glow(x, 1, M(5), GLOW_W);
  v.slab(-W / 2, 1, W / 2, M(160), -0.1, 0.1, (x, z) => (hash(x, z) > 0.6 ? C.grassDk : C.grass), 0.1, 4);
  return K.finish('pumped_storage', { centre: [0, -M(100) * vox] });
}

/* ------------------------------------------------------------------- wind */
function rotorCells(R, vox, colour = 0xeef0f1) {
  const cells = [], seen = new Set();
  const add = (x, y, c) => { const k = `${Math.round(x / vox)},${Math.round(y / vox)}`; if (seen.has(k)) return; seen.add(k); cells.push([Math.round(x / vox) * vox, Math.round(y / vox) * vox, 0, c]); };
  for (let b = 0; b < 3; b++) {
    const a = Math.PI / 2 + b * Math.PI * 2 / 3, dx = Math.cos(a), dy = Math.sin(a);
    for (let s = vox; s <= R; s += vox * 0.5) {
      const chord = Math.max(vox * 0.6, R * 0.09 * (s < R * 0.25 ? s / (R * 0.25) : 1 - 0.75 * (s - R * 0.25) / (R * 0.75)));
      for (let c = -chord / 2; c <= chord / 2; c += vox * 0.5) add(dx * s - dy * c, dy * s + dx * c, s > R * 0.86 ? 0xc8403a : colour);
    }
  }
  for (let x = -1; x <= 1; x++) for (let y = -1; y <= 1; y++) add(x * vox * 0.6, y * vox * 0.6, 0xdfe2e4);
  return cells;
}

function turbineInto(K, x, z, hub, rotor, lattice) {
  const v = K.v, vox = K.vox, H = Math.round(hub / vox);
  if (lattice) {
    for (let y = 0; y < H; y++) {
      const k = Math.max(1, Math.round((H - y) / H * 3));
      for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) v.set(x + sx * k, y, z + sz * k, C.steelLt, 0.05);
      if (y % 3 === 0) for (let i = -k; i <= k; i++) { v.set(x + i, y, z + k, C.steelLt, 0.05); v.set(x + i, y, z - k, C.steelLt, 0.05); v.set(x + k, y, z + i, C.steelLt, 0.05); v.set(x - k, y, z + i, C.steelLt, 0.05); }
    }
  } else {
    const rb = Math.max(0.6, 2.2 / vox), rt = Math.max(0.5, 1.3 / vox);
    for (let y = 0; y < H; y++) {
      const r = rb + (rt - rb) * y / H, ri = Math.ceil(r) + 1;
      for (let i = -ri; i <= ri; i++) for (let j = -ri; j <= ri; j++) if (inDisk(i, j, r)) v.set(x + i, y, z + j, y < 2 ? 0x7da86a : 0xeceeef, 0.03);
    }
    v.box(x - 2, 0, z - 2, x + 2, 0, z + 2, C.concrete, 0.05);
  }
  // nacelle, rotor faces +z (south-west monsoon side)
  const nl = Math.max(2, Math.round(9 / vox)), nw = Math.max(1, Math.round(1.6 / vox));
  v.box(x - nw, H, z - nl + 1, x + nw, H + nw * 2, z + 1, 0xe3e5e6, 0.04);
  return [x * vox, (H + nw) * vox + vox / 2, (z + 2) * vox];
}

function windTurbine(p) {
  const st = p.structure || {};
  const hub = +st.hub_h_m || 65, rotor = +st.rotor_d_m || (hub >= 90 ? 100 : hub >= 75 ? 82 : 64);
  const K = new Kit(rotor > 80 ? 1.5 : 1), vox = K.vox;
  const hubPos = turbineInto(K, 0, 0, hub, rotor, hub < 45);
  K.spin(rotorCells(rotor / 2, vox), [hubPos], new THREE.Vector3(0, 0, 1), { rpm: hub < 45 ? 40 : 20, size: vox });
  // transformer kiosk
  K.v.box(4, 0, 3, 5, 1, 4, 0xd9d6cc, 0.05);
  return K.finish('wind_turbine', { centre: [0, 0], h: hub + rotor / 2 });
}

function windFarm(p) {
  const st = p.structure || {};
  const cap = +p.capacity_mw || 50;
  const hub = +st.hub_h_m || 70, rotor = +st.rotor_d_m || (hub >= 90 ? 100 : hub >= 75 ? 82 : 64);
  const n = clamp(+st.turbines || Math.round(cap / 1.5), 3, 12);
  const K = new Kit(2), v = K.v, vox = K.vox;
  const sp = Math.round(rotor * 3.2 / vox), cols = Math.ceil(Math.sqrt(n * 1.6)), pivots = [];
  for (let i = 0; i < n; i++) {
    const c = i % cols, r = Math.floor(i / cols);
    const x = Math.round((c - (cols - 1) / 2) * sp + (r % 2) * sp / 2 + (hash(i, 1) - 0.5) * sp * 0.3);
    const z = Math.round((r - (Math.ceil(n / cols) - 1) / 2) * sp * 1.4 + (hash(i, 2) - 0.5) * sp * 0.3);
    const h = hub * (0.9 + 0.2 * hash(i, 3));
    pivots.push(turbineInto(K, x, z, h, rotor, false));
    v.slab(x - 4, z - 4, x + 4, z + 4, -0.05, 0.1, 0xb49b73, 0.08, 3);                           // crane hardstand
  }
  K.spin(rotorCells(rotor / 2, vox), pivots, new THREE.Vector3(0, 0, 1), { rpm: 18, size: vox });
  // pooling substation
  const b = v.bounds();
  switchyard(K, Math.round(b.x1 / vox) + 6, -10, Math.round(b.x1 / vox) + 26, 8, 110);
  return K.finish('wind_farm', { centre: [0, 0], h: hub * 1.1 + rotor / 2 });
}

/* ------------------------------------------------------------------ solar */
function solar(p) {
  const st = p.structure || {};
  const cap = +p.capacity_mw || 50;
  const area = +st.area_ha || cap * 1.8;
  const side = clamp(Math.sqrt(area) * 100, 200, 1400);
  const K = new Kit(side > 700 ? 4 : 2), v = K.v, vox = K.vox;
  const W = Math.round(side / vox), Dz = Math.round(side * 0.7 / vox);
  const pitch = Math.max(4, Math.round(Dz / 55)), seg = Math.max(6, Math.round(W / 14));
  const blocks = 4, bw = Math.floor(W / blocks);
  const panelMat = MAT.clone();
  const pm = new Voxels(vox), glints = [];
  for (let z = 2; z < Dz - 2; z += pitch) {
    for (let x = 0; x < W; x += seg) {
      if (x % bw < 2) continue;                                   // access roads between blocks
      const w = Math.min(seg - 1, W - x);
      // fixed tilt facing south (+z): back row higher, front row lower, stepped
      pm.block(x + w / 2, 0.35, z + 0.5, w, 0.3, 1, C.panel, 0.05);
      pm.block(x + w / 2, 0.75, z - 0.5, w, 0.3, 1, 0x2c4770, 0.05);
      pm.block(x + w / 2, 1.0, z - 1, w, 0.12, 0.3, C.panelFr, 0.04);             // top frame edge
      if (hash(x, z) > 0.55) glints.push([x + w / 2, 0.95, z]);
    }
  }
  const pmesh = pm.mesh(panelMat);
  pmesh.name = 'panels';
  K.extra.push(pmesh);
  // inverter stations per block, pooling substation, roads, fence
  for (let bx = 0; bx < blocks; bx++) for (let bz = 0; bz < 2; bz++) v.box(bx * bw + 1, 0, Math.round(Dz * (0.25 + bz * 0.5)), bx * bw + 1, 1, Math.round(Dz * (0.25 + bz * 0.5)) + 1, 0xe5e3dc, 0.04);
  for (let bx = 0; bx < blocks; bx++) v.slab(bx * bw, 0, bx * bw + 1, Dz, -0.05, 0.12, 0xb8a27c, 0.06, 4);
  for (let x = -1; x <= W; x += 2) { v.set(x, 0, -1, 0x80868b, 0.04); v.set(x, 0, Dz, 0x80868b, 0.04); }
  for (let z = -1; z <= Dz; z += 2) { v.set(-1, 0, z, 0x80868b, 0.04); v.set(W, 0, z, 0x80868b, 0.04); }
  switchyard(K, W + 3, Math.round(Dz / 2) - 10, W + 3 + Math.round(60 / vox), Math.round(Dz / 2) + 10, 230);
  v.slab(-1, -1, W, Dz, -0.1, 0.1, (x, z) => hash(x, z) > 0.5 ? 0xb49b73 : 0xa89070, 0.08, 6);
  // glints: a band of bright panels sweeping with the sun
  const gm = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const gl = new THREE.InstancedMesh(BOX, gm, Math.max(1, glints.length));
  glints.forEach((g, i) => { gl.setMatrixAt(i, ZERO); gl.setColorAt(i, new THREE.Color(0xfff6d8)); });
  gl.name = 'glint'; gl.frustumCulled = false;
  K.extra.push(gl);
  K.fns.push((t, L) => {
    const sun = sunAt(t);
    panelMat.color.setScalar(0.35 + 0.65 * sun.day);
    const band = ((sun.h - 6) / 12.5) * (W + Dz) + Math.sin(t * 0.2) * 3;
    glints.forEach(([x, y, z], i) => {
      const d = Math.abs(x + z * 0.6 - band);
      const on = sun.day > 0.2 && d < (W + Dz) * 0.06 && hash(i, Math.floor(t * 2)) < 0.5 + 0.5 * L;
      gl.setMatrixAt(i, on ? _m.makeScale(vox * 1.6, vox * 0.12, vox * 0.5).setPosition(x * vox, y * vox, z * vox) : ZERO);
    });
    gl.instanceMatrix.needsUpdate = true;
  });
  const g = K.finish('solar_farm', { h: 4 });
  g.userData.instances += pmesh.count + glints.length;
  return g;
}

/* ------------------------------------------------------------- substation */
function substation(p) {
  const kv = +(p.voltage_kv || p.kv || p.max_kv || 230);
  const K = new Kit(kv >= 400 ? 2 : 1.5), v = K.v, M = m => K.M(m);
  const W = M(kv >= 765 ? 360 : kv >= 400 ? 260 : kv >= 220 ? 170 : 110), Dz = Math.round(W * 0.6);
  const hG = switchyard(K, 0, 0, W, Dz, kv);
  const nT = kv >= 400 ? 4 : kv >= 220 ? 3 : 2;
  const tz = Dz + M(14);
  for (let i = 0; i < nT; i++) {
    const x = Math.round((i + 0.5) * W / nT);
    trafo(K, x, tz, kv >= 400 ? 3 : 2);
    v.box(x - 5, 0, tz - 5, x - 5, 4, tz + 5, 0x9a968c, 0.05);           // fire walls
    K.blink(x + 1, (kv >= 400 ? 3 : 2) + 2, tz, i % 2 ? 0x6dff7a : 0xff5040, 0.5);
  }
  // control room
  const cx0 = M(10), cz0 = tz + M(20);
  building(v, cx0, cz0, cx0 + M(40), cz0 + M(18), 0, M(8), C.cream, 0x9a4a36, { band: 0.5, bandC: C.glass });
  for (let x = cx0 + 1; x < cx0 + M(40); x += 3) K.glow(x, 2, cz0 + M(18), GLOW_W);
  K.blink(cx0 + M(40) + 1, M(8), cz0, 0x6dff7a, 0.8);
  pad(v, -3, -3, W + 3, cz0 + M(24), 4, C.dust);
  return K.finish('substation', { blinkRate: 3 });
}

/* ------------------------------------------------------------------- pylon */
// Lattice tower by voltage class. The line runs along local Z; cross-arms reach along ±X.
// userData.arms: conductor attach points (bottom of insulator strings), userData.earth: earth-wire peaks.
export function buildPylon(kv = 400) {
  kv = +kv || 400;
  const cls = kv >= 700 ? 765 : kv >= 380 ? 400 : kv >= 200 ? 230 : 110;
  // h: peak; base: leg spread; waist: body width at the lowest arm; arms: [height, reach] per level
  const spec = {
    765: { h: 55, base: 15, waist: 5, top: 34, arms: null },
    400: { h: 46, base: 11, waist: 2.2, top: 40, arms: [[26, 8], [33, 9], [40, 8]], ins: 4 },
    230: { h: 35, base: 8, waist: 1.8, top: 30, arms: [[20, 5.5], [25, 6.5], [30, 5.5]], ins: 2.6 },
    110: { h: 25, base: 5.5, waist: 1.4, top: 21, arms: [[13.5, 3.8], [17.5, 4.5], [21, 3.8]], ins: 1.6 },
  }[cls];
  const vox = cls >= 400 ? 1 : cls >= 230 ? 0.75 : 0.5;
  const K = new Kit(vox), v = K.v, M = m => Math.round(m / vox);
  const steel = 0xa4abb1, g = 0.05, ins = C.insGlass, ins2 = 0x3f6a5c;
  const H = M(spec.h), bodyTop = M(spec.top), yW = M(cls === 765 ? spec.top : spec.arms[0][0]);
  const half = y => y <= yW ? Math.round(M(spec.base / 2) + (M(spec.waist / 2) - M(spec.base / 2)) * y / yW) : Math.max(1, M(spec.waist / 2));
  // legs
  for (let y = 0; y <= bodyTop; y++) { const k = half(y); for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) v.set(sx * k, y, sz * k, steel, g); }
  // faces: single zig-zag diagonals, a horizontal at each panel joint
  let flip = 1;
  for (let y0 = 0; y0 < bodyTop;) {
    const k0 = half(y0), y1 = Math.min(bodyTop, y0 + Math.max(M(4), Math.round(k0 * 1.8))), k1 = half(y1);
    for (const s of [1, -1]) {
      v.line([-flip * k0, y0, s * k0], [flip * k1, y1, s * k1], steel, g);
      v.line([s * k0, y0, -flip * k0], [s * k1, y1, flip * k1], steel, g);
    }
    if (y1 <= yW) for (let i = -k1; i <= k1; i++) { v.set(i, y1, k1, steel, g); v.set(i, y1, -k1, steel, g); v.set(k1, y1, i, steel, g); v.set(-k1, y1, i, steel, g); }
    flip = -flip; y0 = y1;
  }
  const arms = [], earth = [];
  const string = (x, y, L) => { for (let i = 1; i <= L; i++) v.set(x, y - i, 0, i % 2 ? ins : ins2, 0.03); return [x * vox, (y - L - 0.5) * vox, 0]; };
  const arm = (y, reach, s) => {
    const k = half(y), tip = s * M(reach);
    v.line([s * k, y, k], [tip, y, 0], steel, g); v.line([s * k, y, -k], [tip, y, 0], steel, g);        // bottom chords (triangle in plan)
    v.line([s * k, y + Math.max(2, M(reach * 0.4)), 0], [tip, y, 0], steel, g);                         // top chord
  };
  if (cls === 765) {
    // delta (horizontal) configuration: outer phases on a wide cross-arm, middle phase higher in the
    // V-frame window, two earth-wire peaks
    const ya = bodyTop, k = half(ya), reach = 17, L = M(5);
    for (const s of [1, -1]) { arm(ya, reach, s); v.line([s * k, ya, k], [s * k, ya, -k], steel, g); }
    for (let x = -M(reach); x <= M(reach); x++) { v.set(x, ya, k, steel, g); v.set(x, ya, -k, steel, g); }
    const tw = M(9);
    for (const s of [1, -1]) for (const z of [k, -k]) v.line([s * k, ya, z], [s * tw, H, z], steel, g);
    const ym = Math.round(ya + (H - ya) * 0.62);
    const wm = Math.round(k + (tw - k) * 0.62);
    for (let x = -wm; x <= wm; x++) { v.set(x, ym, k, steel, g); v.set(x, ym, -k, steel, g); }
    arms.push(string(-M(reach), ya, L), string(0, ym, L), string(M(reach), ya, L));
    for (const s of [1, -1]) { v.set(s * tw, H + 1, 0, steel, g); v.set(s * tw, H, 0, steel, g); earth.push([s * tw * vox, (H + 1.5) * vox, 0]); }
    for (let x = -tw; x <= tw; x++) { v.set(x, H, k, steel, g); v.set(x, H, -k, steel, g); }
  } else {
    // double circuit, vertical: three cross-arms each side, an earth-wire peak on top
    const L = M(spec.ins);
    const left = [], right = [];
    for (const [ya, reach] of spec.arms) {
      const y = M(ya);
      for (const s of [1, -1]) arm(y, reach, s);
      left.push(string(-M(reach), y, L)); right.push(string(M(reach), y, L));
    }
    // peak above the top arm
    const kt = half(bodyTop);
    for (let y = bodyTop; y <= H; y++) { const k = Math.max(0, Math.round(kt * (1 - (y - bodyTop) / (H - bodyTop + 1)))); for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) v.set(sx * k, y, sz * k, steel, g); }
    const ew = M(spec.arms[2][1] * 0.45);
    v.line([-ew, H - 1, 0], [ew, H - 1, 0], steel, g);
    for (const s of [1, -1]) { v.set(s * ew, H, 0, steel, g); earth.push([s * ew * vox, (H + 0.5) * vox, 0]); }
    arms.push(...left, ...right);
  }
  // concrete chimneys (foundations) under the legs
  const k0 = half(0);
  for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) v.box(sx * k0, 0, sz * k0, sx * k0, 0, sz * k0, C.concrete, 0.05);
  const grp = K.finish('pylon', { centre: [0, 0], h: spec.h });
  // arms: left circuit bottom -> top, then right circuit bottom -> top (765: west, middle, east)
  grp.userData.arms = arms;
  grp.userData.earth = earth;
  grp.userData.kv = cls;
  grp.userData.anim = () => {};
  return grp;
}

/* ----------------------------------------------------------------- vessels */
// Bow points +X. To head along a compass bearing θ (clockwise from north): rotation.y = π/2 − θ.
function hullInto(v, Lc, Bc, Fc, hullC, bootC) {
  for (let x = -Lc / 2; x <= Lc / 2; x++) {
    const bowT = (x - (Lc / 2 - Bc * 1.2)) / (Bc * 1.2), sternT = (-Lc / 2 + 2 - x) / 2;
    const w = Math.round(Bc / 2 * (bowT > 0 ? Math.sqrt(Math.max(0, 1 - bowT * bowT)) : sternT > 0 ? 1 - sternT * 0.3 : 1));
    for (let z = -w; z <= w; z++) for (let y = 0; y < Fc; y++) {
      const edge = Math.abs(z) === w || x === -Lc / 2 || x >= Lc / 2 - 1 || y === Fc - 1;
      if (!edge) continue;
      v.set(x, y, z, y === Fc - 1 && Math.abs(z) < w ? C.deck : (y === 0 ? bootC : hullC), 0.06);
    }
    if (bowT > 0.2) for (let z = -w; z <= w; z++) v.set(x, Fc, z, hullC, 0.06);           // raised forecastle
  }
}

function vessel(kind) {
  const lng = kind === 'lng_tanker';
  const K = new Kit(lng ? 4 : 3), v = new Voxels(K.vox), vox = K.vox;
  const Lc = Math.round((lng ? 290 : 225) / vox), Bc = Math.round((lng ? 46 : 32) / vox), Fc = Math.round((lng ? 14 : 8) / vox);
  hullInto(v, Lc - (Lc % 2), Bc, Fc, lng ? C.navy : C.hull, C.hullRed);
  const aft = -Lc / 2 + 2;
  // superstructure aft with funnel
  const sw = Math.round(Bc * 0.4), sh = Math.round((lng ? 22 : 20) / vox);
  v.box(aft, Fc, -sw, aft + Math.round(14 / vox), Fc + sh, sw, (x, y, z) => (y === Fc + sh - 2 ? 0x2d3f55 : C.superW), 0.04);
  for (let z = -sw - 2; z <= sw + 2; z++) v.set(aft + Math.round(14 / vox), Fc + sh - 1, z, C.superW, 0.04);   // bridge wings
  v.box(aft - 1, Fc + sh - 3, -1, aft + 1, Fc + sh + 2, 1, (x, y) => y > Fc + sh ? 0x1d1d1d : (y === Fc + sh ? C.red : (lng ? C.superW : 0xd9d0c0)), 0.05);
  if (lng) {
    // Moss spheres: four domes standing half out of the deck, with skirts
    const R = Math.round(19 / vox);
    for (let k = 0; k < 4; k++) {
      const cx = Math.round(aft + Math.round(20 / vox) + R + k * (2 * R + 1));
      for (let y = 0; y <= R; y++) {
        const r = Math.sqrt(Math.max(0, R * R - y * y)), ri = Math.ceil(r);
        for (let x = -ri; x <= ri; x++) for (let z = -ri; z <= ri; z++) if (inDisk(x, z, r)) v.set(cx + x, Fc + y, z, y > R * 0.35 ? 0xe9e3d3 : 0xd6cdb7, 0.04);
      }
      for (let x = -R; x <= R; x += 2) v.set(cx + x, Fc, 0, 0x6d6d6d, 0.04);
    }
    v.line([Lc / 2 - 3, Fc + 1, 0], [Lc / 2 - 3, Fc + Math.round(18 / vox), 0], C.yellow, 0.04);
  } else {
    // hatch covers and four deck cranes
    const nh = 7, hl = Math.round(14 / vox), hs = Math.floor((Lc - Math.round(34 / vox)) / nh);
    for (let k = 0; k < nh; k++) {
      const x0 = Math.round(aft + Math.round(18 / vox) + k * hs), hw = Math.round(Bc * 0.32);
      v.box(x0, Fc, -hw, x0 + hl - 1, Fc, hw, C.hatch, 0.06);
      if (k % 2 === 1 && k < nh - 1) {
        const cx = x0 + hl + Math.floor((hs - hl) / 2);
        for (let y = Fc; y < Fc + Math.round(14 / vox); y++) v.set(cx, y, 0, C.yellow, 0.05);
        v.line([cx, Fc + Math.round(12 / vox), 0], [cx + Math.round(18 / vox), Fc + Math.round(18 / vox), Math.round(Bc * 0.2)], C.yellow, 0.05);
      }
    }
  }
  const swell = new THREE.Group();
  swell.name = 'swell';
  swell.rotation.order = 'YXZ';
  const hm = v.mesh();
  swell.add(hm);
  K.extra.push(swell);
  // wake behind the stern ∝ load (speed)
  for (const s of [-1, 1]) K.flow([[aft * vox, 0.2 * vox, s * Bc * 0.3 * vox], [(aft - Math.round(80 / vox)) * vox, 0.2 * vox, s * Bc * 0.9 * vox]], { mode: 'water', n: 12, size: vox, speed: 12, colors: [C.foam, 0xcfe5f0], flat: 0.4 });
  K.fns.push((t, L) => {
    swell.position.y = Math.sin(t * 0.8) * vox * 0.25;
    swell.rotation.z = Math.sin(t * 0.55) * 0.012;
    swell.rotation.x = Math.sin(t * 0.7 + 1) * 0.02;
  });
  const g = K.finish(kind, { centre: [0, 0], h: (Fc + sh + 2) * vox });
  g.userData.instances += hm.count;
  g.userData.length = Lc * vox;
  g.userData.radius = Lc * vox / 2;
  return g;
}

/* ------------------------------------------------------------------- train */
// Coal rake: WAG-9 electric loco + BOXN wagons heaped with coal. Front points +X, origin at the
// middle of the train. userData.cars = [{obj, offset}] for the layer to bend the rake along a route
// (offset = metres behind the front).
function train(p) {
  const nW = clamp(+(p && p.wagons) || 12, 2, 58);
  const vox = 1, K = new Kit(vox);
  const cars = [], wheelPivots = [];
  const wl = 11, ll = 20;
  const total = ll + 1 + nW * (wl + 1);
  const mk = (len, fn) => {
    const v = new Voxels(vox); fn(v); const m = v.mesh(); const g = new THREE.Group(); g.add(m); return { g, n: m.count };
  };
  let x = total / 2, inst = 0;
  const loco = mk(ll, v => {
    v.box(-ll / 2, 1, -1, ll / 2 - 1, 3, 1, (xx, y, z) => (y === 2 ? C.locoCream : C.loco), 0.05);
    v.box(-ll / 2 + 1, 4, -1, ll / 2 - 2, 4, 1, 0x4a4f55, 0.05);
    v.box(ll / 2 - 1, 1, -1, ll / 2 - 1, 3, 1, (xx, y) => y === 3 ? 0x28323c : C.loco, 0.05);    // cab front + windscreen
    v.box(-ll / 2, 3, -1, -ll / 2, 3, 1, 0x28323c, 0.05);
    v.line([-3, 5, 0], [0, 6, 0], 0x333333); v.line([0, 6, 0], [2, 5, 0], 0x333333);             // pantograph
    v.box(-ll / 2 + 1, 0, -1, -ll / 2 + 4, 0, 1, 0x2a2a2a); v.box(ll / 2 - 5, 0, -1, ll / 2 - 2, 0, 1, 0x2a2a2a);
  });
  loco.g.position.x = x - ll / 2; cars.push({ obj: loco.g, offset: 0 }); inst += loco.n;
  for (const bx of [-ll / 2 + 1.5, -ll / 2 + 3.5, ll / 2 - 4.5, ll / 2 - 2.5]) for (const s of [-1.5, 1.5]) wheelPivots.push([x - ll / 2 + bx, 0.5, s]);
  x -= ll + 1;
  for (let i = 0; i < nW; i++) {
    const w = mk(wl, v => {
      v.box(-wl / 2, 1, -1, wl / 2 - 1, 3, 1, (xx, y, z) => (Math.abs(z) === 1 || xx === -wl / 2 || xx === wl / 2 - 1 || y === 1) ? ((xx + 11) % 3 === 0 ? 0x6a3b29 : C.wagon) : null, 0.1);
      for (let xx = -wl / 2 + 1; xx < wl / 2 - 1; xx++) { v.set(xx, 3, 0, C.coal, 0.3); if (Math.abs(xx) < 3) v.set(xx, 4, 0, C.coalHi, 0.3); }
      v.box(-wl / 2 + 1, 0, -1, -wl / 2 + 2, 0, 1, 0x2a2a2a); v.box(wl / 2 - 3, 0, -1, wl / 2 - 2, 0, 1, 0x2a2a2a);
    });
    w.g.position.x = x - wl / 2; cars.push({ obj: w.g, offset: total / 2 - x }); inst += w.n;
    for (const bx of [-wl / 2 + 1, -wl / 2 + 2, wl / 2 - 3, wl / 2 - 2]) for (const s of [-1.5, 1.5]) wheelPivots.push([x - wl / 2 + bx, 0.5, s]);
    x -= wl + 1;
  }
  for (const c of cars) K.extra.push(c.obj);
  K.spin([[0, 0, 0, 0x1c1c1c], [0.35, 0, 0, 0x9aa0a5]], wheelPivots, new THREE.Vector3(0, 0, 1), { rpm: -120, size: 0.45 });
  K.v.set(Math.round(total / 2), 0, 0, 0x5a5047); K.v.set(-Math.round(total / 2), 0, 0, 0x5a5047);
  const g = K.finish('coal_train', { centre: [0, 0], h: 6 });
  g.userData.instances += inst;
  g.userData.length = total;
  g.userData.cars = cars;
  g.userData.radius = total / 2;
  return g;
}

/* ------------------------------------------------------------- dispatcher */
export function archetypeFor(p) {
  if (!p) return 'coal';
  const t = lc(p.type || p.kind);
  if (ARCHETYPES.includes(t)) return t;
  const name = `${p.name || ''} ${(p.aliases || []).join(' ')} ${p.id || ''}`.toLowerCase();
  const fuel = lc(typeof p.fuel === 'string' ? p.fuel : p.fuel?.primary);
  const st = p.structure || {};
  if (t === 'nuclear' || fuel === 'uranium' || fuel === 'thorium') {
    if (/kudankulam|koodankulam|kknpp|vver/.test(name)) return 'nuclear_vver';
    if (/pfbr|breeder|bhavini|fbtr|\bfbr\b/.test(name)) return 'nuclear_fbr';
    return 'nuclear_phwr';
  }
  if (t === 'pumped_storage' || /pumped|\bpsp\b|kadamparai/.test(name)) return 'pumped_storage';
  if (t === 'hydro' || t === 'small_hydro' || fuel === 'water') {
    if (+st.dam_h_m >= 25 || /\bdam\b|barrage|kattalai|weir|anicut|vaigai|sathanur|amaravathi|krishnagiri|lower bhavani|periyar dam/.test(name) || (+p.capacity_mw > 0 && +p.capacity_mw < 12)) return 'hydro_dam';
    return 'hydro_run';
  }
  if (t === 'wind' || fuel === 'wind') return (+st.turbines > 1 || +p.capacity_mw > 5 || /farm|park|belt/.test(name)) ? 'wind_farm' : 'wind_turbine';
  if (t === 'solar' || fuel === 'sun' || fuel === 'solar') return 'solar_farm';
  if (/biomass|cogen|bagasse|waste|sugar|msw/.test(t + ' ' + fuel) || /sugar|cogen/.test(name)) return 'biomass';
  if (t === 'diesel' || /diesel|hsd|lshs|hfo|lsfo/.test(fuel) || /diesel|\bdg\b|\bdgpp\b/.test(name)) return 'diesel';
  if (t === 'gas' || /gas|lng|naphtha/.test(fuel) || /\bgt\b|gas|ccpp|combined cycle|\bgtpp\b/.test(name)) return 'gas';
  if (t === 'substation' || t === 'battery' || (p.voltage_kv && !t)) return 'substation';
  if (t === 'mine' || t === 'coal_mine' || t === 'lignite_mine') return 'mine';
  if (/ship|bulk|vessel/.test(t)) return 'coal_ship';
  if (/tanker|lng_ship/.test(t)) return 'lng_tanker';
  if (/train|rake|rail/.test(t)) return 'coal_train';
  if (t === 'pylon' || t === 'tower') return 'pylon';
  if (fuel === 'lignite' || t === 'lignite' || (/neyveli|lignite|barsingsar|giral|akrimota|bhavnagar|surat lig|kutch lig|\bnlc\b|taqa/.test(name) && !/ntpl|tuticorin/.test(name))) return 'lignite';
  return 'coal';
}

export function buildAsset(archetype, params = {}) {
  const p = params || {};
  switch (archetype) {
    case 'coal': return thermal(p, 'coal');
    case 'lignite': return thermal(p, 'lignite');
    case 'gas': return gas(p);
    case 'diesel': return diesel(p);
    case 'biomass': return biomass(p);
    case 'nuclear_vver': case 'nuclear_phwr': case 'nuclear_fbr': return nuclear(p, archetype);
    case 'hydro_dam': return hydroDam(p);
    case 'hydro_run': return hydroRun(p);
    case 'pumped_storage': return pumped(p);
    case 'wind_turbine': return windTurbine(p);
    case 'wind_farm': return windFarm(p);
    case 'solar_farm': return solar(p);
    case 'substation': return substation(p);
    case 'pylon': { const g = buildPylon(p.voltage_kv || p.kv || 400); return g; }
    case 'coal_ship': case 'lng_tanker': return vessel(archetype);
    case 'coal_train': return train(p);
    case 'mine': return mine(p);
    default: return thermal(p, 'coal');
  }
}
