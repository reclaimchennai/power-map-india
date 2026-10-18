#!/usr/bin/env python3
"""Publish the grid layers to web/data/grid/ with a manifest (index.json) the page reads.

Prefers the OpenStreetMap extraction in build/grid/ (real line routes, see build/grid/NOTES.md);
falls back to the prototype's TNGIS layers in data/geo/ (tn_lines are straight substation-to-
substation segments, so they are marked schematic). Properties are trimmed to what the map uses,
coordinates rounded to 5 decimals (~1 m).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "build" / "grid"
OUT = ROOT / "web" / "data" / "grid"


def rnd(geom):
    def r(c):
        return [r(x) for x in c] if isinstance(c[0], list) else [round(c[0], 5), round(c[1], 5)]
    return {"type": geom["type"], "coordinates": r(geom["coordinates"])}


def write(name, feats):
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": feats}, open(OUT / name, "w"), separators=(",", ":"))
    return {"file": name, "n": len(feats), "bytes": (OUT / name).stat().st_size}


def kv_class(v):
    if v is None:
        return None
    if v >= 700: return "765"
    if v >= 380: return "400"
    if v >= 200: return "220"
    if v >= 60: return "110"
    return "dist"


def main():
    man = {"lines": {}, "substations": None, "turbines": None, "towers": None, "schematic": False}
    osm_ok = (B / "lines_400.geojson").exists()
    if osm_ok:
        for key in ("765", "400", "220", "110", "hvdc"):
            p = B / f"lines_{key}.geojson"
            if not p.exists():
                continue
            feats = []
            for f in json.load(open(p))["features"]:
                pr = f["properties"]
                feats.append({"type": "Feature", "geometry": rnd(f["geometry"]),
                              "properties": {k: pr.get(k) for k in ("voltage_kv", "circuits", "name", "operator") if pr.get(k) not in (None, "")}})
            man["lines"][key] = write(f"lines_{key}.geojson", feats)
        p = B / "lines_tn_distribution.geojson"
        if p.exists():
            feats = [{"type": "Feature", "geometry": rnd(f["geometry"]), "properties": {"voltage_kv": f["properties"].get("voltage_kv")}}
                     for f in json.load(open(p))["features"]]
            man["lines"]["dist"] = write("lines_dist.geojson", feats)
    else:
        by = {}
        for f in json.load(open(ROOT / "data" / "geo" / "tn_lines.geojson"))["features"]:
            k = kv_class(f["properties"].get("kv"))
            by.setdefault(k, []).append({"type": "Feature", "geometry": rnd(f["geometry"]),
                                         "properties": {"voltage_kv": f["properties"]["kv"], "name": f"{f['properties']['from']} – {f['properties']['to']}"}})
        for k, feats in by.items():
            man["lines"][k] = write(f"lines_{k}.geojson", feats)
        man["schematic"] = True

    # substations: merged TN (TNGIS attributes) + OSM India, else TNGIS only
    subs = []
    src = B / "tn_substations_merged.geojson"
    tn = json.load(open(src if src.exists() else ROOT / "data" / "geo" / "tn_substation.geojson"))["features"]
    for f in tn:
        pr = f["properties"]
        name = pr.get("name") or pr.get("sub_station")
        vr = pr.get("volt_ratio") or pr.get("voltage") or ""
        try:
            kv = max(float(x) for x in str(vr).replace("-", "/").split("/") if x.strip().replace(".", "").isdigit())
        except ValueError:
            kv = pr.get("voltage_kv")
        g = f["geometry"]
        if g["type"] != "Point":
            continue
        subs.append({"type": "Feature", "geometry": rnd(g), "properties": {
            "name": name, "kv": kv, "ratio": vr or None, "mva": pr.get("total_capacity") or pr.get("mva"),
            "tx": pr.get("no_pr_tr"), "feeders_out": pr.get("number_of_out_feeder"), "circle": pr.get("circle_name") or pr.get("circle"),
            "type": pr.get("sub_station_type"), "src": "tngis"}})
    p = B / "substations.geojson"
    if p.exists():
        seen = {(round(s["geometry"]["coordinates"][0], 2), round(s["geometry"]["coordinates"][1], 2)) for s in subs}
        for f in json.load(open(p))["features"]:
            pr = f["properties"]
            c = f["geometry"]["coordinates"]
            if (round(c[0], 2), round(c[1], 2)) in seen and pr.get("state") == "Tamil Nadu":
                continue
            subs.append({"type": "Feature", "geometry": rnd(f["geometry"]), "properties": {
                "name": pr.get("name"), "kv": pr.get("voltage_kv"), "operator": pr.get("operator"), "src": "osm"}})
    man["substations"] = write("substations.geojson", subs)

    p = B / "tn_wind_turbines.geojson"
    if p.exists():
        pts = []
        for f in json.load(open(p))["features"]:
            c = f["geometry"]["coordinates"]
            pr = f["properties"]
            def num(v):
                try: return float(str(v).split()[0])
                except Exception: return None
            pts.append([round(c[0], 5), round(c[1], 5), num(pr.get("height:hub") or pr.get("hub_h_m")), num(pr.get("rotor:diameter") or pr.get("rotor_d_m"))])
        json.dump(pts, open(OUT / "turbines.json", "w"), separators=(",", ":"))
        man["turbines"] = {"file": "turbines.json", "n": len(pts)}
    # OSM solar arrays (TN) and plant footprints (India): context polygons for close zoom
    p = B / "tn_solar_arrays.geojson"
    if p.exists():
        feats = [{"type": "Feature", "geometry": rnd(f["geometry"]), "properties": {"name": f["properties"].get("plant_name") or f["properties"].get("name")}}
                 for f in json.load(open(p))["features"] if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
        man["solar_arrays"] = write("solar_arrays.geojson", feats)
    p = B / "osm_plants.geojson"
    if p.exists():
        feats = [{"type": "Feature", "geometry": rnd(f["geometry"]), "properties": {"name": f["properties"].get("name"), "src": f["properties"].get("source_type")}}
                 for f in json.load(open(p))["features"] if f["geometry"]["type"] in ("Polygon", "MultiPolygon")]
        man["footprints"] = write("footprints.geojson", feats)
    json.dump(man, open(OUT / "index.json", "w"), indent=1)
    print(json.dumps(man, indent=1))


if __name__ == "__main__":
    main()
