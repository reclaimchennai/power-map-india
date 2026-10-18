"""CEA / NPP Daily Coal Stock Report scraper.

Parses the "DAILY COAL STOCK REPORT" PDF published by CEA Fuel Management
Division (distributed via https://npp.gov.in/dailyCoalReports and
https://cea.nic.in/dashboard/). Extracts per-plant: capacity, PLF, normative
stock, daily requirement, actual stock (indigenous/import/total), stock %,
critical flag, day's receipt and consumption, and the remarks column which
names the coal source (mine/company e.g. BCCL/CCL, rail vs road vs ship).

Usage:
    python -m scrapers.cea_coal --file data/downloads/dailyCoal1-2026-09-16.pdf
    python -m scrapers.cea_coal --url <direct pdf url>
    python -m scrapers.cea_coal --latest   # try known URL patterns

The report date is taken from the "AS ON DD-MM-YYYY" header line.
"""
import argparse
import io
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber
import requests

from store import connect, log

KNOWN_URLS = [
    "https://npp.gov.in/CMSService/dailyCoal1.pdf",
    "https://cea.nic.in/api/upload/dailycoal/dailyCoal1.pdf",
]

DATE_RE = re.compile(r"AS ON\s+(\d{2}-\d{2}-\d{4})", re.I)
NUM_RE = re.compile(r"^[\d,.]+$")

COLUMNS = dict(capacity_mw=5, plf_pct=6, norm_stock_days=7, daily_req_kt=8,
               norm_stock_kt=9, stock_indigenous_kt=10, stock_import_kt=11,
               stock_total_kt=12, stock_pct=13, critical=14, receipt_kt=15,
               consumption_kt=16, remarks=17)


def _f(v):
    if v is None:
        return None
    v = str(v).replace(",", "").strip().rstrip("%").strip()
    try:
        return float(v)
    except ValueError:
        return None


def parse_date(text):
    m = DATE_RE.search(text)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%d-%m-%Y").date().isoformat()


HEAD = [  # (field, test on the header cell text, lower-cased, newlines as spaces)
    ("state", lambda t: t == "state"), ("utility", lambda t: t == "genco"), ("mode", lambda t: t.startswith("mode of")),
    ("plant", lambda t: t.startswith("name of thermal")), ("capacity_mw", lambda t: t.startswith("capacity")),
    ("plf_pct", lambda t: "plf" in t), ("norm_stock_days", lambda t: "(days)" in t),
    ("daily_req_kt", lambda t: t.startswith("daily requirement")), ("norm_stock_kt", lambda t: t.startswith("normative") and "(in" in t and "days" not in t),
    ("stock_indigenous_kt", lambda t: t.startswith("actual stock")), ("stock_pct", lambda t: t.startswith("% of actual")),
    ("critical", lambda t: t.startswith("critical")), ("receipt_kt", lambda t: t.startswith("receipt")),
    ("consumption_kt", lambda t: t.startswith("consumption")), ("remarks", lambda t: t.startswith("reasons")),
]
TEXT = {"plant", "state", "utility", "mode", "remarks", "critical"}


def header_map(row):
    """Column index per field from the report's header row. Two layouts so far: until Aug 2026 the state is a
    row of its own and there is no GENCO column (16 columns); from late Aug 2026 both are columns (18)."""
    cols = {}
    for i, c in enumerate(row):
        t = re.sub(r"\s+", " ", (c or "").replace("\n", " ")).strip().lower()
        for key, test in HEAD:
            if key not in cols and test(t):
                cols[key] = i
    if "stock_indigenous_kt" in cols:
        cols["stock_import_kt"] = cols["stock_indigenous_kt"] + 1
        cols["stock_total_kt"] = cols["stock_indigenous_kt"] + 2
    return cols if {"plant", "capacity_mw", "stock_indigenous_kt"} <= cols.keys() else None


def parse_pdf(path):
    rows, section, date, cols, state, pending = [], None, None, None, None, []
    with pdfplumber.open(path) as pdf:
        date = parse_date(pdf.pages[0].extract_text() or "")
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    row = [(c or "").replace("\n", " ").strip() for c in raw]
                    if not any(row):
                        continue
                    hm = header_map(raw)
                    if hm:
                        cols = hm
                        continue
                    if cols is None or len(row) <= max(cols.values()):
                        continue                # summary tables at the end have other layouts
                    first = row[0]
                    if re.match(r"^[A-D]\.\s", first):
                        section = first
                        continue
                    filled = [c for c in row if c]
                    if len(filled) == 1 and not NUM_RE.match(first) and first and first.upper() != "STATE":
                        state = first            # old layout: "Haryana" on a row of its own
                        continue
                    name = row[cols["plant"]]
                    tot = next((c for c in row[:cols["plant"] + 1] if c.endswith("-Total")), None)
                    if tot:                     # "HPGCL-Total" closes a utility block (old layout has no GENCO column)
                        for r in pending:
                            if tot[:-6].strip().lower() not in ("sub", "state", "grand", "region"):
                                r["utility"] = r["utility"] or tot[:-6].strip()
                        pending = []
                        continue
                    if not NUM_RE.match(first) or not name or NUM_RE.match(name) or "total" in name.lower():
                        continue
                    rec = {"plant": name, "section": section, "state": state, "utility": None, "mode": None}
                    for key, i in cols.items():
                        if key == "plant":
                            continue
                        rec[key] = row[i] if key in TEXT else _f(row[i])
                    rec["state"] = rec.get("state") or state
                    rec["critical"] = 1 if (rec.get("critical") or "").strip() == "*" else 0
                    for k in ("stock_indigenous_kt", "stock_import_kt", "stock_total_kt", "receipt_kt", "consumption_kt", "remarks"):
                        rec.setdefault(k, None)
                    rows.append(rec)
                    pending.append(rec)
    return date, rows


def save(date, rows, db_path=None):
    if not date:
        raise ValueError("could not find report date (AS ON DD-MM-YYYY)")
    con = connect(db_path)
    with con:
        con.executemany(
            """INSERT OR REPLACE INTO coal_plants_daily
            (date, plant, utility, state, section, mode, capacity_mw, plf_pct,
             norm_stock_days, daily_req_kt, norm_stock_kt, stock_indigenous_kt,
             stock_import_kt, stock_total_kt, stock_pct, critical,
             receipt_kt, consumption_kt, remarks)
            VALUES (:date,:plant,:utility,:state,:section,:mode,:capacity_mw,:plf_pct,
             :norm_stock_days,:daily_req_kt,:norm_stock_kt,:stock_indigenous_kt,
             :stock_import_kt,:stock_total_kt,:stock_pct,:critical,
             :receipt_kt,:consumption_kt,:remarks)""",
            [dict(r, date=date) for r in rows])
    con.close()
    return date, len(rows)


def fetch(url, timeout=60):
    r = requests.get(url, timeout=timeout, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    p = Path("data/downloads") / f"dailyCoal1-{datetime.now():%Y-%m-%d}.pdf"
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(r.content)
    return p


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--url")
    g.add_argument("--latest", action="store_true")
    ap.add_argument("--db", default=None)
    args = ap.parse_args()

    if args.file:
        path = Path(args.file)
    elif args.url:
        path = fetch(args.url)
    else:
        path = None
        for url in KNOWN_URLS:
            try:
                path = fetch(url)
                break
            except Exception as e:
                print(f"  {url} -> {e}", file=sys.stderr)
        if path is None:
            log("cea_coal", "fail", "no known URL reachable")
            sys.exit(1)

    date, rows = parse_pdf(path)
    date, n = save(date, rows, args.db)
    tn = sum(1 for r in rows if "TAMIL" in (r["state"] or "").upper())
    msg = f"{date}: {n} plants ({tn} Tamil Nadu) from {path}"
    print(msg)
    log("cea_coal", "ok", msg)


if __name__ == "__main__":
    main()
