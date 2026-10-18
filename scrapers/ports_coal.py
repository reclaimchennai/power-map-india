"""Coal handled at India's ports, monthly, from the Ministry of Ports, Shipping & Waterways.

Source: the Transport Research wing's monthly "Cargo handled at Major Ports" and "... Non-Major Ports" PDFs,
listed at https://shipmin.gov.in/division/transport-research (latest ~20) and
https://shipmin.gov.in/division/archieve/transport-research?page=0..3 (back to Apr 2017; non-major from 2018-19).
File names are inconsistent, so the report month (table header 'August 2026 (A)', else the opening line
or heading) and the port group are read from the PDF text. Hindi versions are skipped. Dec 2024 - Oct 2025
are linked from neither page but mostly still on the server; --all probes the usual file names for them.
PDFs are cached in raw/coal/ports/.

Table-2 ("Commodity-wise cargo handled") gives Thermal / Coking / Other coal for the month, the same month a
year earlier and both financial-year cumulatives: tonnes since 2024, '000 t before (scaled by magnitude).
Some 2025-26 reports print one undivided "Coal" row; the 2017-18 reports have a month-by-month table with a
single 'Coal (Thermal & Coking)' column. Table-1 is port-wise total cargo only (no port-by-commodity
table), so nothing per port is stored. Scanned reports (2019-20, Apr/Jul-Oct 2020; OCR layer or images)
are not parsed reliably: their rows only fill gaps, and most such months come from the next year's
year-earlier column instead.

Series written to coal_supply (values in Mt):
  port_coal_m:Major-Thermal / -Coking / -Other / -All     month, 12 major ports (-All = sum, or the undivided row)
  port_coal_m:NonMajor-Thermal / ...                       month, state maritime boards / directorates of ports
  port_coal_m:Total-Thermal / ...                          major + non-major, only where both exist
  port_coal_fytd:<group>-<kind>                            April-to-month cumulative, as published
A report's own month replaces; its year-earlier column (and previous-FY rows) only fill periods with
nothing stored, and the source string says so. Months missing between reports are derived from the
cumulatives where possible.

    python -m scrapers.ports_coal            # newest listing page (collect.py)
    python -m scrapers.ports_coal --all      # backfill every report on the listing + archive pages
"""
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
import urllib3

from scrapers.coal_supply import SCHEMA, put
from store import connect, log

urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
BASE = "https://shipmin.gov.in"
LIST = BASE + "/division/transport-research"
ARCH = BASE + "/division/archieve/transport-research?page={}"
RAW = Path(__file__).resolve().parent.parent / "raw" / "coal" / "ports"
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
KINDS = {"thermal": "Thermal", "coking": "Coking", "other": "Other"}
S = requests.Session()
S.headers.update(UA)


def get(url, **kw):
    for i in range(3):
        try:
            r = S.get(url, timeout=120, verify=False, **kw)
            r.raise_for_status()
            return r
        except Exception:
            if i == 2:
                raise
            time.sleep(5)


def listing(pages):
    """[(title, pdf url)] of monthly cargo reports on the given listing pages (None = main page)."""
    out = []
    for p in pages:
        page = get(LIST if p is None else ARCH.format(p)).text
        for tr in re.findall(r"<tr.*?</tr>", page, re.S):
            hrefs = re.findall(r'href="([^"]+\.pdf)"', tr, re.I)
            cells = [re.sub(r"<[^>]+>|\s+", " ", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            title = cells[1] if len(cells) > 1 else ""
            if not hrefs or not re.search(r"cargo", title, re.I) or re.search(r"hindi", title, re.I):
                continue
            if not re.search(r"port|during|upto|up to", title, re.I):
                continue
            out.append((title, urljoin(BASE, hrefs[0])))
        time.sleep(1.5)
    return out


def archive_pages():
    page = get(ARCH.format(0)).text
    n = max([int(x) for x in re.findall(r"archieve/transport-research\?page=(\d+)", page)] or [0])
    return list(range(n + 1))


def fetch(url):
    """Download (cached) and return the local path."""
    RAW.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^\w.\-]+", "_", unquote(url.rsplit("/", 1)[1]))
    path = RAW / name
    if not path.exists() or path.stat().st_size < 1000:
        path.write_bytes(get(url).content)
        time.sleep(1.5)
    return path


def scanned(path):
    """True for scans whose only text is an OCR layer (fonts not embedded): digits there are unreliable."""
    out = subprocess.run(["pdffonts", str(path)], capture_output=True, text=True, timeout=60).stdout.splitlines()[2:]
    return bool(out) and not any(re.search(r"\byes\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", l) for l in out)


def text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, timeout=120).stdout


# ---------------------------------------------------------------- parsing

MONTH_RE = r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
NUM = r"-?\d[\d,]*(?:\.\d+)?"


def report_month(t):
    """(year, month) the report is for: the table column header ('August 2026 (A)'), the opening line
    ('provides data for August 2026'), else the heading ('... DURING [AND UP TO] AUGUST, 2026').
    Headings are sometimes stale (the Jan 2025 non-major report is headed JANUARY 2024)."""
    head = t[:4000]
    for pat in (MONTH_RE + r"[\s,]*(20\d\d)\s*\(A\)",                  # Table header of the month's column
                r"provides\s+data\s+for\s+" + MONTH_RE + r"[\s,]*(20\d\d)",
                r"during\s+(?:and\s+up\s*to\s+|and\s+upto\s+)?" + MONTH_RE + r"[\s,.']*(20\d\d)",
                r"(?:up\s*to|upto)\s+" + MONTH_RE + r"[\s,.']*(20\d\d)",
                ):
        m = re.search(pat, head, re.I) or re.search(pat, t, re.I)
        if m:
            return int(m.group(2)), MONTHS[m.group(1).lower()[:3]]
    return None


def port_group(t):
    head = t[:3000].upper()
    if re.search(r"NON[\s-]*MAJOR|DIRECTORATE OF PORTS|MARITIME BOARD", head):
        return "NonMajor"
    if "MAJOR PORT" in head:
        return "Major"
    return None


def numeric_tokens(line):
    """[(column offset, value)] if the line holds only numbers, else None."""
    toks = [(m.start(), m.group()) for m in re.finditer(r"\S+", line)]
    if not toks or not all(re.fullmatch(NUM, x) for _, x in toks):
        return None
    return [(i, float(x.replace(",", ""))) for i, x in toks]


def coal_lines(t, merge=True):
    """{kind: (prevM, curM, prevCum, curCum)} from Table-2 'Thermal/Coking/Other Coal' rows
    (kind 'All' = an undivided 'Coal' row). pdftotext keeps column offsets, so a row that wrapped
    onto the line above or below is put back together by offset."""
    out = {}
    lines = t.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*(?:Coal\s+)?(Thermal|Coking|Other)\s+Coal\s+)(.*)$", line, re.I)
        kind = KINDS[m.group(2).lower()] if m else None
        if not m:
            m = re.match(r"^(\s*Coal\s+)(" + NUM + r"(?:\s.*)?)$", line)
            kind = "All" if m else None
        if not kind or kind in out:
            continue
        own = numeric_tokens(" " * len(m.group(1)) + m.group(m.lastindex))
        if own is None:
            continue                                  # prose, or OCR noise
        above = numeric_tokens(lines[i - 1]) if i else None
        below = numeric_tokens(lines[i + 1]) if i + 1 < len(lines) else None
        for extra in ([], below or [], above or [], (above or []) + (below or [])) if merge else ([],):
            cols = columns([v for _, v in sorted(own + extra)])
            if cols:
                out[kind] = cols
                break
    return out


def columns(nums):
    """(prev month, month, prev FY cumulative, FY cumulative) from one Table-2 row, or None.

    Layouts seen:  2024-:      prevM curM share% chg% prevCum curCum share% chg%            (tonnes)
                   2018-2023:  prevM share curM share [prevCum share curCum share] chg%     ('000 t)
    (the trailing change % sometimes wraps away)."""
    old = len(nums) >= 4 and nums[0] >= 100 and 0 <= nums[1] < 100 and 0 <= nums[3] < 100 and nums[2] >= 100
    if old and len(nums) in (8, 9) and nums[4] >= 100 and nums[5] < 100 and nums[6] >= 100:
        return nums[0], nums[2], nums[4], nums[6]
    if old and len(nums) in (4, 5):
        return nums[0], nums[2], None, None
    new = len(nums) >= 3 and nums[0] >= 1000 and nums[1] >= 1000 and 0 <= nums[2] < 100
    if new and len(nums) == 8 and nums[4] >= 1000 and nums[5] >= 1000 and 0 <= nums[6] < 100:
        return nums[0], nums[1], nums[4], nums[5]
    if new and len(nums) == 4 and min(nums[0], nums[1]) >= 1e4:
        return nums[0], nums[1], None, None
    return None


def old_monthly_table(t, y, mo):
    """2017-18 layout: Table 2 lists every month (previous FY and current FY to date) with a single
    'Coal (Thermal & Coking)' column in thousand tonnes. -> {(y, m): (value_kt, is_current_fy)}"""
    i = t.find("COMMODITY-WISE MONTHLY CARGO")
    if i < 0:
        return {}
    fy = y if mo >= 4 else y - 1                          # FY start year of the report month
    names = ["apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "jan", "feb", "mar"]
    runs, seen = [[]], set()
    for line in t[i:i + 12000].splitlines():
        m = re.match(r"^\s*([A-Z][a-z]+)\.?\s+((?:\d+\s+){7,}\d+)", line)
        if not m or m.group(1).lower()[:3] not in names:
            continue
        k = names.index(m.group(1).lower()[:3])
        if k in seen:                                     # April again: a new financial year starts
            runs.append([])
            seen = set()
        seen.add(k)
        runs[-1].append((k, [int(x) for x in m.group(2).split()]))
    runs = [r for r in runs if r]
    if not runs or names[runs[-1][-1][0]] != names[(mo - 4) % 12]:
        return {}                                         # last run must end with the report month
    out = {}
    for back, run in enumerate(reversed(runs[-2:])):   # last run = this FY, the one before = last FY
        for k, nums in run:
            start = fy - back
            yy, mm = (start, k + 4) if k < 9 else (start + 1, k - 8)
            if 3000 < nums[3] < 40000:
                out[(yy, mm)] = (nums[3], back == 0)
    return out


def parse(path):
    """-> (group, (y, m), rows) where rows are (series, period, value_Mt, unit, source, own)."""
    t = text(path)
    ym, grp = report_month(t), port_group(t)
    if not ym or not grp:
        return grp, ym, []
    y, mo = ym
    per = f"{y}-{mo:02d}"
    prev = f"{y - 1}-{mo:02d}"
    src = f"MoPSW Transport Research, {'Major' if grp == 'Major' else 'Non-Major'} Ports cargo report {per} ({path.name})"
    rows = []
    ocr = scanned(path)
    if ocr:
        src += " [scan, OCR text layer: used only where nothing better exists]"
    parsed = coal_lines(t, merge=not ocr)
    if parsed:
        scale = 1e-6 if max(v[1] for v in parsed.values()) > 2e5 else 1e-3          # tonnes or '000 t
        if all(k in parsed for k in ("Thermal", "Coking", "Other")):
            parsed["All"] = tuple(None if any(parsed[k][i] is None for k in ("Thermal", "Coking", "Other"))
                                  else sum(parsed[k][i] for k in ("Thermal", "Coking", "Other")) for i in range(4))
        for kind, (pm, cm, pc, cc) in parsed.items():
            if mo == 4:                                   # April reports repeat last FY's Apr-Mar in the cumulative columns
                pc, cc = pm, cm
            s = f"{grp}-{kind}"
            rows.append((f"port_coal_m:{s}", per, round(cm * scale, 4), "Mt", src, not ocr))
            rows.append((f"port_coal_m:{s}", prev, round(pm * scale, 4), "Mt", src + " [year-earlier column]", False))
            if cc is not None and cc >= cm:
                rows.append((f"port_coal_fytd:{s}", per, round(cc * scale, 4), "Mt", src, not ocr))
            if pc is not None and pc >= pm:
                rows.append((f"port_coal_fytd:{s}", prev, round(pc * scale, 4), "Mt", src + " [year-earlier column]", False))
    elif grp == "Major":
        for (yy, mm), (v, cur) in old_monthly_table(t, y, mo).items():
            p = f"{yy}-{mm:02d}"
            rows.append(("port_coal_m:Major-All", p, round(v / 1000, 4), "Mt",
                         src + (" [monthly table]" if cur else " [monthly table, previous FY]"), cur and p == per))
    return grp, ym, rows


# ---------------------------------------------------------------- storing

def existing():
    """(series, period) holding a published figure (derived ones may be overwritten by a year-earlier column)."""
    con = connect()
    con.executescript(SCHEMA)
    got = {(s, p) for s, p in con.execute("SELECT series, period FROM coal_supply WHERE series LIKE 'port_coal_%' "
                                          "AND source NOT LIKE 'derived%' AND source NOT LIKE 'sum of%'")}
    con.close()
    return got


def store(rows):
    """Own-month figures replace; year-earlier / previous-FY figures only fill gaps."""
    have = existing()
    own = {(r[0], r[1]): r[:5] for r in rows if r[5]}
    fill = {}
    for r in rows:
        k = (r[0], r[1])
        if not r[5] and k not in own and k not in have and k not in fill:
            fill[k] = r[:5]
    put(list(own.values()) + list(fill.values()))
    derive()
    return len(own) + len(fill)


def prev_month(p):
    y, m = int(p[:4]), int(p[5:])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def derive():
    """Fill months missing between reports from FY cumulatives, then the major + non-major totals."""
    con = connect()
    data = {}
    for s, p, v, src in con.execute("SELECT series, period, value, source FROM coal_supply WHERE series LIKE 'port_coal_%'"):
        data[(s, p)] = (v, src)
    rows = []
    for (s, p), (v, _) in sorted(data.items(), reverse=True):   # FY cumulative to month m-1 = to m minus month m
        if not s.startswith("port_coal_fytd:") or p.endswith("-04"):
            continue
        before, month = (s, prev_month(p)), data.get((s.replace("port_coal_fytd:", "port_coal_m:"), p))
        if before not in data and month and v >= month[0]:
            data[before] = (v - month[0], "derived")
            rows.append((s, before[1], round(v - month[0], 4), "Mt", "derived from MoPSW FY-cumulative and monthly columns"))
    for (s, p), (v, _) in list(data.items()):
        if not s.startswith("port_coal_fytd:"):
            continue
        ms = s.replace("port_coal_fytd:", "port_coal_m:")
        if (ms, p) in data:
            continue
        if p.endswith("-04"):
            val = v
        else:
            before = data.get((s, prev_month(p)))
            if not before or v < before[0]:
                continue
            val = v - before[0]
        rows.append((ms, p, round(val, 4), "Mt", "derived from MoPSW FY-cumulative columns"))
        data[(ms, p)] = (val, "derived")
    for (s, p), (v, _) in list(data.items()):
        if not s.startswith("port_coal_m:Major-"):
            continue
        kind = s.split("-", 1)[1]
        nm = data.get((f"port_coal_m:NonMajor-{kind}", p))
        if nm:
            rows.append((f"port_coal_m:Total-{kind}", p, round(v + nm[0], 4), "Mt", "sum of MoPSW major + non-major port reports"))
    con.close()
    put(rows)


# ---------------------------------------------------------------- driver

FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
GUESS = {"Major": ["Cargo handled at Major Ports {M} {Y}", "Report Cargo handled at Major Ports {M} {Y}",
                   "Cargo handled at Major Port {M} {Y}", "Report Monthly Major Port {M} {Y}"],
         "NonMajor": ["Cargo handled at Non-Major Ports {M} {Y}", "Non-Major Cargo report {M} {Y}",
                      "Cargo handled at Non- Major Ports {M} {Y}", "Non-Major cargo report {M} {Y}"]}


def guess(grp, y, m):
    """Reports dropped from both listings (e.g. Dec 2024 - Oct 2025) are often still on the server
    under the usual names."""
    for pat in GUESS[grp]:
        for mn in (FULL[m - 1], FULL[m - 1][:3]):
            url = BASE + "/sites/default/files/" + pat.format(M=mn, Y=y).replace(" ", "%20") + ".pdf"
            try:
                r = S.get(url, timeout=60, verify=False)
            except Exception:
                r = None
            time.sleep(1.2)
            if r is not None and r.status_code == 200 and r.content[:4] == b"%PDF":
                path = RAW / re.sub(r"[^\w.\-]+", "_", unquote(url.rsplit("/", 1)[1]))
                path.write_bytes(r.content)
                return url
    return None


def run(pages=(None,), guess_from=None):
    """Parse every report on the given listing pages; with guess_from=(y, m), also probe the server for
    months (from then to last month) that no listing links. Returns (rows stored, months done, failures)."""
    rows, done, failed = [], set(), []
    for title, url in listing(pages):
        try:
            grp, ym, r = parse(fetch(url))
        except Exception as e:
            failed.append(f"{title}: {e}")
            continue
        if not any(x[5] and x[0].startswith("port_coal_m:") for x in r):
            failed.append(f"{title} ({url.rsplit('/', 1)[1]}): no coal rows parsed")
        if ym and grp:
            done.add((grp, ym))
        rows += r
    if guess_from:
        y, m = guess_from
        today = time.localtime()
        while (y, m) < (today.tm_year, today.tm_mon):
            for grp in ("Major", "NonMajor"):
                if (grp, (y, m)) in done:
                    continue
                url = guess(grp, y, m)
                if url:
                    g, ym, r = parse(fetch(url))
                    print("guessed", url, g, ym, len(r), flush=True)
                    if ym and g:
                        done.add((g, ym))
                    rows += r
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    n = store(rows)
    return n, done, failed


def summary():
    con = connect()
    out = con.execute("SELECT series, min(period), max(period), count(*) FROM coal_supply WHERE series LIKE 'port_coal_%' "
                      "GROUP BY series ORDER BY series").fetchall()
    con.close()
    return out


if __name__ == "__main__":
    if "--all" in sys.argv:
        n, done, failed = run([None] + archive_pages(), guess_from=(2024, 11))
    else:
        n, done, failed = run()
    log("ports_coal", "ok" if n else "error", f"{n} rows, {len(done)} reports, {len(failed)} failed")
    for f in failed:
        print("FAILED", f)
    for r in summary():
        print(*r)
