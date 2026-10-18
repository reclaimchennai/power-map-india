#!/usr/bin/env python3
"""build/emissions/stations.json (CEA CO2 DB, FGD, fly ash, CAAQMS, incidents, estimates) ->
web/data/emissions.json keyed by the site's plant ids (joined on DGR / NPP / dossier names).
Kept compact for the card; the full research record stays in build/."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "build" / "emissions" / "stations.json"
OUT = ROOT / "web" / "data" / "emissions.json"


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", (s or "").upper())).strip()


GENERIC = set("TPS TPP STPS STPP SCTPP CCPP CCGT GPS GT DG GTPS LIG LIGNITE POWER PLANT STATION THERMAL PROJECT LTD LIMITED "
              "PVT STAGE UNIT NEW EXT EXTN I II III IV V VI PH GAS SUPER CRITICAL COMBINED CYCLE UPPER LOWER NORTH SOUTH".split())
STATE = {"ORISSA": "ODISHA", "CHATTISGARH": "CHHATTISGARH", "CHHATISGARH": "CHHATTISGARH", "PONDICHERRY": "PUDUCHERRY"}


def first_token(name):
    t = [w for w in norm(name).split() if w not in GENERIC and not w.isdigit() and len(w) > 2]
    return t[0] if t else None


def st(s):
    s = norm(s)
    return STATE.get(s, s)


def main():
    plants = json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]
    fuzzy = {}
    for p in plants:
        ft = first_token(p.get("npp_name") or p["name"])
        if ft:
            fuzzy.setdefault((st(p.get("state")), ft), []).append(p)
    by = {}
    for p in plants:
        for k in (p.get("npp_name"), p["name"], p["id"]):
            if k:
                by.setdefault(norm(k), p["id"])
    src = json.load(open(SRC))
    extra = {k: v for k, v in src.items() if k not in ("stations", "meta")}
    out, unmatched = {}, []
    for s in src["stations"]:
        names = s.get("names") or {}
        keys = [s.get("id"), s.get("name"), names.get("dgr"), *(names.get("cea_coal") or [])]
        pid = next((by[norm(k)] for k in keys if k and norm(k) in by), None)
        if not pid:
            for k in keys:
                cand = fuzzy.get((st(s.get("state")), first_token(k))) if k else None
                if cand:
                    cap = s.get("capacity_mw") or 0
                    pid = min(cand, key=lambda p: abs((p.get("cap") or 0) - cap))["id"]
                    break
        if not pid:
            unmatched.append(s.get("name"))
            continue
        co2 = s.get("co2") or {}
        units = s.get("units") or []
        fgd = sorted({(u.get("fgd") or {}).get("status") for u in units if (u.get("fgd") or {}).get("status")})
        dl = sorted({(u.get("fgd") or {}).get("so2_deadline") for u in units if (u.get("fgd") or {}).get("so2_deadline")})
        norms = sorted({(u.get("norm_2015") or {}).get("so2_mg_nm3") for u in units if (u.get("norm_2015") or {}).get("so2_mg_nm3")})
        fa = (s.get("flyash") or {})
        fa = fa.get("2021_22") or next(iter(fa.values()), {}) if isinstance(fa, dict) else {}
        so2m = [u for u in ((s.get("so2_measured_2021") or {}).get("units") or []) if u.get("so2_rti_mean_mg_nm3")]
        est = s.get("estimates") or {}
        rec = {
            "co2_t_per_mwh": co2.get("t_co2_per_mwh"), "co2_t": co2.get("co2_t"), "co2_fy": co2.get("fy"),
            "co2_hist": co2.get("history_t_co2_per_mwh"), "co2_src": co2.get("source"),
            "fgd": ", ".join(fgd) or None, "so2_deadline": dl[-1] if dl else None, "so2_norm": norms,
            "fgd_context": (s.get("fgd_summary") or {}).get("context"),
            "fly_ash": {k: fa.get(k) for k in ("fly_ash_generated_mt", "fly_ash_utilised_mt", "utilisation_pct", "ash_content_pct", "coal_consumed_mt")} if fa else None,
            "so2_measured": [{"unit": u.get("unit_name"), "mean": u.get("so2_rti_mean_mg_nm3"), "limit": u.get("so2_limit_mg_nm3")} for u in so2m] or None,
            "caaqms": s.get("caaqms_nearby"), "incidents": s.get("incidents"),
            "est": {k: v for k, v in (est.get("fy2026_27_run_rate") or {}).items() if k in ("co2_t", "so2_t_best", "nox_t", "pm_t", "fuel_t", "dgr_date")} or None,
            "est_method": est.get("method"), "est_caveats": est.get("caveats"),
            "sources": s.get("sources"),
        }
        out[pid] = {k: v for k, v in rec.items() if v not in (None, [], {}, "")}
    json.dump({"meta": src.get("meta"), "stations": out, **extra}, open(OUT, "w"), separators=(",", ":"))
    print(f"emissions: {len(out)} plants joined, {len(unmatched)} unmatched -> {OUT} ({OUT.stat().st_size // 1024} KB)")
    print("unmatched sample:", unmatched[:12])


if __name__ == "__main__":
    main()
