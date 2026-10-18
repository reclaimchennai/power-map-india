"""FastAPI backend serving scraped data + static geo layers.

    uvicorn api.main:app --port 8300
"""
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from store import DB_PATH

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "data" / "geo"
WEB = ROOT / "web"

app = FastAPI(title="tneb energy archive", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


def q(sql, args=()):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(sql, args)]
    con.close()
    return rows


@app.get("/api/coal/latest")
def coal_latest(state: str | None = Query(None)):
    date = q("SELECT max(date) d FROM coal_plants_daily")[0]["d"]
    if not date:
        raise HTTPException(404, "no coal data yet")
    rows = q("SELECT * FROM coal_plants_daily WHERE date=? ORDER BY state, plant", (date,))
    if state:
        rows = [r for r in rows if state.lower() in (r["state"] or "").lower()]
    return {"date": date, "plants": rows}


@app.get("/api/res/states")
def res_states():
    date = q("SELECT max(date) d FROM merit_state_daily WHERE metric='energy_mu'")[0]["d"]
    return {"date": date,
            "states": q("SELECT * FROM merit_state_daily WHERE date=? AND metric='energy_mu' ORDER BY res_total DESC", (date,))}


@app.get("/api/res/stations")
def res_stations(state: str | None = Query(None)):
    date = q("SELECT max(date) d FROM res_stations_daily")[0]["d"]
    sql = "SELECT * FROM res_stations_daily WHERE date=?"
    args = [date]
    if state:
        sql += " AND state LIKE ?"
        args.append(f"%{state}%")
    sql += " ORDER BY capacity_mw DESC"
    return {"date": date, "stations": q(sql, args)}


@app.get("/api/tn/district")
def tn_district(table: str | None = Query(None)):
    sql = "SELECT * FROM tn_district"
    args = []
    if table:
        sql += " WHERE source_table LIKE ?"
        args.append(f"{table}%")
    return {"rows": q(sql + " ORDER BY source_table, capacity_mw DESC", args)}


@app.get("/api/tneb/mix")
def tneb_mix():
    date = q("SELECT max(date) d FROM tn_generation_mix")[0]["d"]
    if not date:
        raise HTTPException(404, "no mix data yet")
    return {"date": date,
            "rows": q("SELECT * FROM tn_generation_mix WHERE date=? ORDER BY section, item", (date,))}


@app.get("/api/supply/stations")
def supply_stations(state: str | None = Query(None),
                    low_stock: bool = Query(False)):
    date = q("SELECT max(date) d FROM dgr_stations")[0]["d"]
    if not date:
        raise HTTPException(404, "no dgr data yet")
    sql = ("SELECT * FROM dgr_stations WHERE date=? "
           "AND station NOT LIKE '%TOTAL%' AND cap_mw > 0")
    args = [date]
    if state:
        sql += " AND (state LIKE ? OR region LIKE ?)"
        args += [f"%{state}%", f"%{state}%"]
    if low_stock:
        sql += " AND coal_stock_days IS NOT NULL AND coal_stock_days > 0"
        sql += " ORDER BY coal_stock_days LIMIT 25"
    else:
        sql += " ORDER BY cap_mw DESC"
    return {"date": date, "stations": q(sql, args)}


@app.get("/api/supply/coal_india")
def coal_india_stats():
    return q("SELECT source, key, value, ts FROM coal_india_stats "
             "ORDER BY source, key")


@app.get("/api/nuclear/npcil")
def npcil():
    return q("SELECT * FROM npcil_units ORDER BY station, unit")


@app.get("/api/tneb/peak")
def tneb_peak():
    return q("SELECT * FROM peak_demand_daily ORDER BY date DESC LIMIT 60")


@app.get("/api/status")
def status():
    return q("SELECT * FROM scrape_log ORDER BY id DESC LIMIT 20")


@app.get("/geo/{name}")
def geo(name: str):
    path = (GEO / f"{name}.geojson")
    if not path.is_file() or ".." in name:
        raise HTTPException(404)
    return FileResponse(path, media_type="application/geo+json")


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
