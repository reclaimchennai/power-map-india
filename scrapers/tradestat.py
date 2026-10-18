"""India's monthly coal imports by HS code, from the Ministry of Commerce's TradeStat database.

Source: https://tradestat.commerce.gov.in/meidb/commoditywise_import (Laravel form; GET gives the _token
hidden field + session cookies, every POST response carries the next token). One POST = one month + one
HS code + one measure: imddMonth=1-12, imddYear=2018..2026, comlev=specific, comval=<HS>,
imddReportVal=2 (quantity) or 1 (US$ million), imddReportYear=1. The result table has the month, the same
month a year earlier (revised) and both April-to-month cumulatives; the month's own column is stored and
the year-earlier column only fills periods with nothing stored (that is how 2017 gets in).

Unit trap: quantities are in tonnes up to FY 2020-21 and in kilograms from April 2021, and the UNIT
column cannot be trusted (8-digit rows say KGS on tonne figures; 4-digit rows are blank). The unit of
every column is therefore taken from the HS 2701 total in the same column (India imports 10-40 Mt a month:
~1e7 means tonnes, ~1e10 kilograms) and applied to every code of that month.
Months not yet published come back as 0 and are not stored.

Series written to coal_supply:
  imports_m:Total       HS 2701 all coal, Mt             imports_usd_m:Total       US$ million
  imports_m:Thermal     27011920 steam coal              imports_usd_m:Thermal ...
  imports_m:Coking      27011910 coking coal
  imports_m:Other       27011990 other bituminous
  imports_m:Anthracite  27011100
  imports_m:Lignite     2702
  imports_m:Coke        2704 coke and semi-coke
Raw result tables are cached in raw/coal/tradestat/.

    python -m scrapers.tradestat               # last 4 months, always refetched (collect.py)
    python -m scrapers.tradestat --all         # backfill Jan 2018 onwards (cached months are not refetched)
"""
import html as htmllib
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
import urllib3

from scrapers.coal_supply import SCHEMA, put
from store import connect, log

urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
URL = "https://tradestat.commerce.gov.in/meidb/commoditywise_import"
RAW = Path(__file__).resolve().parent.parent / "raw" / "coal" / "tradestat"
CODES = {"2701": "Total", "27011920": "Thermal", "27011910": "Coking", "27011990": "Other",
         "27011100": "Anthracite", "2702": "Lignite", "2704": "Coke"}
MEASURES = {"2": ("imports_m", "Mt"), "1": ("imports_usd_m", "USD mn")}
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
FIRST = (2018, 1)


class Client:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update(UA)
        self.token = None

    def refresh(self):
        page = self.s.get(URL, timeout=90, verify=False).text
        self.token = re.search(r'name="_token" value="([^"]+)"', page).group(1)
        time.sleep(1)

    def query(self, y, m, code, val):
        """The result table's HTML for one month / code / measure."""
        for attempt in range(4):
            try:
                if not self.token:
                    self.refresh()
                r = self.s.post(URL, timeout=120, verify=False, data={
                    "_token": self.token, "imddMonth": str(m), "imddYear": str(y), "comlev": "specific",
                    "comval": code, "imddReportVal": val, "imddReportYear": "1"})
                tok = re.search(r'name="_token" value="([^"]+)"', r.text)
                self.token = tok.group(1) if r.status_code == 200 and tok else None
                if r.status_code == 200:
                    t = re.search(r"<table.*?</table>", r.text, re.S)
                    if t:
                        return t.group(0)
                time.sleep(3 * (attempt + 1))
            except requests.RequestException:
                self.token = None
                time.sleep(10 * (attempt + 1))
            finally:
                time.sleep(1)
        raise RuntimeError(f"TradeStat gave no table for {code} {y}-{m:02d} val={val}")


def cells(row):
    return [htmllib.unescape(re.sub(r"<[^>]+>|\s+", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]


def parse(table, code):
    """-> [(period, value)] for the single-month columns (year-earlier first), value None when blank."""
    rows = [cells(r) for r in re.findall(r"<tr.*?</tr>", table, re.S)]
    if not rows:
        return []
    head = rows[0]
    cols = [(i, f"{int(m.group(2))}-{MON[m.group(1).lower()]:02d}") for i, h in enumerate(head)
            for m in [re.fullmatch(r"([A-Za-z]{3})-(\d{4})\s*(\([A-Z]\))?", h)] if m]
    row = next((r for r in rows[1:] if len(r) > 2 and r[1] == code), None)
    if not row:
        return [(p, None) for _, p in cols]
    out = []
    for i, p in cols:
        v = row[i].replace(",", "") if i < len(row) else ""
        try:
            out.append((p, float(v)))
        except ValueError:
            out.append((p, None))
    return out


def cached(y, m, code, val, refetch, client):
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{code}_{y}-{m:02d}_{'qty' if val == '2' else 'usd'}.html"
    if path.exists() and not refetch:
        return path.read_text()
    t = client.query(y, m, code, val)
    path.write_text(t)
    return t


def month_rows(y, m, client, refetch=False):
    """All series for one query month: [(series, period, value, unit, source, own)]."""
    rows = []
    for val, (measure, unit) in MEASURES.items():
        scale = {}
        for code, kind in CODES.items():
            got = parse(cached(y, m, code, val, refetch, client), code)
            if code == "2701" and val == "2":
                # tonnes (~1e7 a month) or kilograms (~1e10), per column, from the all-coal total
                scale = {p: (1e-9 if v > 1e9 else 1e-6) for p, v in got if v}
            for k, (p, v) in enumerate(got):
                if not v or v <= 0:
                    continue                            # blank, or month not yet published
                own = p == f"{y}-{m:02d}"
                if val == "2":
                    if p not in scale:
                        continue
                    v = v * scale[p]
                src = f"Ministry of Commerce TradeStat (HS {code})" + ("" if own else " [year-earlier column]")
                rows.append((f"{measure}:{kind}", p, round(v, 6 if val == "2" else 3), unit, src, own))
    return rows


def store(rows):
    """Own-month figures replace; year-earlier figures only fill periods with nothing stored."""
    con = connect()
    con.executescript(SCHEMA)
    have = {(s, p) for s, p in con.execute("SELECT series, period FROM coal_supply WHERE series LIKE 'imports%'")}
    con.close()
    own = {(r[0], r[1]): r[:5] for r in rows if r[5]}
    fill = {}
    for r in rows:
        k = (r[0], r[1])
        if not r[5] and k not in own and k not in have:
            fill.setdefault(k, r[:5])
    put(list(own.values()) + list(fill.values()))
    return len(own) + len(fill)


def months(start, end):
    y, m = start
    while (y, m) <= end:
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def run(back=4, start=None, refetch_recent=6):
    """Query `back` months up to last month (or every month from `start`); months within
    `refetch_recent` of today are always refetched, older ones come from the cache when present."""
    t = date.today()
    end = (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)
    if start is None:
        y, m = end
        for _ in range(back - 1):
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        start = (y, m)
    client, n, failed = Client(), 0, []
    for y, m in months(start, end):
        recent = (t.year - y) * 12 + t.month - m <= refetch_recent
        try:
            rows = month_rows(y, m, client, refetch=recent)
            n += store(rows)
            tot = next((r[2] for r in rows if r[0] == "imports_m:Total" and r[5]), None)
            print(f"{y}-{m:02d} {len(rows)} rows, total {tot} Mt", flush=True)
        except Exception as e:
            failed.append(f"{y}-{m:02d}: {e}")
            print(f"{y}-{m:02d} error {e}", flush=True)
    return n, failed


def check():
    """Continuity report: months far off the neighbouring months, parts larger than the total."""
    con = connect()
    data = {}
    for s, p, v in con.execute("SELECT series, period, value FROM coal_supply WHERE series LIKE 'imports%'"):
        data.setdefault(s, {})[p] = v
    con.close()
    notes = []
    for kind in ("Total", "Thermal", "Coking"):         # implied US$/t far off its neighbours = bad quantity
        q, u = data.get(f"imports_m:{kind}", {}), data.get(f"imports_usd_m:{kind}", {})
        ps = sorted(p for p in q if p in u and q[p] > 0)
        for a, b, c in zip(ps, ps[1:], ps[2:]):
            ua, ub, uc = (u[p] / q[p] for p in (a, b, c))
            if ub < (ua + uc) / 2 / 1.6 or ub > (ua + uc) / 2 * 1.6:
                notes.append(f"{kind} {b}: implied {ub:.0f} US$/t vs neighbours {ua:.0f}, {uc:.0f}")
    tot = data.get("imports_m:Total", {})
    for p, v in sorted(tot.items()):
        if not 8 <= v <= 40:
            notes.append(f"Total {p} = {v} Mt outside 8-40")
    for s, ser in data.items():
        if not s.startswith("imports_m:"):
            continue
        ps = sorted(ser)
        for a, b, c in zip(ps, ps[1:], ps[2:]):
            mid, nb = ser[b], (ser[a] + ser[c]) / 2
            if nb > 0.05 and (mid > 3 * nb or mid < nb / 3):
                notes.append(f"{s} {b} = {mid} vs neighbours {ser[a]}, {ser[c]}")
        if s != "imports_m:Total":
            for p, v in ser.items():
                if p in tot and v > tot[p] * 1.02:
                    notes.append(f"{s} {p} = {v} > total {tot[p]}")
    return notes


def summary():
    con = connect()
    out = con.execute("SELECT series, min(period), max(period), count(*) FROM coal_supply WHERE series LIKE 'imports%' "
                      "GROUP BY series ORDER BY series").fetchall()
    con.close()
    return out


if __name__ == "__main__":
    if "--all" in sys.argv:
        n, failed = run(start=FIRST)
    else:
        n, failed = run()
    log("tradestat", "ok" if n and not failed else ("error" if not n else "partial"), f"{n} rows, {len(failed)} months failed")
    for f in failed:
        print("FAILED", f)
    for r in summary():
        print(*r)
    for c in check():
        print("CHECK", c)
