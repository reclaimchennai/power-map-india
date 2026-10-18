"""TNEB/TANTRANSCO SLDC grid-details parser — full generation mix + imports.

peakdet.pdf (https://tnebsldc.org/reports1/peakdet.pdf) carries the daily
source-wise picture for Tamil Nadu:
  * TNEB own generation: hydro / thermal / gas (capacity, inst, min, morning
    peak, MU)
  * IPPs (PPN, TAQA, SEPC) and captive plants
  * NCES: co-gen, bio-mass, wind, solar
  * CGS (central generating station) share for TN — Ramagundam, Talcher,
    Simhadri, Kudgi, NTECL Vallur, Neyveli TS1/TS2, NTPL, MAPS, Kaiga,
    Kudankulam 1&2 — i.e. electricity TN imports via its allocated share
  * LTOA / MTOA / STOA & SWAP (open access), REMC through ISTS,
    Exchange (+ import / - export), DSM

Stored table tn_generation_mix: (date, section, item, capacity_mw,
inst_mw, min_mw, morning_mw, mu).
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber
import requests

from store import connect, log

PEAKDET_URL = "https://tnebsldc.org/reports1/peakdet.pdf"

TRAILING_NUMS = re.compile(
    r"\s+(-?\*?[\d,]+(?:\.\d+)?(?:\s+-?\*?[\d,]+(?:\.\d+)?)*)\s*$")
NUMS = re.compile(r"-?\*?[\d,]+(?:\.\d+)?")

# (keyword found anywhere in line, section) — first match wins
SECTIONS = [
    ("CGS", "CGS share"), ("TNPGCL/TNGECL", "TNEB own"),
    ("Independent Power Plant", "IPP"), ("Captive Power Plant", "CPP"),
    ("Non-Conventional Energy", "NCES"),
    ("LTOA", "OA"), ("MTOA", "OA"), ("STOA", "OA"),
    ("REMC", "ISTS"), ("Exchange", "interchange"), ("DSM", "DSM"),
    ("Load Shedding", "curtailment"), ("HT Relief", "curtailment"),
    ("Total", "total"),
]
NOISE = ("Date", "Hrs", "HZ", "Hz", "All time High", "solar generation",
         "Sl.", "Details", "Frequency", "Note:", "yesterday", "MW on",
         "OD(+)")


def _f(v):
    v = (v or "").replace(",", "").replace("*", "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    date = None
    m = re.search(r"Date\s*:\s*(\d{2}-\w{2,3}-\d{2,4})", text)
    if m:
        raw = m.group(1)
        for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d-%m-%y"):
            try:
                date = datetime.strptime(raw, fmt).date().isoformat()
                break
            except ValueError:
                continue
    rows, section = [], None
    pending_label = None
    for line in text.split("\n"):
        line = line.strip()
        if not line or any(n in line for n in NOISE):
            continue
        for key, sec in SECTIONS:
            if key in line.upper():
                section = sec
        m = TRAILING_NUMS.search(line)
        if not m:
            if re.fullmatch(r"[-\d.,*]+", line):
                # numeric-only continuation — the real MU of the previous
                # wrapped row (peakdet wraps MU onto its own line sometimes)
                if rows and pending_label:
                    rows[-1]["mu"] = _f(line)
                    pending_label = None
            elif re.search(r"[A-Za-z]", line):
                # wrapped label (e.g. "OA Consumers") — remember it for the
                # next numeric row
                pending_label = line.strip(" .*()-+")
            continue
        vals = [_f(n) for n in NUMS.findall(m.group(1))]
        name = line[:m.start()].strip(" .*()-+")
        name = re.sub(r"^\s*(?:\(?[ivx]+\)|\d+)\s*", "", name).strip()
        if pending_label:
            name = pending_label        # wrapped label from the line above
            pending_label = None
        if name.startswith("CPP (Wheeling)"):
            name = "CPP Wheeling / Third-Party OA consumers"
        if not name or not vals or len(vals) > 5 or name.isdigit():
            continue
        if len(vals) == 5:
            cap, a, b, c, mu = vals
        elif len(vals) == 4:                    # inst/min/morning + MU
            cap, (a, b, c, mu) = None, vals
        elif len(vals) == 3:                    # inst/min/morning, no MU
            cap = mu = None
            a, b, c = vals
        elif len(vals) == 2:
            if section == "CGS share":          # stray digit + capacity
                cap, mu = vals[-1], None
            else:
                cap, mu = vals[0], vals[1]
            a = b = c = None
        else:                                   # single figure
            cap = a = b = c = None
            if section == "CGS share":
                cap = vals[0]                   # e.g. "MAPS 330.5" = MW share
            else:
                mu = vals[0]
        rows.append(dict(
            section=section or "other", item=name[:60],
            capacity_mw=cap, inst_mw=a, min_mw=b, morning_mw=c, mu=mu))
    # de-duplicate lines whose text wrapped (same item twice in one report)
    best = {}
    for r in rows:
        k = (r["section"], re.sub(r"[^A-Za-z]", "", r["item"]).upper())
        if k not in best or sum(v is not None for v in r.values()) > \
                sum(v is not None for v in best[k].values()):
            best[k] = r
    return date, list(best.values())


def save(date, rows):
    con = connect()
    with con:
        con.execute("DELETE FROM tn_generation_mix WHERE date=?", (date,))
        con.executescript("""
        CREATE TABLE IF NOT EXISTS tn_generation_mix (
            date TEXT NOT NULL, section TEXT, item TEXT,
            capacity_mw REAL, inst_mw REAL, min_mw REAL,
            morning_mw REAL, mu REAL,
            PRIMARY KEY (date, section, item));
        """)
        con.executemany(
            """INSERT OR REPLACE INTO tn_generation_mix
            (date, section, item, capacity_mw, inst_mw, min_mw,
             morning_mw, mu)
            VALUES (:date,:section,:item,:capacity_mw,:inst_mw,:min_mw,
             :morning_mw,:mu)""",
            [dict(r, date=date) for r in rows])
    con.close()


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--url", default=PEAKDET_URL)
    args = ap.parse_args()
    if args.file:
        path = Path(args.file)
    else:
        r = requests.get(args.url, timeout=60, verify=False,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        path = Path("data/downloads/peakdet.pdf")
        path.write_bytes(r.content)
    date, rows = parse_pdf(path)
    if not date or not rows:
        log("tn_mix", "fail", f"could not parse {path}")
        sys.exit(1)
    save(date, rows)
    print(f"{date}: {len(rows)} mix rows")
    log("tn_mix", "ok", f"{date}: {len(rows)} rows")


if __name__ == "__main__":
    main()
