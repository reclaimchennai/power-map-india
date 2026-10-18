#!/usr/bin/env python3
"""Build data/geo/: GeoJSON (source of truth), one GeoPackage with every layer, and per-layer Shapefile zips.
Needs GDAL's ogr2ogr on PATH. All coordinates are WGS84 (EPSG:4326)."""
import json, shutil, subprocess, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "geo"
GJ, SHP = OUT / "geojson", OUT / "shapefile"
for d in (GJ, SHP):
    shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)

def fc(features):
    return {"type": "FeatureCollection", "features": features}

def flat(props):
    return {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in props.items()}

# 1. OSM grid layers (ODbL) -> verbatim copies
osm = {}
for p in sorted((ROOT / "build/grid").glob("*.geojson")):
    shutil.copy(p, GJ / f"grid_{p.stem}.geojson"); osm[p.stem] = True

# 2. supply chain + stations layers built from the JSON datasets
plants = json.load(open(ROOT / "web/data/plants.json"))["plants"]
(GJ / "power_stations_india.geojson").write_text(json.dumps(fc([
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
     "properties": flat({k: v for k, v in p.items() if k not in ("lat", "lon")})}
    for p in plants if p.get("lat") is not None and p.get("lon") is not None]), ensure_ascii=False))

feed = json.load(open(ROOT / "web/data/feed.json"))
(GJ / "supply_chain_nodes.geojson").write_text(json.dumps(fc([
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
     "properties": flat({k: v for k, v in n.items() if k not in ("lat", "lon")})}
    for n in feed["nodes"] if n.get("lat") is not None]), ensure_ascii=False))
(GJ / "supply_chain_routes.geojson").write_text(json.dumps(fc([
    {"type": "Feature", "geometry": {"type": "LineString", "coordinates": r["coords"]},
     "properties": flat({k: v for k, v in r.items() if k != "coords"})}
    for r in feed["routes"] if r.get("coords")]), ensure_ascii=False))

mines = json.load(open(ROOT / "build/feedstock/mines.json"))["mines"]
(GJ / "coal_mines_india.geojson").write_text(json.dumps(fc([
    {"type": "Feature", "geometry": {"type": "Point", "coordinates": [m["lon"], m["lat"]]},
     "properties": flat({k: v for k, v in m.items() if k not in ("lat", "lon")})}
    for m in mines if m.get("lat") is not None and m.get("lon") is not None]), ensure_ascii=False))
for name, src in (("gem_coal_mines", "build/feedstock/gem/india_coal_mines.json"),
                  ("gem_coal_terminals", "build/feedstock/gem/india_coal_terminals.json")):
    recs = json.load(open(ROOT / src))["records"]
    feats = []
    for r in recs:
        lat, lon = r.get("lat", r.get("latitude")), r.get("lon", r.get("longitude"))
        if lat is None or lon is None: continue
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
                      "properties": flat({k: v for k, v in r.items() if k not in ("lat", "lon", "latitude", "longitude")})})
    (GJ / f"{name}.geojson").write_text(json.dumps(fc(feats), ensure_ascii=False))

# 3. GeoPackage (all layers) + Shapefile zips
gpkg = OUT / "power_map_india.gpkg"
gpkg.unlink(missing_ok=True)
for p in sorted(GJ.glob("*.geojson")):
    n = len(json.load(open(p))["features"])
    if not n:
        p.unlink(); continue
    subprocess.run(["ogr2ogr", "-f", "GPKG", "-append" if gpkg.exists() else "-overwrite", "-update", str(gpkg), str(p),
                    "-nln", p.stem, "-nlt", "PROMOTE_TO_MULTI", "-lco", "SPATIAL_INDEX=YES", "-a_srs", "EPSG:4326"], check=True, capture_output=True)
    tmp = SHP / p.stem; tmp.mkdir()
    # Shapefiles hold one geometry type per file: split mixed layers
    kinds = {f["geometry"]["type"].replace("Multi", "") for f in json.load(open(p))["features"]}
    ok = True
    for k in sorted(kinds):
        suffix = f"_{k.lower()}" if len(kinds) > 1 else ""
        r = subprocess.run(["ogr2ogr", "-f", "ESRI Shapefile", str(tmp / f"{p.stem[:56]}{suffix}.shp"), str(p),
                            "-nlt", "PROMOTE_TO_MULTI", "-lco", "ENCODING=UTF-8", "-a_srs", "EPSG:4326",
                            "-mapFieldType", "StringList=String", "-where", f"OGR_GEOMETRY IN ('{k.upper()}','MULTI{k.upper()}')"],
                           capture_output=True, text=True)
        if r.returncode:
            print("shapefile failed", p.name, k, r.stderr[-200:]); ok = False
    if not ok:
        shutil.rmtree(tmp); continue
    with zipfile.ZipFile(SHP / f"{p.stem}.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(tmp.iterdir()): z.write(f, f.name)
    shutil.rmtree(tmp)
    print(p.stem, n)
