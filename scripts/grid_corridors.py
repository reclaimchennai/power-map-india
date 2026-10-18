"""Check that major interstate / HVDC / Chennai corridors are present in build/grid outputs.
Writes build/grid/corridor_check.json (consumed by NOTES.md)."""
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "grid")


def load(n):
    return json.load(open(os.path.join(OUT, n)))["features"]


def km(a, b):
    return math.hypot((a[0] - b[0]) * 111.32 * math.cos(math.radians((a[1] + b[1]) / 2)), (a[1] - b[1]) * 110.57)


def geod(coords):
    return sum(km(a, b) for a, b in zip(coords, coords[1:]))


def flat(g):
    return g["coordinates"] if g["type"] == "LineString" else [c for p in g["coordinates"] for c in p]


SUBS = load("substations.geojson")
LINES = {c: load(f"lines_{c}.geojson") for c in ("765", "400", "220", "110", "hvdc")}


def sub(pattern, vmin=0, state=None):
    out = []
    for f in SUBS:
        p = f["properties"]
        if p["name"] and re.search(pattern, p["name"], re.I) and (p["voltage_kv"] or 0) >= vmin \
                and (state is None or p["state"] == state):
            out.append(f)
    return out


def lines_near(pt, classes, r=1.5):
    n = {}
    for c in classes:
        k = 0
        for f in LINES[c]:
            co = flat(f["geometry"])
            if km(pt, co[0]) < r or km(pt, co[-1]) < r:
                k += 1
        if k:
            n[c] = k
    return n


def named_lines(pattern, classes=("hvdc", "765", "400")):
    fs = [f for c in classes for f in LINES[c] if re.search(pattern, " ".join(
        str(f["properties"].get(k) or "") for k in ("name", "ref", "operator")), re.I)]
    return {"segments": len(fs), "km": round(sum(geod(flat(f["geometry"])) for f in fs)),
            "voltages": sorted({f["properties"]["voltage_kv"] for f in fs}, reverse=True)}


def sub_check(label, pattern, vmin, state=None, classes=("765", "400", "220", "hvdc")):
    hits = sub(pattern, vmin, state)
    res = []
    for f in hits:
        c = f["geometry"]["coordinates"]
        res.append({"name": f["properties"]["name"], "voltages": f["properties"]["voltages"],
                    "osm_id": f["properties"]["osm_id"], "lonlat": c, "line_ends_within_1_5km": lines_near(c, classes)})
    return {"check": label, "found": bool(hits), "substations": res}


def main():
    hv = LINES["hvdc"]
    checks = {
        "hvdc_by_name": {
            "Raigarh-Pugalur +-800kV": named_lines(r"raigarh|pugalur|pugaloor", ("hvdc",)),
            "Pugalur-Thrissur +-320kV VSC": named_lines(r"thrissur|trichur|madakkathara", ("hvdc",)),
            "Talcher-Kolar +-500kV": named_lines(r"talcher|kolar", ("hvdc",)),
            "Champa-Kurukshetra +-800kV": named_lines(r"champa|kurukshetra", ("hvdc",)),
            "Biswanath Chariali-Agra +-800kV": named_lines(r"biswanath|agra|alipurduar", ("hvdc",)),
            "Rihand-Dadri +-500kV": named_lines(r"rihand|dadri", ("hvdc",)),
            "Mundra-Mohindergarh +-500kV": named_lines(r"mundra|mohindergarh|mahendragarh", ("hvdc",)),
            "Balia-Bhiwadi +-500kV": named_lines(r"balia|bhiwadi", ("hvdc",)),
            "Chandrapur-Padghe +-500kV": named_lines(r"chandrapur|padghe", ("hvdc",)),
        },
        "hvdc_all": {"segments": len(hv), "km": round(sum(geod(flat(f["geometry"])) for f in hv)),
                     "named": sorted({f["properties"]["name"] for f in hv if f["properties"]["name"]})},
        "hvdc_terminals": [
            sub_check("Pugalur HVDC", r"pugalur|pugaloor", 300),
            sub_check("Raigarh HVDC", r"raigarh", 400),
            sub_check("Kolar HVDC", r"kolar", 400),
            sub_check("Talcher HVDC", r"talcher", 400),
            sub_check("Thrissur/Madakkathara", r"madakkathara|thrissur|trichur", 300),
        ],
        "tn_nodes": [
            sub_check("Kudankulam NPP switchyard", r"kudankulam|koodankulam", 400),
            sub_check("Tirunelveli (PGCIL Abishekapatti)", r"tirunelveli|thirunelveli|abishek", 400),
            sub_check("Tuticorin pooling 765/400", r"tuticorin pool|thoothukudi pool", 400),
            sub_check("Virudhunagar 765", r"virudhunagar", 700),
            sub_check("Salem 765 (Dharmapuri)", r"salem|dharmapuri", 700),
            sub_check("Thiruvalam 765/400", r"thiruvalam|tiruvalam", 400),
            sub_check("Ariyalur 765", r"ariyalur", 700),
            sub_check("North Chennai Pooling 765", r"ncps|north chennai pool", 700),
            sub_check("Nagapattinam 765", r"nagapattinam", 700),
            sub_check("Madurai (Chekkanurani) 400", r"madurai|cheack|chekk|checka", 400),
            sub_check("Udumalpet 400", r"udumalpet", 400),
        ],
        "chennai_400kv_ring": [
            sub_check(n, p, 380) for n, p in [
                ("Alamathy", r"alamath"), ("Manali", r"^manali"), ("Sriperumbudur (PGCIL)", r"sriperum"),
                ("Pennalur/Sriperumbudur (TANTRANSCO)", r"pennalur"), ("Tiruvalam", r"thiruvalam|tiruvalam"),
                ("NCTPS", r"north chennai"), ("Vallur", r"vallur"), ("Kalivanthapattu", r"kalivan"),
                ("Pulianthope 400 kV GIS", r"pulian"), ("Sunguvarchatram", r"sungu|sunga"),
                ("Ottiyambakkam (Sholinganallur)", r"ottiyam|sholinga"), ("Thervoy Kandigai", r"thervo"),
                ("Ennore SEZ", r"ennore sez"), ("NCPS 765/400", r"ncps")]],
    }
    json.dump(checks, open(os.path.join(OUT, "corridor_check.json"), "w"), indent=1, ensure_ascii=False)
    for k, v in checks["hvdc_by_name"].items():
        print(k, v)
    for grp in ("hvdc_terminals", "tn_nodes", "chennai_400kv_ring"):
        for c in checks[grp]:
            print(grp, c["check"], c["found"], [(s["name"], s["voltages"], s["line_ends_within_1_5km"]) for s in c["substations"]][:3])


if __name__ == "__main__":
    main()
