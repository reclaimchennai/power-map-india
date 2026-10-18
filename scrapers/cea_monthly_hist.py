"""CEA monthly coal statement and imported-coal report, Apr 2014 - Feb 2024, from the PDF archive on cea.nic.in:
back-fills what scrapers/cea_monthly.py stores from the NPP XLS files (Apr 2023 on).

Source: the "Fuel Management Division -> monthly reports" archive on cea.nic.in. Each month's list of files comes from
    POST https://cea.nic.in/wp-admin/admin-ajax.php  action=monthly_archive_report&selMonthYear=YYYY-MM&reportType=coal
which returns HTML with links to PDFs: coal_stat-MM[-N].pdf (2014-2020), Monthly_Coal_Report_<Mon>_<YYYY>*.pdf (2020+),
coal_import-MM[-N].pdf / Import_Report_<Mon>_<YYYY>*.pdf (Feb 2017 on; one FY 2014-15 import summary sits in May 2015),
plus gas / liquid-fuel reports that are ignored. Listing months are not always the report month (Jul 2015 is listed
under Jun 2015, the "Apr 2020" coal file is the Mar 2020 report, two Jul 2017 files are swapped), so each PDF's month
and kind are read from its own title.

Layouts (column labels read from the ruled header of every page, so the parser follows each month's own header):
  Apr 2014 - Mar 2016  requirement | receipt CIL/SCCL, other source, import, total, % | receipt equiv. raw |
                       consumption actual, equiv. raw | closing stock, days
  Apr 2016 - Feb 2017  CIL/SCCL allocation | receipt CIL/SCCL, other source, import, total, % | consumption | closing
  Mar 2017 - Feb 2019  capacity | allocation | opening | receipt CIL/SCCL, captive, e-auction, import, [others from
                       Jul 2017], total, % | consumption | closing
  Mar 2019 - Feb 2024  as above with CIL and SCCL receipts split
Jan 2017 (coal) and Feb 2017 (import) are scanned images and are skipped. "Equiv. raw" (washed-coal equivalent)
columns, requirement, % and stock-days are not stored (except % receipt w.r.t. allocation -> rcpt_pct_alloc).

Table coal_plants_monthly (schema and names as scrapers.cea_monthly): one row per plant for months that the NPP XLS
does not cover. Up to Feb 2019 CIL and SCCL receipts are one figure, stored in the extra column rcpt_cil_sccl_kt
(added here, NULL otherwise); up to Feb 2017 "other source" (all non-CIL/SCCL domestic coal: captive, e-auction,
others) goes to rcpt_other_kt. Region comes from the "Total of <region>" rows. State/utility from coal_plants_daily.
Table coal_import_power_monthly: entities are utilities / IPP plants as named in the old reports.

National series in coal_supply (Mt, CEA's own All-India / grand-total rows):
  cea_rcpt_m:Total|Domestic|Import      every month        cea_cons_m:Total, cea_stock_m:Total  every month
  cea_rcpt_m:Captive|E-Auction          from Mar 2017      cea_rcpt_m:Others  from Jul 2017
  cea_rcpt_m:CIL|SCCL                   from Mar 2019      import_power_m:Blending|Design|Total  from Feb 2017
Checks: plant rows are summed against CEA's region and All-India rows (mismatches reported); plant names mangled by
the PDF layout are mapped to their usual spelling (canonical_names); typing errors in the PDFs that CEA carried into
its totals are nulled and the affected All-India figures left out (sanity).
Months already stored from the NPP XLS are never overwritten (only compared); rows whose source is a "same month
last year" column of a later report are replaced by the month's own report.

    python -m scrapers.cea_monthly_hist              # full back-fill, cached listing and PDFs reused
    python -m scrapers.cea_monthly_hist --relist     # re-query the archive listing first
    python -m scrapers.cea_monthly_hist --month 2019-07
PDFs and the listing are cached in raw/coal/cea_monthly_hist/.
"""
import json
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests
import urllib3

from scrapers.cea_monthly import COLS, MONTHS, RENAMED, SCHEMA, _lookup, _shift
from scrapers.coal_supply import put
from store import connect, log

urllib3.disable_warnings()
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 (reclaimchennai power map)"}
AJAX = "https://cea.nic.in/wp-admin/admin-ajax.php"
RAW = Path(__file__).resolve().parent.parent / "raw" / "coal" / "cea_monthly_hist"
FIRST, LAST = "2014-04", "2024-03"
HCOLS = COLS + ["rcpt_cil_sccl_kt"]
SUMMABLE = [c for c in HCOLS if c.endswith("_kt")]
MON_RE = r"(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*"
JUNK = r"STATEMENT|REPORT|FIGURES|QUANTITY|AUTHORITY|DIVISION|PAGE\s*\d+\s*OF"
NUM_RE = re.compile(r"^\(?-?[\d,]*\.?\d+\)?%?$")
REGIONS = [("NORTHEAST", "North Eastern"), ("NORTH-EAST", "North Eastern"), ("NORTHERN", "Northern"),
           ("WESTERN", "Western"), ("SOUTHERN", "Southern"), ("EASTERN", "Eastern"), ("NORTH", "North Eastern")]


# ---------------------------------------------------------------- listing and download

# The archive listing is not stable: in Sep 2026 it returned nothing for Jun 2021 - Nov 2022 (bar Jan and Sep 2022;
# Sep 2022 only its import report)
# and dropped the Jan / May 2021 import reports, although the files are still served. These URLs were listed
# earlier and are always added (duplicates of a month are detected from the PDF titles and skipped).
FALLBACK = {
    "2021-01": ["2021/01/coal_import.pdf"],
    "2021-05": ["2021/05/Import_Report_May_2021_Send_Final.pdf"],
    "2021-06": ["2021/06/Coal_Import_Report_June_2021_send.pdf", "2021/06/Monthly_Coal_Report_June_2021_send.pdf"],
    "2021-07": ["2021/08/Monthly_Coal_Report_July_2021_send-1.pdf"],
    "2021-08": ["2021/08/Coal_Import_Report_August_2021_send.pdf", "2021/08/Monthly_Coal_Report_Aug_2021_send-1.pdf"],
    "2021-09": ["2021/09/Coal_Import_Report_September_2021_send.pdf", "2021/09/Monthly_Coal_Report_Sep_2021_send.pdf"],
    "2021-10": ["2021/10/Import_Report_October_2021__send.pdf", "2021/10/Monthly_Coal_Report_October_2021_External.pdf"],
    "2021-11": ["2022/01/Import_Report_November_2021.pdf", "2022/01/Monthly_Coal_Report_Nov_2021_send-1.pdf"],
    "2021-12": ["2021/12/Import_Report_December_2021.pdf", "2022/01/Monthly_Coal_Report_Dec_2021.pdf"],
    "2022-02": ["2022/02/Import_Report_February_2022__send.pdf", "2022/02/Monthly_Coal_Report_Feb_2022_send.pdf"],
    "2022-03": ["2022/03/Monthly_Coal_Report_Mar_2022_send-1.pdf", "2022/04/Import_Report_March_2022__Send.pdf"],
    "2022-04": ["2022/04/Import_Report_April_2022__send.pdf", "2022/04/Monthly_Coal_Report_Apr_2022_send.pdf"],
    "2022-05": ["2022/05/Import_Report_May_2022__send.pdf", "2022/05/Monthly_Coal_Report_May_2022_send.pdf"],
    "2022-06": ["2022/07/Import_Report_June_2022__send.pdf", "2022/07/Monthly_Coal_Report_June_2022_send.pdf"],
    "2022-07": ["2022/08/Import_Report_July_2022__Send-1.pdf", "2022/08/Monthly_Coal_Report_July_2022_Send.pdf"],
    "2022-08": ["2022/08/Monthly_Coal_Report_Aug_2022_send.pdf"],
    "2022-09": ["2022/11/Monthly_Coal_Report_Sep_2022_send.pdf"],
    "2022-10": ["2022/11/Import_Report_Oct_2022__send.pdf", "2022/11/Monthly_Coal_Report_Oct_2022_send.pdf"],
    "2022-11": ["2022/12/Import_Report_Nov_2022__send.pdf", "2022/12/Monthly_Coal_Report_Nov_2022_Send.pdf"],
}


def listing(months, refresh=False):
    """{listing month: [pdf url]} for coal statements and import reports (gas / liquid fuel reports dropped).
    A re-query only adds URLs to the cached listing, never removes them."""
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / "listing.json"
    out = json.loads(cache.read_text()) if cache.exists() else {}
    for m in months:
        if m not in out or refresh:
            r = requests.post(AJAX, data={"action": "monthly_archive_report", "selMonthYear": m, "reportType": "coal"},
                              headers=UA, verify=False, timeout=60)
            time.sleep(1)
            r.raise_for_status()
            urls = set(re.findall(r'href="(https?://[^"]+\.pdf)"', r.text, re.I))
            urls = {u for u in urls if not re.search(r"gas|liq|overview", u.rsplit("/", 1)[1], re.I)}
            out[m] = sorted(urls | set(out.get(m, [])))
        out[m] = sorted(set(out[m]) | {"https://cea.nic.in/wp-content/uploads/coal/" + u for u in FALLBACK.get(m, [])})
        cache.write_text(json.dumps(out, indent=1, sort_keys=True))
    return out


def fetch(m, url):
    name = url.rsplit("/", 1)[1].replace("%20", "_")
    kind = "import" if "import" in name.lower() else "coal"
    path = RAW / f"{m}_{kind}_{name}"
    if path.exists() and path.stat().st_size:
        return path
    r = requests.get(url, headers=UA, verify=False, timeout=120)
    time.sleep(1)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError(f"{url}: not a PDF ({r.headers.get('content-type')})")
    path.write_bytes(r.content)
    return path


# ---------------------------------------------------------------- generic ruled-table reader

def _c(s):
    """compact upper-case label: 'Consumpti on' -> 'CONSUMPTION'."""
    return re.sub(r"[\s*#]+", "", s or "").upper()


def _num(s):
    s = (s or "").strip()
    if not s or s in ("-", "--", "NA", "N.A."):
        return None
    if not NUM_RE.match(s.replace(" ", "")):
        return None
    s = s.replace(",", "").replace("%", "").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")")
    v = float(s.strip("()"))
    return -v if neg else v


def _inside(w, box):
    xc, yc = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
    return box[0] - 0.5 <= xc <= box[2] + 0.5 and box[1] - 0.5 <= yc <= box[3] + 0.5


def _lines(words):
    """group words into text lines: a word joins the current line when its vertical centre lies within the line's
    extent (label and figure fonts differ, so tops alone do not line up)."""
    out = []
    for w in sorted(words, key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"])):
        yc = (w["top"] + w["bottom"]) / 2
        if out and out[-1][0] - 0.5 <= yc <= out[-1][1] + 0.5:
            out[-1][2].append(w)
            out[-1][0], out[-1][1] = min(out[-1][0], w["top"]), max(out[-1][1], w["bottom"])
        else:
            out.append([w["top"], w["bottom"], [w]])
    return [sorted(ws, key=lambda w: w["x0"]) for _, _, ws in out]


def _header(page, words, name_re):
    """-> (columns [(x0, x1, label)], header bottom) from the ruled table whose header has a cell matching name_re."""
    lw = page.extract_words(x_tolerance=1.5, y_tolerance=1)     # tight: stacked label lines must not interleave
    for t in page.find_tables():
        cells = [c for r in t.rows for c in r.cells if c]
        tw = t.bbox[2] - t.bbox[0]
        texts = {c: " ".join(w["text"] for w in lw if _inside(w, c)) for c in cells}
        name = [c for c in cells if re.search(name_re, texts[c], re.I) and (c[2] - c[0]) < 0.5 * tw]
        if not name:
            continue
        nc = min(name, key=lambda c: c[1])
        top, bottom = nc[1], nc[3]
        for r in sorted((r for r in t.rows if r.bbox[3] <= nc[1] + 1), key=lambda r: -r.bbox[1]):
            rw = [w for w in words if _inside(w, r.bbox)]           # header rows above the name cell, up to the
            if not rw or any(_num(w["text"]) is not None for w in rw):  # first row that holds figures
                break
            top = r.bbox[1]
        head = [c for c in cells if c[1] >= top - 1 and c[3] <= bottom + 1 and (c[2] - c[0]) < 0.6 * tw]
        edges = sorted({round(x, 1) for c in head for x in (c[0], c[2])})
        merged = []
        for x in edges:
            if not merged or x - merged[-1] > 2.5:
                merged.append(x)
        ltext = lambda box: " ".join(w["text"] for w in lw if _inside(w, box))
        cols = []
        for x0, x1 in zip(merged, merged[1:]):
            lab = [ltext(c) for c in sorted(head, key=lambda c: c[1]) if c[0] <= x0 + 2.5 and c[2] >= x1 - 2.5]
            lab = " ".join(s for s in lab if s and not re.fullmatch(r"[\d.=()+ ]+", s))
            cols.append((x0, x1, lab))
        extra = [w for w in lw if w["x0"] > merged[-1] + 1 and top - 1 <= w["top"] <= bottom + 1]
        if extra:                     # a last column left outside the ruled table (Jun-Dec 2019 closing stock)
            cols.append((merged[-1], max(w["x1"] for w in words) + 2, " ".join(w["text"] for w in extra)))
        return cols, (top, bottom)
    return None, None


def page_rows(page, cols, zone):
    """Rows of the page outside the header zone (top, bottom): list of (top, {column index: text}). Uses the table's
    ruled row bands where they hold a single record (joining wrapped cell text) and falls back to one row per text
    line inside unruled blocks."""
    zt, zb = zone or (-1, -1)
    words = [w for w in page.extract_words(x_tolerance=1.5, y_tolerance=2.5, keep_blank_chars=False)
             if not zt - 0.5 <= (w["top"] + w["bottom"]) / 2 <= zb + 0.5]
    x_lo, x_hi = cols[0][0] - 3, cols[-1][1] + 3

    def colof(w):
        xc = (w["x0"] + w["x1"]) / 2
        for i, (x0, x1, _) in enumerate(cols):
            if x0 - 0.5 <= xc <= x1 + 0.5:
                return i
        return None

    numcols = {i for i, c in enumerate(cols) if c[2] and not re.search(r"NAME|UTILIT|BOARD|S\.?NO|SL\.|REGION", _c(c[2]))}

    def rowdict(ws):
        d = {}
        for w in ws:
            i = colof(w)
            if i is not None:
                d.setdefault(i, []).append(w["text"])
        return {i: " ".join(v) for i, v in d.items()}

    def numeric(ws):
        return sum(1 for w in ws if colof(w) in numcols and _num(w["text"]) is not None)

    bands = []
    for t in page.find_tables():
        for r in t.rows:
            b = r.bbox
            if not (b[1] >= zt - 1 and b[3] <= zb + 1):
                bands.append((b[1], b[3]))
    bands.sort()
    used, out = set(), []
    for y0, y1 in bands:
        ws = [w for w in words if id(w) not in used and y0 - 0.5 <= (w["top"] + w["bottom"]) / 2 <= y1 + 0.5
              and x_lo <= (w["x0"] + w["x1"]) / 2 <= x_hi]
        if not ws:
            continue
        used.update(id(w) for w in ws)
        lines = _lines(ws)
        if sum(1 for l in lines if numeric(l)) <= 1:
            out.append((y0, rowdict(sorted(ws, key=lambda w: (w["top"], w["x0"])))))
        else:
            out += [(l[0]["top"], rowdict(l)) for l in lines]
    rest = [w for w in words if id(w) not in used and x_lo <= (w["x0"] + w["x1"]) / 2 <= x_hi]
    out += [(l[0]["top"], rowdict(l)) for l in _lines(rest)]
    return sorted(out, key=lambda r: r[0])


def merge_wrapped(rows, namecols, valcols, gap=7.5):
    """A record whose name wraps over two lines in an unruled block shows up as a figures-only line with text-only
    lines just above / below it: join those into its name."""
    hasnum = lambda d: any(_num(d.get(i)) is not None for i in valcols)
    textonly = lambda d: d and not hasnum(d) and any(i in namecols for i in d)
    out, skip = [], set()
    for k, (top, d) in enumerate(rows):
        if k in skip:
            continue
        if hasnum(d) and not any(d.get(i, "").strip() for i in namecols if re.search(r"[A-Za-z]", d.get(i, ""))):
            d = dict(d)
            parts = []
            if out and textonly(out[-1][1]) and top - out[-1][0] <= gap:
                parts.append(out.pop()[1])
            parts.append(d)
            if k + 1 < len(rows) and textonly(rows[k + 1][1]) and rows[k + 1][0] - top <= gap:
                parts.append(rows[k + 1][1])
                skip.add(k + 1)
            for i in namecols:
                txt = " ".join(p[i] for p in parts if p.get(i))
                if txt:
                    d[i] = txt
        out.append((top, d))
    return out


def _title_month(text):
    """report month from the title: 'FOR APR to APR-2014', 'FOR JULY-2019', '(APRIL-2017)', 'JUNE-2019'."""
    for pat in (r"FOR\s+(?:[A-Z]{3,9}\s+to\s+)?" + MON_RE + r"[\s\-,']*(\d{4})",
                r"^\(?\s*" + MON_RE + r"[\s\-,']*(\d{4})\s*\)?\s*$"):
        mt = re.search(pat, text, re.I | re.M)
        if mt:
            return f"{mt.group(2)}-{MONTHS.index(mt.group(1).title()) + 1:02d}"
    mt = re.search(r"\b" + MON_RE + r"-(\d{2})\b", text, re.I)          # 'Nov-22' (Nov 2022 report)
    if mt:
        return f"20{mt.group(2)}-{MONTHS.index(mt.group(1).title()) + 1:02d}"
    return None


# ---------------------------------------------------------------- monthly coal statement

def coal_field(lab):
    L = _c(lab)
    if not L or ("%" not in L and len(re.sub(r"[^A-Z]", "", L)) < 3):
        return None
    if re.search(r"NAMEOF|NAME", L):
        return "name"
    if re.search(r"^S\.?NO|^SL\.|^REGION|^SL\.NO", L):
        return "idx"
    for pat, f in ((r"EQUIV", "skip"), (r"DAYS", "skip"), (r"%|LINK", "rcpt_pct_alloc"), (r"CAPACITY", "capacity_mw"),
                   (r"REQUIREMENT", "skip"), (r"ALLOCATION|ALLOTED|FROMCIL", "alloc_cil_sccl_kt"),
                   (r"OPENING", "opening_stock_kt"), (r"CONSUM", "consumption_kt"), (r"CLOSING|STOCK", "closing_stock_kt"),
                   (r"AUCTION", "rcpt_eauction_kt"), (r"CAPTIVE", "rcpt_captive_kt"), (r"IMPORT", "rcpt_import_kt"),
                   (r"OTHER", "rcpt_other_kt"), (r"CIL/SCCL", "rcpt_cil_sccl_kt"), (r"SCCL", "rcpt_sccl_kt"),
                   (r"CIL", "rcpt_cil_kt"), (r"TOTAL", "rcpt_total_kt")):
        if re.search(pat, L):
            return f
    return "?" + L


def _region(name):
    s = re.sub(r"[^A-Z-]", "", name.upper())
    s = re.sub(r"(SUB)?TOTAL(OF)?", "", s).replace("REGION", "").strip("-")
    for key, reg in REGIONS:
        if s.startswith(key):
            return reg
    mt = re.search(r"\b(NER|NR|WR|SR|ER)\b", name.upper())
    return mt and {"NR": "Northern", "WR": "Western", "SR": "Southern", "ER": "Eastern", "NER": "North Eastern"}[mt.group(1)]


def parse_coal(path):
    """-> (month, plants [dict], region totals {region: dict}, all-India dict, layout [field names])."""
    pdf = pdfplumber.open(str(path))
    first = pdf.pages[0].extract_text() or ""
    if not first.strip():
        raise ValueError("scanned PDF (no text layer)")
    month = _title_month(first)
    cols = fields = None
    plants, regtot, india, pending = [], {}, None, []
    for page in pdf.pages:
        words = page.extract_words(x_tolerance=1.5, y_tolerance=2.5)
        c, bottom = _header(page, words, r"^Name\s*of")
        if c:
            f = [coal_field(x[2]) for x in c]
            if "name" not in f:
                continue
            if fields and len(f) == len(fields) and any(x and x.startswith("?") for x in f):
                f = fields            # a repeat header whose upper label row was not captured: same columns
            if fields and [x for x in f if x] != [x for x in fields if x]:
                raise ValueError(f"header changes between pages: {fields} / {f}")
            cols, fields = c, f
        elif cols is None:
            continue
        else:
            bottom = None
        bad = [x for x in fields if x and x.startswith("?")]
        if bad:
            raise ValueError(f"unknown column labels {bad}")
        data = [x for x in fields if x not in (None, "skip", "name", "idx")]
        if len(set(data)) != len(data) or not {"rcpt_total_kt", "consumption_kt", "closing_stock_kt"} <= set(data):
            raise ValueError(f"bad field list {fields}")
        rows = merge_wrapped(page_rows(page, cols, bottom), [i for i, f in enumerate(fields) if f in ("name", "idx")],
                             [i for i, f in enumerate(fields) if f and f not in ("skip", "name", "idx", "rcpt_pct_alloc")])
        for k, (_, d) in enumerate(rows):
            name = " ".join(d[i] for i in sorted(d) if fields[i] in ("name", "idx"))
            name = re.sub(r"\s+", " ", re.sub(r"^\s*\d+[.)]?\s+", "", name)).strip()
            vals = {fields[i]: _num(v) for i, v in d.items() if fields[i] not in (None, "skip", "name", "idx")}
            vals = {k: v for k, v in vals.items() if v is not None}
            if not vals or not re.search(r"[A-Za-z]{2}", name) or re.search(JUNK, name, re.I):
                continue
            up = name.upper()
            if re.match(r"TOTAL\s*-?\s*(OF\s*)?ALL\s*-?\s*INDIA", up):
                india = vals
                break
            if re.search(r"\bTOTAL\b", up):
                reg = _region(up)
                if reg is None:       # "Total of" with the region name wrapped onto the next text line
                    nxt = next((" ".join(d2.values()) for _, d2 in rows[k + 1:k + 3]
                                if not any(_num(v) is not None for v in d2.values())), "")
                    if re.search(r"ALL\s*-?\s*INDIA|^\s*INDIA", (up + " " + nxt.upper()).split("TOTAL", 1)[1]):
                        india = vals
                        break
                    reg = _region("TOTAL " + nxt)
                if reg is None:
                    raise ValueError(f"unrecognised total row {name!r}")
                regtot[reg] = vals
                for p in pending:
                    p["region"] = reg
                pending = []
                continue
            if len(vals) < 3:
                continue
            p = dict(plant=RENAMED.get(name, name), region=None, **vals)
            plants.append(p)
            pending.append(p)
        if india:
            break
    if india is None:
        raise ValueError("no 'Total All India' row")
    return month, plants, regtot, india, [x for x in fields if x not in (None, "skip", "name", "idx")]


def check_coal(plants, regtot, india):
    """plant sums vs CEA's region and All-India totals -> list of mismatch strings."""
    bad = []
    keys = [k for k in ("rcpt_total_kt", "rcpt_import_kt", "consumption_kt", "closing_stock_kt") if k in india]
    for reg, t in regtot.items():
        for k in keys:
            s = sum(p.get(k) or 0 for p in plants if p["region"] == reg)
            if t.get(k) is not None and abs(s - t[k]) > max(2, 0.002 * abs(t[k])):
                bad.append(f"{reg} plants {k[:-3]} {s:.0f} vs total row {t[k]:.0f}")
    for k in keys:
        s = sum(p.get(k) or 0 for p in plants)
        if abs(s - india[k]) > max(2, 0.002 * abs(india[k])):
            bad.append(f"all plants {k[:-3]} {s:.0f} vs All-India {india[k]:.0f}")
    parts = [k for k in ("rcpt_cil_kt", "rcpt_sccl_kt", "rcpt_cil_sccl_kt", "rcpt_captive_kt", "rcpt_eauction_kt",
                         "rcpt_import_kt", "rcpt_other_kt") if k in india]
    if abs(sum(india[k] for k in parts) - india["rcpt_total_kt"]) > 2:
        bad.append(f"All-India receipt sources sum {sum(india[k] for k in parts):.0f} vs total {india['rcpt_total_kt']:.0f}")
    if None in {p["region"] for p in plants}:
        bad.append(f"{sum(p['region'] is None for p in plants)} plants without region total")
    return bad


# ---------------------------------------------------------------- monthly import report

def import_field(lab, month):
    L = _c(lab)
    if not L:
        return None
    if re.search(r"UTILIT|BOARD|NAME", L):
        return "name"
    if re.search(r"^S\.?NO|^SL", L):
        return "idx"
    if "CAPACITY" in L:
        return "capacity_mw"
    if re.search(r"GROWTH|%|ANNUAL|PRORATA|TARGET|PROGRAM", L):
        return "skip"
    if "SAME" in L:
        return "ly_month" if "MONTH" in L else "ly_ytd"
    if re.search(r"CUMULATIVE|TOTAL", L):
        return "ytd"
    mons = [MONTHS.index(m.title()) + 1 for m in re.findall(MON_RE, L)]
    if not mons and "RECEIPT" in L:
        return "month"
    if not mons:
        return "?" + L
    if len(set(mons)) >= 2 or re.search(MON_RE + r"[-'\d,]*TO", L):
        return "ytd" if month and mons[-1] == int(month[5:]) else "prev_cum"
    return "month"


def parse_import(path):
    """-> (month, entity rows [dict], totals {'Blending'|'Design'|'Total': kt}, unit note)."""
    pdf = pdfplumber.open(str(path))
    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if not text.strip():
        raise ValueError("scanned PDF (no text layer)")
    month = _title_month("\n".join(text.split("\n")[:8]))
    scale = 1.0 if re.search(r"Thousand\s+Tonnes|'000", text, re.I) else 1000.0      # else million tonnes
    cols = fields = None
    rows, tot, cat, sector = [], {}, None, None
    for page in pdf.pages:
        words = page.extract_words(x_tolerance=1.5, y_tolerance=2.5)
        c, bottom = _header(page, words, r"Utilit|Board")
        if c:
            if month is None:          # FY summary: month from the 'during <Month> <yyyy>' column
                for x in c:
                    mt = re.search(r"during\s+" + MON_RE + r"[\s\-,']*(\d{2,4})\s*$", x[2], re.I)
                    if mt:
                        y = int(mt.group(2)) % 100 + 2000
                        month = f"{y}-{MONTHS.index(mt.group(1).title()) + 1:02d}"
            cols, fields = c, [import_field(x[2], month) for x in c]
        elif cols is None:
            continue
        else:
            bottom = None
        bad = [x for x in fields if x and x.startswith("?")]
        if bad:
            raise ValueError(f"unknown column labels {bad}")
        if "month" not in fields and not {"ytd", "prev_cum"} <= set(fields):
            raise ValueError(f"no month receipt column in {fields}")
        prow = merge_wrapped(page_rows(page, cols, bottom), [i for i, f in enumerate(fields) if f in ("name", "idx")],
                             [i for i, f in enumerate(fields) if f in ("month", "ytd", "prev_cum")])
        for _, d in prow:
            name = " ".join(d[i] for i in sorted(d) if fields[i] in ("name", "idx"))
            name = re.sub(r"\s+", " ", name).strip()
            up = name.upper()
            vals = {fields[i]: _num(v) for i, v in d.items() if fields[i] not in (None, "skip", "name", "idx")}
            vals = {k: v for k, v in vals.items() if v is not None}
            full = re.sub(r"\s+", " ", " ".join(d[i] for i in sorted(d))).upper()
            if not up.startswith(("TOTAL", "SUB", "GRAND")) and not full.startswith(("TOTAL", "SUB", "GRAND")):
                if re.search(r"POWER PLANTS?\b.*(BLENDING|INDIGEN)", full):
                    cat = "Blending"
                    continue
                if re.search(r"POWER PLANTS?\b.*DESIGNED ON IMPORTED", full):
                    cat = "Design"
                    continue
                if not vals and re.search(r"\bSECTOR\b|\(IPPS?\)", full):
                    sector = "Ipp" if re.search(r"PRIVATE|IPP", full) else full.split("SECTOR")[0].strip(" -").title()
                    continue
            rec = vals.get("month")
            if rec is None and "ytd" in vals and "prev_cum" in vals:
                rec = vals["ytd"] - vals["prev_cum"]
            if rec is None and "ytd" in vals and month and month[5:] == "04":
                rec = vals["ytd"]
            if not vals or rec is None:
                continue
            rec *= scale
            if up.startswith(("GRAND TOTAL", "TOTAL IMPORT (I", "TOTAL (I")) or up in ("TOTAL", "TOTAL IMPORT"):
                tot["Total"] = rec
            elif up.startswith(("TOTAL", "SUB TOTAL")):
                if "BLENDING" in up or ("SUB TOTAL" in up and cat == "Blending"):
                    tot["Blending"] = rec
                elif re.search(r"IMPORTED COAL|\(II", up) or ("SUB TOTAL" in up and cat == "Design"):
                    tot["Design"] = rec
            elif cat and re.search(r"[A-Za-z]{2}", name):
                ent = re.sub(r"^\d+[.)]?\s+|\s+\d+$", "", name).strip(" *#")
                ytd = vals.get("ytd")
                rows.append(dict(category=cat, entity=ent, sector=sector, capacity_mw=vals.get("capacity_mw"),
                                 receipt_kt=round(rec, 3), receipt_ytd_kt=None if ytd is None else round(ytd * scale, 3)))
    if "Design" not in tot and {"Total", "Blending"} <= tot.keys():
        tot["Design"] = tot["Total"] - tot["Blending"]
    return month, rows, tot, "Mt" if scale > 1 else "kt"


def check_import(rows, tot):
    bad = []
    for k in ("Blending", "Design"):
        s = sum(r["receipt_kt"] or 0 for r in rows if r["category"] == k)
        if k in tot and abs(s - tot[k]) > max(1.5, 0.005 * tot[k]):
            bad.append(f"{k} entity sum {s:.1f} vs total {tot[k]:.1f} kt")
    if {"Blending", "Design", "Total"} <= tot.keys() and abs(tot["Blending"] + tot["Design"] - tot["Total"]) > 1.5:
        bad.append(f"blending {tot['Blending']:.1f} + design {tot['Design']:.1f} != total {tot['Total']:.1f}")
    return bad


# ---------------------------------------------------------------- storing

def _existing(con):
    ser = {(s, p): (v, src) for s, p, v, src in con.execute(
        "SELECT series, period, value, source FROM coal_supply WHERE series LIKE 'cea_%_m:%' OR series LIKE 'import_power_m:%'")}
    # months written by scrapers.cea_monthly from the NPP XLS (its own report, not a "same month last year" column)
    npp = lambda series: {p for (s, p), (_, src) in ser.items() if s == series and "(NPP)" in src and "last year" not in src}
    return ser, npp("cea_rcpt_m:Total"), npp("import_power_m:Total")


def _write(ser, rows, compared):
    """rows whose stored value may be replaced (none, a 'same month last year' derivation, or ours); the others and
    replaced derivations are noted in compared as (period, series, new, stored, stored source)."""
    out = []
    for r in rows:
        v, src = ser.get((r[0], r[1]), (None, None))
        if src is None or "cea.nic.in PDF" in src:
            out.append(r)
        elif "last year" in src:
            out.append(r)
            compared.append((r[1], r[0], r[2], v, src))
        else:
            compared.append((r[1], r[0], r[2], v, src))
    return out


def coal_series(month, india, fields, src):
    mt = lambda v: round(v / 1000, 4)
    out = [("cea_rcpt_m:Total", india["rcpt_total_kt"]), ("cea_cons_m:Total", india["consumption_kt"]),
           ("cea_stock_m:Total", india["closing_stock_kt"])]
    if "rcpt_import_kt" in india:
        out += [("cea_rcpt_m:Import", india["rcpt_import_kt"]),
                ("cea_rcpt_m:Domestic", india["rcpt_total_kt"] - india["rcpt_import_kt"])]
    if "rcpt_captive_kt" in fields:                        # from Mar 2017 "others" really is others
        out += [(f"cea_rcpt_m:{e}", india[k]) for k, e in (("rcpt_cil_kt", "CIL"), ("rcpt_sccl_kt", "SCCL"),
                ("rcpt_captive_kt", "Captive"), ("rcpt_eauction_kt", "E-Auction"), ("rcpt_other_kt", "Others")) if k in india]
    return [(s, month, mt(v), "Mt", src) for s, v in out]


def run(months=None, relist=False, verbose=True):
    con = connect()
    con.executescript(SCHEMA)
    if "rcpt_cil_sccl_kt" not in [r[1] for r in con.execute("PRAGMA table_info(coal_plants_monthly)")]:
        con.execute("ALTER TABLE coal_plants_monthly ADD COLUMN rcpt_cil_sccl_kt REAL")   # CIL+SCCL before Mar 2019
        con.commit()
    look = _lookup(con)
    allm, m = [], FIRST
    while m <= LAST:
        allm.append(m)
        m = _shift(m, 1)
    lst = listing(allm, refresh=relist)
    ser, npp_coal, npp_imp = _existing(con)
    coal_done, imp_done, failed, warned, compared, notes = {}, {}, [], [], [], []
    for lm in sorted(lst):
        for url in lst[lm]:
            try:
                path = fetch(lm, url)
                head = (pdfplumber.open(str(path)).pages[0].extract_text() or "").upper()
                kind = "import" if "IMPORT OF COAL" in head else "coal" if head.strip() else (
                    "import" if "import" in path.name.lower() else "coal")
                if kind == "coal":
                    month, plants, regtot, india, fields = parse_coal(path)
                    if month is None:
                        raise ValueError("report month not found in title")
                    nxt = _shift(month, 1) if month else None
                    if (month in coal_done and nxt == lm and nxt not in coal_done and india.get("opening_stock_kt")
                            and abs(india["opening_stock_kt"] - coal_done[month]["india"]["closing_stock_kt"])
                            < 0.03 * india["opening_stock_kt"]):
                        # the "Apr 2020" file is titled MARCH-2020 but opens with March's closing stock: April
                        notes.append(f"{path.name}: titled {month}, opening stock = {month} closing -> stored as {nxt}")
                        month = nxt
                    if months and month not in months:
                        continue
                    if month in coal_done:
                        prev = coal_done[month]
                        same = abs(prev["india"]["rcpt_total_kt"] - india["rcpt_total_kt"]) < 1
                        if verbose:
                            print(f"{month} coal: duplicate file {path.name} ({'identical totals' if same else 'DIFFERENT totals'}); kept {prev['file']}")
                        continue
                    bad = check_coal(plants, regtot, india)
                    coal_done[month] = dict(file=path.name, india=india, n=len(plants), fields=fields, bad=bad,
                                            plants=plants)
                    if bad:
                        warned.append(f"{month} coal: " + "; ".join(bad))
                    if verbose:
                        print(f"{month} coal  {len(plants):3d} plants  rcpt {india['rcpt_total_kt']:8.0f}  cons "
                              f"{india['consumption_kt']:8.0f}  stock {india['closing_stock_kt']:7.0f} kt  "
                              f"[{lm} {path.name}]" + (f"  !! {'; '.join(bad)}" if bad else ""), flush=True)
                else:
                    month, rows, tot, unit = parse_import(path)
                    if months and month not in months:
                        continue
                    if month is None or not tot.get("Total"):
                        raise ValueError(f"import report month {month}, totals {tot}")
                    if month in imp_done:
                        if verbose:
                            print(f"{month} import: duplicate file {path.name}; kept {imp_done[month]['file']}")
                        continue
                    bad = check_import(rows, tot)
                    imp_done[month] = dict(file=path.name, tot=tot, n=len(rows), bad=bad)
                    store_import(con, month, rows, tot, npp_imp, ser, compared)
                    if bad:
                        warned.append(f"{month} import: " + "; ".join(bad))
                    if verbose:
                        print(f"{month} import {len(rows):3d} entities  " + "  ".join(f"{k} {v:7.1f}" for k, v in tot.items())
                              + f" kt ({unit}) [{lm} {path.name}]" + (f"  !! {'; '.join(bad)}" if bad else ""), flush=True)
            except Exception as e:
                failed.append(f"{lm} {url.rsplit('/', 1)[1]}: {type(e).__name__}: {e}")
                if verbose:
                    print(f"{lm} FAILED {url.rsplit('/', 1)[1]}: {type(e).__name__}: {e}", flush=True)
    notes += canonical_names(con, coal_done, npp_coal)
    for month in sorted(coal_done):
        d = coal_done[month]
        store_coal(con, month, d["plants"], d["india"], d["fields"], npp_coal, ser, look, compared)
    notes += sanity(con, [m for m in coal_done if m not in npp_coal])
    con.close()
    want = [m for m in allm if m < "2024-03" and (not months or m in months)]
    missing = [m for m in want if m not in coal_done]
    log("cea_monthly_hist", "ok" if not failed else "partial",
        f"coal {len(coal_done)} months, import {len(imp_done)} months, {len(warned)} with total mismatches; "
        f"missing coal: {','.join(missing)}" + (f"; failed: {' | '.join(failed)}" if failed else ""))
    return coal_done, imp_done, failed, warned, compared, missing, notes


def _key(name):
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def canonical_names(con, coal_done, npp_coal):
    """Plant names in ruled cells get clipped ('CHANDRAPUR(MAHARAS'), pick up the wrapped tail of the row above
    ('SHTRA) DAHANU TPS') or, in Sep 2018, come out as overlapped characters ('ADSAHHTARNAU) TSTPSPS'). Anchor names
    are the NPP-report names plus names seen in >= 6 months with balanced brackets. Any other name is mapped to the
    same-region anchor it is a clipped start of, if unique, else to the anchor of the same region (and a matching capacity where the report has one) with the most similar letters
    (ratio >= 0.5 with capacity, >= 0.75 without), provided that anchor is not already listed that month. Rewrites
    the plant names in coal_done in place; returns notes."""
    from difflib import SequenceMatcher
    seen = {}                                            # name -> {"months": set, "region": .., "caps": set}
    add = lambda name, month, region, cap: (seen.setdefault(name, {"months": set(), "region": region, "caps": set()}),
                                            seen[name]["months"].add(month), cap and seen[name]["caps"].add(round(cap)))
    for month, d in coal_done.items():
        for p in d["plants"]:
            add(p["plant"], month, p["region"], p.get("capacity_mw"))
    npp_names = set()
    for month, plant, region, cap in con.execute("SELECT month, plant, region, capacity_mw FROM coal_plants_monthly"):
        if month in npp_coal:
            add(plant, month, region, cap)
            npp_names.add(plant)
    balanced = lambda n: n.count("(") == n.count(")") and not re.match(r"^[^(]*\)", n)
    anchors = {n for n, v in seen.items() if n in npp_names or (len(v["months"]) >= 6 and balanced(n))}
    bykey = {}
    for n in anchors:                                     # spacing / case variants of one anchor: keep the NPP or
        k = _key(n)                                       # most frequent spelling
        if k not in bykey or n in npp_names or len(seen[n]["months"]) > len(seen[bykey[k]]["months"]):
            if bykey.get(k) not in npp_names:
                bykey[k] = n
    notes, mapped = [], {}
    for month, d in sorted(coal_done.items()):
        present = {p["plant"] for p in d["plants"]}
        for p in d["plants"]:
            n = p["plant"]
            if n in anchors and bykey[_key(n)] == n:
                continue
            target = bykey.get(_key(n))
            if target is None and len(_key(n)) >= 8:           # clipped name: unique anchor that it begins
                pre = [a for a in bykey.values() if _key(a).startswith(_key(n)) and a not in present
                       and seen[a]["region"] == p["region"]]
                target = pre[0] if len(pre) == 1 else None
            if target is None:
                cap = p.get("capacity_mw")
                best = []
                for a in bykey.values():
                    if seen[a]["region"] != p["region"] or a in present:
                        continue
                    if cap and seen[a]["caps"] and round(cap) not in seen[a]["caps"]:
                        continue
                    best.append((SequenceMatcher(None, _key(n), _key(a)).ratio(), a))
                best.sort(reverse=True)
                need = 0.5 if cap else 0.75
                if best and best[0][0] >= need and (len(best) == 1 or best[1][0] < best[0][0] - 0.05):
                    target = best[0][1]
            if target and target != n and target not in present:
                mapped.setdefault((n, target), []).append(month)
                present.discard(n)
                present.add(target)
                p["plant"] = target
            elif not balanced(n) or target is None and len(seen[n]["months"]) < 3:
                notes.append(f"{month} plant name {n!r} left as printed (no unique match)")
    for (n, t), ms in sorted(mapped.items()):
        if _key(n) != _key(t):
            notes.append(f"plant name {n!r} -> {t!r} ({len(ms)} months, {min(ms)}..{max(ms)})")
    return notes


# national series that include each plant figure
SERIES_OF = {"rcpt_total_kt": ["cea_rcpt_m:Total", "cea_rcpt_m:Domestic"], "rcpt_import_kt": ["cea_rcpt_m:Import",
             "cea_rcpt_m:Domestic"], "consumption_kt": ["cea_cons_m:Total"], "closing_stock_kt": ["cea_stock_m:Total"],
             "rcpt_cil_kt": ["cea_rcpt_m:CIL"], "rcpt_sccl_kt": ["cea_rcpt_m:SCCL"], "rcpt_captive_kt": ["cea_rcpt_m:Captive"],
             "rcpt_eauction_kt": ["cea_rcpt_m:E-Auction"], "rcpt_other_kt": ["cea_rcpt_m:Others"]}


def sanity(con, months):
    """Typing errors in the PDFs (e.g. Haldia TPP Jun 2015: receipt 127,258 kt; Mejia Jun 2014: stock 67,870 kt) run
    straight into CEA's region and All-India totals. A plant figure above 10x (and 3,000 kt over) the plant's median
    for that column over all stored months is set NULL, and the All-India series built on that column are dropped
    for the month rather than stored wrong. Returns notes."""
    if not months:
        return []
    cols = [c for c in SUMMABLE if c != "opening_stock_kt"] + ["opening_stock_kt"]
    rows = con.execute(f"SELECT month, plant, {', '.join(cols)} FROM coal_plants_monthly").fetchall()
    hist = {}
    for r in rows:
        for c, v in zip(cols, r[2:]):
            if v:
                hist.setdefault((r[1], c), []).append(v)
    med = {k: sorted(v)[len(v) // 2] for k, v in hist.items()}
    notes, drop = [], set()
    for r in rows:
        if r[0] not in months:
            continue
        for c, v in zip(cols, r[2:]):
            m = med.get((r[1], c))
            if v and m is not None and v > 10 * m and v - m > 3000:
                notes.append(f"{r[0]} {r[1]}: {c} {v:.0f} kt vs its median {m:.0f}: set NULL")
                con.execute(f"UPDATE coal_plants_monthly SET {c}=NULL WHERE month=? AND plant=?", (r[0], r[1]))
                if c == "rcpt_cil_sccl_kt":
                    c = "rcpt_total_kt"
                drop.update((r[0], sr) for sr in SERIES_OF.get(c, []))
    for mo, sr in sorted(drop):
        con.execute("DELETE FROM coal_supply WHERE series=? AND period=? AND source LIKE '%cea.nic.in PDF%'", (sr, mo))
        notes.append(f"{mo} {sr}: All-India figure includes the error above, not stored")
    con.commit()
    return notes


def store_coal(con, month, plants, india, fields, npp_coal, ser, look, compared):
    src = f"CEA monthly coal statement (cea.nic.in PDF), {MONTHS[int(month[5:]) - 1]} {month[:4]}"
    rows = coal_series(month, india, fields, src)
    if month in npp_coal:                                  # NPP XLS is authoritative: compare only
        _write(ser, rows, compared)
        return
    seen = {}
    for p in plants:
        k = p["plant"]
        if k in seen:
            for c in SUMMABLE:
                if p.get(c) is not None:
                    seen[k][c] = (seen[k].get(c) or 0) + p[c]
        else:
            seen[k] = dict(p)
    with con:
        con.execute("DELETE FROM coal_plants_monthly WHERE month=?", (month,))
        con.executemany(
            f"INSERT INTO coal_plants_monthly (month, plant, region, state, utility, {', '.join(HCOLS)}) "
            f"VALUES ({', '.join('?' * (5 + len(HCOLS)))})",
            [(month, p["plant"], p["region"], *look.get(p["plant"].upper(), (None, None)), *[p.get(c) for c in HCOLS])
             for p in seen.values()])
    put(_write(ser, rows, compared))


def store_import(con, month, rows, tot, npp_imp, ser, compared):
    src = f"CEA monthly import coal report (cea.nic.in PDF), {MONTHS[int(month[5:]) - 1]} {month[:4]}"
    out = [(f"import_power_m:{k}", month, round(v / 1000, 4), "Mt", src) for k, v in tot.items()]
    if month in npp_imp:
        _write(ser, out, compared)
        return
    agg = {}
    for r in rows:
        k = (r["category"], r["entity"])
        if k in agg:
            for c in ("capacity_mw", "receipt_kt", "receipt_ytd_kt"):
                if r[c] is not None:
                    agg[k][c] = (agg[k][c] or 0) + r[c]
        else:
            agg[k] = dict(r)
    with con:
        con.execute("DELETE FROM coal_import_power_monthly WHERE month=?", (month,))
        con.executemany("INSERT INTO coal_import_power_monthly VALUES (?,?,?,?,?,?,?)",
                        [(month, r["category"], r["entity"], r["sector"], r["capacity_mw"], r["receipt_kt"],
                          r["receipt_ytd_kt"]) for r in agg.values()])
    put(_write(ser, out, compared))


if __name__ == "__main__":
    months = None
    if "--month" in sys.argv:
        months = [sys.argv[sys.argv.index("--month") + 1]]
    coal, imp, failed, warned, compared, missing, notes = run(months, relist="--relist" in sys.argv)
    print(f"\n{len(coal)} coal months stored/compared, {len(imp)} import months; {len(failed)} failed; "
          f"{len(warned)} with total mismatches; coal months missing: {', '.join(missing) or 'none'}")
    for line in failed + warned + notes:
        print("  " + line)
    if compared:
        print("\nOverlap with existing rows (Mt): month series  this PDF  stored  [stored source]")
        for p, s, v, o, src in sorted(compared):
            flag = "" if o is None or abs(v - o) <= 0.002 * max(abs(o), 1) else "  <-- differs"
            kind = "replaced (last-year value)" if "last year" in src else "kept (NPP)"
            print(f"  {p} {s:22s} {v:9.4f} {o:9.4f}  {kind}{flag}")
