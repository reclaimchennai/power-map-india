"""Shared SQLite store for the tneb energy dashboard."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "power.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS coal_plants_daily (
    date TEXT NOT NULL,
    plant TEXT NOT NULL,
    utility TEXT,
    state TEXT,
    section TEXT,
    mode TEXT,
    capacity_mw REAL,
    plf_pct REAL,
    norm_stock_days REAL,
    daily_req_kt REAL,
    norm_stock_kt REAL,
    stock_indigenous_kt REAL,
    stock_import_kt REAL,
    stock_total_kt REAL,
    stock_pct REAL,
    critical INTEGER DEFAULT 0,
    receipt_kt REAL,
    consumption_kt REAL,
    remarks TEXT,
    PRIMARY KEY (date, plant)
);

CREATE TABLE IF NOT EXISTS merit_state_daily (
    date TEXT NOT NULL,
    state TEXT NOT NULL,
    metric TEXT NOT NULL,          -- 'energy_mu' | 'peak_demand' etc (from MERIT report blocks)
    wind REAL, solar REAL, res_other REAL, res_total REAL,
    hydro REAL, thermal REAL, nuclear REAL, total REAL,
    PRIMARY KEY (date, state, metric)
);

CREATE TABLE IF NOT EXISTS peak_demand_daily (
    date TEXT NOT NULL,
    capacity_mw REAL,
    peak_demand_mw REAL,
    morning_peak_mw REAL,
    evening_peak_mw REAL,
    consumption_mu REAL,
    PRIMARY KEY (date)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')),
    source TEXT,
    status TEXT,
    detail TEXT
);
"""


def connect(db_path=None):
    con = sqlite3.connect(str(db_path or DB_PATH), timeout=120)   # several collectors and backfills write at once
    con.executescript(SCHEMA)
    return con


def log(source, status, detail=""):
    con = connect()
    with con:
        con.execute("INSERT INTO scrape_log (source, status, detail) VALUES (?,?,?)",
                    (source, status, detail[:500]))
    con.close()
