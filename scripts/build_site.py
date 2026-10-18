#!/usr/bin/env python3
"""Merge every plant source into the published atlas: web/data/plants.json.

Sources, in order of authority for each field:
  1. build/dossier/*.json      hand/agent-verified dossiers (TN first), SCHEMA.md records
  2. NPP gc-map station list   (data/power.db npp_stations) — all-India conventional stations
  3. CEA DGR2 daily XLS        (dgr_stations) — fuel subtype (GT/DG), sector, monitored capacity
  4. OSM power=plant           (build/grid/osm_plants.geojson) — footprint + position check, RE farms
  5. seed atlas                (data/plants_tn_seed.csv) — the prototype's hand list

Positions are QA'd like the lighthouse ledgers: NPP coordinates are often wrong (digit slips such
as Ennore SCTPP at 3.29°N, stations copied onto a neighbour's point, hydro stations dropped in
the plains). A position is kept only if it falls inside (or within 8 km of) its own state, is not
a copy of another station's point, and — when an OSM or dossier position exists — agrees with
it. Every correction lands in build/build_notes.txt.
"""
import json
import math
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import shape, Point
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "power.db"
OUT = ROOT / "web" / "data"
BUILD = ROOT / "build"
NOTES = []

# NPP state names -> raw/geo/india_states_polygons.geojson (ST_NM, from ~/projects/nfhs)
STATE_ALIASES = {"Jammu and Kashmir": "Jammu & Kashmir", "Andaman & Nicobar Islands": "Andaman & Nicobar",
                 "Chhatisgarh": "Chhattisgarh", "Pondicherry": "Puducherry",
                 "Dadra & Nagar Haveli": "Dadra and Nagar Haveli and Daman and Diu",
                 "Daman & Diu": "Dadra and Nagar Haveli and Daman and Diu"}
LIGNITE = re.compile(r"NEYVELI|BARSINGSAR|GIRAL|AKRIMOTA|SURAT LIG|KUTCH LIG|BHAVNAGAR|RAJPARDI|JALIPA|KAPURDI|"
                     r"GURHA|BHADESAR|TPS\(Z\)|ST-CMSECP|NNTPP", re.I)


STATE_BACK = {"Andaman and Nicobar Islands": "Andaman & Nicobar Islands"}


def note(msg):
    NOTES.append(msg)


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def norm(s):
    s = (s or "").upper().replace("`", "").replace("'", "")
    s = re.sub(r"\bTHERMAL POWER (STATION|PLANT|PROJECT)\b", "TPS", s)
    s = re.sub(r"\b(STPS|STPP|TPP|TPS|SCTPP|CCPP|GPS|HPS|HEP|APS|NPP)\b", r" \1 ", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ACRONYMS = {"TPS", "TPP", "STPS", "STPP", "SCTPP", "HPS", "HEP", "CCPP", "CCGT", "GPS", "GT", "DG", "APS", "NPP", "PSP", "PSS",
            "NTPC", "NLC", "NTPL", "ITPCL", "OPG", "TCP", "GMR", "JSW", "KSK", "RKM", "MB", "NTECL", "NCTPS", "MTPS", "TTPS",
            "BBGTPS", "KGTPS", "VGTPS", "GTPS", "PH", "ST", "RB", "LBC", "RBC", "SBU", "UP", "MP", "TN", "AP", "HP", "JP", "NEC",
            "IPP", "CPP", "SEPC", "PPN", "TAQA", "BHEL", "DVC", "NHPC", "SJVN", "THDC", "NEEPCO", "BBMB", "APGENCO", "TSGENCO",
            "KPCL", "MSPGCL", "GSECL", "RRVUNL", "UPRVUNL", "WBPDCL", "OPGC", "CESC", "IGSTPP", "PFBR", "BHAVINI", "LTD", "PVT"}
ROMAN = re.compile(r"^(?=[IVX]+$)X{0,3}(IX|IV|V?I{0,3})$")


def nice(name):
    """NPP names are upper case: 'METTUR TPS-II' -> 'Mettur TPS-II', keeping acronyms and numerals."""
    def run(m):
        w = m.group(0).upper()
        return w if w in ACRONYMS or ROMAN.match(w) else w.capitalize()
    s = re.sub(r"\s+", " ", name.replace("`", "'")).strip()
    s = re.sub(r"[A-Za-z]+", run, s)
    return re.sub(r"'S\b", "'s", s).replace("( ", "(")


def km(a_lat, a_lon, b_lat, b_lon):
    R = 6371.0
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp, dl = p2 - p1, math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def load_states():
    base = json.load(open(ROOT / "raw" / "geo" / "india_states_polygons.geojson"))
    states = {}
    for f in base["features"]:
        g = shape(f["geometry"]).buffer(0)
        states[f["properties"]["ST_NM"]] = (g, prep(g.buffer(0.08)))   # ~8 km tolerance
    return states


def fuel_of(name, npp_type, dgr_type):
    n = name.upper()
    if npp_type == "nuclear":
        return "nuclear"
    if npp_type == "hydro":
        return "pumped_storage" if re.search(r"\bPSP\b|PUMPED|PSS", n) else "hydro"
    if dgr_type == "THER (GT)" or re.search(r"CCPP|\bGPS\b|\bGT\b|GAS|CCGT|\bGTPS\b|LNG", n):
        return "gas"
    if dgr_type == "THER (DG)" or re.search(r"\bDG\b|DIESEL|\(LIQ", n):
        return "diesel"
    if LIGNITE.search(n):
        return "lignite"
    return "coal"


def load_dossiers():
    out = []
    for p in sorted((BUILD / "dossier").glob("*.json")):
        try:
            data = json.load(open(p))
        except Exception as e:
            note(f"dossier {p.name} unreadable: {e}")
            continue
        recs = data if isinstance(data, list) else data.get("plants", [])
        out += recs
    return out


GENERIC = set("""TPS TPP STPS STPP SCTPP HPS HEP APS NPP PSP CCPP CCGT GPS GT DG GTPS POWER PLANT STATION STATIONS THERMAL
PROJECT PROJECTS LTD LIMITED PVT PRIVATE STAGE UNIT UNITS HYDRO HYDEL HYDROELECTRIC ELECTRIC NUCLEAR ATOMIC GAS
DIESEL SOLAR WIND ENERGY GENERATION COMPANY CORPORATION NEW OLD EXT EXTN EXTENSION PH I II III IV V VI VII DAM
BARRAGE THE OF AND POWERHOUSE HOUSE SUPER CRITICAL COMBINED CYCLE TURBINE UPPER LOWER NORTH SOUTH EAST WEST MAIN BIG""".split())


def key_tokens(name):
    return [t for t in norm(name).split() if t not in GENERIC and not t.isdigit() and len(t) > 2]


def load_osm_plants():
    p = BUILD / "grid" / "osm_plants.geojson"
    if not p.exists():
        return []
    fc = json.load(open(p))
    res = []
    for f in fc["features"]:
        pr = f["properties"]
        try:
            c = shape(f["geometry"]).representative_point() if f["geometry"]["type"] != "Point" else shape(f["geometry"])
        except Exception:
            continue
        res.append({"name": pr.get("name") or pr.get("name:en") or "", "lat": c.y, "lon": c.x, "props": pr,
                    "geom": f["geometry"]})
    return res


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    states = load_states()

    def in_state(state, lat, lon):
        st = STATE_ALIASES.get(state, state)
        if st not in states or lat is None:
            return None
        return states[st][1].contains(Point(lon, lat))

    dgr_day = con.execute("SELECT max(date) FROM dgr_stations").fetchone()[0]
    dgr = {norm(r["station"]): dict(r) for r in con.execute(
        "SELECT * FROM dgr_stations WHERE date=? AND station!='__STATE_TOTAL__'", (dgr_day,))}
    stations = [dict(r) for r in con.execute("SELECT * FROM npp_stations ORDER BY station_id")]

    # coordinates shared by >1 station with different names -> copies, not positions
    by_pt = defaultdict(list)
    for s in stations:
        if s["lat"] is not None:
            by_pt[(round(s["lat"], 3), round(s["lon"], 3))].append(s)

    dossiers = load_dossiers()
    dos_by_alias = {}
    for d in dossiers:
        for a in [d.get("name", "")] + (d.get("aliases") or []):
            dos_by_alias[norm(a)] = d
        npp_id = (d.get("links") or {}).get("npp_station_id")
        if npp_id:
            dos_by_alias[f"#npp{npp_id}"] = d
    osm = load_osm_plants()

    plants, used_dossiers = [], set()
    for s in stations:
        name = s["name"]
        d = dos_by_alias.get(f"#npp{s['station_id']}") or dos_by_alias.get(norm(name))
        g = dgr.get(norm(name))
        fuel = fuel_of(name, s["type"], (g or {}).get("type"))
        lat, lon, q = s["lat"], s["lon"], "npp"
        problems = []
        if lat is None:
            problems.append("no position")
        else:
            first = lambda n: norm(n).replace(" ", "")[:5]
            # same complex (URI-I/URI-II, KOTHAGUDEM/KOTHAGUDEM NEW) may share a point; strangers may not
            twins = [t for t in by_pt[(round(lat, 3), round(lon, 3))]
                     if norm(t["name"]) != norm(name) and first(t["name"]) != first(name)]
            if twins:
                problems.append("same point as " + ", ".join(t["name"] for t in twins))
            if in_state(s["state"], lat, lon) is False:
                problems.append(f"outside {s['state']}")
        # same-named OSM plant in the same state, far from the NPP point: the NPP point is a slip
        if lat is not None and not problems and not d:
            kt = key_tokens(name)
            if kt:
                cand = [o for o in osm if o["name"] and kt[0] in key_tokens(o["name"]) and in_state(s["state"], o["lat"], o["lon"])]
                if cand and all(km(lat, lon, o["lat"], o["lon"]) > 8 for o in cand):
                    o = min(cand, key=lambda o: km(lat, lon, o["lat"], o["lon"]))
                    note(f"{name}: NPP {lat:.4f},{lon:.4f} is {km(lat, lon, o['lat'], o['lon']):.0f} km from OSM '{o['name']}' -> OSM {o['lat']:.4f},{o['lon']:.4f}")
                    lat, lon, q = o["lat"], o["lon"], "osm"
        if d and d.get("lat") is None and lat is not None:
            # the dossier researched this station and could not verify a position: don't trust NPP's alone
            note(f"{name}: dossier has no verified position; NPP {lat:.4f},{lon:.4f} not used — not mapped")
            lat = lon = None
        if d and d.get("lat") is not None:
            if lat is not None and not problems and km(lat, lon, d["lat"], d["lon"]) > 3:
                note(f"{name}: NPP {lat:.4f},{lon:.4f} vs dossier {d['lat']:.4f},{d['lon']:.4f} "
                     f"({km(lat, lon, d['lat'], d['lon']):.1f} km) -> dossier")
            lat, lon, q = d["lat"], d["lon"], d.get("loc_quality", "dossier")
        elif problems:
            # nearest same-named OSM plant within the state
            cand = [o for o in osm if o["name"] and (norm(o["name"]).split(" ")[0] in norm(name).split(" "))
                    and in_state(s["state"], o["lat"], o["lon"])]
            if cand and lat is not None:
                cand.sort(key=lambda o: km(lat, lon, o["lat"], o["lon"]))
            if cand:
                o = cand[0]
                note(f"{name}: NPP position rejected ({'; '.join(problems)}) -> OSM '{o['name']}' {o['lat']:.4f},{o['lon']:.4f}")
                lat, lon, q = o["lat"], o["lon"], "osm"
            else:
                note(f"{name}: NPP position rejected ({'; '.join(problems)}); no replacement — not mapped")
                lat = lon = None
        if d:
            used_dossiers.add(id(d))
        cap = (d or {}).get("capacity_mw") or s["capacity_mw"] or (g or {}).get("cap_mw") or 0
        rec = {
            "id": (d or {}).get("id") or slug(name),
            "name": (d or {}).get("name") or nice(name),
            "type": (d or {}).get("type") or fuel,
            "state": s["state"], "lat": lat, "lon": lon, "q": q,
            "cap": round(cap, 2), "npp": s["station_id"], "npp_name": name,
            "sector": ((g or {}).get("sector") or "").replace(" SECTOR", "").lower() or None,
            "status": (d or {}).get("status") or "operating",
        }
        if d:
            rec["dossier"] = True
        plants.append(rec)

    # dossier records not in NPP (RE farms, planned, retired, captive...)
    for d in dossiers:
        if id(d) in used_dossiers or d.get("lat") is None:
            continue
        plants.append({"id": d["id"], "name": d["name"], "type": d["type"], "state": d.get("state"),
                       "lat": d["lat"], "lon": d["lon"], "q": d.get("loc_quality", "dossier"),
                       "cap": d.get("capacity_mw") or 0, "npp": (d.get("links") or {}).get("npp_station_id"),
                       "status": d.get("status") or "operating", "dossier": True,
                       **({"cluster": True} if d.get("cluster") else {}),
                       **({"part_of": d["part_of"]} if d.get("part_of") else {})})

    # OpenStreetMap renewables across India: NPP lists only conventional stations. Solar/wind/biomass/
    # waste plants >= ~1 MW, skipping any within 1.5 km of a station already placed. Capacity from the
    # OSM tag, else estimated from the array area (~2 ha per MW, labelled cap_est).
    RE = {"solar": "solar", "wind": "wind", "biomass": "biomass", "biofuel": "biomass", "biogas": "biomass", "waste": "waste"}
    placed = [(p["lat"], p["lon"]) for p in plants if p.get("lat") is not None]
    grid_idx = defaultdict(list)
    for la, lo in placed:
        grid_idx[(round(la, 1), round(lo, 1))].append((la, lo))
    def near(la, lo, r_km=1.5):
        for dy in (-0.1, 0, 0.1):
            for dx in (-0.1, 0, 0.1):
                for q in grid_idx.get((round(la + dy, 1), round(lo + dx, 1)), []):
                    if km(la, lo, *q) < r_km:
                        return True
        return False
    n_osm = 0
    for o in osm:
        pr = o["props"]
        t = RE.get(pr.get("source_type") or "")
        if not t:
            continue
        cap, est = pr.get("capacity_mw"), False
        if not cap and pr.get("area_ha"):
            cap, est = round(pr["area_ha"] / 2.0, 1), True
        if not cap or cap < 1 or cap > 5000 or near(o["lat"], o["lon"]):
            continue
        st = pr.get("state") or ""
        rec = {"id": f"osm-{slug(o['name'] or t)}-{pr.get('osm_id', '').split('/')[-1]}",
               "name": o["name"] or f"{t.title()} plant ({pr.get('operator') or 'unnamed'})",
               "type": t, "state": STATE_BACK.get(st, st), "lat": round(o["lat"], 5), "lon": round(o["lon"], 5),
               "q": "osm", "cap": cap, "status": "operating", "osm": pr.get("osm_id")}
        if est:
            rec["cap_est"] = True
        plants.append(rec)
        grid_idx[(round(o["lat"], 1), round(o["lon"], 1))].append((o["lat"], o["lon"]))
        n_osm += 1
    note(f"OSM renewables added: {n_osm}")

    # prototype seed list: RE clusters the other sources lack
    have = {norm(p["name"]) for p in plants}
    import csv
    for r in csv.DictReader(open(ROOT / "data" / "plants_tn_seed.csv")):
        if r["type"] in ("wind", "solar") and norm(r["name"]) not in have and not dossiers:
            plants.append({"id": slug(r["name"]), "name": r["name"], "type": r["type"], "state": "Tamil Nadu",
                           "lat": float(r["lat"]), "lon": float(r["lon"]), "q": r["accuracy"],
                           "cap": float(r["capacity_mw"]), "status": "operating", "cluster": True})

    # unique ids
    seen = defaultdict(int)
    for p in plants:
        seen[p["id"]] += 1
        if seen[p["id"]] > 1:
            p["id"] = f"{p['id']}-{seen[p['id']]}"

    mapped = [p for p in plants if p["lat"] is not None]
    # coastal plants: compass bearing to the nearest coastline, so sea-cooled layouts (intake canals,
    # jetties) face the real sea. Natural Earth land (web/data/basemap.json), within ~6 km of the coast.
    from shapely.ops import nearest_points, unary_union
    land = unary_union([shape(f["geometry"]).buffer(0) for f in json.load(open(OUT / "basemap.json"))["land"]["features"]])
    coast = land.boundary
    for p in mapped:
        pt = Point(p["lon"], p["lat"])
        if coast.distance(pt) > 0.055:
            continue
        q = nearest_points(pt, coast)[1]
        dx, dy = (q.x - pt.x) * math.cos(math.radians(p["lat"])), q.y - pt.y
        if not land.contains(pt):          # plant point already in the sea polygon: face away from land
            dx, dy = -dx, -dy
        if abs(dx) + abs(dy) > 1e-6:
            p["sea"] = round((math.degrees(math.atan2(dx, dy)) + 360) % 360)
    counts = defaultdict(lambda: [0, 0.0])
    for p in mapped:
        counts[p["type"]][0] += 1
        counts[p["type"]][1] += p["cap"] or 0
    out = {"meta": {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "counts": {k: {"n": v[0], "mw": round(v[1])} for k, v in sorted(counts.items())},
                    "unmapped": [p["name"] for p in plants if p["lat"] is None]},
           "plants": mapped}
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(OUT / "plants.json", "w"), separators=(",", ":"))
    # full dossiers served per plant for the card
    ddir = OUT / "dossier"
    ddir.mkdir(exist_ok=True)
    for d in dossiers:
        json.dump(d, open(ddir / f"{d['id']}.json", "w"), separators=(",", ":"))
    (BUILD / "build_notes.txt").write_text("\n".join(NOTES) + "\n")
    print(f"plants: {len(mapped)} mapped, {len(out['meta']['unmapped'])} unmapped; notes: {len(NOTES)}")
    for k, v in out["meta"]["counts"].items():
        print(f"  {k:15s} {v['n']:4d}  {v['mw']:>8,} MW")


if __name__ == "__main__":
    main()
