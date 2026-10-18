"""Indian coal mines and coal terminals from Global Energy Monitor's trackers (CC BY 4.0).

GEM publishes the map data behind its Global Coal Mine Tracker (GCMT) and Global Coal Terminals Tracker (GCTT) as
GeoJSON; the file name (with its release month) sits in each tracker map's config.js under `geojson:`.
run() reads both configs, downloads a file only when the config names one not yet in raw/coal/gem/ (gitignored), and
writes India-only compact records:

  build/feedstock/gem/india_coal_mines.json      every status (operating, proposed, shelved, cancelled, mothballed,
                                                 closed); a mine with an expansion phase has one record per phase
                                                 (same id, different status / capacity)
  build/feedstock/gem/india_coal_terminals.json  one record per terminal unit / phase

The public map data has no import / export / domestic split for terminals (that field is only in GEM's
form-gated spreadsheet), so terminal "type" is null.

    python -m scrapers.gem_coal
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "coal" / "gem"
OUT = ROOT / "build" / "feedstock" / "gem"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 (reclaimchennai power map)"}
CONFIG = "https://globalenergymonitor.github.io/interim-maps/trackers/{t}/config.js"
TRACKER = {"gcmt": "Global Coal Mine Tracker", "gctt": "Global Coal Terminals Tracker"}
LICENCE = "CC BY 4.0, Global Energy Monitor"
MONTHS = "January February March April May June July August September October November December".split()


def latest_url(tracker):
    js = requests.get(CONFIG.format(t=tracker), headers=UA, timeout=60).text
    m = re.search(r"""geojson\s*:\s*['"]([^'"]+)['"]""", js)
    if not m:
        raise RuntimeError(f"{tracker}: no geojson key in config.js")
    return m.group(1)


def file_month(name):
    m = re.search(r"(\d{4})-(\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def fetch(tracker):
    """(url, local path, downloaded?) for the tracker's current GeoJSON; falls back to the newest local copy offline."""
    RAW.mkdir(parents=True, exist_ok=True)
    ign = RAW / ".gitignore"
    if not ign.exists():
        ign.write_text("*\n")
    try:
        url = latest_url(tracker)
    except Exception as e:
        have = sorted(RAW.glob(f"{tracker}*.geojson"), key=lambda p: file_month(p.name) or "")
        if not have:
            raise
        print(f"{tracker}: config unreachable ({e}); using {have[-1].name}")
        return None, have[-1], False
    path = RAW / url.rsplit("/", 1)[1]
    if path.exists() and path.stat().st_size > 1000:
        return url, path, False
    r = requests.get(url, headers=UA, timeout=300)
    r.raise_for_status()
    json.loads(r.content)                         # refuse to keep a truncated file
    tmp = path.with_suffix(".part")
    tmp.write_bytes(r.content)
    tmp.replace(path)
    return url, path, True


def num(v, whole=False):
    try:
        f = float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return int(f) if whole and f.is_integer() else f


def txt(v):
    v = (v or "").strip() if isinstance(v, str) else v
    return v or None


def meta(tracker, url, path):
    month = file_month(path.name)
    rel = f"{MONTHS[int(month[5:]) - 1]} {month[:4]}" if month else "current"
    return {
        "source": f"Global Energy Monitor, {TRACKER[tracker]}",
        "source_url": url or f"(cached) {path.name}",
        "config_url": CONFIG.format(t=tracker),
        "file": path.name,
        "file_date": month,
        "licence": LICENCE,
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": f"Global Energy Monitor, {TRACKER[tracker]}, {rel} release. "
                       f"Licensed under CC BY 4.0 (https://globalenergymonitor.org).",
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def india(path):
    g = json.loads(path.read_text())
    return [f for f in g["features"] if (f["properties"].get("country-area1") or "").strip() == "India"]


def point(f):
    p = f["properties"]
    lat, lon = num(p.get("Latitude")), num(p.get("Longitude"))
    geom = f.get("geometry") or {}
    if (lat is None or lon is None) and geom.get("type") == "Point":
        lon, lat = geom["coordinates"][:2]
    return (round(lat, 5) if lat is not None else None), (round(lon, 5) if lon is not None else None)


def mines(path):
    seen, out = set(), []
    # Point features first, so a mine drawn both as a point and a polygon keeps the point
    for f in sorted(india(path), key=lambda f: (f.get("geometry") or {}).get("type") != "Point"):
        p = f["properties"]
        key = (p["project-id"], p.get("status"), str(p.get("capacity")), p.get("start-year"))
        if key in seen:
            continue
        seen.add(key)
        lat, lon = point(f)
        mt = (p.get("mine-type") or "").strip().lower()
        out.append({
            "id": p["project-id"], "name": txt(p.get("name")), "owner": txt(p.get("owner")), "parent": txt(p.get("parent")),
            "status": txt(p.get("status")), "type": mt or None, "coal_grade": txt(p.get("coal-grade")),
            "coalfield": txt(p.get("coal-field")), "state": txt(p.get("subnational")), "lat": lat, "lon": lon,
            "loc_accuracy": txt(p.get("location-accuracy")),
            "geometry": (f.get("geometry") or {}).get("type", "").lower() or None,
            "capacity_mtpa": num(p.get("capacity")), "production_mt": num(p.get("prod-coal")),
            "production_year": num(p.get("prod-year-coal"), True), "start_year": num(p.get("start-year"), True),
            "end_year": num(p.get("end-year"), True), "workforce": num(p.get("workforce"), True), "url": txt(p.get("url")),
        })
    out.sort(key=lambda r: (r["id"], r["status"] != "operating"))
    return out


def terminals(path):
    out = []
    for f in india(path):
        p = f["properties"]
        lat, lon = point(f)
        out.append({
            "id": p.get("unit-id") or p.get("project-id"), "project_id": p.get("project-id"),
            "name": txt(p.get("name")), "phase": txt(p.get("name-other")), "port": txt(p.get("port")),
            "owner": txt(p.get("owner")), "status": txt(p.get("status")), "type": None,
            "capacity_mtpa": num(p.get("capacity")), "start_year": num(p.get("start-year"), True), "end_year": num(p.get("end-year"), True),
            "state": txt(p.get("subnational")), "lat": lat, "lon": lon, "url": txt(p.get("url")),
        })
    out.sort(key=lambda r: (r["name"] or "", r["id"] or ""))
    return out


def write(name, m, records, extra=None):
    OUT.mkdir(parents=True, exist_ok=True)
    doc = {"meta": {**m, "count": len(records), **(extra or {})}, "records": records}
    (OUT / name).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    return OUT / name


def status_counts(records):
    c = {}
    for r in records:
        c[r["status"]] = c.get(r["status"], 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def run(force=False):
    """Refresh both files when a config names a newer GeoJSON (or the outputs are missing, or force)."""
    report = {}
    for tracker, name, build in (("gcmt", "india_coal_mines.json", mines), ("gctt", "india_coal_terminals.json", terminals)):
        url, path, new = fetch(tracker)
        out = OUT / name
        if not (new or force or not out.exists()):
            try:
                if json.loads(out.read_text())["meta"].get("file") == path.name:
                    report[tracker] = f"unchanged ({path.name})"
                    continue
            except Exception:
                pass
        recs = build(path)
        extra = {"note": "terminal import/export/domestic type is not in GEM's public map data"} if tracker == "gctt" else \
                {"note": "one record per mine phase: an expansion appears as a second record with the same id"}
        write(name, meta(tracker, url, path), recs, {"by_status": status_counts(recs), **extra})
        report[tracker] = f"{len(recs)} records from {path.name}"
    try:
        from store import log
        log("gem_coal", "ok", "; ".join(f"{k}: {v}" for k, v in report.items()))
    except Exception:
        pass
    return report


if __name__ == "__main__":
    print(run(force="--force" in sys.argv))
