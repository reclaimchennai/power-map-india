// three.js custom layer for MapLibre: the power fleet in voxels.
//
//  * Pillars (every station, any zoom): a translucent shell whose height is the installed
//    capacity and a solid core whose height is yesterday's average output (energy ÷ 24 h).
//    Sized in screen pixels so the whole fleet reads from India scale down to a district.
//  * Smoke: square pixel puffs from every burning station, count and size by output, blown
//    along the live Open-Meteo wind at that site. Gone when the station is idle.
//  * Models (z >= 10.5): the real-scale voxel model of each station in view (models.js),
//    animated by its load: smoke, steam, spinning rotors, spillway water.
//  * Turbines: every OpenStreetMap wind turbine in Tamil Nadu as an instanced voxel tower with a
//    rotor that turns at the statewide wind output and faces the live wind.
//
// Coordinates follow ~/projects/lighthouses/web/js/layer3d.js: the scene is re-centred on the map
// centre every frame (float32), world x = metres east, y = metres SOUTH (Mercator's direction),
// z = metres up. Never mirror with a negative scale (MapLibre's matrix already carries the
// reflection; three would flip winding again and cull every face).
import * as THREE from 'three';
import { fuel } from './fuels.js?v=3';

let MODELS = null;
const modelsReady = import('./models.js?v=2').then(m => { MODELS = m; return m; })
  .catch(e => { console.warn('models.js unavailable, pillars only', e); return null; });

const hash = s => { let h = 2166136261; for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619); return ((h >>> 0) % 10000) / 10000; };
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const PUFFS = 9;

const SMOKE_VERT = /* glsl */`
  attribute float aSize; attribute float aAlpha; attribute vec3 aColor;
  uniform float uPx;
  varying float vAlpha; varying vec3 vColor;
  void main(){
    vAlpha = aAlpha; vColor = aColor;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * uPx;
  }`;
// square pixels, alpha posterized to 4 steps with a 4×4 ordered dither (the lighthouse beams' recipe)
const SMOKE_FRAG = /* glsl */`
  varying float vAlpha; varying vec3 vColor;
  float bayer2(vec2 a){ a = floor(a); return fract(dot(a, vec2(0.5, a.y * 0.75))); }
  float bayer4(vec2 a){ return bayer2(0.5 * a) * 0.25 + bayer2(a); }
  void main(){
    float a = floor(clamp(vAlpha, 0.0, 1.0) * 4.0 + bayer4(gl_FragCoord.xy)) / 4.0;
    if (a <= 0.0) discard;
    gl_FragColor = vec4(vColor, a * 0.85);
  }`;

export class PowerLayer {
  constructor(ml, plants) {
    this.id = 'power-3d';
    this.type = 'custom';
    this.renderingMode = '3d';
    this.ml = ml;
    this.plants = plants;
    this.live = {};                 // plant id -> live record (export_live.py)
    this.weather = null;
    this.stateLoad = {};            // fuel -> 0..1 statewide (TN SLDC), for stations without their own figure
    this.show = new Set();          // fuels on
    this.visible = { smoke: true, models: true, turbines: true };
    this.selected = null;
    this.mapDark = false;
    this.t0 = performance.now();
    this.turbinePts = null;
  }

  merc(lon, lat) { return this.ml.MercatorCoordinate.fromLngLat([lon, lat], 0); }
  local(lon, lat) {
    const m = this.merc(lon, lat);
    return [(m.x - this.origin.x) / this.s, (m.y - this.origin.y) / this.s];
  }

  /* ------------------------------------------------------------ live data */
  setLive(now) {
    this.live = now?.plants || {};
    const w = now?.weather;
    this.weather = w ? { grid: w.grid, vars: w.vars, cells: w.cells } : null;
    for (const e of this.entries || []) e.wind = this.windAt(e.p.lat, e.p.lon);
    this.map?.triggerRepaint();
  }
  setStateLoad(obj) { this.stateLoad = obj || {}; }
  windAt(lat, lon) {
    const w = this.weather;
    if (!w) return null;
    const g = w.grid, key = `${(Math.round(lat / g) * g).toFixed(1)},${(Math.round(lon / g) * g).toFixed(1)}`;
    const v = w.cells[key];
    if (!v) return null;
    const o = {};
    w.vars.forEach((k, i) => { o[k] = v[i]; });
    return o;
  }
  // time machine: {plant id: load 0..1} for a past day replaces yesterday's figures
  setDay(loads) { this.dayLoads = loads; this.map?.triggerRepaint(); }
  load(e) {
    if (this.dayLoads) { const v = this.dayLoads[e.p.id]; return v == null ? null : clamp(v, 0, 1); }
    const l = this.live[e.p.id];
    if (l && l.lf != null) return clamp(l.lf, 0, 1);
    const s = this.stateLoad[e.p.type];
    if (e.p.state === 'Tamil Nadu' && s != null) return clamp(s, 0, 1);
    return null;
  }
  setFilter(set) { this.show = set; this.map?.triggerRepaint(); }
  setVisible(v) { Object.assign(this.visible, v); this.map?.triggerRepaint(); }
  select(id) { this.selected = id; this.map?.triggerRepaint(); }

  /* ------------------------------------------------------- theme and sun */
  // pillar colours follow the basemap under them: the light fuel steps on the day map, dark steps at night
  paint() {
    if (!this.core) return;
    const dim = new THREE.Color(), grey = new THREE.Color(this.mapDark ? 0x5d6480 : 0x9aa0b0), white = new THREE.Color(0xffffff);
    for (const e of this.entries) {
      e.col.set(this.mapDark ? e.f.dark : e.f.light);
      this.core.setColorAt(e.i, e.col);
      // planned / under construction / retired: a greyed shell, never an output core
      const live = !e.p.status || e.p.status === 'operating';
      this.shell.setColorAt(e.i, live ? dim.copy(e.col).multiplyScalar(this.mapDark ? 0.7 : 0.85) : dim.copy(e.col).lerp(grey, 0.75));
      this.cap.setColorAt(e.i, dim.copy(e.col).lerp(white, 0.55));
    }
    for (const m of [this.core, this.shell, this.cap]) if (m.instanceColor) m.instanceColor.needsUpdate = true;
    this.shell.material.opacity = this.mapDark ? 0.38 : 0.5;
  }
  // smoke: pale on the night map, a darker grey by day so it reads against the cream basemap
  paintSmoke() {
    if (!this.smoke) return;
    const a = this.smoke.geometry.attributes.aColor, c = new THREE.Color();
    for (const e of this.entries) {
      c.setHex(e.f.smoke || 0xcccccc);
      if (!this.mapDark) c.multiplyScalar(0.62);
      for (let k = 0; k < PUFFS; k++) a.array.set([c.r, c.g, c.b], (e.i * PUFFS + k) * 3);
    }
    a.needsUpdate = true;
  }
  setMapTheme(dark) {
    if (this.mapDark === dark) return;
    this.mapDark = dark;
    this.paint(); this.paintSmoke();
    this.map?.triggerRepaint();
  }
  // sun: altitude/azimuth (degrees) over the map centre; below the horizon a dim bluish moonlight
  setSun(alt, az) {
    if (!this.sunLight) return;
    const a = Math.max(alt, 4) * Math.PI / 180, z = az * Math.PI / 180;
    // world x east, y SOUTH, z up
    this.sunLight.position.set(Math.sin(z) * Math.cos(a), -Math.cos(z) * Math.cos(a), Math.sin(a));
    const day = clamp((alt + 6) / 18, 0, 1);
    this.sunLight.color.set(day > 0.5 ? 0xfff1dc : 0xffc58a).lerp(new THREE.Color(0x9fb4e0), 1 - day);
    // by day the pillars must read in their fuel colours on the cream map: strong sky fill, softer sun
    this.sunLight.intensity = 0.5 + 1.3 * day;
    this.hemi.intensity = 0.9 + 1.9 * day;
    this.hemi.color.set(day > 0.5 ? 0xffffff : 0xc4d4ea);
  }

  /* ------------------------------------------------------------------ add */
  onAdd(map, gl) {
    this.map = map;
    this.origin = this.merc(80.0, 16.0);
    this.s = this.origin.meterInMercatorCoordinateUnits();
    this.camera = new THREE.Camera();
    this.scene = new THREE.Scene();
    this.world = new THREE.Group();
    this.scene.add(this.world);
    this.hemi = new THREE.HemisphereLight(0xc4d4ea, 0x2a2118, 1.6);
    this.sunLight = new THREE.DirectionalLight(0xfff1dc, 2.0);
    this.sunLight.position.set(0.5, 0.6, 1.0);           // replaced by setSun(): the real sun over the map centre
    this.scene.add(this.hemi, this.sunLight);

    this.entries = this.plants.map((p, i) => {
      const [x, y] = this.local(p.lon, p.lat);
      const f = fuel(p.type);
      return { p, i, xy: [x, y], k: this.merc(p.lon, p.lat).meterInMercatorCoordinateUnits() / this.s,
               col: new THREE.Color(this.mapDark ? f.dark : f.light), f, seed: hash(p.id), elev: 0 };
    });

    // pillars: base at z = 0
    const box = new THREE.BoxGeometry(1, 1, 1);
    box.translate(0, 0, 0.5);
    const n = this.entries.length;
    this.shell = new THREE.InstancedMesh(box, new THREE.MeshLambertMaterial({ transparent: true, opacity: 0.38, depthWrite: false }), n);
    this.core = new THREE.InstancedMesh(box, new THREE.MeshLambertMaterial({}), n);
    this.cap = new THREE.InstancedMesh(box, new THREE.MeshBasicMaterial({ color: 0xffffff }), n);
    for (const m of [this.shell, this.core, this.cap]) { m.frustumCulled = false; m.instanceMatrix.setUsage(THREE.DynamicDrawUsage); }
    this.paint();
    this.shell.renderOrder = 2;
    this.world.add(this.core, this.cap, this.shell);

    // smoke puffs
    const np = n * PUFFS;
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(np * 3), 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aSize', new THREE.BufferAttribute(new Float32Array(np), 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aAlpha', new THREE.BufferAttribute(new Float32Array(np), 1).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('aColor', new THREE.BufferAttribute(new Float32Array(np * 3), 3));
    this.px = { value: map.getPixelRatio ? map.getPixelRatio() : 1 };
    this.smoke = new THREE.Points(g, new THREE.ShaderMaterial({
      vertexShader: SMOKE_VERT, fragmentShader: SMOKE_FRAG, transparent: true, depthWrite: false,
      uniforms: { uPx: this.px },
    }));
    this.smoke.frustumCulled = false;
    this.smoke.renderOrder = 4;
    this.world.add(this.smoke);
    this.paintSmoke();

    this.models = new THREE.Group();
    this.world.add(this.models);
    this.turbines = new THREE.Group();
    this.world.add(this.turbines);

    this.renderer = new THREE.WebGLRenderer({ canvas: map.getCanvas(), context: gl, antialias: false });
    this.renderer.autoClear = false;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    if (this.turbinePts) this.buildTurbines(this.turbinePts);
    if (this.routeData) modelsReady.then(() => this.setRoutes(this.routeData));
  }

  /* ------------------------------------------------------------- turbines */
  // pts: [[lon, lat, hub_m?, rotor_m?], ...] from OSM generator:source=wind
  setTurbines(pts) {
    this.turbinePts = pts;
    if (this.scene) this.buildTurbines(pts);
  }
  buildTurbines(pts) {
    this.turbines.clear();
    const V = 4;                                       // metres per voxel (tower 80 m = 20 blocks)
    const tower = [], blades = [];
    const addBox = (arr, x, y, z, sx = 1, sy = 1, sz = 1) => {
      const b = new THREE.BoxGeometry(V * sx, V * sy, V * sz);
      b.translate(x * V, y * V, z * V);
      arr.push(b);
    };
    for (let z = 0; z < 20; z++) addBox(tower, 0, 0, z + 0.5, z < 6 ? 1.5 : 1, z < 6 ? 1.5 : 1);
    addBox(tower, 0, 0.6, 20.3, 1.4, 2.6, 1.2);        // nacelle, rotor faces -y before yaw
    for (let b = 0; b < 3; b++) {                        // three blades in the x-z plane, hub at origin
      const a = b * Math.PI * 2 / 3;
      for (let r = 1; r <= 9; r++) {
        const bx = new THREE.BoxGeometry(V * (r < 3 ? 1.1 : 0.8), V * 0.5, V);
        bx.translate(0, 0, r * V);
        bx.rotateY(a);
        blades.push(bx);
      }
    }
    const merge = arr => {
      const g = new THREE.BufferGeometry();
      let n = 0; for (const a of arr) n += a.attributes.position.count;
      const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3);
      const idx = []; let o = 0;
      for (const a of arr) {
        const ai = a.index.array;
        for (let i = 0; i < ai.length; i++) idx.push(ai[i] + o);
        pos.set(a.attributes.position.array, o * 3);
        nor.set(a.attributes.normal.array, o * 3);
        o += a.attributes.position.count;
      }
      g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
      g.setAttribute('normal', new THREE.BufferAttribute(nor, 3));
      g.setIndex(idx);
      return g;
    };
    const tg = merge(tower), bg = merge(blades);
    const n = pts.length;
    this.tw = new THREE.InstancedMesh(tg, new THREE.MeshLambertMaterial({ color: 0xe9ecef }), n);
    this.bl = new THREE.InstancedMesh(bg, new THREE.MeshLambertMaterial({ color: 0xf6f7f8 }), n);
    for (const m of [this.tw, this.bl]) { m.frustumCulled = false; m.instanceMatrix.setUsage(THREE.DynamicDrawUsage); }
    this.tEntries = pts.map((q, i) => {
      const [x, y] = this.local(q[0], q[1]);
      return { i, xy: [x, y], lon: q[0], lat: q[1], k: this.merc(q[0], q[1]).meterInMercatorCoordinateUnits() / this.s,
               hub: q[2] || 80, rot: q[3] || 76, ph: hash(`${q[0]},${q[1]}`) * 6.28, spin: 0,
               wind: this.windAt(q[1], q[0]) };
    });
    this.turbines.add(this.tw, this.bl);
  }

  /* --------------------------------------------------------------- movers */
  // Coal ships, LNG tankers and coal trains running the documented supply routes, at one simulated
  // hour per second (a 1,000 km coastal leg at 12 knots takes ~45 s). Sized up at far zoom so a
  // ship reads as ~26 px.
  setRoutes(routes) {
    this.routeData = routes;
    if (!this.scene || !MODELS) return;
    if (!this.movers) { this.movers = new THREE.Group(); this.world.add(this.movers); }
    for (const o of [...this.movers.children]) this.movers.remove(o);
    this.moverList = [];
    const SPEED = { sea: 22, rail: 40 };          // km/h
    for (const r of routes) {
      if (!SPEED[r.mode] || r.coords.length < 2) continue;
      const pts = r.coords.map(([lo, la]) => { const [x, y] = this.local(lo, la); return { x, y, k: this.merc(lo, la).meterInMercatorCoordinateUnits() / this.s }; });
      const cum = [0];
      for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y) / pts[i].k);
      const Lm = cum.at(-1);
      if (Lm < 2000) continue;
      const arch = r.mode === 'rail' ? 'coal_train' : /lng|gas/i.test(r.cargo || '') ? 'lng_tanker' : 'coal_ship';
      const n = Math.max(1, Math.min(4, Math.round(Lm / 350e3)));
      for (let j = 0; j < n; j++) {
        let m;
        try { m = MODELS.buildAsset(arch, {}); } catch { continue; }
        m.rotation.x = Math.PI / 2;
        const holder = new THREE.Group();
        holder.add(m);
        this.movers.add(holder);
        this.moverList.push({ holder, m, pts, cum, Lm, period: (Lm / 1000) / SPEED[r.mode], off: j / n + hash(r.id) * 0.3,
                              len: m.userData.length || (arch === 'coal_train' ? 700 : 230), route: r });
      }
    }
  }
  placeMovers(t, zoom, mpp0) {
    if (!this.moverList) return;
    const on = this.visible.feed !== false && zoom >= 4.5;
    this.movers.visible = on;
    if (!on) return;
    for (const mv of this.moverList) {
      const u = ((t / mv.period) + mv.off) % 1, d = u * mv.Lm;
      let i = 1; while (i < mv.cum.length - 1 && mv.cum[i] < d) i++;
      const a = mv.pts[i - 1], b = mv.pts[i], f = (d - mv.cum[i - 1]) / Math.max(1, mv.cum[i] - mv.cum[i - 1]);
      const x = a.x + (b.x - a.x) * f, y = a.y + (b.y - a.y) * f;
      const lat = mv.route.coords[i][1];
      const ex = Math.max(1, (26 * mpp0 * Math.cos(lat * Math.PI / 180)) / mv.len) * a.k;
      mv.holder.position.set(x, y, 0);
      mv.holder.rotation.z = Math.atan2(b.y - a.y, b.x - a.x);     // bow (+X) along the route; world y is south
      mv.holder.scale.setScalar(ex);
      mv.m.userData.anim?.(t, 0.7);
    }
  }

  /* ---------------------------------------------------------- pylons/wires */
  // lines: [{kv, coords: [[lon, lat], ...]}] for the lines in view. Towers go on every vertex and every
  // SPAN metres between (OSM routes are simplified, so vertices alone would skip straight runs);
  // conductors sag between the model's own arm points (models.buildPylon userData.arms).
  setSpans(lines, detail = false) {
    this.spanLines = lines;
    if (!this.scene || !MODELS?.buildPylon) return;
    if (!this.pylons) { this.pylons = new THREE.Group(); this.world.add(this.pylons); this.pylonKit = {}; }
    for (const o of [...this.pylons.children]) { this.pylons.remove(o); o.geometry?.dispose(); }
    const SPAN = { 765: 450, 400: 380, 230: 320, 110: 260 };
    const cls = kv => kv >= 700 ? 765 : kv >= 380 ? 400 : kv >= 200 ? 230 : 110;
    const towers = { 765: [], 400: [], 230: [], 110: [] };
    const wires = [];
    for (const ln of lines) {
      const c = cls(ln.kv), span = SPAN[c], pts = [];
      const xy = ln.coords.map(([lo, la]) => [...this.local(lo, la), la]);
      for (let i = 0; i < xy.length - 1; i++) {
        const [x0, y0, la] = xy[i], [x1, y1] = xy[i + 1];
        const k = this.merc(ln.coords[i][0], la).meterInMercatorCoordinateUnits() / this.s;   // world units per metre
        const L = Math.hypot(x1 - x0, y1 - y0) / k, n = Math.max(1, Math.round(L / span));
        for (let j = 0; j < n; j++) pts.push([x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n, k]);
      }
      const last = xy.at(-1);
      pts.push([last[0], last[1], pts.at(-1)?.[2] || 1]);
      if (pts.length < 2) continue;
      const tw = pts.map((p, i) => {
        const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)];
        const th = Math.atan2(b[1] - a[1], b[0] - a[0]) - Math.atan2(-1, 0);     // model +Z (-> north) turned onto the line
        return { x: p[0], y: p[1], k: p[2], th };
      });
      towers[c].push(...tw);
      wires.push({ c, tw });
    }
    const M = new THREE.Matrix4(), R = new THREE.Matrix4().makeRotationX(Math.PI / 2), Z = new THREE.Matrix4(), S = new THREE.Matrix4();
    const wirePos = [];
    for (const c of [765, 400, 230, 110]) {
      const list = towers[c];
      if (!list.length) continue;
      const kit = this.pylonKit[c] ||= bakePylon(MODELS.buildPylon(c));
      const im = new THREE.InstancedMesh(kit.geom, kit.mat, list.length);
      im.frustumCulled = false;
      list.forEach((t, i) => {
        M.makeTranslation(t.x, t.y, 0).multiply(Z.makeRotationZ(t.th)).multiply(R).multiply(S.makeScale(t.k, t.k, t.k));
        im.setMatrixAt(i, M);
        t.m = M.clone();
      });
      this.pylons.add(im);
    }
    // conductors: 8 segments per span, parabolic sag ~2.5% of the span
    const v0 = new THREE.Vector3(), v1 = new THREE.Vector3();
    for (const { c, tw } of wires) {
      const all = this.pylonKit[c]?.arms || [];
      // far: the top conductor each side (3 wires read as a band at this zoom); near: every phase + earth
      const arms = detail ? all : all.filter(a => Math.abs(a[1] - Math.max(...all.filter(b => Math.sign(b[0]) === Math.sign(a[0])).map(b => b[1]))) < 0.01 && a[0] !== 0);
      for (let i = 0; i < tw.length - 1; i++) {
        const a = tw[i], b = tw[i + 1];
        const L = Math.hypot(b.x - a.x, b.y - a.y), sag = Math.min(14 * a.k, L * 0.025);
        for (const arm of arms) {
          v0.set(...arm).applyMatrix4(a.m); v1.set(...arm).applyMatrix4(b.m);
          let px = v0.x, py = v0.y, pz = v0.z;
          for (let s2 = 1; s2 <= 8; s2++) {
            const f = s2 / 8, x = v0.x + (v1.x - v0.x) * f, y = v0.y + (v1.y - v0.y) * f, z = v0.z + (v1.z - v0.z) * f - sag * 4 * f * (1 - f);
            wirePos.push(px, py, pz, x, y, z);
            px = x; py = y; pz = z;
          }
        }
      }
    }
    if (wirePos.length) {
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(wirePos), 3));
      const w = new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: 0x6d767f, transparent: true, opacity: detail ? 0.75 : 0.5 }));
      w.frustumCulled = false;
      this.pylons.add(w);
    }
    this.map?.triggerRepaint();
  }

  /* --------------------------------------------------------------- models */
  buildModel(e) {
    if (!MODELS || e.model || e.failed) return;
    try {
      const arch = MODELS.archetypeFor(e.p);
      const m = MODELS.buildAsset(arch, e.p);
      m.rotation.x = Math.PI / 2;                        // model Y-up -> world Z-up: (x, y, z) -> (x, -z, y)
      // the pin marks the main block (boilers / reactor), not the site's bounding-box centre
      const [fx, fz] = m.userData.focus || [0, 0];
      m.position.set(-fx, fz, 0);
      const holder = new THREE.Group();
      holder.add(m);
      // turn sea-cooled layouts so their seaward side faces the real coast (plants.json "sea" = compass bearing)
      const sw = m.userData.seaward;
      if (sw && e.p.sea != null) {
        const b = e.p.sea * Math.PI / 180, target = Math.atan2(-Math.cos(b), Math.sin(b));   // world angle, y south
        const own = Math.atan2(-sw[1], sw[0]);                    // model (x, z) -> world (x, -z)
        holder.rotation.z = target - own;
      } else holder.rotation.z = (e.p.heading || 0) * Math.PI / 180;
      holder.position.set(e.xy[0], e.xy[1], 0);
      holder.userData = m.userData || {};
      e.model = holder;
      e.arch = arch;
      this.models.add(holder);
    } catch (err) {
      console.warn('model failed', e.p.id, err);
      e.failed = true;
    }
  }
  dropModel(e) {
    if (!e.model) return;
    this.models.remove(e.model);
    e.model.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material && o.material.dispose) o.material.dispose(); });
    e.model = null;
  }

  /* ---------------------------------------------------------------- render */
  render(gl, args) {
    const t = (performance.now() - this.t0) / 1000;
    const map = this.map, zoom = map.getZoom();
    const c = map.getCenter();
    const cm = this.merc(c.lng, c.lat);
    this.world.position.set((this.origin.x - cm.x) / this.s, (this.origin.y - cm.y) / this.s, 0);
    const mm = args?.defaultProjectionData?.mainMatrix || args?.modelViewProjectionMatrix || args;
    const m4 = new THREE.Matrix4().fromArray(mm);
    const l = new THREE.Matrix4().makeTranslation(cm.x, cm.y, 0).scale(new THREE.Vector3(this.s, this.s, this.s));
    this.camera.projectionMatrix = m4.multiply(l);
    this.px.value = map.getPixelRatio ? map.getPixelRatio() : 1;

    const mpp0 = 40075016.686 / (512 * Math.pow(2, zoom));      // metres per CSS px at the equator
    const terrain = !!map.getTerrain?.();
    const canvas = map.getCanvas();
    const viewM = mpp0 * Math.hypot(canvas.clientWidth, canvas.clientHeight) * (map.getPitch() > 50 ? 2.2 : 1.0);
    const cx = (cm.x - this.origin.x) / this.s, cy = (cm.y - this.origin.y) / this.s;
    const modelZoom = this.visible.models && zoom >= 10.5;
    const M = new THREE.Matrix4(), q = new THREE.Quaternion(), pos = new THREE.Vector3(), scl = new THREE.Vector3();
    const sm = this.smoke.geometry.attributes;
    const wpx = zoom < 5 ? 5 : zoom < 8 ? 7 : 9;
    let builds = 0;
    const tStep = Math.floor(t * 12) / 12;                       // 12 fps pixel clock for smoke
    // labels thin out with distance: none below z 4.8, the biggest stations first, every one from z 10
    const minCap = zoom < 4.8 ? Infinity : zoom < 5.8 ? 2000 : zoom < 6.8 ? 1000 : zoom < 7.8 ? 400 : zoom < 8.8 ? 150 : zoom < 10 ? 50 : zoom < 11.5 ? 20 : 0;
    const anchors = [];
    // far out the fleet's smoke would blanket the country: fewer, smaller, fainter puffs until z 9
    const zf = clamp((zoom - 3.5) / 5.5, 0.22, 1);

    for (const e of this.entries) {
      const p = e.p, on = this.show.has(p.type);
      const mpp = mpp0 * Math.cos(p.lat * Math.PI / 180);
      const d = Math.hypot(e.xy[0] - cx, e.xy[1] - cy);
      const near = d < viewM;
      if (terrain && near && (e.elevT === undefined || t - e.elevT > 2)) {
        e.elev = map.queryTerrainElevation?.([p.lon, p.lat]) || 0;
        e.elevT = t;
      } else if (!terrain) e.elev = 0;
      const ld = this.load(e);
      e.ld = ld;

      // real model when close
      let modelShown = false;
      if (modelZoom && on && near && d < viewM * 0.8) {
        if (!e.model && builds < 1 && MODELS) { this.buildModel(e); builds++; }
        if (e.model) {
          const h = e.model.userData.h || 80;
          const ex = clamp((40 * mpp) / h, 1, 2.5) * e.k;
          e.model.scale.setScalar(ex);
          e.model.position.set(e.xy[0], e.xy[1], e.elev);
          e.model.visible = true;
          // live wind for the model's own smoke: a unit vector in model x/z (model z -> world -y)
          if (e.wind && e.model.children[0]?.userData) {
            const to = ((e.wind.wind_direction_10m ?? 270) + 180) * Math.PI / 180;
            e.model.children[0].userData.wind = { x: Math.sin(to), z: Math.cos(to) };
          }
          e.model.userData.anim?.(t, ld ?? 0);
          modelShown = true;
        }
      } else if (e.model) {
        e.model.visible = false;
        if (d > viewM * 3) this.dropModel(e);
      }

      // label anchor: above the pillar top, or above the model's highest point, never on the object
      const capMW = p.cap || 0;
      const unnamed = /unnamed|^Solar plant \(|^Wind plant \(/i.test(p.name);
      if (on && near && ((capMW >= minCap && (!unnamed || zoom >= 12.5)) || this.selected === p.id)) {
        const top = modelShown ? e.elev + (e.model.userData.h || 80) * e.model.scale.x
                               : e.elev + ((capMW < 50 ? 3 : 10) + 1.25 * Math.sqrt(capMW || 1)) * mpp * e.k;
        anchors.push([e, top]);
      }

      // pillar
      const cap = p.cap || 1;
      // small stations (most of the ~2,000 OSM solar farms) get a low base and a thin pillar, or they carpet the country
      const Hpx = ((cap < 50 ? 3 : 10) + 1.25 * Math.sqrt(cap)) * (this.selected === p.id ? 1.15 : 1);
      const H = Hpx * mpp * e.k, W = (cap < 50 ? Math.max(3, wpx - 3) : wpx) * mpp * e.k;
      const hide = !on || modelShown;
      const z0 = e.elev;
      pos.set(e.xy[0], e.xy[1], z0);
      scl.set(hide ? 0 : W, hide ? 0 : W, hide ? 0 : H);
      this.shell.setMatrixAt(e.i, M.compose(pos, q, scl));
      const coreH = ld == null ? 0 : Math.max(ld, 0.02) * H;
      scl.set(hide ? 0 : W * 0.72, hide ? 0 : W * 0.72, hide || !coreH ? 0 : coreH);
      this.core.setMatrixAt(e.i, M.compose(pos, q, scl));
      // a bright block rides on the core top (the "flame"); selected station gets a white cap
      const capH = 1.6 * mpp * e.k;
      pos.set(e.xy[0], e.xy[1], z0 + (ld == null ? H : coreH));
      const sel = this.selected === p.id;
      scl.set(hide ? 0 : W * (sel ? 1.25 : 0.72), hide ? 0 : W * (sel ? 1.25 : 0.72), hide || (!coreH && !sel) ? 0 : capH * (sel ? 2 : 1));
      this.cap.setMatrixAt(e.i, M.compose(pos, q, scl));

      // smoke from the pillar top (models make their own)
      const burning = this.visible.smoke && on && !modelShown && e.f.thermal && ld != null && ld > 0.02 && near;
      const mw = (ld || 0) * cap;
      const w = e.wind;
      const to = ((w?.wind_direction_10m ?? 270) + 180) * Math.PI / 180;   // wind blows FROM that bearing
      const spd = w?.wind_speed_10m ?? 3;
      const vx = Math.sin(to), vy = -Math.cos(to);                         // y is south
      const Lpx = (16 + 2.0 * Math.sqrt(mw)) * (0.6 + Math.min(spd, 12) / 10) * zf;
      const Rpx = (10 + 0.9 * Math.sqrt(mw)) / (0.7 + Math.min(spd, 12) / 12) * zf;
      for (let k = 0; k < PUFFS; k++) {
        const j = e.i * PUFFS + k;
        if (!burning || k >= Math.ceil(PUFFS * clamp(0.35 + ld, 0, 1) * (0.4 + 0.6 * zf))) { sm.aAlpha.array[j] = 0; continue; }
        const ph = ((tStep * (0.10 + spd / 90)) + k / PUFFS + e.seed) % 1;
        const ease = Math.sqrt(ph);
        sm.position.array[j * 3] = e.xy[0] + vx * ph * Lpx * mpp * e.k;
        sm.position.array[j * 3 + 1] = e.xy[1] + vy * ph * Lpx * mpp * e.k;
        sm.position.array[j * 3 + 2] = z0 + H + ease * Rpx * mpp * e.k;
        sm.aSize.array[j] = (2 + 7 * ph) * (0.55 + Math.sqrt(mw) / 40) * (0.35 + 0.65 * zf);
        sm.aAlpha.array[j] = (1 - ph) * (0.45 + 0.55 * clamp(ld, 0, 1)) * (0.5 + 0.5 * zf);
      }
    }
    this.shell.instanceMatrix.needsUpdate = this.core.instanceMatrix.needsUpdate = this.cap.instanceMatrix.needsUpdate = true;
    sm.position.needsUpdate = sm.aSize.needsUpdate = sm.aAlpha.needsUpdate = true;

    // turbines: from z 10, those in view only
    if (this.tw) {
      const showT = this.visible.turbines && this.show.has('wind') && zoom >= 10;
      this.turbines.visible = showT;
      if (showT) {
        const ld = clamp(this.stateLoad.wind ?? 0.3, 0, 1);
        const dt = Math.min(0.1, t - (this.tPrev ?? t));
        for (const e of this.tEntries) {
          const d = Math.hypot(e.xy[0] - cx, e.xy[1] - cy);
          if (d > viewM) { M.makeScale(0, 0, 0); this.tw.setMatrixAt(e.i, M); this.bl.setMatrixAt(e.i, M); continue; }
          const mpp = mpp0 * Math.cos(e.lat * Math.PI / 180);
          const ex = clamp((26 * mpp) / e.hub, 1, 3) * e.k * (e.hub / 80);
          if (terrain && (e.elevT === undefined || t - e.elevT > 3)) { e.elev = map.queryTerrainElevation?.([e.lon, e.lat]) || 0; e.elevT = t; }
          const z0 = terrain ? e.elev || 0 : 0;
          const w = e.wind;
          // rotor faces into the wind: yaw so the rotor's -y normal points at the wind's source bearing
          const from = (w?.wind_direction_10m ?? 250) * Math.PI / 180;
          const yaw = -from;                                // world y is south: rotate about +z
          const rpm = 16 * ld * clamp((w?.wind_speed_80m ?? 7) / 9, 0.3, 1.3);
          e.spin += dt * rpm / 60 * Math.PI * 2;
          q.setFromAxisAngle(new THREE.Vector3(0, 0, 1), yaw);
          pos.set(e.xy[0], e.xy[1], z0);
          scl.setScalar(ex);
          this.tw.setMatrixAt(e.i, M.compose(pos, q, scl));
          const hubZ = z0 + 20.3 * 4 * ex;
          const q2 = q.clone().multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), e.spin + e.ph));
          // blades rotate about the rotor axis (local y), sitting just in front of the nacelle
          const off = new THREE.Vector3(0, -1.2 * 4 * ex, 0).applyQuaternion(q);
          pos.set(e.xy[0] + off.x, e.xy[1] + off.y, hubZ);
          this.bl.setMatrixAt(e.i, M.compose(pos, q2, scl.setScalar(ex * e.rot / 76)));
        }
        this.tw.instanceMatrix.needsUpdate = this.bl.instanceMatrix.needsUpdate = true;
      }
    }
    this.tPrev = t;
    this.placeMovers(t, zoom, mpp0);
    if (this.pylons) this.pylons.visible = this.visible.pylons !== false && zoom >= 12.8;

    // project label anchors to CSS pixels (MVP of the scene; skip points behind the camera)
    const P = this.camera.projectionMatrix.elements, wx = this.world.position.x, wy = this.world.position.y;
    const cw = canvas.clientWidth, ch = canvas.clientHeight, out = [];
    for (const [e, top] of anchors) {
      const x = e.xy[0] + wx, y = e.xy[1] + wy, z = top;
      const w = P[3] * x + P[7] * y + P[11] * z + P[15];
      if (w <= 0) continue;
      const nx = (P[0] * x + P[4] * y + P[8] * z + P[12]) / w, ny = (P[1] * x + P[5] * y + P[9] * z + P[13]) / w;
      if (nx < -1.2 || nx > 1.2 || ny < -1.2 || ny > 1.3) continue;
      out.push({ p: e.p, ld: e.ld, sx: (nx * 0.5 + 0.5) * cw, sy: (-ny * 0.5 + 0.5) * ch, depth: w });
    }
    this.labelAnchors = out;
    this.onLabels?.(out, zoom);

    this.renderer.resetState();
    this.renderer.render(this.scene, this.camera);
    map.triggerRepaint();
  }
}

// Bake a voxel model (InstancedMesh / Mesh children) into one vertex-coloured geometry so it can
// itself be instanced thousands of times (pylons).
function bakePylon(group) {
  group.updateMatrixWorld(true);
  const pos = [], nor = [], col = [], m = new THREE.Matrix4(), nm = new THREE.Matrix3(), c = new THREE.Color();
  const v = new THREE.Vector3(), n = new THREE.Vector3();
  group.traverse(o => {
    if (!o.geometry) return;
    const g = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry;
    const P = g.attributes.position, N = g.attributes.normal;
    const count = o.isInstancedMesh ? o.count : 1;
    for (let k = 0; k < count; k++) {
      if (o.isInstancedMesh) { o.getMatrixAt(k, m); m.premultiply(o.matrixWorld); if (o.instanceColor) o.getColorAt(k, c); else c.set(o.material.color || 0xaaaaaa); }
      else { m.copy(o.matrixWorld); c.set(o.material?.color || 0xaaaaaa); }
      nm.getNormalMatrix(m);
      for (let i = 0; i < P.count; i++) {
        v.fromBufferAttribute(P, i).applyMatrix4(m); pos.push(v.x, v.y, v.z);
        n.fromBufferAttribute(N, i).applyMatrix3(nm).normalize(); nor.push(n.x, n.y, n.z);
        col.push(c.r, c.g, c.b);
      }
    }
  });
  const geom = new THREE.BufferGeometry();
  geom.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geom.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
  geom.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  return { geom, mat: new THREE.MeshLambertMaterial({ vertexColors: true, emissive: 0x3a4048 }), arms: [...(group.userData.arms || []), ...(group.userData.earth || [])] };
}

export { modelsReady };
