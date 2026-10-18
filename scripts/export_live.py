#!/usr/bin/env python3
"""Write the live feeds the page polls: web/data/live/now.json and web/data/live/tn_history.json.

now.json
  tn       latest SLDC grid-details version (every row), the day's versions, all-time highs
  india    NPP latest day: zone and state generation, all-India programme vs actual
  plants   per plant id: yesterday's generation (MU, programme, last year), average MW and load
           factor, FY cumulative, coal stock (days, % of normative, critical), capacity under
           outage and CEA's remark — joined on NPP station id / normalised names
  weather  Open-Meteo cells (0.5°) for plumes, rotors and solar shading
tn_history.json
  every archived SLDC version (timestamp + key MW figures) and one row per day of energy by source

Files are written to a temp name and renamed, so the web server never serves half a file.
"""
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "power.db"
LIVE = ROOT / "web" / "data" / "live"


def norm(s):
    s = (s or "").upper().replace("`", "").replace("'", "")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def put(name, obj):
    LIVE.mkdir(parents=True, exist_ok=True)
    tmp = LIVE / f".{name}.tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, LIVE / name)


def rows(con, sql, *a):
    return [dict(r) for r in con.execute(sql, a)]


def tn_block(con):
    try:
        vers = rows(con, "SELECT * FROM sldc_versions ORDER BY pdf_modified")
    except sqlite3.OperationalError:
        return None, None
    if not vers:
        return None, None
    latest = vers[-1]
    r = {x["key"]: {k: x[k] for k in ("label", "capacity_mw", "capacity_excluded", "lighting_mw", "min_mw", "morning_mw", "mu")}
         for x in rows(con, "SELECT * FROM sldc_rows WHERE pdf_modified=?", latest["pdf_modified"])}
    extra = json.loads(latest.pop("extra") or "{}")
    latest.pop("file", None)
    latest.pop("sha1", None)
    tn = {"version": latest, "rows": r, "records": extra}
    # history: every version's headline figures; one energy row per consumption date
    keys = ["hydro", "thermal", "gas", "ipp_sepc", "ipp_ppn", "ipp_taqa", "cpp", "nces", "wind", "solar", "cgs",
            "ltoa", "mtoa_tnpdcl", "stoa", "exchange_tnpdcl", "remc", "dsm", "total"]
    hist_v, daily = [], {}
    for v in vers:
        rr = {x["key"]: x for x in rows(con, "SELECT * FROM sldc_rows WHERE pdf_modified=?", v["pdf_modified"])}
        hist_v.append({"t": v["pdf_modified"], "date": v["report_date"],
                       "lighting": [v["lighting_date"], v["lighting_time"], v["lighting_hz"]],
                       "min": [v["min_date"], v["min_time"], v["min_hz"]],
                       "morning": [v["morning_date"], v["morning_time"], v["morning_hz"]],
                       "mw": {k: [rr[k]["lighting_mw"], rr[k]["min_mw"], rr[k]["morning_mw"]] for k in keys if k in rr}})
        if v["mu_date"]:
            daily[v["mu_date"]] = {k: rr[k]["mu"] for k in keys if k in rr and rr[k]["mu"] is not None}
    # the prototype's parsed mix (2026-09-17) fills the earliest day if missing
    return tn, {"versions": hist_v, "daily": [{"date": d, **m} for d, m in sorted(daily.items())]}


def india_block(con):
    day = con.execute("SELECT max(date) FROM npp_state_daily").fetchone()[0]
    if not day:
        return None
    st = rows(con, "SELECT state, zone, prog_mu, actual_mu, actual_mu_ly, actual_cum_mu FROM npp_state_daily WHERE date=?", day)
    zones = {}
    for s in st:
        z = zones.setdefault(s["zone"], [0, 0, 0])
        z[0] += s["prog_mu"] or 0
        z[1] += s["actual_mu"] or 0
        z[2] += s["actual_mu_ly"] or 0
    cap = {}
    for r in rows(con, "SELECT state, payload FROM npp_state_capacity WHERE date=(SELECT max(date) FROM npp_state_capacity)"):
        try:
            p = json.loads(r["payload"])
            ic = p.get("installed_Capacity") or {}
            cap[r["state"]] = {k.replace("installed_capacity_", ""): v for k, v in ic.items()
                               if k.startswith("installed_capacity") and isinstance(v, (int, float))}
        except Exception:
            pass
    return {"date": day, "states": {s["state"]: [s["prog_mu"], s["actual_mu"], s["actual_mu_ly"], s["actual_cum_mu"]] for s in st},
            "zones": {k: [round(v, 2) for v in z] for k, z in zones.items()}, "capacity": cap}


def plants_block(con, plants):
    out = {}
    day = con.execute("SELECT max(date) FROM npp_station_daily").fetchone()[0]
    npp = {r["station_id"]: r for r in rows(con, "SELECT * FROM npp_station_daily WHERE date=?", day)} if day else {}
    dday = con.execute("SELECT max(date) FROM dgr_stations").fetchone()[0]
    dgr = {norm(r["station"]): r for r in rows(con, "SELECT * FROM dgr_stations WHERE date=?", dday)} if dday else {}
    cday = con.execute("SELECT max(date) FROM coal_plants_daily").fetchone()[0]
    coal = {norm(r["plant"]): r for r in rows(con, "SELECT * FROM coal_plants_daily WHERE date=?", cday)} if cday else {}
    coal_by_state = {}
    for k, r in coal.items():
        coal_by_state.setdefault((r["state"] or "").upper(), []).append((k, r))
    for p in plants:
        rec = {}
        n = npp.get(p.get("npp"))
        cap = p.get("cap") or 0
        if n:
            mu = n["actual_mu"]
            rec.update(d=day, mu=mu, prog=n["prog_mu"], ly=n["actual_mu_ly"], cum=n["actual_cum_mu"], cum_ly=n["actual_cum_mu_ly"])
            if mu is not None and cap:
                rec["mw"] = round(mu * 1000 / 24, 1)
                rec["lf"] = round(min(1.2, mu * 1000 / 24 / cap), 3)
        key = norm(p.get("npp_name") or p["name"])
        g = dgr.get(key)
        if g:
            rec.update(coal_d=g["coal_stock_days"], out_mw=g["outage_mw"], rmk=(g["remarks"] or "").strip() or None, dgr_d=dday)
            # NPP's map feed can go stale for days (stuck on 10 Oct while CEA's DGR had 12 Oct), so
            # prefer the DGR whenever it is newer than the NPP row for this plant.
            if g["gen_actual_mu"] is not None and ("mu" not in rec or dday > rec.get("d", "")):
                for k in ("ly", "cum_ly"):
                    rec.pop(k, None)  # last-year comparators belong to the NPP day
                rec.update(d=dday, mu=g["gen_actual_mu"], prog=g["gen_prog_mu"], cum=g["ytd_actual_mu"])
                if cap:
                    rec["mw"] = round(g["gen_actual_mu"] * 1000 / 24, 1)
                    rec["lf"] = round(min(1.2, g["gen_actual_mu"] * 1000 / 24 / cap), 3)
        c = coal.get(key)
        if not c and p.get("type") in ("coal", "lignite"):
            # CEA spells some plants differently: match on the first two name tokens within the state
            toks = key.split()[:2]
            for k, r in coal_by_state.get((p.get("state") or "").upper(), []):
                if k.split()[:2] == toks:
                    c = r
                    break
        if c:
            rec.update(stock_kt=c["stock_total_kt"], stock_pct=c["stock_pct"], crit=c["critical"],
                       rcpt_kt=c["receipt_kt"], cons_kt=c["consumption_kt"], coal_mode=c["mode"],
                       coal_rmk=(c["remarks"] or "").strip(". ") or None, coal_date=cday,
                       norm_days=c["norm_stock_days"], req_kt=c["daily_req_kt"])
        if rec:
            out[p["id"]] = rec
    return out


def history(con, plants):
    """Per-plant daily MU from the DGR archive (lazy-loaded by cards) + daily totals by fuel."""
    dates = [r[0] for r in con.execute("SELECT DISTINCT date FROM dgr_stations ORDER BY date")][-400:]
    if not dates:
        return None, None
    ix = {d: i for i, d in enumerate(dates)}
    key2ids = {}
    for p in plants:
        key2ids.setdefault(norm(p.get("npp_name") or p["name"]), []).append(p)
    series, totals = {}, {}
    for r in con.execute("SELECT date, station, gen_actual_mu, cap_mw, state FROM dgr_stations WHERE date >= ?", (dates[0],)):
        d, st, mu = r[0], r[1], r[2]
        if st == "__STATE_TOTAL__" or mu is None:
            continue
        for p in key2ids.get(norm(st), []):
            series.setdefault(p["id"], [None] * len(dates))[ix[d]] = round(mu, 2)
            t = totals.setdefault(p["type"], [0.0] * len(dates))
            t[ix[d]] += mu
            if p.get("state") == "Tamil Nadu":
                t = totals.setdefault("tn:" + p["type"], [0.0] * len(dates))
                t[ix[d]] += mu
    return ({"dates": dates, "plants": series},
            {"dates": dates, "by_type": {k: [round(v, 1) for v in arr] for k, arr in totals.items()}})


def vp_block(con):
    """Vidyut Pravah: latest block for India and every state, and today's TN / India blocks."""
    try:
        last = con.execute("SELECT max(block) FROM vp_blocks").fetchone()[0]
    except sqlite3.OperationalError:
        return None
    if not last:
        return None
    latest = {}
    for r in con.execute("SELECT state, block, demand_mw, demand_yday_mw, exch_mw, exch_yday_mw, price, price_yday, ts FROM vp_blocks "
                         "WHERE block = (SELECT max(block) FROM vp_blocks b WHERE b.state = vp_blocks.state)"):
        latest[r[0]] = {"block": r[1], "mw": r[2], "yday": r[3], "exch": r[4], "exch_yday": r[5], "price": r[6], "price_yday": r[7], "ts": r[8]}
    day = last[:10]
    series = {}
    for st in ("Tamil Nadu", "__INDIA__"):
        series[st] = [[b[11:16], mw] for b, mw in con.execute(
            "SELECT block, demand_mw FROM vp_blocks WHERE state=? AND block >= ? ORDER BY block", (st, day))]
    return {"block": last, "india": latest.pop("__INDIA__", None), "states": latest, "today": series}


def merit_block(con):
    """All-India demand and generation by source: the latest ~4-min reading and today's curve (15-min)."""
    try:
        last = con.execute("SELECT max(ts) FROM merit_rt WHERE series='demand'").fetchone()[0]
    except sqlite3.OperationalError:
        return None
    if not last:
        return None
    latest = {r[0]: r[1] for r in con.execute("SELECT series, mw FROM merit_rt WHERE ts=?", (last,))}
    from datetime import timedelta
    t_last = datetime.fromisoformat(last)
    ist0 = (t_last + timedelta(hours=5, minutes=30)).replace(hour=0, minute=0, second=0) - timedelta(hours=5, minutes=30)
    series = {}
    for ts, s_, mw in con.execute("SELECT ts, series, mw FROM merit_rt WHERE ts >= ? ORDER BY ts", (ist0.isoformat(),)):
        t = datetime.fromisoformat(ts) + timedelta(hours=5, minutes=30)
        slot = f"{t.hour:02d}:{t.minute // 15 * 15:02d}"
        series.setdefault(slot, {})[s_] = mw
    today = [{"t": k, **v} for k, v in sorted(series.items())]
    # daily energy by source (MU) for the history charts: mean MW over the day x 24 / 1000
    daily = {}
    for d, s_, mean in con.execute("""SELECT substr(datetime(ts, '+330 minutes'), 1, 10) d, series, avg(mw)
                                      FROM merit_rt GROUP BY d, series ORDER BY d"""):
        daily.setdefault(d, {})[s_] = round(mean * 24 / 1000, 1)
    return {"ts": last, "latest": latest, "today": today, "daily": [{"date": d, **v} for d, v in sorted(daily.items())][-400:]}


def nfms_block(con):
    try:
        day = con.execute("SELECT max(date) FROM nfms_state").fetchone()[0]
    except sqlite3.OperationalError:
        return None
    if not day:
        return None
    nat = json.loads(con.execute("SELECT payload FROM nfms_national WHERE date=?", (day,)).fetchone()[0])
    states = {r["state_code"]: r for r in rows(con, "SELECT * FROM nfms_state WHERE date=?", day)}
    month = con.execute("SELECT max(month) FROM nfms_city").fetchone()[0]
    cities = rows(con, "SELECT state, discom, city, saifi, saidi FROM nfms_city WHERE month=? ORDER BY saidi DESC", month)
    comm = (nat.get("comm") or {}).get("communication_tech") or [{}]
    return {"date": day, "hours": nat.get("hours"), "feeders": nat.get("feeders"), "comm": comm[0],
            "states": {k: {kk: v[kk] for kk in ("state", "data_refresh", "hrs_inc_ag", "hrs_exc_ag", "urban", "rural", "agri", "industrial", "mixed",
                                                  "feeders_total", "feeders_integrated", "integration_pct")} for k, v in states.items()},
            "cities": cities, "city_month": month}


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    plants = json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]
    tn, tn_hist = tn_block(con)
    now = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "tn": tn, "india": india_block(con), "plants": plants_block(con, plants), "vp": vp_block(con),
           "merit": merit_block(con), "nfms": nfms_block(con)}
    w = ROOT / "data" / "weather_now.json"
    if w.exists():
        now["weather"] = json.load(open(w))
    # freshness of every source, for the "last updated" line
    now["sources"] = {r["source"]: r["ts"] for r in rows(con, "SELECT source, max(ts) ts FROM scrape_log WHERE status='ok' GROUP BY source")}
    put("now.json", now)
    if tn_hist:
        put("tn_history.json", tn_hist)
    h, ht = history(con, plants)
    if h:
        put("history.json", h)
        put("history_totals.json", ht)
    print(f"live: {len(now['plants'])} plants with data; tn={'yes' if tn else 'no'}")


if __name__ == "__main__":
    main()
