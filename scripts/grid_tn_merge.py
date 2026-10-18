"""Merge TNGIS/TNEB substations (data/geo/tn_substation.geojson) with OSM substations and the
official TANTRANSCO/SLDC EHV lists. Output: build/grid/tn_substations_merged.geojson and
build/grid/tn_ehv_osm_check.json (official 765/400/230 kV substations missing from OSM).

Run after grid_build.py and grid_tn_official.py.
"""
import difflib
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grid_tn_official import phon, similar  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "build", "grid")
TNGIS = os.path.join(ROOT, "data", "geo", "tn_substation.geojson")
TNGIS_SRC = "file:data/geo/tn_substation.geojson (TNGIS generic_viewer:tn_substation)"
MAX_KM = 3.0

GENERIC = r"\b(SUB\s*-?\s*STATION|SUBSTATION|SS|S\s+S|TNEB|TANTRANSCO|TANGEDCO|TNEB\s+LTD|EB|OFFICE|KV|GIS|NCES|" \
          r"SWITCHING|SWITCH\s*YARD|SWITCHYARD|STATION|AUTO|CMRL|UG|HYBRID|ELECTRICITY|BOARD|POWERGRID|PGCIL|" \
          r"GRID|NEW|OLD|SUBSTN|SUB|STN)\b"


def clean_name(s):
    s = (s or "").upper()
    s = re.sub(r"\d+(\s*[/-]\s*\d+)*\s*K\s*V", " ", s)
    s = re.sub(r"\d+", " ", s)
    s = re.sub(r"[^A-Z() ]", " ", s)
    return " ".join(s.split())


def aliases(s):
    s = clean_name(s)
    parts = [re.sub(r"\(.*?\)", " ", s)] + re.findall(r"\((.*?)\)", s)
    out = set()
    for p in parts:
        p = re.sub(r"^(AT|NEAR)\s+", "", p.strip())
        p = re.sub(GENERIC, " ", p)
        k = phon(p, vowels=True)
        if len(k) >= 3:
            out.add(k)
        words = p.split()
        if len(words) >= 3:  # acronym alias, e.g. NORTH CHENNAI POOLING (STATION) -> NCPS
            out.add("".join(w[0] for w in words) + "S")
    return out


def sim(a, b):
    return similar(a, b) if a and b else 0.0


def km(a, b):
    dx = (a[0] - b[0]) * 111.32 * math.cos(math.radians((a[1] + b[1]) / 2))
    dy = (a[1] - b[1]) * 110.57
    return math.hypot(dx, dy)


def vmax(ratio):
    v = [int(x) for x in re.findall(r"\d{2,3}", ratio or "")]
    return max(v) if v else None


def vclass(v):
    if v is None:
        return None
    return 765 if v >= 700 else 400 if v >= 380 else 230 if v >= 200 else 110 if v >= 66 else v


def main():
    tg = json.load(open(TNGIS))["features"]
    osm = [f for f in json.load(open(os.path.join(OUT, "substations.geojson")))["features"]
           if f["properties"]["state"] == "Tamil Nadu"]
    off = json.load(open(os.path.join(OUT, "tn_ehv_substations_official.json")))["substations"]
    for f in osm:
        f["_al"] = aliases(f["properties"]["name"])
        f["_c"] = f["geometry"]["coordinates"]
    # ---- TNGIS <-> OSM, candidate pairs within MAX_KM
    pairs = []
    for i, t in enumerate(tg):
        p = t["properties"]
        c = t["geometry"]["coordinates"]
        t["_al"] = aliases(p["sub_station"])
        tv = vclass(vmax(p["volt_ratio"]))
        for j, o in enumerate(osm):
            d = km(c, o["_c"])
            if d > MAX_KM:
                continue
            ov = vclass(o["properties"]["voltage_kv"])
            s = sim(t["_al"], o["_al"]) if t["_al"] and o["_al"] else 0.0
            vok = ov is not None and tv is not None and ov == tv
            if s >= 0.8:
                score, kind = s + (0.1 if vok else 0) - d / 30, "name"
            elif d <= 0.4 and vok and (not o["_al"] or s >= 0.5):
                score, kind = 0.5 - d, "proximity+voltage"
            else:
                continue
            pairs.append((score, i, j, d, s, kind))
    pairs.sort(reverse=True)
    ti, oj = {}, {}
    for score, i, j, d, s, kind in pairs:
        if i in ti or j in oj:
            continue
        ti[i] = (j, d, s, kind)
        oj[j] = i
    # ---- official EHV list -> TNGIS / OSM by name + voltage class (greedy one-to-one)
    for r in off:
        r["_al"] = aliases(r["name"]) | aliases(r.get("sldc_name") or "")
    cand = []
    for k, r in enumerate(off):
        for i, t in enumerate(tg):
            if vclass(vmax(t["properties"]["volt_ratio"])) == r["voltage_class_kv"] and t["_al"]:
                sc = sim(r["_al"], t["_al"])
                if sc >= 0.82:
                    cand.append((sc, k, i))
    cand.sort(reverse=True)
    used_t = set()
    for r in off:
        r["_t"] = None
    for sc, k, i in cand:
        if off[k]["_t"] is None and i not in used_t:
            off[k]["_t"] = i
            used_t.add(i)
    cand = []
    for k, r in enumerate(off):
        tc = tg[r["_t"]]["geometry"]["coordinates"] if r["_t"] is not None else None
        for j, o in enumerate(osm):
            if not o["_al"]:
                continue
            sc = sim(r["_al"], o["_al"])
            if sc < 0.82:
                continue
            d = km(tc, o["_c"]) if tc else None
            ov = vclass(o["properties"]["voltage_kv"])
            if d is not None and d > MAX_KM and not (ov == r["voltage_class_kv"] and sc >= 0.9 and d <= 15):
                continue  # TNGIS points can be a few km off; allow a strong same-class name match up to 15 km
            if d is None and ov not in (r["voltage_class_kv"], None):
                continue  # no location to confirm: only accept same-class / untagged namesakes
            bonus = 0.2 if ov == r["voltage_class_kv"] else 0.1 if ov is None else 0
            cand.append((sc + bonus - (d or 0) / 30, k, j))
    cand.sort(reverse=True)
    used_o = set()
    for r in off:
        r["_o"] = None
    for sc, k, j in cand:
        if off[k]["_o"] is None and j not in used_o:
            off[k]["_o"] = j
            used_o.add(j)
    for r in off:
        if r["_o"] is None and r["_t"] is not None and r["_t"] in ti and ti[r["_t"]][0] not in used_o:
            r["_o"] = ti[r["_t"]][0]
            used_o.add(r["_o"])
        if r["_o"] is None and r["_t"] is not None:  # same-class OSM substation within 1.5 km of TNGIS point
            c = tg[r["_t"]]["geometry"]["coordinates"]
            near = [(km(c, o["_c"]), j) for j, o in enumerate(osm) if j not in used_o
                    and vclass(o["properties"]["voltage_kv"]) == r["voltage_class_kv"] and km(c, o["_c"]) <= 1.5]
            if near:
                r["_o"] = min(near)[1]
                used_o.add(r["_o"])
    off_hit = {r["_t"]: k for k, r in enumerate(off) if r["_t"] is not None}

    feats = []
    for i, t in enumerate(tg):
        p = t["properties"]
        props = {
            "name": p["sub_station"], "voltage_ratio": p["volt_ratio"], "voltage_kv": vmax(p["volt_ratio"]),
            "mva": p["total_capacity"] or None, "transformers": p["no_pr_tr"] or None,
            "feeders_in": p["number_of_in_feeder"], "feeders_out": p["number_of_out_feeder"],
            "in_feeder": p["in_feeder"], "type": p["sub_station_type"], "town_category": p["town_category"],
            "circle": p["circle_name"], "circle_code": p["circle_code"], "region_id": p["region_id"],
            "tneb_ss_id": p["sub_station_id"], "owner": "TNEB/TANTRANSCO/TNPDCL",
            "in_tngis": True, "source": "tngis+osm" if i in ti else "tngis",
            "sources": [TNGIS_SRC],
        }
        if i in ti:
            j, d, s, kind = ti[i]
            o = osm[j]["properties"]
            props.update({"osm_id": o["osm_id"], "osm_name": o["name"], "osm_voltages": o["voltages"],
                          "osm_operator": o["operator"], "osm_lonlat": osm[j]["_c"], "match": kind,
                          "match_dist_m": round(d * 1000), "match_name_score": round(s, 2)})
            props["sources"] = props["sources"] + o["sources"]
        else:
            props.update({"osm_id": None, "match": None})
        if i in off_hit:
            r = off[off_hit[i]]
            props.update({"official_name": r["name"], "official_voltage_ratio": r["voltage_ratio"],
                          "commissioned": r.get("commissioned"), "operation_circle": r.get("operation_circle"),
                          "edc": r.get("edc")})
            props["sources"] = props["sources"] + [s for s in r["sources"] if s not in props["sources"]]
        feats.append({"type": "Feature", "geometry": t["geometry"], "properties": props})
    # OSM-only TN substations
    for j, o in enumerate(osm):
        if j in oj:
            continue
        op = o["properties"]
        feats.append({"type": "Feature", "geometry": o["geometry"], "properties": {
            "name": op["name"], "voltage_ratio": "/".join(str(v) for v in op["voltages"]) or None,
            "voltage_kv": op["voltage_kv"], "mva": None, "circle": None, "owner": op["owner"],
            "in_tngis": False, "source": "osm", "osm_id": op["osm_id"], "osm_name": op["name"],
            "osm_voltages": op["voltages"], "osm_operator": op["operator"], "match": None,
            "sources": op["sources"]}})
    # ---- official EHV check
    check = []
    for r in off:
        o = osm[r["_o"]]["properties"] if r["_o"] is not None else None
        t = tg[r["_t"]] if r["_t"] is not None else None
        status = "in_osm" if o else "missing_from_osm"
        if o and vclass(o["voltage_kv"]) is not None and vclass(o["voltage_kv"]) < r["voltage_class_kv"]:
            status = "in_osm_lower_voltage_tag"
        if o and o["voltage_kv"] is None:
            status = "in_osm_no_voltage_tag"
        near = None
        if not o and t:
            c = t["geometry"]["coordinates"]
            nn = min(((km(c, x["_c"]), x) for x in osm), key=lambda z: z[0], default=None)
            if nn and nn[0] <= 1.0:
                near = {"osm_id": nn[1]["properties"]["osm_id"], "name": nn[1]["properties"]["name"],
                        "voltages": nn[1]["properties"]["voltages"], "dist_m": round(nn[0] * 1000)}
        check.append({"name": r["name"], "voltage_class_kv": r["voltage_class_kv"], "voltage_ratio": r["voltage_ratio"],
                      "commissioned": r.get("commissioned"), "operation_circle": r.get("operation_circle"),
                      "status": status, "osm_id": o["osm_id"] if o else None, "osm_name": o["name"] if o else None,
                      "osm_voltages": o["voltages"] if o else None,
                      "tngis_name": t["properties"]["sub_station"] if t else None,
                      "nearest_osm_substation_within_1km_of_tngis_point": near,
                      "lonlat": (osm[r["_o"]]["_c"] if o else t["geometry"]["coordinates"] if t else None),
                      "sources": r["sources"]})
        if not o and t:  # still carry the official record in the merged file via TNGIS
            pass
    # official records with neither TNGIS nor OSM location: not in merged file (no geometry) -> listed in check
    json.dump({"type": "FeatureCollection",
               "attribution": "TNGIS/TNEB substations (tngis.tn.gov.in); OSM © OpenStreetMap contributors, ODbL",
               "features": feats},
              open(os.path.join(OUT, "tn_substations_merged.geojson"), "w"), separators=(",", ":"), ensure_ascii=False)
    json.dump(check, open(os.path.join(OUT, "tn_ehv_osm_check.json"), "w"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("TNGIS", len(tg), "matched", len(ti), Counter(v[3] for v in ti.values()))
    print("OSM TN", len(osm), "osm-only", len(osm) - len(oj))
    print("official", len(off), Counter((c["voltage_class_kv"], c["status"]) for c in check))
    print("merged features", len(feats), "size", os.path.getsize(os.path.join(OUT, "tn_substations_merged.geojson")))


if __name__ == "__main__":
    main()
