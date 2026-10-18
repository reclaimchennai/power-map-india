"""Build build/grid/*.geojson from cached Overpass responses in raw/osm/.

Run grid_fetch_osm.py first. Data (c) OpenStreetMap contributors, ODbL.
"""
import glob
import json
import math
import os
import re
from collections import Counter, defaultdict

from shapely.geometry import LineString, MultiPolygon, Point, Polygon, mapping, shape
from shapely.ops import linemerge, polygonize, unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw", "osm")
OUT = os.path.join(ROOT, "build", "grid")
os.makedirs(OUT, exist_ok=True)

SIMPLIFY_DEG = 0.000135  # ~15 m
OSM_URL = "https://www.openstreetmap.org/{}/{}"
ATTRIB = "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright)"
STATES = {e["tags"]["ISO3166-2"]: e["tags"].get("name:en", e["tags"]["name"])
          for e in json.load(open(os.path.join(RAW, "india_states.json")))["elements"]}


def load(name):
    p = os.path.join(RAW, name + ".json")
    return json.load(open(p))["elements"] if os.path.exists(p) else []


def per_state(prefix):
    out = {}
    for p in sorted(glob.glob(os.path.join(RAW, prefix + "_IN-*.json"))):
        code = os.path.basename(p)[len(prefix) + 1:-5]
        out[code] = json.load(open(p))["elements"]
    return out


# ---------------------------------------------------------------- tag parsing
def parse_voltages(v):
    """'400000;220000' -> [400, 220] (kV, desc). Handles '220 kV', '-500000', '11kV'."""
    if not v:
        return []
    out = []
    for part in re.split(r"[;,/]", str(v)):
        part = part.strip().lower()
        m = re.search(r"[-+±]?\s*(\d+(?:\.\d+)?)", part)
        if not m:
            continue
        x = float(m.group(1))
        if "kv" in part or x < 2000:
            x = x * 1000 if x < 2000 else x
        kv = x / 1000
        if kv >= 1:
            out.append(int(round(kv)) if abs(kv - round(kv)) < 0.01 else round(kv, 1))
    return sorted(set(out), reverse=True)


def parse_power(v):
    """'1200 MW' / '1.2 GW' / '500 kW' / '2 MWp' -> MW float; 'yes' -> None."""
    if not v:
        return None
    s = str(v).strip().lower().replace(",", ".")
    m = re.match(r"^([\d.]+)\s*([kmg]?)w", s) or re.match(r"^([\d.]+)\s*$", s)
    if not m:
        return None
    try:
        x = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
    if unit == "k":
        x /= 1000
    elif unit == "g":
        x *= 1000
    elif unit == "":
        x = x / 1e6 if x > 10000 else x  # bare numbers: watts if huge, else assume MW
    return round(x, 3)


def to_int(v):
    try:
        return int(str(v).split(";")[0].strip())
    except (TypeError, ValueError):
        return None


def rnd(geom):
    """Round coordinates to 5 decimals (~1 m)."""
    def r(c):
        if isinstance(c[0], (int, float)):
            return [round(c[0], 5), round(c[1], 5)]
        return [r(x) for x in c]
    g = mapping(geom)
    return {"type": g["type"], "coordinates": r(g["coordinates"])}


def compact(features, keep=()):
    """Drop null/empty properties (missing == null) except the schema fields in `keep`."""
    for f in features:
        f["properties"] = {k: v for k, v in f["properties"].items() if k in keep or v not in (None, "", [])}
    return features


LINE_KEEP = ("voltage_kv", "circuits", "name", "operator", "source", "osm_id")
LINE_SOURCES = {"sources_template": "https://www.openstreetmap.org/{osm_id}",
                "sources_note": "per-feature source URL = sources_template with the feature's osm_id "
                                "(omitted per feature to keep line files small)"}


def slim_lines(features):
    """Line layers: drop redundant per-feature fields (URL is derivable from osm_id)."""
    for f in features:
        p = f["properties"]
        p.pop("sources", None)
        if len(p.get("voltages") or []) <= 1:
            p.pop("voltages", None)
        if p.get("power") == "line":
            p.pop("power")
    return compact(features, LINE_KEEP)


def fc(features, **meta):
    return {"type": "FeatureCollection", "attribution": ATTRIB, **meta, "features": features}


def write(name, obj):
    p = os.path.join(OUT, name)
    with open(p, "w") as f:
        json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)
    return os.path.getsize(p)


# ---------------------------------------------------------------- geometry helpers
def way_line(e):
    pts = [(g["lon"], g["lat"]) for g in e.get("geometry") or [] if g]
    return LineString(pts) if len(pts) >= 2 else None


def area_geom(e):
    """Polygon/MultiPolygon for closed ways & multipolygon relations (from `out geom`)."""
    if e["type"] == "way":
        pts = [(g["lon"], g["lat"]) for g in e.get("geometry") or [] if g]
        if len(pts) >= 4 and pts[0] == pts[-1]:
            p = Polygon(pts)
            return p if p.is_valid else p.buffer(0)
        return None
    if e["type"] == "relation":
        outers, inners = [], []
        for m in e.get("members", []):
            if m.get("type") != "way" or not m.get("geometry"):
                continue
            pts = [(g["lon"], g["lat"]) for g in m["geometry"] if g]
            if len(pts) >= 2:
                (inners if m.get("role") == "inner" else outers).append(LineString(pts))
        if not outers:
            return None
        polys = list(polygonize(unary_union(outers)))
        if not polys:
            return None
        g = unary_union(polys)
        if inners:
            holes = list(polygonize(unary_union(inners)))
            if holes:
                g = g.difference(unary_union(holes))
        return g if g.is_valid else g.buffer(0)
    return None


def centre(e):
    if e["type"] == "node":
        return e["lon"], e["lat"]
    if "center" in e:
        return e["center"]["lon"], e["center"]["lat"]
    b = e.get("bounds")
    if b:
        return (b["minlon"] + b["maxlon"]) / 2, (b["minlat"] + b["maxlat"]) / 2
    return None


def hectares(g):
    if g is None or g.is_empty:
        return None
    lat = g.centroid.y
    return round(abs(g.area) * (111320 ** 2) * math.cos(math.radians(lat)) / 1e4, 2)


def osm_id(e):
    return f"{e['type']}/{e['id']}"


# ---------------------------------------------------------------- lines
HVDC_KV = {320, 500, 800}


def line_class(t, volts):
    if not volts:
        return None
    vmax = volts[0]
    if t.get("frequency") == "0" or "hvdc" in (t.get("name", "") + t.get("line", "") + t.get("ref", "")).lower() \
            or vmax in HVDC_KV:
        return "hvdc"
    if vmax >= 700:
        return "765"
    if vmax >= 380:
        return "400"
    if vmax >= 200:
        return "220"
    if vmax >= 66:
        return "110"
    return "dist"


def line_props(e, volts, states):
    t = e.get("tags", {})
    circuits = to_int(t.get("circuits"))
    cables = to_int(t.get("cables"))
    if circuits is None and cables and cables % 3 == 0 and line_class(t, volts) != "hvdc":
        circuits_est = cables // 3
    else:
        circuits_est = None
    return {
        "voltage_kv": volts[0] if volts else None, "voltages": volts,
        "circuits": circuits, "circuits_from_cables": circuits_est, "cables": cables,
        "name": t.get("name") or t.get("name:en"), "ref": t.get("ref"),
        "operator": t.get("operator"), "owner": t.get("owner"),
        "power": t.get("power"), "location": t.get("location"), "line_type": t.get("line"),
        "frequency": t.get("frequency"), "start_date": t.get("start_date"),
        "states": sorted(states), "source": "osm", "osm_id": osm_id(e),
        "sources": [OSM_URL.format(e["type"], e["id"])],
    }


def build_lines():
    ways, wstates = {}, defaultdict(set)
    for code, els in per_state("lines_hv").items():
        for e in els:
            if e["type"] == "way":
                ways[e["id"]] = e
                wstates[e["id"]].add(STATES.get(code, code))
    # TN all-voltage fetch may carry HV ways missed by the HV query (different mirror replication)
    tn_all = load("tn_lines_all")
    for e in tn_all:
        if e["type"] == "way" and e["id"] not in ways and parse_voltages(e.get("tags", {}).get("voltage")) \
                and parse_voltages(e["tags"]["voltage"])[0] >= 66:
            ways[e["id"]] = e
            wstates[e["id"]].add("Tamil Nadu")
    classes = defaultdict(list)
    for wid, e in ways.items():
        t = e.get("tags", {})
        volts = parse_voltages(t.get("voltage"))
        cls = line_class(t, volts)
        if cls in (None, "dist"):
            continue
        g = way_line(e)
        if g is None:
            continue
        gs = g.simplify(SIMPLIFY_DEG, preserve_topology=False)
        classes[cls].append({"type": "Feature", "geometry": rnd(gs), "properties": line_props(e, volts, wstates[wid])})
    return classes, ways


def geod_km(g):
    """Approximate geodesic length (km) of a (Multi)LineString in lon/lat."""
    tot = 0.0
    lines = [g] if g.geom_type == "LineString" else list(g.geoms)
    for ln in lines:
        c = list(ln.coords)
        for (x1, y1), (x2, y2) in zip(c, c[1:]):
            p1, p2 = math.radians(y1), math.radians(y2)
            dp, dl = p2 - p1, math.radians(x2 - x1)
            a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
            tot += 2 * 6371.0088 * math.asin(math.sqrt(a))
    return tot


def build_tn_distribution():
    feats, unknown, ch = [], [], []
    for e in load("tn_lines_all"):
        t = e.get("tags", {})
        volts = parse_voltages(t.get("voltage"))
        g = way_line(e)
        if g is None:
            continue
        gs = g.simplify(SIMPLIFY_DEG / 3, preserve_topology=False)  # ~5 m: distribution is local detail
        f = {"type": "Feature", "geometry": rnd(gs), "properties": line_props(e, volts, {"Tamil Nadu"})}
        if (volts and volts[0] <= 33) or (not volts and t.get("power") == "minor_line"):
            feats.append(f)
        elif not volts:
            unknown.append(f)
    for e in load("chennai_lines_all"):
        t = e.get("tags", {})
        volts = parse_voltages(t.get("voltage"))
        g = way_line(e)
        if g is None:
            continue
        p = line_props(e, volts, set())
        p["class"] = line_class(t, volts) or "unknown"
        ch.append({"type": "Feature", "geometry": rnd(g.simplify(SIMPLIFY_DEG / 3, preserve_topology=False)),
                   "properties": p})
    return feats, unknown, ch


# ---------------------------------------------------------------- substations
def sub_props(e, volts, state):
    t = e.get("tags", {})
    return {
        "name": t.get("name") or t.get("name:en"), "name_ta": t.get("name:ta"),
        "voltage_kv": volts[0] if volts else None, "voltages": volts,
        "mva": parse_power(t.get("rating")) if t.get("rating") else None,
        "owner": t.get("operator") or t.get("owner"), "operator": t.get("operator"),
        "circle": None, "substation": t.get("substation"), "location": t.get("location"),
        "gis": ("gis" in (t.get("name", "") + " " + t.get("substation:type", "") + " " +
                         t.get("gas_insulated", "")).lower()) or t.get("gas_insulated") == "yes" or None,
        "ref": t.get("ref"), "state": state, "source": "osm", "osm_id": osm_id(e),
        "sources": [OSM_URL.format(e["type"], e["id"])],
    }


def build_substations():
    pts, seen, no_volt = [], set(), Counter()
    for code, els in per_state("substations").items():
        st = STATES.get(code, code)
        for e in els:
            key = osm_id(e)
            if key in seen:
                continue
            t = e.get("tags", {})
            volts = parse_voltages(t.get("voltage"))
            is_tn = code == "IN-TN"
            if not volts:
                no_volt[st] += 1
            if not (is_tn or (volts and volts[0] >= 66)):
                continue
            c = centre(e)
            if not c:
                continue
            seen.add(key)
            pts.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [round(c[0], 5), round(c[1], 5)]},
                        "properties": sub_props(e, volts, st)})
    polys = []
    for e in load("tn_substation_polygons"):
        g = area_geom(e)
        if g is None or g.is_empty:
            continue
        volts = parse_voltages(e.get("tags", {}).get("voltage"))
        p = sub_props(e, volts, "Tamil Nadu")
        p["area_ha"] = hectares(g)
        polys.append({"type": "Feature", "geometry": rnd(g.simplify(0.00001)), "properties": p})
    return pts, polys, no_volt


# ---------------------------------------------------------------- plants / generators
def plant_props(e, state, kind, g=None):
    t = e.get("tags", {})
    src = t.get("plant:source") or t.get("generator:source")
    out = t.get("plant:output:electricity") or t.get("generator:output:electricity")
    return {
        "kind": kind, "name": t.get("name") or t.get("name:en"), "name_ta": t.get("name:ta"),
        "source_type": src, "method": t.get("plant:method") or t.get("generator:method"),
        "capacity_mw": parse_power(out), "capacity_raw": out,
        "operator": t.get("operator"), "owner": t.get("owner"),
        "start_date": t.get("start_date"), "wikidata": t.get("wikidata"), "wikipedia": t.get("wikipedia"),
        "area_ha": hectares(g) if g is not None and g.geom_type in ("Polygon", "MultiPolygon") else None,
        "state": state, "source": "osm", "osm_id": osm_id(e), "sources": [OSM_URL.format(e["type"], e["id"])],
    }


def build_plants():
    feats, seen = [], set()
    for code, els in per_state("plants").items():
        st = STATES.get(code, code)
        for e in els:
            if osm_id(e) in seen:
                continue
            seen.add(osm_id(e))
            g = None
            if e["type"] == "node":
                g = Point(e["lon"], e["lat"])
            else:
                g = area_geom(e)
                if g is None or g.is_empty:
                    c = centre(e)
                    g = Point(*c) if c else None
            if g is None:
                continue
            gs = g if g.geom_type == "Point" else g.simplify(0.00003)
            feats.append({"type": "Feature", "geometry": rnd(gs), "properties": plant_props(e, st, "plant", g)})
    plant_polys = [shape(f["geometry"]) for f in feats if f["geometry"]["type"] != "Point"]
    plant_union = unary_union(plant_polys) if plant_polys else None
    from shapely.prepared import prep
    pu = prep(plant_union) if plant_union is not None else None

    # standalone generators (not wind turbines / not inside a plant polygon): >=1 MW or named, all India;
    # TN: also solar generator polygons >= 1 ha (real farm footprints)
    gen_count, wind = Counter(), []
    tn_poly = {osm_id(e): e for e in load("tn_generator_polygons")}
    for code, els in per_state("generators").items():
        st = STATES.get(code, code)
        for e in els:
            t = e.get("tags", {})
            src = t.get("generator:source")
            gen_count[(st, src)] += 1
            if src == "wind" and code == "IN-TN":
                if e["type"] != "node":
                    continue
                wind.append({"type": "Feature",
                             "geometry": {"type": "Point", "coordinates": [round(e["lon"], 5), round(e["lat"], 5)]},
                             "properties": {"osm_id": osm_id(e), "name": t.get("name"), "ref": t.get("ref"),
                                            "operator": t.get("operator"),
                                            "output_mw": parse_power(t.get("generator:output:electricity")),
                                            "manufacturer": t.get("manufacturer"), "model": t.get("model"),
                                            "height_m": t.get("height"), "rotor_diameter_m": t.get("rotor:diameter"),
                                            "start_date": t.get("start_date"),
                                            "sources": [OSM_URL.format("node", e["id"])]}})
                continue
            if src == "wind" or osm_id(e) in seen:
                continue
            c = centre(e)
            if not c:
                continue
            mw = parse_power(t.get("generator:output:electricity"))
            g = None
            if code == "IN-TN" and osm_id(e) in tn_poly:
                g = area_geom(tn_poly[osm_id(e)])
            ha = hectares(g) if g is not None else None
            big = (mw or 0) >= 1 or bool(t.get("name")) or (ha or 0) >= 1
            if not big:
                continue
            if pu is not None and pu.contains(Point(*c)) and not t.get("name"):
                continue  # part of a mapped plant
            seen.add(osm_id(e))
            geom = rnd(g.simplify(0.00003)) if g is not None and not g.is_empty else \
                {"type": "Point", "coordinates": [round(c[0], 5), round(c[1], 5)]}
            feats.append({"type": "Feature", "geometry": geom, "properties": plant_props(e, st, "generator", g)})
    return feats, wind, gen_count


def build_tn_solar_arrays(plants):
    """All TN solar generator polygons >= 0.5 ha (panel-array footprints), tagged with the enclosing plant."""
    from shapely.strtree import STRtree
    pp = [(shape(f["geometry"]), f["properties"]) for f in plants
          if f["properties"]["kind"] == "plant" and f["geometry"]["type"] != "Point"
          and f["properties"]["state"] == "Tamil Nadu"]
    tree = STRtree([g for g, _ in pp]) if pp else None
    out = []
    for e in load("tn_generator_polygons"):
        t = e.get("tags", {})
        if t.get("generator:source") != "solar":
            continue
        g = area_geom(e)
        ha = hectares(g)
        if g is None or g.is_empty or (ha or 0) < 0.5:
            continue
        host = None
        if tree is not None:
            c = g.representative_point()
            for i in tree.query(c):
                if pp[i][0].contains(c):
                    host = pp[i][1]
                    break
        out.append({"type": "Feature", "geometry": rnd(g.simplify(0.00003)), "properties": {
            "osm_id": osm_id(e), "name": t.get("name"), "operator": t.get("operator"),
            "capacity_mw": parse_power(t.get("generator:output:electricity")), "area_ha": ha,
            "plant_osm_id": host["osm_id"] if host else None, "plant_name": host["name"] if host else None,
            "sources": [OSM_URL.format(e["type"], e["id"])]}})
    return out


# ---------------------------------------------------------------- towers
def build_towers(ways):
    vert = {}
    for e in ways.values():
        volts = parse_voltages(e.get("tags", {}).get("voltage"))
        if not volts or volts[0] < 380:
            continue
        for g in e.get("geometry") or []:
            if g:
                k = (round(g["lon"], 7), round(g["lat"], 7))
                vert[k] = max(vert.get(k, 0), volts[0])
    feats = []
    for e in load("tn_towers_400_765"):
        if e["type"] != "node" or "lat" not in e:
            continue
        t = e.get("tags", {})
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [round(e["lon"], 5), round(e["lat"], 5)]},
                      "properties": {"osm_id": osm_id(e), "power": t.get("power"), "ref": t.get("ref"),
                                     "design": t.get("design"), "structure": t.get("structure"),
                                     "material": t.get("material"), "height_m": t.get("height"),
                                     "line_voltage_kv": vert.get((round(e["lon"], 7), round(e["lat"], 7)))}})
    return feats


# ---------------------------------------------------------------- main
def main():
    stats = {"sizes_bytes": {}, "counts": {}, "km": {}}
    classes, ways = build_lines()
    for cls in ("765", "400", "220", "110", "hvdc"):
        fs = classes.get(cls, [])
        stats["counts"][f"lines_{cls}"] = len(fs)
        stats["km"][f"lines_{cls}"] = round(sum(geod_km(shape(f["geometry"])) for f in fs))
        tn = [f for f in fs if "Tamil Nadu" in f["properties"]["states"]]
        stats["counts"][f"lines_{cls}_tn"] = len(tn)
        stats["km"][f"lines_{cls}_tn"] = round(sum(geod_km(shape(f["geometry"])) for f in tn))
        stats["sizes_bytes"][f"lines_{cls}.geojson"] = write(f"lines_{cls}.geojson", fc(slim_lines(fs), voltage_class=cls, **LINE_SOURCES))
    dist, unknown, ch = build_tn_distribution()
    stats["counts"].update(lines_tn_distribution=len(dist), lines_tn_unknown_voltage=len(unknown), lines_chennai_all=len(ch))
    stats["km"]["lines_tn_distribution"] = round(sum(geod_km(shape(f["geometry"])) for f in dist))
    stats["sizes_bytes"]["lines_tn_distribution.geojson"] = write("lines_tn_distribution.geojson", fc(slim_lines(dist), **LINE_SOURCES))
    stats["sizes_bytes"]["lines_tn_unknown_voltage.geojson"] = write("lines_tn_unknown_voltage.geojson", fc(slim_lines(unknown), **LINE_SOURCES))
    stats["sizes_bytes"]["lines_chennai_all.geojson"] = write(
        "lines_chennai_all.geojson", fc(slim_lines(ch), **LINE_SOURCES, bbox_latlon=[12.75, 79.95, 13.35, 80.40]))

    pts, polys, no_volt = build_substations()
    stats["counts"]["substations"] = len(pts)
    stats["counts"]["substations_by_class"] = dict(Counter(
        (lambda v: "765" if v and v >= 700 else "400" if v and v >= 380 else "220" if v and v >= 200 else
         "110" if v and v >= 66 else "<66" if v else "unknown")(f["properties"]["voltage_kv"]) for f in pts))
    stats["counts"]["substations_tn"] = sum(f["properties"]["state"] == "Tamil Nadu" for f in pts)
    stats["counts"]["substations_without_voltage_by_state"] = dict(no_volt)
    stats["counts"]["substations_tn_polygons"] = len(polys)
    stats["sizes_bytes"]["substations.geojson"] = write("substations.geojson", fc(compact(pts, (
        "name", "voltage_kv", "voltages", "mva", "owner", "operator", "circle", "state", "source", "osm_id", "sources"))))
    stats["sizes_bytes"]["substations_tn_polygons.geojson"] = write("substations_tn_polygons.geojson", fc(polys))

    plants, wind, gen_count = build_plants()
    stats["counts"]["osm_plants"] = dict(Counter(f["properties"]["kind"] for f in plants))
    stats["counts"]["osm_plants_by_source"] = dict(Counter(f["properties"]["source_type"] for f in plants))
    stats["counts"]["generators_by_state_source"] = {f"{k[0]}|{k[1]}": v for k, v in sorted(gen_count.items(), key=str)}
    stats["counts"]["tn_wind_turbines"] = len(wind)
    stats["sizes_bytes"]["osm_plants.geojson"] = write("osm_plants.geojson", fc(compact(plants, (
        "kind", "name", "source_type", "capacity_mw", "operator", "state", "source", "osm_id", "sources"))))
    stats["sizes_bytes"]["tn_wind_turbines.geojson"] = write("tn_wind_turbines.geojson", fc(compact(wind)))
    arrays = build_tn_solar_arrays(plants)
    stats["counts"]["tn_solar_arrays"] = len(arrays)
    stats["sizes_bytes"]["tn_solar_arrays.geojson"] = write("tn_solar_arrays.geojson", fc(arrays))

    towers = build_towers(ways)
    stats["counts"]["towers_tn"] = len(towers)
    stats["counts"]["towers_tn_by_voltage"] = dict(Counter(str(f["properties"]["line_voltage_kv"]) for f in towers))
    stats["sizes_bytes"]["towers_tn.geojson"] = write("towers_tn.geojson", fc(compact(towers)))
    import gzip
    stats["sizes_gzip_bytes"] = {n: len(gzip.compress(open(os.path.join(OUT, n), "rb").read(), 9))
                                 for n in stats["sizes_bytes"]}
    stats["osm_provenance"] = json.load(open(os.path.join(RAW, "manifest.json")))
    json.dump(stats, open(os.path.join(OUT, "osm_stats.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in stats.items() if k != "counts"}, indent=1))
    print(json.dumps({k: v for k, v in stats["counts"].items() if k != "generators_by_state_source"}, indent=1))


if __name__ == "__main__":
    main()
