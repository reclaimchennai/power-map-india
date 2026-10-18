"""TNEB SLDC peak-demand scraper (tnebsldc.org).

Downloads https://tnebsldc.org/Content/PDF/peakdet.pdf (Grid Details daily
peak report) and stores the state Total row: capacity, peak load, minimum
load, morning peak and consumption (MU).
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber
import requests

from store import connect, log

PEAKDET_URL = "https://tnebsldc.org/reports1/peakdet.pdf"


def _f(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        first = pdf.pages[0]
        text = first.extract_text() or ""
        date = None
        for line in text.split("\n"):
            if "Date" in line:
                parts = line.split("Date")
                if len(parts) > 1:
                    raw = parts[-1].strip().lstrip(":").split()[0]
                    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d-%b-%Y"):
                        try:
                            date = datetime.strptime(raw, fmt).date().isoformat()
                            break
                        except ValueError:
                            continue
                    if date:
                        break
        for table in first.extract_tables():
            for row in table:
                row = [(c or "").replace("\n", " ").strip() for c in row]
                if len(row) >= 8 and row[2] == "Total":
                    return date, {
                        "capacity_mw": _f(row[3]),
                        "peak_demand_mw": _f(row[4]),
                        "evening_peak_mw": _f(row[4]),  # report's peak load col
                        "morning_peak_mw": _f(row[6]),
                        "consumption_mu": _f(row[7]),
                    }
    return date, None


def save(date, data):
    con = connect()
    with con:
        con.execute(
            """INSERT OR REPLACE INTO peak_demand_daily
            (date, capacity_mw, peak_demand_mw, morning_peak_mw,
             evening_peak_mw, consumption_mu)
            VALUES (:date,:capacity_mw,:peak_demand_mw,:morning_peak_mw,
             :evening_peak_mw,:consumption_mu)""",
            dict(data, date=date))
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file")
    ap.add_argument("--url", default=PEAKDET_URL)
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
    else:
        r = requests.get(args.url, timeout=60, verify=False,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        path = Path("data/downloads/peakdet.pdf")
        path.write_bytes(r.content)

    date, data = parse_pdf(path)
    if not (date and data):
        log("tneb_sldc", "fail", f"could not parse {path}")
        sys.exit(1)
    save(date, data)
    msg = f"{date}: {data}"
    print(msg)
    log("tneb_sldc", "ok", msg)


if __name__ == "__main__":
    main()
