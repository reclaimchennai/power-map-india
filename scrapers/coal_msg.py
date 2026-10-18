"""Ministry of Coal "Monthly Coal Statistics at a Glance" -> coal_supply monthly series.

The Ministry posts one PDF a month (msg-<month><yy>.pdf; names are inconsistent) on
https://www.coal.nic.in/public-information/monthly-statistics-at-glance (also coal.gov.in; ?page=0,1; Apr 2021 on).
Aug 2022 and Dec 2022 are on the server but not linked from the listing (UNLISTED). Each report has company-wise coal
production and dispatch (month, monthly target, same month last year, FY cumulative), dispatch to sectors (all-India
and separately for CIL, SCCL and captive/other mines), lignite production and dispatch by company, rakes loaded per
day by CIL subsidiary (all sectors and power sector, plus a 13-month history), CIL's rail/road/MGR offtake (from
Jun 2023), top-35 mines, power generation and CIL's tax payments (the last three are not read).

Parsing works on pdfplumber words, not its table extraction (the ruled tables merge header and data cells in the
2024-26 layouts). A line is a table row when it starts with a known row label (ECL ... Grand Total, Power ... Others,
NLCIL ...) followed by numbers; chart labels between tables (reversed digits, pie labels) never qualify. In the
'FY 27 Achmt.(%) FY 26 Growth (%) ...' tables every number goes to the nearest header column by x position, so blank
cells don't shift values; the first FY column is the report month, the second the comparison month (checked against
the report's FY). Which table is which comes from the nearest title line above it ("Coking Coal Production" is
skipped, "Despatch of Coal By CIL", ...). Rakes and CIL mode-wise tables have no blanks and are read by position in
the row. The report month is taken from the PDF's title ("Monthly Coal Statistics for Aug'2026"), not the file name.

Series written (period 'YYYY-MM' = report month; Mt unless noted):
  prod_m:<CO>, dispatch_m:<CO>, prod_target_m:<CO>, dispatch_target_m:<CO>
        CO = CIL, SCCL, Captive (captive + other mines), Total, and CIL subsidiaries BCCL CCL ECL MCL NCL SECL WCL NEC
        (the Total target covers CIL + SCCL only: captive mines have no monthly target in the reports)
  dispatch_power_m:<CO>      dispatch to the power sector: CIL, SCCL, Captive, Total
  dispatch_sector_m:<S>      all-India dispatch by sector: Power CPP Steel Cement Sponge Others Total (NRS when given)
  rakes_m:<CO>, rakes_power_m:<CO>   rakes loaded per day (monthly average), CIL subsidiaries and Total  [rakes/day]
  cil_mode_m:<M>             CIL offtake by mode: Rail Road MGR Others Total (RCR = rail-cum-road, some 2025 reports)
  lignite_prod_m:<CO>, lignite_dispatch_m:<CO>   NLCIL GMDCL GIPCL RSMML BLMCL GHCL VSLignite GSPL Total
Each table's same-month-last-year column (and the rakes history table) is stored into that earlier month only when
no report of its own covers it, with the source marked "(prior-year column)" / "(rakes history table)" (the Aug 2021
report compares with Aug 2019: "(2-years-earlier column)"); so the series start in Apr 2020. Figures are provisional
and later reports sometimes revise them; each month keeps the figure from its own report.

    python -m scrapers.coal_msg              # backfill: fetch listing, download new PDFs, parse every cached PDF, store
    python -m scrapers.coal_msg --new        # only the newly downloaded reports (what run() does by default)
    python -m scrapers.coal_msg --file x.pdf # parse one PDF and print its rows (no store)
    COAL_MSG_DEBUG=1 ...                     # print how each table was identified
"""
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests
import urllib3

from scrapers.coal_supply import SCHEMA, put
from store import connect, log

urllib3.disable_warnings()
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "raw" / "coal" / "msg"
HOSTS = ("https://www.coal.nic.in", "https://coal.gov.in")
LISTING = "/public-information/monthly-statistics-at-glance"
# reports that exist on the server but are not linked from the listing
UNLISTED = ["/sites/default/files/2022-09/msg-aug2022.pdf", "/sites/default/files/2023-01/msg-dec2022.pdf"]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
SRC = "Ministry of Coal, Monthly Coal Statistics at a Glance"
DEBUG = bool(__import__("os").environ.get("COAL_MSG_DEBUG"))

MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
MON_RE = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"

COAL_CO = {"ECL": "ECL", "BCCL": "BCCL", "CCL": "CCL", "NCL": "NCL", "WCL": "WCL", "SECL": "SECL", "MCL": "MCL", "NEC": "NEC",
           "CIL": "CIL", "SCCL": "SCCL", "SINGARENI": "SCCL", "GRANDTOTAL": "Total", "TOTAL": "Total"}
SECTORS = {"POWER": "Power", "CPP": "CPP", "STEEL": "Steel", "CEMENT": "Cement", "SPONGEIRON": "Sponge", "SPONGE": "Sponge",
           "OTHERS": "Others", "TOTAL": "Total", "DISPATCHTONRS": "NRS", "DESPATCHTONRS": "NRS"}
LIGNITE = {"NLCIL": "NLCIL", "NLC": "NLCIL", "GMDCL": "GMDCL", "GMDC": "GMDCL", "GIPCL": "GIPCL", "RSMML": "RSMML",
           "BLMCL": "BLMCL", "GHCL": "GHCL", "VSLIGNITE": "VSLignite", "GSPL": "GSPL", "GRANDTOTAL": "Total", "TOTAL": "Total"}


# ---------------------------------------------------------------- fetching

def listing(max_pages=8):
    """Every msg-*.pdf link on the listing pages (?page=0,1,... until a page adds nothing), plus the known unlisted ones."""
    for base in HOSTS:
        links = []
        try:
            for p in range(max_pages):
                page = requests.get(base + LISTING + (f"?page={p}" if p else ""), headers=UA, timeout=60, verify=False).text
                found = [l for l in re.findall(r'href="(?:https?://[^"/]+)?(/sites/default/files/[^"]*?msg-[^"]*?\.pdf)"', page, re.I)
                         if l not in links]
                if not found:
                    break
                links += found
                time.sleep(1.5)
        except requests.RequestException as e:
            print(f"listing {base}: {e}")
        if links:
            return [base + l for l in links + [u for u in UNLISTED if u not in links]]
    raise RuntimeError("no msg-*.pdf links on the listing pages")


def local(url):
    m = re.search(r"/files/(\d{4}-\d{2})/([^/]+\.pdf)$", url, re.I)
    return CACHE / (f"{m.group(1)}_{m.group(2)}" if m else url.rsplit("/", 1)[-1])


def download(url):
    path = local(url)
    if path.exists() and path.stat().st_size > 10000:
        return path, False
    r = requests.get(url, headers=UA, timeout=120, verify=False)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError(f"not a PDF: {url}")
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(r.content)
    return path, True


# ---------------------------------------------------------------- parsing helpers

def ym(y, m):
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}"


def shift(period, months):
    y, m = map(int, period.split("-"))
    return ym(y, m + months)


def month_label(s):
    """"Aug'25", "Sept'2025", "May-22", "Apr 2021" -> 'YYYY-MM' (None if no month+year)."""
    m = re.search(MON_RE + r"\s*['’`\-]?\s*(\d{4}|\d{2})\b", s or "", re.I)
    if not m:
        return None
    y = int(m.group(2))
    return ym(y + 2000 if y < 100 else y, MONTHS[m.group(1).lower()[:3]])


def report_month(pdf):
    text = (pdf.pages[0].extract_text() or "")[:600]
    m = re.search(r"Statistics.{0,40}?" + MON_RE + r"\s*['’`]?\s*(\d{4}|\d{2})", text, re.I | re.S)
    if not m:
        return None
    y = int(m.group(2))
    return ym(y + 2000 if y < 100 else y, MONTHS[m.group(1).lower()[:3]])


def num(s):
    """'12.34' / '-1.5' / '1,299.85' -> float; pie labels ('8.45,') and percentages ('97%') are not numbers."""
    s = str(s or "").strip()
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?|-?\d+(\.\d+)?", s):
        return float(s.replace(",", ""))
    return None


def key(s):
    return re.sub(r"[^A-Z]", "", str(s or "").upper())


ARROW = {"▲", "▼", "▲▼", "-", "–"}


def page_lines(pg):
    """Words grouped into text lines: [(top, [(text, x0, x1), ...]), ...] sorted top to bottom, left to right."""
    words = sorted(pg.extract_words(x_tolerance=1.5, y_tolerance=2), key=lambda w: (round(w["top"]), w["x0"]))
    lines = []
    for w in words:
        if lines and abs(lines[-1][0] - w["top"]) <= 2.5:
            lines[-1][1].append((w["text"], w["x0"], w["x1"]))
        else:
            lines.append([w["top"], [(w["text"], w["x0"], w["x1"])]])
    return [(t, sorted(ws, key=lambda w: w[1])) for t, ws in lines]


def data_row(words):
    """A table row: optional serial no., a text label, then numbers. -> (label key, [(value, x centre)]) or None."""
    i = 0
    if len(words) > 1 and re.fullmatch(r"\d{1,2}\.?", words[0][0]) and num(words[1][0]) is None:
        i = 1
    label = []
    while i < len(words) and num(words[i][0]) is None and words[i][0] not in ARROW:
        label.append(words[i][0])
        i += 1
    vals = []
    for t, x0, x1 in words[i:]:
        if t in ARROW or re.fullmatch(r"[▲▼]", t) or t.startswith("#"):
            continue
        v = num(t.lstrip("▲▼"))
        if v is None:
            break                      # trailing narrative text next to a table (2021 layouts)
        vals.append((v, (x0 + x1) / 2))
    if not label or not vals or len(key(" ".join(label))) < 2 or re.fullmatch(r"FY", key(" ".join(label))):
        return None
    return key(" ".join(label)), vals


def phrases(words, gap=4.0):
    out = []
    for t, x0, x1 in words:
        if out and x0 - out[-1][2] < gap:
            out[-1] = (out[-1][0] + " " + t, out[-1][1], x1)
        else:
            out.append((t, x0, x1))
    return out


def fy_header(words):
    """Line like 'FY 27 Achmt.(%) FY 26 Growth (%) FY 27 FY 26 Growth (%)' -> anchors [(kind, fy, x centre)]."""
    ph = phrases(words)
    anchors = []
    for t, x0, x1 in ph:
        m = re.search(r"\bFY\s*'?(\d{2})\b(?![-\d])", t, re.I)
        if m and len(t) <= 12:
            anchors.append(("fy", int(m.group(1)), (x0 + x1) / 2))
        elif re.search(r"target|monthly", t, re.I):
            anchors.append(("target", None, (x0 + x1) / 2))
        else:
            anchors.append(("other", None, (x0 + x1) / 2))
    return anchors if sum(1 for a in anchors if a[0] == "fy") >= 3 else None


def extra_anchors(anchors, words):
    """Header words on the lines around the FY line ('Target', 'Growth (%)', 'Achmt') mark columns too."""
    for t, x0, x1 in phrases(words):
        kind = "target" if re.fullmatch(r"(monthly\s*)?target", t, re.I) else \
               "other" if re.match(r"growth|achm|\(%\)", t, re.I) else None
        c = (x0 + x1) / 2
        if kind and not any(abs(a[2] - c) < 12 for a in anchors):
            anchors.append((kind, None, c))


TITLE_PATTERNS = {
    "coal": [(r"coking", "skip"), (r"top\s*\d+|mines", "skip"), (r"coal\s*production", "prod"), (r"coal\s*(d[ei]spatch|offtake)", "dispatch")],
    "sector": [(r"\bmines\b|top\s*\d+", "skip"), (r"\bby\s*cil\b", "sector_CIL"), (r"\bby\s*(sccl|singareni)", "sector_SCCL"), (r"captive", "sector_Captive"),
               (r"different\s*sectors?", "sector_Total")],
    "lignite": [(r"lignite\s*produc", "lignite_prod"), (r"lignite\s*d[ei]sp", "lignite_dispatch")],
    "rakes": [(r"rake.*power|power\s*sector|\(power", "power"), (r"rake.*(all|overall)\s*sector|\(all\s*sector", "all")],
}
# a line like this ends the table above it (chart titles, the next table's title)
STOP_RE = re.compile(r"coal\s*production|coal\s*d[ei]spatch|d[ei]spatch\s*of\s*coal|different\s*sectors|lignite\s*(produc|d[ei]sp)|"
                     r"rake|modewise|mode\s*wise|top\s*\d+|power\s*generation|electricity|exchequer|royalty|coking|stock", re.I)


def classify(ctx, struct):
    for line in reversed(ctx):
        for pat, kind in TITLE_PATTERNS[struct]:
            if re.search(pat, line, re.I):
                return kind
    return None


def struct_of(k):
    if k in COAL_CO or "CAPTIVE" in k:
        return "coal"
    if k in LIGNITE:
        return "lignite"
    if k in SECTORS or k.startswith("DISPATCHTO") or k.startswith("DESPATCHTO"):
        return "sector"
    return None


# ---------------------------------------------------------------- one report

def parse_pdf(path):
    """-> (period, primary rows, secondary rows, notes); rows are {(series, period): (value, unit, source)}.
    Secondary rows are for earlier months (prior-year columns, rakes history)."""
    with pdfplumber.open(path) as pdf:
        period = report_month(pdf)
        if not period:
            raise ValueError("report month not found on page 1")
        y, m = map(int, period.split("-"))
        mname = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[m - 1]
        src = f"{SRC}, {mname} {y}"
        fy = (y + 1 if m >= 4 else y) % 100
        prim, sec, notes, seen = {}, {}, [], set()

        def add(series, per, val, unit, primary=True, source=None, overwrite=False):
            if val is None or per is None:
                return
            d, row = (prim, (val, unit, source or src)) if primary and per == period else \
                     (sec, (val, unit, source or f"{src} (prior-year column)"))
            if per > period or (not primary and per == period):
                return
            if overwrite:
                d[(series, per)] = row
            else:
                d.setdefault((series, per), row)

        ctx = []          # text lines since the last data row (titles, chart labels, header lines)
        recent = []       # words of the last few lines (to find a 'Target' header above the FY line)
        tab = None        # the table being read: dict(type, kind, anchors | months | modes, ...)
        for pg in pdf.pages:
            for _, words in page_lines(pg):
                text = " ".join(w[0] for w in words)
                row = data_row(words)
                recent = (recent + [words])[-6:]
                anchors = fy_header(words)
                if anchors:
                    for ws in recent[-4:-1]:
                        extra_anchors(anchors, ws)
                    tab = {"type": "fy", "anchors": anchors, "kind": None, "hdr": ctx + [text]}
                    ctx.append(text)
                    continue
                if re.search(r"achie", text, re.I) and re.search(r"loading|rake", " ".join(ctx[-3:] + [text]), re.I) and not row:
                    if not (tab and tab["type"] == "rakes" and not tab.get("rows")):
                        tab = {"type": "rakes", "kind": None, "rows": 0}
                    ctx.append(text)
                    continue
                mons = [month_label(w[0]) for w in words]
                ml = [x for x in mons if x]
                if (len(ml) >= 5 and not row and (mons[0] or re.match(r"company", text, re.I))
                        and not (tab and tab["type"] == "rakes" and not tab["rows"])
                        and all(shift(a, 1) == b for a, b in zip(ml, ml[1:]))):
                    tab = {"type": "hist", "months": [x for x in mons if x], "kind": None}
                    ctx.append(text)
                    continue
                if re.search(r"\brail\b", text, re.I) and re.search(r"\broad\b", text, re.I) and not row:
                    tab = {"type": "mode", "modes": [w[0].upper() if w[0].upper() in ("MGR", "RCR") else w[0].capitalize() for w in words
                                                     if re.fullmatch(r"rail|rcr|road|mgr|others|total", w[0], re.I)], "months": []}
                    ctx.append(text)
                    continue
                if tab and tab["type"] == "mode" and not row and sum(1 for x in mons if x) >= 2:
                    tab["months"] = [x for x in mons if x]
                if tab and tab["type"] == "fy" and tab["kind"] is None and not row:
                    extra_anchors(tab["anchors"], words)
                if not row:
                    if tab and STOP_RE.search(text) and (tab["type"] != "fy" or tab["kind"]):
                        tab = None
                    ctx.append(text)
                    continue
                if not tab:
                    continue
                k, vals = row
                if handle_row(tab, k, vals, ctx, period, fy, add, seen, notes, src):
                    ctx = []
        return period, prim, sec, notes


def handle_row(tab, k, vals, ctx, period, fy, add, seen, notes, src):
    typ = tab["type"]
    if typ == "fy" and tab["kind"] is None and not struct_of(k):
        return False
    if typ == "fy":
        st = struct_of(k)
        if tab["kind"] is None:
            if not st:
                return
            ctx_all = tab["hdr"]
            kind = classify(ctx_all, st)
            if st == "lignite" and not kind:
                h = " ".join(ctx_all)
                kind = "lignite_prod" if re.search(r"produc", h, re.I) else "lignite_dispatch" if re.search(r"d[ei]sp", h, re.I) else None
            if st == "coal" and not kind:
                h = " ".join(ctx_all[-3:])
                kind = "prod" if re.search(r"produc", h, re.I) else "dispatch" if re.search(r"d[ei]sp", h, re.I) else None
            if st == "sector" and not kind:        # untitled: they always come in the order Total, CIL, SCCL, Captive
                kind = next((c for c in ("sector_Total", "sector_CIL", "sector_SCCL", "sector_Captive") if c not in seen), None)
                notes.append(f"untitled sector table taken as {kind}")
            if not kind or kind == "skip" or kind in seen:
                if DEBUG:
                    print("  skipped table", st, kind, "| context:", ctx_all[-4:], k)
                if kind and kind != "skip":
                    notes.append(f"second {kind} table ignored")
                tab["kind"] = "skip"
                return
            fys = [a for a in tab["anchors"] if a[0] == "fy"]
            if fys[0][1] != fy:
                if any(month_label(w) == period for l in ctx_all for w in l.split()):
                    notes.append(f"{kind}: columns labelled FY{fys[0][1]}/FY{fys[1][1]} under '{period}' headings: read as this year/last year")
                    fys = [("fy", fy, fys[0][2]), ("fy", fy - (fys[0][1] - fys[1][1]), fys[1][2])]
                else:
                    notes.append(f"{kind}: first FY column is FY{fys[0][1]}, expected FY{fy}")
                    tab["kind"] = "skip"
                    return
            if DEBUG:
                print("  table", kind, "| title:", next((l for l in reversed(ctx_all) if re.search(r"[a-z]{4}", l, re.I)), "")[:70], "| first row:", k, vals[:3])
            tab["kind"], tab["struct"] = kind, st
            tab["lag"] = (fys[0][1] - fys[1][1]) * 12
            tab["cap"] = {}
            seen.add(kind)
        kind = tab["kind"]
        if kind == "skip" or not ({"coal": "CAPTIVE" in k or k in COAL_CO or k in ("OTHERS", "COMMERCIAL"),
                                   "sector": k in SECTORS, "lignite": k in LIGNITE}[tab["struct"]]):
            return
        # each value goes to the nearest header anchor
        anchors = tab["anchors"]
        fyx = [a[2] for a in anchors if a[0] == "fy"]
        cols = {}
        for v, x in vals:
            j = min(range(len(anchors)), key=lambda j: abs(anchors[j][2] - x))
            a = anchors[j]
            name = "target" if a[0] == "target" else "cur" if a[0] == "fy" and a[2] == fyx[0] else \
                   "prev" if a[0] == "fy" and a[2] == fyx[1] else None
            if name and (name not in cols or abs(a[2] - x) < cols[name][1]):
                cols[name] = (v, abs(a[2] - x))
        cur, prv, tgt = (cols.get(n, (None,))[0] for n in ("cur", "prev", "target"))
        prev = shift(period, -tab["lag"])
        psrc = f"{src} (prior-year column)" if tab["lag"] == 12 else f"{src} ({tab['lag'] // 12}-years-earlier column)"
        if kind in ("prod", "dispatch"):
            if "CAPTIVE" in k or k in ("OTHERS", "COMMERCIAL"):
                ent = "Captive"
                if ent in tab["cap"]:           # separate captive and other rows are summed
                    c0, p0, t0 = tab["cap"][ent]
                    cur = round((c0 or 0) + (cur or 0), 4) if (c0 is not None or cur is not None) else None
                    prv = round((p0 or 0) + (prv or 0), 4) if (p0 is not None or prv is not None) else None
                    tgt = round((t0 or 0) + (tgt or 0), 4) if (t0 is not None or tgt is not None) else None
                tab["cap"][ent] = (cur, prv, tgt)
                add_over = True
            else:
                ent, add_over = COAL_CO.get(k), False
            if not ent:
                return
            for series, v, per in ((f"{kind}_m:{ent}", cur, period), (f"{kind}_m:{ent}", prv, prev), (f"{kind}_target_m:{ent}", tgt, period)):
                if v is None:
                    continue
                add(series, per, v, "Mt", primary=(per == period), overwrite=add_over, source=None if per == period else psrc)
        elif kind.startswith("lignite"):
            ent = LIGNITE.get(k)
            if ent:
                add(f"{kind}_m:{ent}", period, cur, "Mt")
                add(f"{kind}_m:{ent}", prev, prv, "Mt", primary=False, source=psrc)
        else:
            ent = SECTORS.get(k)
            who = kind.split("_")[1]
            if who == "Total":
                if ent:
                    add(f"dispatch_sector_m:{ent}", period, cur, "Mt")
                    add(f"dispatch_sector_m:{ent}", prev, prv, "Mt", primary=False, source=psrc)
                if ent == "Power":
                    add("dispatch_power_m:Total", period, cur, "Mt")
                    add("dispatch_power_m:Total", prev, prv, "Mt", primary=False, source=psrc)
            elif ent == "Power":
                add(f"dispatch_power_m:{who}", period, cur, "Mt")
                add(f"dispatch_power_m:{who}", prev, prv, "Mt", primary=False, source=psrc)
    elif typ == "rakes":
        ent = COAL_CO.get(k)
        if not ent:
            return
        if tab["kind"] is None:
            kind = classify(ctx, "rakes")
            if kind in seen or kind is None:
                kind = "power" if "all" in seen else "all"
            if kind in seen:
                tab["kind"] = "skip"
                notes.append("third rakes table ignored")
                return
            tab["kind"] = kind
            seen.add(kind)
        if tab["kind"] == "skip":
            return
        tab["rows"] += 1
        pre = "rakes_m" if tab["kind"] == "all" else "rakes_power_m"
        v = [x for x, _ in vals]
        if len(v) < 4:
            notes.append(f"rakes {k}: {len(v)} values")
            return
        if v[0] and abs(v[1] / v[0] * 100 - v[2]) > 3:     # plan, actual, achievement %, last year, growth
            notes.append(f"rakes {tab['kind']} {k}: {v[:3]} actual/plan != achievement")
        add(f"{pre}:{ent}", period, v[1], "rakes/day")
        add(f"{pre}:{ent}", shift(period, -12), v[3], "rakes/day", primary=False)
    elif typ == "hist":
        ent = COAL_CO.get(k)
        if not ent:
            return
        if tab["kind"] is None:
            kind = "hist_" + (classify(ctx, "rakes") or "?")
            if kind == "hist_?" or kind in seen:
                kind = "hist_power" if "hist_all" in seen else "hist_all"
            if kind in seen:
                tab["kind"] = "skip"
                return
            tab["kind"] = kind
            seen.add(kind)
        if tab["kind"] == "skip":
            return
        months = tab["months"]
        v = [x for x, _ in vals]
        extra = len(v) - len(months)
        if extra > 0 and shift(months[-1], extra) == period:    # month headings wrapped onto a second line
            months = months + [shift(months[-1], i) for i in range(1, extra + 1)]
        if len(v) != len(months):
            if not tab.get("warned"):
                notes.append(f"{tab['kind']} {k}: {len(v)} values for {len(months)} months (row skipped)")
                tab["warned"] = True
            return
        pre = "rakes_m" if tab["kind"] == "hist_all" else "rakes_power_m"
        for p, x in zip(months, v):
            if p == period:                   # used only when the report has no monthly rakes table (Sep 2023)
                add(f"{pre}:{ent}", p, x, "rakes/day")
            elif p < period:
                add(f"{pre}:{ent}", p, x, "rakes/day", primary=False, source=f"{src} (rakes history table)")
    elif typ == "mode":
        if k != "CIL":
            return
        modes, v = tab["modes"], [x for x, _ in vals]
        if "mode" in seen or not modes:
            return
        seen.add("mode")
        if len(v) == 2 * len(modes):
            cur_first = not tab["months"] or tab["months"][0] == period
            for i, mode in enumerate(modes):
                c, p = (v[2 * i], v[2 * i + 1]) if cur_first else (v[2 * i + 1], v[2 * i])
                add(f"cil_mode_m:{mode}", period, c, "Mt")
                add(f"cil_mode_m:{mode}", shift(period, -12), p, "Mt", primary=False)
        elif len(v) == len(modes):
            for mode, c in zip(modes, v):
                add(f"cil_mode_m:{mode}", period, c, "Mt")
        else:
            notes.append(f"mode: {len(v)} values for {modes}")
    return True


# ---------------------------------------------------------------- store

def existing():
    con = connect()
    con.executescript(SCHEMA)
    try:
        return {(s, p): src for s, p, src in con.execute("SELECT series, period, source FROM coal_supply")}
    finally:
        con.close()


def store(results):
    """results: list of (period, prim, sec). Primary rows overwrite; secondary rows only fill gaps and never replace
    a primary row (stored now or before). Among secondaries a comparison column beats the rakes history table,
    then the newest report wins."""
    rank = lambda src: 0 if not src else 2 if src.endswith("column)") else 1 if src.endswith("history table)") else 3
    have = existing()
    primary_keys = {k for _, prim, _ in results for k in prim}
    rows, fill = [], {}
    for _, prim, _ in results:
        rows += [(s, p, v, u, src) for (s, p), (v, u, src) in prim.items()]
    for rep, _, sec in sorted(results, key=lambda r: r[0], reverse=True):
        for (s, p), (v, u, src) in sec.items():
            if (s, p) in primary_keys:
                continue
            if (s, p) in fill and rank(fill[(s, p)][4]) >= rank(src):
                continue
            if rank(have.get((s, p))) > rank(src):
                continue                       # a report of its own (or a better secondary) already covers it
            fill[(s, p)] = (s, p, v, u, src)
    rows += list(fill.values())
    put(rows)
    return len(rows)


def check(period, prim):
    """Sanity: parts add up to totals (within rounding)."""
    g = lambda s: prim.get((s, period), (None,))[0]
    bad = []
    for pre in ("prod_m", "dispatch_m"):
        parts = [g(f"{pre}:{c}") for c in ("CIL", "SCCL", "Captive")]
        tot = g(f"{pre}:Total")
        if None in parts or tot is None:
            bad.append(f"{pre} missing parts/total")
        elif abs(sum(parts) - tot) > 0.15:
            bad.append(f"{pre}: CIL+SCCL+Captive {sum(parts):.2f} != Total {tot}")
        subs = [g(f"{pre}:{c}") for c in ("ECL", "BCCL", "CCL", "NCL", "WCL", "SECL", "MCL", "NEC")]
        if g(f"{pre}:CIL") is not None and all(v is not None for v in subs[:7]) and abs(sum(v or 0 for v in subs) - g(f"{pre}:CIL")) > 0.15:
            bad.append(f"{pre}: subsidiaries {sum(v or 0 for v in subs):.2f} != CIL {g(f'{pre}:CIL')}")
    pw = [g(f"dispatch_power_m:{c}") for c in ("CIL", "SCCL", "Captive")]
    if None not in pw and g("dispatch_power_m:Total") is not None and abs(sum(pw) - g("dispatch_power_m:Total")) > 0.3:
        bad.append(f"power dispatch CIL+SCCL+Captive {sum(pw):.2f} != Total {g('dispatch_power_m:Total')}")
    secs = [g(f"dispatch_sector_m:{s}") for s in ("Power", "CPP", "Steel", "Cement", "Sponge", "Others")]
    if g("dispatch_sector_m:Total") is None or None in secs[:1]:
        bad.append("sector table missing")
    elif abs(sum(v or 0 for v in secs) - g("dispatch_sector_m:Total")) > 0.2:
        bad.append(f"sectors {sum(v or 0 for v in secs):.2f} != total {g('dispatch_sector_m:Total')}")
    for pre in ("rakes_m", "rakes_power_m"):
        if g(f"{pre}:Total") is None:
            bad.append(f"{pre} missing")
    if g("rakes_m:Total") and g("rakes_power_m:Total") and g("rakes_power_m:Total") > g("rakes_m:Total") + 0.5:
        bad.append("power rakes > all rakes")
    return bad


def parse_all(paths, verbose=True):
    results, failed = [], []
    for p in paths:
        try:
            period, prim, sec, notes = parse_pdf(p)
        except Exception as e:
            failed.append(f"{p.name}: {e}")
            continue
        bad = check(period, prim)
        if verbose:
            print(f"{p.name}: {period} {len(prim)} rows (+{len(sec)} earlier)" + (f"  CHECK: {'; '.join(bad)}" if bad else "")
                  + (f"  NOTE: {'; '.join(notes)}" if notes else ""), flush=True)
        if not prim:
            failed.append(f"{p.name}: no rows")
            continue
        results.append((period, prim, sec))
    dup = {}
    for r in results:
        dup.setdefault(r[0], []).append(r)
    if any(len(v) > 1 for v in dup.values()):
        print("duplicate report months:", [k for k, v in dup.items() if len(v) > 1])
    return results, failed


def run(all_cached=False):
    new = []
    try:
        for u in listing():
            path, fresh = download(u)
            if fresh:
                new.append(path)
                time.sleep(1.5)
    except Exception as e:
        log("coal_msg", "error", f"listing/download: {e}")
        print("listing/download error:", e)
    paths = sorted(CACHE.glob("*.pdf")) if all_cached else new
    if not paths:
        log("coal_msg", "ok", "no new reports")
        return 0
    results, failed = parse_all(paths)
    n = store(results) if results else 0
    months = sorted(r[0] for r in results)
    suspect = [r[0] for r in results if check(r[0], r[1])]
    detail = (f"{len(results)} reports ({months[0] if months else '-'}..{months[-1] if months else '-'}), {n} rows"
              + (f"; failed {failed}" if failed else "") + (f"; checks failed for {suspect}" if suspect else ""))
    log("coal_msg", "ok" if not failed else "error", detail)
    print(detail)
    return n


if __name__ == "__main__":
    if "--file" in sys.argv:
        per, prim, sec, notes = parse_pdf(Path(sys.argv[sys.argv.index("--file") + 1]))
        for (s, p), (v, u, src) in sorted(prim.items()):
            print(s, p, v, u)
        print(f"{per}: {len(prim)} rows, {len(sec)} earlier-month rows; checks: {check(per, prim)}; notes: {notes}")
    else:
        run(all_cached="--new" not in sys.argv)
