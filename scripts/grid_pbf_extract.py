"""Fallback for the India-wide OSM layers: Overpass mirrors were returning 504s for per-state
queries, so the Geofabrik India extract is filtered locally with pyosmium and written in the
same Overpass-JSON shape (raw/osm/<layer>_IN-XX.json) that grid_build.py reads.

  .venv/bin/python scripts/grid_pbf_extract.py raw/osm/india-YYMMDD.osm.pbf [--include-tn]

Tamil Nadu files from Overpass are kept unless --include-tn is passed.
"""
import json
import os
import re
import sys
import time

import osmium
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid_build import area_geom  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw", "osm")
KEEP_POWER = {"line", "cable", "minor_line", "substation", "plant", "generator", "converter"}
HV = re.compile(r"(^|;) *[-+]?(6[6-9][0-9]{3}|[7-9][0-9]{4}|[1-9][0-9]{5})( *;|$)")


def filter_pbf(src, dst):
    """Write power features + Indian state boundaries (+ all referenced ways/nodes) to a small PBF."""
    if os.path.exists(dst) and os.path.getmtime(dst) > os.path.getmtime(src):
        return
    t0 = time.time()
    n = 0
    with osmium.BackReferenceWriter(dst, ref_src=src, overwrite=True) as w:
        for o in osmium.FileProcessor(src).with_filter(osmium.filter.KeyFilter("power", "boundary")):
            t = o.tags
            if t.get("power") in KEEP_POWER or (
                    o.is_relation() and t.get("boundary") == "administrative" and t.get("admin_level") == "4"
                    and t.get("ISO3166-2", "").startswith("IN-")):
                w.add(o)
                n += 1
    print(f"filtered {n} objects in {time.time() - t0:.0f}s -> {dst}", file=sys.stderr)


def read_small(path):
    nodes, ways, rels = {}, {}, []
    for o in osmium.FileProcessor(path).with_locations():
        if o.is_node():
            if o.tags.get("power") in KEEP_POWER and o.location.valid():
                nodes[o.id] = {"type": "node", "id": o.id, "lat": o.location.lat, "lon": o.location.lon,
                               "tags": dict(o.tags)}
        elif o.is_way():
            geom = [{"lat": nd.location.lat, "lon": nd.location.lon} for nd in o.nodes if nd.location.valid()]
            ways[o.id] = {"type": "way", "id": o.id, "tags": dict(o.tags), "geometry": geom}
        elif o.is_relation():
            rels.append({"type": "relation", "id": o.id, "tags": dict(o.tags),
                         "members": [{"type": {"n": "node", "w": "way", "r": "relation"}[m.type], "ref": m.ref,
                                      "role": m.role} for m in o.members]})
    for r in rels:
        for m in r["members"]:
            if m["type"] == "way" and m["ref"] in ways:
                m["geometry"] = ways[m["ref"]]["geometry"]
    return nodes, ways, rels


def bounds_center(pts):
    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    return ({"minlat": min(lats), "minlon": min(lons), "maxlat": max(lats), "maxlon": max(lons)},
            {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2})


def main():
    src = sys.argv[1]
    include_tn = "--include-tn" in sys.argv
    small = os.path.join(RAW, "india-power-filtered.osm.pbf")
    filter_pbf(src, small)
    nodes, ways, rels = read_small(small)
    print(f"nodes {len(nodes)} ways {len(ways)} rels {len(rels)}", file=sys.stderr)

    states = [r for r in rels if r["tags"].get("boundary") == "administrative"]
    polys, codes = [], []
    for r in states:
        g = area_geom(r)
        if g is not None and not g.is_empty:
            polys.append(g.simplify(0.002))
            codes.append(r["tags"]["ISO3166-2"])
    tree = STRtree(polys)
    print(f"state polygons: {len(polys)}", file=sys.stderr)

    def states_of(geom):
        return {codes[i] for i in tree.query(geom, predicate="intersects")}

    out = {}

    def add(layer, codeset, el):
        for c in codeset:
            out.setdefault((layer, c), []).append(el)

    # lines (HV only, all states) + count of voltage-less lines
    novolt = {}
    for w in ways.values():
        t = w["tags"]
        if t.get("power") not in ("line", "cable") or len(w["geometry"]) < 2:
            continue
        g = LineString([(p["lon"], p["lat"]) for p in w["geometry"]])
        st = states_of(g)
        if not t.get("voltage"):
            if t.get("power") == "line":
                for c in st:
                    novolt[c] = novolt.get(c, 0) + 1
            continue
        if HV.search(t["voltage"]):
            b, _ = bounds_center(w["geometry"])
            add("lines_hv", st, {**w, "bounds": b})

    member_of_power_rel = set()
    for r in rels:
        if r["tags"].get("power") in KEEP_POWER:
            member_of_power_rel.update(m["ref"] for m in r["members"] if m["type"] == "way")

    def point_state(lon, lat):
        s = states_of(Point(lon, lat))
        return s or set()

    for layer, pv in (("substations", ("substation", "converter")), ("plants", ("plant",)),
                      ("generators", ("generator",))):
        for n in nodes.values():
            if n["tags"].get("power") in pv:
                add(layer, point_state(n["lon"], n["lat"]), n)
        for w in ways.values():
            if w["tags"].get("power") in pv and len(w["geometry"]) >= 2:
                b, c = bounds_center(w["geometry"])
                el = {"type": "way", "id": w["id"], "tags": w["tags"], "bounds": b, "center": c}
                if layer == "plants":
                    el["geometry"] = w["geometry"]
                add(layer, point_state(c["lon"], c["lat"]), el)
        for r in rels:
            if r["tags"].get("power") in pv:
                pts = [p for m in r["members"] for p in m.get("geometry", [])]
                if not pts:
                    continue
                b, c = bounds_center(pts)
                el = {"type": "relation", "id": r["id"], "tags": r["tags"], "bounds": b, "center": c}
                if layer == "plants":
                    el["members"] = r["members"]
                add(layer, point_state(c["lon"], c["lat"]), el)

    manifest_p = os.path.join(RAW, "manifest.json")
    manifest = json.load(open(manifest_p)) if os.path.exists(manifest_p) else {}
    stamp = os.path.basename(src)
    all_codes = set(codes)
    for layer in ("lines_hv", "substations", "plants", "generators"):
        for c in sorted(all_codes):
            if c == "IN-TN" and not include_tn:
                continue
            els = out.get((layer, c), [])
            json.dump({"generator": f"pyosmium from {stamp}", "elements": els},
                      open(os.path.join(RAW, f"{layer}_{c}.json"), "w"))
            manifest[f"{layer}_{c}"] = f"geofabrik:{stamp}"
    for c in sorted(all_codes):
        if c == "IN-TN" and not include_tn:
            continue
        json.dump({"elements": [{"type": "count", "tags": {"ways": str(novolt.get(c, 0))}}]},
                  open(os.path.join(RAW, f"lines_novolt_count_{c}.json"), "w"))
        manifest[f"lines_novolt_count_{c}"] = f"geofabrik:{stamp}"
    json.dump(manifest, open(manifest_p, "w"), indent=1, sort_keys=True)
    print("done", file=sys.stderr)


if __name__ == "__main__":
    main()
