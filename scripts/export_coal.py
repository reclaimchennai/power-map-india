#!/usr/bin/env python3
"""Write web/data/coal/coal.json for the /coal dashboard: India's coal supply chain end to end.

  national   one row per CEA report day: stock at power plants, receipts, consumption, normative need,
             critical plants (a plant is critical under 25% of its normative stock), days of stock
  plants     every plant in the latest CEA daily coal report: stock, receipt and burn today, 7-day
             averages, days left at the current burn, % of normative, 90-day stock history, yesterday's
             generation (CEA DGR2), the company named in CEA's remark, and the plant's position
  supply     monthly production, offtake, pithead stock, rakes, imports and port coal (scrapers/coal_supply.py)
  reserves   geological resources by state (Ministry of Coal)
  map        mines and coalfields (build/feedstock/mines.json), ports, rail / sea / conveyor routes and the
             CEA-named coal links (web/data/feed.json, build/feedstock/derived_links.json)

Run by scripts/export_live.py after every collection pass; written atomically.
"""
import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "power.db"
OUT = ROOT / "web" / "data" / "coal"
COMPANIES = ["MCL", "SECL", "NCL", "CCL", "BCCL", "ECL", "WCL", "NEC", "SCCL", "NLC", "NLCIL", "SCL"]


def norm(s):
    s = (s or "").upper().replace("`", "").replace("'", "")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def rows(con, sql, *a):
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute(sql, a)]


def r1(v, d=1):
    return None if v is None else round(v, d)


def match_plants(cea_names, plants):
    """CEA plant name -> our plant record: exact normalised name, NPP name, then first two tokens in the state."""
    by = {}
    for p in plants:
        if p.get("type") not in ("coal", "lignite"):
            continue
        for k in (p.get("npp_name"), p["name"]):
            if k:
                by.setdefault(norm(k), p)
    out = {}
    for n, st in cea_names:
        k = norm(n)
        p = by.get(k)
        if not p:
            toks = k.split()[:2]
            p = next((q for q in plants if q.get("type") in ("coal", "lignite") and (q.get("state") or "").upper()[:6] == (st or "").upper()[:6]
                      and norm(q.get("npp_name") or q["name"]).split()[:2] == toks), None)
        if p:
            out[n] = p
    return out


# A plant row whose stock is over 3 Mt and four times its normative stock is a typo in the report
# (e.g. Thamminapatnam 27,728 kt on 2 Oct 2025 for a plant that held nothing the day before): left out of totals.
GOOD = "NOT (stock_total_kt > 3000 AND stock_total_kt > 4 * coalesce(norm_stock_kt, 0))"


def national(con):
    """One row per report day. days_req = stock of the plants that state a requirement ÷ that requirement:
    CEA's yardstick, comparable across the whole record (receipt and burn only exist from late 2021)."""
    out = []
    for r in rows(con, f"""SELECT date, count(*) n, sum(stock_total_kt) stock, sum(stock_import_kt) imp, sum(receipt_kt) rcpt,
                                 sum(consumption_kt) cons, sum(daily_req_kt) req, sum(norm_stock_kt) norm, sum(critical) crit,
                                 sum(capacity_mw) cap, sum(CASE WHEN daily_req_kt > 0 THEN stock_total_kt END) stock_r
                          FROM coal_plants_daily WHERE section NOT LIKE 'C.%' AND {GOOD} GROUP BY date ORDER BY date"""):
        if not r["n"] or r["n"] < 90:
            continue
        out.append([r["date"], r["n"], r1(r["stock"] / 1000, 2), r1((r["imp"] or 0) / 1000, 2), r1(r["rcpt"]), r1(r["cons"]),
                    r1(r["req"]), r1((r["norm"] or 0) / 1000, 2), r["crit"], round(r["cap"] or 0),
                    r1(r["stock_r"] / r["req"], 2) if r["req"] and r["stock_r"] else None])
    return {"cols": ["date", "plants", "stock_mt", "import_stock_mt", "receipt_kt", "consumption_kt", "requirement_kt", "normative_mt", "critical", "cap_mw", "days_req"],
            "rows": out}


def company_of(remark):
    m = re.findall(r"\b(" + "|".join(COMPANIES) + r")\b", (remark or "").upper())
    return sorted(set(m)) or None


def plants_block(con, plants):
    day = con.execute("SELECT max(date) FROM coal_plants_daily").fetchone()[0]
    if not day:
        return day, []
    since = (date.fromisoformat(day) - timedelta(days=90)).isoformat()
    hist = defaultdict(dict)
    for r in rows(con, "SELECT date, plant, stock_total_kt s, receipt_kt r, consumption_kt c FROM coal_plants_daily WHERE date>=?", since):
        hist[r["plant"]][r["date"]] = r
    dates = sorted({d for h in hist.values() for d in h})
    dgr_day = con.execute("SELECT max(date) FROM dgr_stations").fetchone()[0]
    dgr = {norm(r["station"]): r for r in rows(con, "SELECT station, gen_actual_mu, gen_prog_mu, coal_stock_days FROM dgr_stations WHERE date=?", dgr_day)}
    latest = rows(con, "SELECT * FROM coal_plants_daily WHERE date=? ORDER BY stock_pct", day)
    m = match_plants([(r["plant"], r["state"]) for r in latest], plants)
    out = []
    for r in latest:
        h = hist[r["plant"]]
        last7 = [h[d] for d in dates[-7:] if d in h]
        c7 = sum(x["c"] or 0 for x in last7) / len(last7) if last7 else None
        rc7 = sum(x["r"] or 0 for x in last7) / len(last7) if last7 else None
        p = m.get(r["plant"])
        g = dgr.get(norm(r["plant"])) or (dgr.get(norm(p.get("npp_name") or p["name"])) if p else None)
        out.append({
            "n": r["plant"], "id": p["id"] if p else None, "lat": p["lat"] if p else None, "lon": p["lon"] if p else None,
            "st": r["state"], "u": r["utility"], "mode": (r["mode"] or "").upper() or None, "sec": (r["section"] or "")[:1] or None,
            "cap": r["capacity_mw"], "plf": r["plf_pct"], "req": r["daily_req_kt"], "norm": r["norm_stock_kt"],
            "stock": r["stock_total_kt"], "imp": r["stock_import_kt"], "pct": r["stock_pct"], "crit": r["critical"],
            "rcpt": r["receipt_kt"], "cons": r["consumption_kt"], "c7": r1(c7, 2), "r7": r1(rc7, 2),
            "days": r1(r["stock_total_kt"] / c7, 1) if c7 and r["stock_total_kt"] is not None and c7 > 0.05 else None,
            "rmk": (r["remarks"] or "").strip() or None, "co": company_of(r["remarks"]),
            "gen": g["gen_actual_mu"] if g else None,
            "h": [r1(h[d]["s"]) if d in h else None for d in dates],
        })
    return day, dates, out


# The series the dashboard draws, each built from the raw coal_supply rows: (key, label, unit, how, sources, note).
# how: a list of raw series summed per period (all must be present), and an optional scale.
DERIVED = [
    ("production_daily", "Coal mined per day, CIL and Singareni", "Mt", (["prod_d:CIL", "prod_d:SCCL"], 1e-3), "CIL MOC Dashboard",
     "about four-fifths of India's coal; captive and commercial mines report monthly"),
    ("dispatch_daily", "Coal dispatched per day, CIL and Singareni", "Mt", (["offtake_d:CIL", "offtake_d:SCCL"], 1e-3), "CIL MOC Dashboard", ""),
    ("rakes", "Coal trains loaded per day, Coal India", "rakes", (["rakes_loaded_d:CIL"], 1), "CIL Rakes Data (FOIS)", "about 4,000 tonnes a train"),
    ("production", "Coal production, all India", "Mt a month", (["prod_m:Total"], 1), "Ministry of Coal, Monthly Coal Statistics", ""),
    ("offtake", "Coal dispatched from the mines, all India", "Mt a month", (["dispatch_m:Total"], 1), "Ministry of Coal, Monthly Coal Statistics", ""),
    ("dispatch_power", "Coal dispatched to power stations", "Mt a month", (["dispatch_power_m:Total"], 1), "Ministry of Coal, Monthly Coal Statistics", ""),
    ("rakes_power", "Coal trains to power stations", "rakes a day", (["rakes_power_m:Total"], 1), "Ministry of Coal, Monthly Coal Statistics", "monthly average"),
    ("imports", "Coal imports, all uses", "Mt a month", (["imports_m:Total"], 1), "Ministry of Commerce TradeStat (HS 2701)", ""),
    ("imports_thermal", "Steam (thermal) coal imports", "Mt a month", (["imports_m:Thermal"], 1), "Ministry of Commerce TradeStat (HS 27011920)", ""),
    ("import_power", "Imported coal received by power stations", "Mt a month", (["import_power_m:Total"], 1), "CEA monthly import report", ""),
    ("port_coal", "Thermal coal handled at ports", "Mt a month", (["port_coal_m:Total-Thermal"], 1), "Ministry of Ports, Shipping and Waterways", "major and non-major ports"),
    ("cea_rcpt", "Coal received by power stations", "Mt a month", (["cea_rcpt_m:Total"], 1), "CEA monthly coal report", ""),
    ("cea_cons", "Coal burnt by power stations", "Mt a month", (["cea_cons_m:Total"], 1), "CEA monthly coal report", ""),
    ("cea_stock", "Coal at power stations, month end", "Mt", (["cea_stock_m:Total"], 1), "CEA monthly coal report", ""),
    ("gas_power", "Natural gas burnt for power", "million m³ a month", (["gas_power_m:Total"], 1), "PPAC sectoral gas consumption", ""),
    ("hydro_storage", "Water in India's reservoirs", "% of capacity", (["cwc_pct_w:AllIndia"], 1), "Central Water Commission weekly bulletin", ""),
    ("hydro_normal", "Reservoirs, 10-year normal", "% of capacity", (["cwc_pct_normal_w:AllIndia"], 1), "Central Water Commission weekly bulletin", ""),
]


def supply(con):
    """The dashboard's supply series (DERIVED) plus the full raw table for web/data/coal/series.json."""
    try:
        raw = defaultdict(dict)
        units, srcs = {}, {}
        for r in rows(con, "SELECT series, period, value, unit, source FROM coal_supply ORDER BY series, period"):
            raw[r["series"]][r["period"]] = r["value"]
            units[r["series"]] = r["unit"]
            srcs[r["series"]] = r["source"]
    except sqlite3.OperationalError:
        return {"series": {}, "units": {}, "meta": {}}, {}
    out, meta, un = {}, {}, {}
    for key, label, unit, (parts, k), src, note in DERIVED:
        if not all(p in raw for p in parts):
            continue
        periods = sorted(set.intersection(*(set(raw[p]) for p in parts)))
        vals = [[pd, round(sum(raw[p][pd] for p in parts) * k, 4)] for pd in periods if all(raw[p][pd] is not None for p in parts)]
        if len(vals) < 2:
            continue
        out[key] = vals
        un[key] = unit
        meta[key] = {"label": label, "source": src, "note": note}
    full = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "series": {k: sorted([[p, v] for p, v in d.items()]) for k, d in raw.items()}, "units": units, "sources": srcs}
    return {"series": out, "units": un, "meta": meta}, full


def fy_block(con):
    """This financial year so far. Running total from the National Coal Portal (daily, all mines); the year-on-year
    comparison from the Ministry of Coal's monthly statistics over the same completed months."""
    def one(series):
        r = con.execute("SELECT period, value FROM coal_supply WHERE series=? ORDER BY period DESC LIMIT 1", (series,)).fetchone()
        return (r[0], r[1]) if r else (None, None)
    out = {}
    for kind, ncp, msg in (("prod", "ncp_prod_ytd:Total", "prod_m:Total"), ("dispatch", "ncp_offtake_ytd:Total", "dispatch_m:Total")):
        d, v = one(ncp)
        last_m = con.execute("SELECT max(period) FROM coal_supply WHERE series=?", (msg,)).fetchone()[0]
        if not last_m:
            continue
        y, m = int(last_m[:4]), int(last_m[5:7])
        fy = y if m >= 4 else y - 1
        cur = [f"{fy + (mm < 4)}-{mm:02d}" for mm in list(range(4, 13)) + list(range(1, 4))]
        cur = cur[:cur.index(last_m) + 1]
        prev = [f"{int(c[:4]) - 1}{c[4:]}" for c in cur]
        q = lambda ps: con.execute(f"SELECT sum(value), count(*) FROM coal_supply WHERE series=? AND period IN ({','.join('?' * len(ps))})", (msg, *ps)).fetchone()
        a_, n1 = q(cur)
        b_, n2 = q(prev)
        out[kind] = {"ytd": v, "ytd_date": d, "months": [cur[0], cur[-1]], "msg_ytd": r1(a_, 2), "msg_ytd_ly": r1(b_, 2) if n2 == n1 else None,
                     "yoy": r1(a_ / b_ - 1, 4) if a_ and b_ and n1 == n2 else None}
    return out


def reserves(con):
    """GSI National Coal Inventory via the Ministry of Coal (billion tonnes): measured, indicated, inferred, total."""
    out = {"coal": {}, "lignite": {}, "history": {"coal": [], "lignite": []}, "total": {}}
    for r in rows(con, "SELECT source, key, value FROM coal_india_stats WHERE source LIKE 'reserve%'"):
        v = json.loads(r["value"]) if r["value"].startswith("[") else float(r["value"])
        src = r["source"]
        if src.startswith("reserves_") and src[9:] in ("coal", "lignite"):
            out[src[9:]][r["key"]] = v
        elif src.startswith("reserve_history_"):
            out["history"][src[16:]].append([r["key"].replace("1st April ", ""), *v])
        elif src == "reserves_total":
            out["total"][r["key"]] = v
    for k in out["history"]:
        out["history"][k].sort()
    out["production_fy"] = {r["key"]: json.loads(r["value"]) for r in rows(con, "SELECT key, value FROM coal_india_stats WHERE source='production'")
                            if r["value"].startswith("[")}
    return out


def map_block():
    feed = json.load(open(ROOT / "web" / "data" / "feed.json"))
    mines = json.load(open(ROOT / "build" / "feedstock" / "mines.json"))
    derived = json.load(open(ROOT / "build" / "feedstock" / "derived_links.json"))
    ms = []
    for x in mines["mines"]:
        if x.get("lat") is None:
            continue
        pm = x.get("production_mt") or {}
        ms.append({"id": x["id"], "name": x["name"], "kind": x["kind"], "co": x.get("subsidiary_code") or x.get("company"), "st": x.get("state"),
                   "lat": x["lat"], "lon": x["lon"], "fuel": x.get("fuel"), "prod": pm.get("value") if isinstance(pm, dict) else None,
                   "cap": x.get("capacity_mtpa"), "status": x.get("status")})
    have = {m["id"] for m in ms}
    for n in feed["nodes"]:
        if n["kind"] in ("mine", "coalfield", "lignite_mine", "captive_block") and n["id"] not in have:
            ms.append({"id": n["id"], "name": n["name"], "kind": n["kind"], "lat": n["lat"], "lon": n["lon"]})
    ports = [{"id": n["id"], "name": n["name"], "kind": n["kind"], "lat": n["lat"], "lon": n["lon"], "role": n.get("role")}
             for n in feed["nodes"] if n["kind"] in ("port", "terminal", "foreign_port")]
    routes = [{"mode": r["mode"], "cargo": r.get("cargo"), "c": [[round(a, 3), round(b, 3)] for a, b in r["coords"]], "serves": r.get("serves")}
              for r in feed["routes"] if "coal" in (r.get("cargo") or "").lower() or "lignite" in (r.get("cargo") or "").lower()
              or "MCL" in (r.get("cargo") or "")]
    for r in derived["routes"]:
        routes.append({"mode": r["mode"], "cargo": r.get("cargo"), "c": [[round(a, 3), round(b, 3)] for a, b in r["coords"]], "serves": r.get("serves"),
                       "from": r.get("from_name"), "to": r.get("to_name"), "km": r.get("km"), "derived": True})
    gem, terms, gem_meta = [], [], None
    gp = ROOT / "build" / "feedstock" / "gem" / "india_coal_mines.json"
    if gp.exists():
        g = json.load(open(gp))
        gem_meta = g.get("meta")
        seen = set()
        for m in g["records"]:
            if m.get("lat") is None or m["status"] not in ("operating", "proposed", "mothballed", "construction"):
                continue
            k = (m["id"], m["status"])
            if k in seen:
                continue
            seen.add(k)
            gem.append({"id": m["id"], "name": m["name"], "owner": re.sub(r"\s*\[.*?\]", "", m.get("owner") or ""), "status": m["status"],
                        "type": m.get("type"), "cf": m.get("coalfield"), "st": m.get("state"), "lat": m["lat"], "lon": m["lon"],
                        "cap": m.get("capacity_mtpa"), "prod": m.get("production_mt"), "py": m.get("production_year"), "url": m.get("url")})
    tp = ROOT / "build" / "feedstock" / "gem" / "india_coal_terminals.json"
    if tp.exists():
        for t in json.load(open(tp))["records"]:
            if t.get("lat") is not None and t["status"] in ("operating", "construction"):
                terms.append({"name": t["name"], "port": t.get("port"), "owner": t.get("owner"), "status": t["status"], "cap": t.get("capacity_mtpa"),
                              "lat": t["lat"], "lon": t["lon"], "st": t.get("state")})
    return {"mines": ms, "ports": ports, "routes": routes, "gem_mines": gem, "gem_terminals": terms,
            "gem_attribution": (gem_meta or {}).get("attribution"), "companies": [
        {"code": c["code"], "name": c["name"], "prod": (c.get("production_mt") or {}).get("value"), "target": (c.get("production_mt") or {}).get("annual_target"),
         "fy": (c.get("production_mt") or {}).get("fy"), "fuel": c.get("fuel")} for c in mines["companies"]]}


def main():
    con = sqlite3.connect(DB, timeout=60)
    plants = json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]
    day, dates, pl = plants_block(con, plants)
    sup, full = supply(con)
    obj = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "day": day, "hist_dates": dates,
           "national": national(con), "fy": fy_block(con), "plants": pl, "supply": sup, "reserves": reserves(con), "map": map_block()}
    con.close()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / ".coal.json.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, OUT / "coal.json")
    tmp = OUT / ".series.json.tmp"
    with open(tmp, "w") as f:
        json.dump(full, f, separators=(",", ":"))
    os.replace(tmp, OUT / "series.json")
    print(f"coal.json: {day}, {len(pl)} plants, {len(obj['national']['rows'])} days, {len(obj['map']['mines'])} mines, "
          f"{sum(1 for p in pl if p['id'])} placed, {(OUT / 'coal.json').stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
