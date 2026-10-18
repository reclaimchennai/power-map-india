"""Current weather at power sites, from Open-Meteo (no key; CC BY 4.0).

Wind direction/speed drive smoke plumes and wind-turbine rotors on the map; cloud cover and
short-wave radiation shade the solar farms. Plants are snapped to a 0.5° grid (≈55 km) so one
call covers several sites; that keeps the hourly run to ~250 locations, inside Open-Meteo's
free fair-use budget. Output: data/weather_now.json (read by scripts/export_live.py).
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from scrapers import netfetch
from store import log

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "weather_now.json"
API = "https://api.open-meteo.com/v1/forecast"
VARS = "temperature_2m,wind_speed_10m,wind_direction_10m,wind_speed_80m,cloud_cover,shortwave_radiation,is_day"
GRID = 0.5


def cell(lat, lon):
    return (round(lat / GRID) * GRID, round(lon / GRID) * GRID)


def run():
    plants = json.load(open(ROOT / "web" / "data" / "plants.json"))["plants"]
    cells = sorted({cell(p["lat"], p["lon"]) for p in plants if p.get("lat") is not None})
    out = {}
    for i in range(0, len(cells), 80):
        chunk = cells[i:i + 80]
        r = netfetch.get(API, params={
            "latitude": ",".join(f"{c[0]:.2f}" for c in chunk),
            "longitude": ",".join(f"{c[1]:.2f}" for c in chunk),
            "current": VARS, "wind_speed_unit": "ms", "timezone": "Asia/Kolkata"}, timeout=60)
        data = r.json()
        data = data if isinstance(data, list) else [data]
        for c, d in zip(chunk, data):
            cur = d.get("current") or {}
            out[f"{c[0]:.1f},{c[1]:.1f}"] = [cur.get(k) for k in VARS.split(",")]
        time.sleep(1)
    json.dump({"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "grid": GRID,
               "vars": VARS.split(","), "cells": out}, open(OUT, "w"), separators=(",", ":"))
    log("weather", "ok", f"{len(out)} cells")
    return len(out)


if __name__ == "__main__":
    print(run())
