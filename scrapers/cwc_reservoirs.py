"""Live storage in India's major reservoirs, weekly, from the Central Water Commission's reservoir bulletin.

Hydro's feedstock. CWC publishes a bulletin every Thursday with, per monitored reservoir (91 in 2015,
~178 in 2026): FRL, current level, live capacity at FRL, current live storage (BCM), storage as % of live
capacity this year / same week last year / average of last ten years ("normal"), and benefits (irrigation
CCA, hydel MW). Plus region/state subtotals (Table-01, from ~2019), a basin table and an all-India total.

Sources
  old site  https://cwc.gov.in/en/reservoir-level-storage-bulletin?page=N   2015-04-16 .. 2025-05  (PDF links)
  RSMS      https://rsms.cwc.gov.in/frameWork/web/bulletin-report-page     2025-03 .. today
            (listing is rendered from encrypted API payloads, so it is read with Playwright; the PDFs
            themselves are plain GETs: /admin/storage/bulletins/bulletin-DD-MM-YYYY-<serial>.pdf)

Table cwc_reservoir_weekly (date, reservoir, ...) PK (date, reservoir): one row per reservoir per bulletin.
  date is the bulletin date ('week ending'); obs_date is the date the reading refers to (a day or two earlier
  for some reservoirs). reservoir is a normalised key (see norm_name) so that 'PONG DAM(BEAS)' / 'PONG DAM',
  'METTUR(STANLEY)' / 'METTUR' etc. line up across years; name_raw keeps the printed name.
Series (coal_supply table via scrapers.coal_supply.put), period = bulletin date 'YYYY-MM-DD':
  cwc_storage_w:<R>  cwc_capacity_w:<R>  (BCM)   cwc_pct_w:<R> cwc_pct_lastyear_w:<R> cwc_pct_normal_w:<R> (% of capacity)
  cwc_storage_lastyear_w:<R> cwc_storage_normal_w:<R> (BCM, where printed)   cwc_n_w:<R> (reservoirs monitored)
  R = AllIndia | Northern | Eastern | Western | Central | Southern: the bulletin's own totals (Table-01 sub-totals
      from ~Aug 2019, the basin table's TOTAL line, else the brief note's paragraphs; summed from the reservoir rows
      only as a last resort, flagged in `source`).  "normal" = average of the last ten years for that week.
  R = Hydel (reservoirs with hydel MW > 0) and Hydel60 (hydel >= 60 MW, the bulletin's '*' definition) are summed
      here from the reservoir rows; they also carry cwc_hydel_mw_w:<R>. The monitored set grows (91 -> 178), so
      use the % series for comparisons across years.

Awkward files: a few bulletins are scans (2017-05-25, 2018-08-09, 2018-08-16, 2019-01-03) -> tesseract OCR, rows
kept only when they match a known reservoir's FRL+capacity; two (2020-10-08, 2020-11-19) have fonts pdfminer cannot
decode -> pdfium text. Reading dates are printed month-first in 2015 and some 2018 bulletins; the brief note is
sometimes dated a year off -- the bulletin date is the heading date best supported by the reading dates.

    python -m scrapers.cwc_reservoirs              # newest bulletins (first page of the RSMS listing)
    python -m scrapers.cwc_reservoirs --backfill   # all listings 2015 ->, download missing PDFs, parse all
    python -m scrapers.cwc_reservoirs --reparse    # re-parse every cached PDF (no network)
"""
import json
import logging
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
import urllib3

from store import connect, log

urllib3.disable_warnings()
logging.getLogger("pdfminer").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw" / "cwc"
INDEX = RAW / "index.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 (reclaimchennai power map)"}
OLD_LIST = "https://cwc.gov.in/en/reservoir-level-storage-bulletin?page={}"
RSMS_LIST = "https://rsms.cwc.gov.in/frameWork/web/bulletin-report-page"
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
SRC = "CWC reservoir storage bulletin"
PAUSE = 2.5

SCHEMA = """
CREATE TABLE IF NOT EXISTS cwc_reservoir_weekly (
    date TEXT NOT NULL,            -- bulletin date (week ending), YYYY-MM-DD
    reservoir TEXT NOT NULL,       -- normalised name key
    name_raw TEXT,                 -- name as printed in this bulletin
    state TEXT,
    region TEXT,                   -- Northern / Eastern / Western / Central / Southern
    frl_m REAL,
    level_m REAL,
    live_cap_frl_bcm REAL,
    live_storage_bcm REAL,
    obs_date TEXT,                 -- date of the reading (YYYY-MM-DD)
    pct_capacity REAL,             -- current storage as % of live capacity at FRL
    pct_last_year REAL,            -- same period last year, % of live capacity
    pct_normal REAL,               -- average of last 10 years (normal), % of live capacity
    irr_cca_th_ha TEXT,            -- irrigation CCA, thousand ha (text: may be '$', '#', '@' footnote marks)
    hydel_mw REAL,
    hydro_flag INTEGER,            -- 1 if marked '*' (significant hydropower), where the bulletin marks it
    source TEXT,                   -- PDF file name
    PRIMARY KEY (date, reservoir)
);
"""


# ----------------------------------------------------------------------------------------------- listings
def _get(url, timeout=180, **kw):
    for i in range(4):
        try:
            r = requests.get(url, headers=UA, verify=False, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return r
        except requests.RequestException:
            pass
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"GET failed {url}")


def list_old(pages=range(0, 40)):
    """[(label, url)] from the old cwc.gov.in listing (newest first). Stops at the first page with nothing new."""
    out, seen = [], set()
    for pg in pages:
        try:
            r = _get(OLD_LIST.format(pg), timeout=60)
        except RuntimeError as e:
            print("old listing", pg, e)
            continue
        new = 0
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S):
            links = [l for l in re.findall(r'href="([^"]+)"', row) if l.lower().endswith(".pdf")]
            if not links:
                continue
            url = links[0] if links[0].startswith("http") else "https://cwc.gov.in" + links[0]
            txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row)).strip()
            if url not in seen:
                seen.add(url)
                out.append((txt[:120], url))
                new += 1
        if new == 0:
            break
        time.sleep(1)
    return out


def list_rsms(max_pages=40):
    """[(label, url)] from the RSMS bulletin listing (Angular app, encrypted API -> read the rendered table)."""
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        kw = {"args": ["--ignore-certificate-errors"]}
        if os.path.exists(CHROME):
            kw["executable_path"] = CHROME
        b = p.chromium.launch(**kw)
        pg = b.new_context(ignore_https_errors=True).new_page()
        pg.goto(RSMS_LIST, wait_until="networkidle", timeout=120000)
        pg.wait_for_timeout(3000)
        for _ in range(max_pages):
            rows = pg.eval_on_selector_all(
                "table tr", "els=>els.map(e=>[e.innerText, (e.querySelector('a[href*=\"bulletins\"]')||{}).href||''])")
            new = 0
            for txt, href in rows:
                if href and href not in [u for _, u in out]:
                    out.append((re.sub(r"\s+", " ", txt).strip()[:160], href))
                    new += 1
            if max_pages == 1 or new == 0:
                break
            nxt = pg.get_by_text("Next", exact=False).last
            try:
                nxt.click(timeout=10000)
            except Exception:
                break
            pg.wait_for_timeout(3500)
        b.close()
    return out


# ---------------------------------------------------------------------------------------------- downloads
def _index():
    try:
        return json.loads(INDEX.read_text())
    except (OSError, ValueError):
        return {}


def local_name(url):
    base = url.rsplit("/", 1)[-1]
    return ("rsms_" if "rsms.cwc" in url else "") + re.sub(r"[^\w.\-]", "_", base)


def download(items, pause=PAUSE):
    """items: [(label, url)]. Downloads missing PDFs into raw/cwc/, returns [Path] of all local files for items."""
    RAW.mkdir(parents=True, exist_ok=True)
    idx = _index()
    paths = []
    for label, url in items:
        f = RAW / local_name(url)
        idx.setdefault(f.name, {"url": url, "label": label})
        if not (f.exists() and f.stat().st_size > 1000):
            if idx[f.name].get("missing", 0) >= 3:     # listed but 404 on the server (e.g. 17.09.2026): stop retrying
                continue
            try:
                r = _get(url, timeout=300)
            except RuntimeError as e:
                print("  download failed", url, e)
                log("cwc_reservoirs", "error", f"download {url}: {e}")
                continue
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                idx[f.name]["missing"] = idx[f.name].get("missing", 0) + 1
                print("  not a pdf", r.status_code, url)
                log("cwc_reservoirs", "error", f"not a pdf {r.status_code} {url}")
                continue
            f.write_bytes(r.content)
            print(f"  got {f.name} {len(r.content)//1024} kB", flush=True)
            time.sleep(pause)
        paths.append(f)
    INDEX.write_text(json.dumps(idx, indent=0))
    return paths


# ------------------------------------------------------------------------------------------------ parsing
REGIONS = {"NORTHERN": "Northern", "NORTH": "Northern", "EASTERN": "Eastern", "EAST": "Eastern",
           "WESTERN": "Western", "WEST": "Western", "CENTRAL": "Central", "SOUTHERN": "Southern", "SOUTH": "Southern"}
# state header spellings seen in the bulletins -> canonical state
STATES = {
    "HIMACHALPRADESH": "Himachal Pradesh", "HP": "Himachal Pradesh", "PUNJAB": "Punjab", "RAJASTHAN": "Rajasthan",
    "JHARKHAND": "Jharkhand", "ODISHA": "Odisha", "ORISSA": "Odisha", "WESTBENGAL": "West Bengal", "WBENGAL": "West Bengal",
    "TRIPURA": "Tripura", "NAGALAND": "Nagaland", "ASSAM": "Assam", "BIHAR": "Bihar", "MEGHALAYA": "Meghalaya",
    "MIZORAM": "Mizoram", "MANIPUR": "Manipur", "SIKKIM": "Sikkim", "ARUNACHALPRADESH": "Arunachal Pradesh",
    "GUJARAT": "Gujarat", "GUJRAT": "Gujarat", "MAHARASHTRA": "Maharashtra", "MAH": "Maharashtra", "GOA": "Goa",
    "UTTARPRADESH": "Uttar Pradesh", "UP": "Uttar Pradesh", "UTTRAKHAND": "Uttarakhand", "UTTARAKHAND": "Uttarakhand",
    "UTTARANCHAL": "Uttarakhand", "MADHYAPRADESH": "Madhya Pradesh", "MP": "Madhya Pradesh",
    "CHHATTISGARH": "Chhattisgarh", "CHHATISGARH": "Chhattisgarh", "CHATTISGARH": "Chhattisgarh", "CHATTISHGARH": "Chhattisgarh",
    "CHHATTISHGARH": "Chhattisgarh",
    "ANDHRAPRADESH": "Andhra Pradesh", "AP": "Andhra Pradesh", "TELANGANA": "Telangana", "TG": "Telangana",
    "APTG": "AP&TG", "APTELANGANA": "AP&TG", "ANDHRAPRADESHTELANGANA": "AP&TG", "ANDHRAPRADESHANDTELANGANA": "AP&TG",
    "APTGCOMBINED": "AP&TG", "KARNATAKA": "Karnataka", "KERALA": "Kerala", "TAMILNADU": "Tamil Nadu", "TN": "Tamil Nadu",
    "JAMMUKASHMIR": "Jammu & Kashmir", "JK": "Jammu & Kashmir",
}
STATE_REGION = {
    "Himachal Pradesh": "Northern", "Punjab": "Northern", "Rajasthan": "Northern", "Jammu & Kashmir": "Northern",
    "Jharkhand": "Eastern", "Odisha": "Eastern", "West Bengal": "Eastern", "Tripura": "Eastern", "Nagaland": "Eastern",
    "Assam": "Eastern", "Bihar": "Eastern", "Meghalaya": "Eastern", "Mizoram": "Eastern", "Manipur": "Eastern",
    "Sikkim": "Eastern", "Arunachal Pradesh": "Eastern",
    "Gujarat": "Western", "Maharashtra": "Western", "Goa": "Western",
    "Uttar Pradesh": "Central", "Uttarakhand": "Central", "Madhya Pradesh": "Central", "Chhattisgarh": "Central",
    "Andhra Pradesh": "Southern", "Telangana": "Southern", "AP&TG": "Southern", "Karnataka": "Southern",
    "Kerala": "Southern", "Tamil Nadu": "Southern",
}
MONTHS = {m: i for i, m in enumerate(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
                                      "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1)}
DATE_RE = r"(\d{1,2})\s?[./\-]\s?(\d{1,2})\s?[./\-]\s?((?:19|20)\d{2}|\d{2})"
NUM = r"-?\d+(?:\.\d+)?"


def _key(s):
    return re.sub(r"[^A-Z]", "", s.upper().replace("&", ""))


def as_state(line):
    k = _key(re.sub(r"\(.*?\)", "", line))
    return STATES.get(k)


def as_region(line):
    m = re.match(r"^\s*(NORTHERN|EASTERN|WESTERN|CENTRAL|SOUTHERN)\s+(?:REGION|ZONE)\b\s*(\(.*)?$", line.strip(), re.I)
    return REGIONS[m.group(1).upper()] if m else None


def fnum(t):
    if t is None:
        return None
    t = str(t).strip().replace(",", "")
    t = re.sub(r"[%*]", "", t)
    try:
        return float(t)
    except ValueError:
        return None


def mkdate(d, m, y):
    y = int(y)
    if y < 100:
        y += 2000
    try:
        return date(y, int(m), int(d)).isoformat()
    except ValueError:
        return None


def norm_name(raw):
    """Stable key for a reservoir across years: upper case, parenthetical aliases and 'DAM'/'RESERVOIR' dropped,
    spelling variants unified via ALIASES."""
    s = raw.upper().replace("’", "'").replace("`", "'").split("/")[0]   # 2016 layout: 'UKAI/TAPTI R.' (river)
    s = re.sub(r"[*†$#@]", " ", s)
    s = re.sub(r"\(.*?\)|\(.*$", " ", s)           # GOBIND SAGAR(BHAKRA) -> GOBIND SAGAR, METTUR(STANLEY) -> METTUR
    s = re.sub(r"[^A-Z0-9 &\-]", " ", s)
    s = re.sub(r"\b(DAM|RESERVOIR|RESERVIOR|PROJECT|HEP|TANK|LAKE)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    s = re.sub(r"\bLOWER\b", "LOWER", s)
    k = s.replace(" ", "").replace("-", "")
    return ALIASES.get(k, s)


# spaceless key -> canonical name (spelling variants across years)
ALIASES = {
    "KRISHNARAJASAGRA": "KRISHNARAJA SAGARA", "KRISHNARAJASAGAR": "KRISHNARAJA SAGARA", "KRS": "KRISHNARAJA SAGARA",
    "VANIVILASSAGAR": "VANI VILAS SAGAR", "VANIVILAS": "VANI VILAS SAGAR",
    "MALAPMUZHA": "MALAMPUZHA", "MALAMPUZA": "MALAMPUZHA",
    "BHIMAUJJAINI": "BHIMA", "BHIMAUJJANI": "BHIMA", "UJJANI": "BHIMA",
    "SRIRAMSAGAR": "SRIRAM SAGAR", "SRSP": "SRIRAM SAGAR",
    "NAGARJUNASAGAR": "NAGARJUNA SAGAR", "NJSAGAR": "NAGARJUNA SAGAR",
    "UPPERVAITARNA": "UPPER VAITARNA",
    "PANSHETTANAJISAGAR": "PANSHET", "BHAMAASKHED": "BHAMA ASKHED",
    "LOWERMANAR": "LOWER MANAR", "LOWERMANAIR": "LOWER MANAIR",
    "MINIMATABANGO": "MINIMATA BANGO", "BANGO": "MINIMATA BANGO", "HASDEOBANGO": "MINIMATA BANGO",
    "MACHKUND": "MACHKUND", "PENCHTOTALADOH": "PENCH", "PENCHTOTLADOH": "PENCH", "TOTLADOH": "PENCH",
    "MANIKDOHKUKADI": "MANIKDOH", "JAYAKWADIPAITHON": "JAYAKWADI", "JAYAKWADIPAITHAN": "JAYAKWADI",
    "MALAPRABHARENUKA": "MALAPRABHA", "KABINISANCHERLA": "KABINI", "KALLADAPARAPPAR": "KALLADA",
    "MAHIBAJAJSAGAR": "MAHI BAJAJ SAGAR", "RANAPRATAPSAGAR": "RANA PRATAP SAGAR",
    "SARDARSAROVAR": "SARDAR SAROVAR", "SSP": "SARDAR SAROVAR",
    "PRIYADARSHINIJURALA": "PRIYADARSHINI JURALA", "JURALA": "PRIYADARSHINI JURALA",
    "MUSI": "MUSI", "MACHCHHUI": "MACHCHHU I", "MACHCHHU": "MACHCHHU I", "MACHCHHU1": "MACHCHHU I", "MACHCHHUII": "MACHCHHU II",
    "MACHCHHU2": "MACHCHHU II", "UNDI": "UND I", "UND1": "UND I", "HIRANII": "HIRAN II", "HIRAN2": "HIRAN II",
    "RANJITSAGAR": "THEIN DAM", "GOBINDSAGAR": "GOBIND SAGAR", "BHAKRA": "GOBIND SAGAR",
    "INDIRASAGAR": "INDIRA SAGAR", "GANDHISAGAR": "GANDHI SAGAR",
    "SANJAYSAROVAR": "SANJAY SAROVAR", "ATALSAGAR": "ATAL SAGAR", "RAJGHAT": "RAJGHAT",
    "SHARDASAGAR": "SHARDA SAGAR", "NANAKSAGAR": "NANAK SAGAR", "UPPERKOLAB": "UPPER KOLAB",
    "UPPERINDRAVATI": "UPPER INDRAVATI", "PANCHETHILL": "PANCHET HILL", "PANCHET": "PANCHET HILL",
    "GARHIUPPERKIUL": "GARHI UPPER KIUL", "SOMKAMLAAMBA": "SOM KAMLA AMBA", "BRAHMAMSAGAR": "BRAHMAM SAGAR",
    "LOWERBHAWANI": "LOWER BHAWANI", "BHAWANISAGAR": "LOWER BHAWANI", "METTURSTANLEY": "METTUR",
    "UPPERTAPI": "UPPER TAPI", "UPPERWARDHA": "UPPER WARDHA", "NIRADEOGHAR": "NIRA DEOGHAR",
    "LOWERDUDHANA": "LOWER DUDHANA", "LOWERTERNA": "LOWER TERNA", "NIZAMSAGAR": "NIZAM SAGAR",
    "GUMTI": "GUMTI", "TUIRIAL": "TUIRIAL", "DAMANAGANGA": "DAMANGANGA", "MINIMATABANGOI": "MINIMATA BANGO",
    "JAKHAM": "JHAKAM", "KOL": "KOL DAM", "MANI": "MANI DAM", "PONG": "PONG DAM", "THEIN": "THEIN DAM",
    "DOYANG": "DOYANG HEP",
}


def _lines(page):
    try:
        return page.extract_text_lines(x_tolerance=1.5, return_chars=False)
    except TypeError:
        return page.extract_text_lines(x_tolerance=1.5)


def _fix(t):
    t = re.sub(r"\(cid:\d+\)", " ", t)
    t = t.replace("–", "-").replace("—", "-").replace(" ", " ")
    t = re.sub(r"\b(\d{1,2}) ?([./\-]) ?(\d{1,2}) ?\2 ?((?:19|20)\d{2})", r"\1\2\3\2\4", t)   # '26 / 7 / 2018'
    t = re.sub(r"(\d{1,2}[.\-/]\d{1,2}[.\-/](?:19|20)\d{2})(?=[\d.])", r"\1 ", t)   # date glued to next number
    return t


ROW_START = re.compile(r"^\s*([*$#@†‡']*)\s*(\d{1,3})?\s*[.)]?\s*([*$#@†‡']*)\s*([A-Za-z(].*|\d.*)$")
NUMTOK = re.compile(r"^(?:-?\d+(?:\.\d*)?|-|--|NA|N\.A\.?|NR|N\.R\.?|NIL)$", re.I)


def rest_of(m):
    return m.group(4) or ""


def parse_row(text):
    """One reservoir line -> dict or None."""
    m = ROW_START.match(_fix(text))
    if not m:
        return None
    star = "*" in (m.group(1) + m.group(3))
    if m.group(2) is None and not re.search(DATE_RE, rest_of(m)):
        return None                            # rows without a serial number must at least carry a reading date
    rest = m.group(4)
    toks = rest.split()
    di = next((i for i, t in enumerate(toks) if re.fullmatch(DATE_RE, t)), None)
    if di is None:
        # no reading date: need at least name + 4 numbers
        nums = [i for i, t in enumerate(toks) if NUMTOK.match(t)]
        if len(nums) < 4:
            return None
        first = next((i for i in range(len(toks)) if all(NUMTOK.match(t) for t in toks[i:])), 0)
        if first == 0 or len(toks) - first < 4:
            return None
        name_t, pre, post, obs = toks[:first], toks[first:first + 4], toks[first + 4:], None
    else:
        pre_all = toks[:di]
        k = 0
        while k < 4 and k < len(pre_all) and NUMTOK.match(pre_all[-1 - k]):
            k += 1
        if k < 3:
            # name glued to FRL, e.g. OMKARESHWAR196.600
            g = re.match(r"^(.*?[A-Za-z)])(\d+\.\d+)$", pre_all[-1 - k]) if len(pre_all) > k else None
            if not g:
                return None
            pre_all = pre_all[:-1 - k] + [g.group(1), g.group(2)] + (pre_all[len(pre_all) - k:] if k else [])
            k += 1
        name_t, pre, post = pre_all[:len(pre_all) - k], pre_all[len(pre_all) - k:], toks[di + 1:]
        dm = re.fullmatch(DATE_RE, toks[di])
        obs = mkdate(*dm.groups())
        obs_raw = dm.groups()
    if di is None:
        obs_raw = None
    name = " ".join(name_t)
    if not re.search(r"[A-Za-z]{2}", name):
        if obs is None:
            return None
        name = ""                              # name cell blank in the PDF: resolved later from FRL + capacity
    pre = [None] * (4 - len(pre)) + pre
    if re.search(r"\bTOTAL\b|PERCENTAGE", name, re.I):
        return None
    post = post + [None] * 5
    cap, sto = fnum(pre[2]), fnum(pre[3])
    if cap is not None and (cap > 15 or (sto is not None and sto > 1.5 * cap + 0.05)):
        return None                            # misread row (columns shifted)
    return {"_obs": obs_raw, "sno": int(m.group(2)) if m.group(2) else None, "name_raw": name, "hydro_flag": int(star),
            "frl_m": fnum(pre[0]), "level_m": fnum(pre[1]), "live_cap_frl_bcm": fnum(pre[2]),
            "live_storage_bcm": fnum(pre[3]), "obs_date": obs,
            "pct_capacity": fnum(post[0]), "pct_last_year": fnum(post[1]), "pct_normal": fnum(post[2]),
            "irr_cca_th_ha": post[3], "hydel_mw": fnum(post[4]) if post[4] not in (None,) else None}


HEADER_JUNK = re.compile(r"WEEKLY REPORT|WEEK ENDING|GOVERNMENT OF INDIA|CENTRAL WATER|STORAGE AS|BENEFITS|^FRL|"
                         r"CURRENT|NAME OF|^S\.? ?NO|SR\.|^\(?M\)?$|AVERAGE|TH\. ?HA|^\d+( \d+[AB]?)+$|^NO\.?$|RESERVOIR|"
                         r"HYDRO|TOTAL CCA|SUPPLEMENTED|^Pg|^Sd|Director|W\. ?M|^\d+$|^-\d+-$|LIVE|CAPACITY", re.I)


def parse_reservoir_pages(pages):
    """pages: pdfplumber pages holding the reservoir-wise weekly report. -> list of row dicts with state/region."""
    rows, region, state = [], None, None
    for page in pages:
        # dict {"lines", "plain"}: plain = pdfium / OCR text, no positions and headers not in reading order
        plain = isinstance(page, dict) and page["plain"]
        lines = page["lines"] if isinstance(page, dict) else _lines(page)
        if plain:
            region = state = None
        items = []
        for ln in lines:
            t = _fix(ln["text"]).strip()
            if not t:
                continue
            r = as_region(t)
            if r and not plain:
                region, state = r, None
                items.append(("region", ln, r))
                continue
            s = None if plain else as_state(t)
            if s:
                state = s
                if STATE_REGION.get(s) and region is None:
                    region = STATE_REGION[s]
                items.append(("state", ln, s))
                continue
            row = parse_row(t)
            if row:
                row["state"], row["region"] = state, region or STATE_REGION.get(state)
                row["_top"], row["_bot"], row["_x0"] = ln["top"], ln["bottom"], ln["x0"]
                items.append(("row", ln, row))
                rows.append(row)
                continue
            items.append(("other", ln, t))
        # wrapped reservoir names: text-only fragment lines just below (or above) a data row, indented to the name column
        prow = [it[2] for it in items if it[0] == "row"] if not plain else []
        for kind, ln, t in items:
            if kind != "other" or not prow or HEADER_JUNK.search(t) or re.search(r"\d{2}[.\-]\d{2}[.\-]\d{4}", t):
                continue
            if not re.fullmatch(r"[A-Za-z][A-Za-z .()&'\-/]{0,40}", t):
                continue
            h = ln["bottom"] - ln["top"]
            mid = (ln["top"] + ln["bottom"]) / 2
            best = min(prow, key=lambda r: abs((r["_top"] + r["_bot"]) / 2 - mid))
            gap = abs((best["_top"] + best["_bot"]) / 2 - mid)
            if gap <= 1.6 * max(h, 6) and ln["x0"] > best["_x0"] - 2:
                if mid > best["_top"]:
                    best["name_raw"] = best["name_raw"] + " " + t
                else:
                    best["name_raw"] = t + " " + best["name_raw"]
    for r in rows:
        for k in ("_top", "_bot", "_x0"):
            r.pop(k, None)
    return rows


def _obs_options(r):
    """Both readings of a row's reading date: 2015 and some 2018 bulletins print it month-first."""
    if not r.get("_obs"):
        return []
    d, m, y = r["_obs"]
    return [x for x in {mkdate(d, m, y), mkdate(m, d, y)} if x]


def bulletin_date(texts, rows=()):
    """The bulletin's own date, from 'AS ON dd.mm.yyyy' / 'WEEK ENDING :- dd.mm.yyyy' / 'BULLETIN OF dd.mm.yyyy'.
    Candidates are scored by how many reservoir reading dates fall 0-10 days before them: the brief note is
    sometimes copied with last year's date ('17.05.2017' in the 17.05.2018 bulletin, '06.06.21' in 06.06.2019)."""
    from collections import Counter
    c = Counter()
    for t in texts:
        t = t.replace("\n", " ")
        for m in re.finditer(r"(?:AS ON|WEEK ENDING|BULLETIN (?:OF|DATED)|dated)\s*[:\-]*\s*" + DATE_RE, t, re.I):
            d = mkdate(*m.groups())
            if d:
                c[d] += 1
        for m in re.finditer(r"AS ON\s*[:\-]*\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Z]+),?\s+(20\d{2})", t, re.I):
            if m.group(2).upper() in MONTHS:
                c[mkdate(m.group(1), MONTHS[m.group(2).upper()], m.group(3))] += 1
    opts = [[date.fromisoformat(x) for x in _obs_options(r)] for r in rows]
    opts = [o for o in opts if o]

    def support(d):
        d = date.fromisoformat(d)
        return sum(any(0 <= (d - o).days <= 10 for o in oo) for oo in opts)
    if c:
        return max(c, key=lambda d: (support(d), c[d]))
    if len(opts) >= 20:
        return Counter(r["obs_date"] for r in rows if r.get("obs_date")).most_common(1)[0][0]
    return None


def fix_obs_dates(d, rows):
    """Pick, per row, the reading-date orientation that falls within 60 days before the bulletin date."""
    b = date.fromisoformat(d)
    for r in rows:
        oo = _obs_options(r)
        good = [o for o in oo if -1 <= (b - date.fromisoformat(o)).days <= 60]
        if good:
            r["obs_date"] = min(good, key=lambda o: abs((b - date.fromisoformat(o)).days))
        elif r.get("obs_date"):
            r["obs_date"] = r["obs_date"]      # keep as printed (stale reading or misprint)


def _floats(s):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


def parse_totals(texts):
    """Region / all-India totals.
    Table-01 (2019 ->): 'SUB-TOTAL n cap cur ly normal pcur ply pnorm dep' after a region header; 'COUNTRY AS A WHOLE ...'.
    Basin table: 'TOTAL cap cur ly normal' (all-India BCM).  Brief note: region paragraphs (2015 ->)."""
    out = {}
    region = None
    for t in texts:
        if not re.search(r"TABLE\s*-?\s*0?1\b.*STATUS OF CURRENT STORAGE|STATUS OF CURRENT STORAGE", t, re.I | re.S):
            continue
        if re.search(r"CHANGE IN STORAGE", t, re.I):
            continue
        for line in _fix(t).split("\n"):
            r = as_region(line) or (REGIONS.get(line.strip().split()[0].upper()) if re.match(r"^\s*(NORTHERN|EASTERN|WESTERN|CENTRAL|SOUTHERN)\s*$", line, re.I) else None)
            if r:
                region = r
                continue
            m = re.match(r"^\s*(SUB[\s\-]*TOTAL|COUNTRY(?: AS)?(?: A)?(?: WHOLE)?)\s*(.*)$", line, re.I)
            if m:
                v = _floats(m.group(2))
                key = "AllIndia" if m.group(1).upper().startswith("COUNTRY") else region
                if key and len(v) >= 8 and key not in out:
                    out[key] = {"n": v[0], "cap": v[1], "cur": v[2], "ly": v[3], "normal": v[4],
                                "pct": v[5], "pct_ly": v[6], "pct_normal": v[7], "src": "table01"}
    for t in texts:
        if "BASIN" not in t.upper():
            continue
        m = re.search(r"\n\s*TOTAL\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)", _fix(t), re.I)
        if m and "AllIndia" not in out:
            cap, cur, ly, nm = map(float, m.groups())
            out["AllIndia"] = {"cap": cap, "cur": cur, "ly": ly, "normal": nm, "pct": 100 * cur / cap,
                               "pct_ly": 100 * ly / cap, "pct_normal": 100 * nm / cap, "src": "basin"}
            break
    note = re.sub(r"\s+", " ", " ".join(texts[:6]))
    if "AllIndia" not in out:
        g = re.search(r"total live storage capacity of (?:these )?(\d+) reservoirs is (\d+\.\d+) ?BCM.*?"
                      r"live storage available in these reservoirs is (\d+\.\d+) ?BCM", note, re.I)
        if g:
            n, cap, cur = map(float, g.groups())
            a = {"n": n, "cap": cap, "cur": cur, "pct": 100 * cur / cap, "src": "note"}
            rest = note[g.end():g.end() + 700]
            h = re.search(r"last year .*?was (\d+\.\d+) ?BCM and (?:the )?(?:average of last 10 years live storage|"
                          r"Normal\*? storage) was (\d+\.\d+) ?BCM", rest, re.I)
            k = re.search(r"storage is (\d+\.?\d*) ?% of the storage of corresponding period of last year and "
                          r"(\d+\.?\d*) ?% of (?:the )?storage of average", rest, re.I)
            if h:
                a["ly"], a["normal"] = map(float, h.groups())
            elif k and float(k.group(1)) > 0 and float(k.group(2)) > 0:
                a["ly"], a["normal"] = cur / (float(k.group(1)) / 100), cur / (float(k.group(2)) / 100)
            if "ly" in a:
                a["pct_ly"], a["pct_normal"] = 100 * a["ly"] / cap, 100 * a["normal"] / cap
                a["src"] = "note" if h else "note~"
            out["AllIndia"] = a
    for m in re.finditer(r"\b(NORTHERN|EASTERN|WESTERN|CENTRAL|SOUTHERN) REGION\b(.{0,900}?)(?=\b(?:NORTHERN|EASTERN|WESTERN|CENTRAL|SOUTHERN) REGION\b|The region wise|BROAD ANALYSIS|$)", note, re.I):
        reg = REGIONS[m.group(1).upper()]
        if reg in out:
            continue
        s = re.sub(r"\s+", " ", m.group(2))
        g = re.search(r"There (?:are|is)\s*(\d+)\s*reservoirs?.*?capacity of\s*(\d+\.?\d*)\s*BCM.*?"
                      r"storage available in these\s*e?reservoirs is\s*(\d+\.?\d*)\s*BCM which is\s*(\d+\.?\d*)\s*%.*?"
                      r"last year was\s*(\d+\.?\d*)\s*%.*?(?:average storage of last ten years|Normal storage)"
                      r"[^%]*?was\s*(\d+\.?\d*)\s*%", s, re.I)
        if g:
            n, cap, cur, p, ply, pn = map(float, g.groups())
            out[reg] = {"n": n, "cap": cap, "cur": cur, "pct": p, "pct_ly": ply, "pct_normal": pn,
                        "ly": cap * ply / 100, "normal": cap * pn / 100, "src": "note%"}
    return out


def _ocr(page):
    """OCR one scanned page with tesseract (if installed) -> text, or '' ."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("tesseract"):
        return ""
    with tempfile.TemporaryDirectory() as td:
        png = os.path.join(td, "p.png")
        page.render(scale=300 / 72).to_pil().save(png)
        try:
            r = subprocess.run(["tesseract", png, "-", "--psm", "6"], capture_output=True, text=True, timeout=180)
        except (subprocess.SubprocessError, OSError):
            return ""
    return r.stdout


_N = r"(?:-?\d+(?:\.\d+)?|-)"
MAIN_ROW = re.compile(r"(?m)^[^\S\n]*[*$#@†]*\d{0,3}[*$#@†]*[^\S\n]*[A-Za-z(][^\n]*?\s" + r"\s+".join([_N] * 4)
                      + r"\s+\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}(?:[^\S\n]+\S+){3,6}[^\S\n]*$")


def parse_pdf(path):
    """-> (bulletin_date, reservoir rows, totals dict).
    pdfium (fast) classifies pages and serves the date / brief note; pdfplumber (layout-aware, x_tolerance=1.5 to
    split the numbers the PDFs print without gaps) reads the reservoir table, Table-01 and the basin table."""
    import pdfplumber
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(path))
    quick, ocred = [], set()
    for i in range(len(doc)):
        try:
            quick.append(doc[i].get_textpage().get_text_range().replace("\r", ""))
        except Exception:
            quick.append("")
    if len(doc) <= 12 and sum(len(t.strip()) < 50 for t in quick) >= 2:    # scanned bulletin (a few in 2017-2019)
        for i, t in enumerate(quick):
            if len(t.strip()) < 50:
                o = _ocr(doc[i])
                if o:
                    quick[i] = o
                    ocred.add(i)
    doc.close()
    res_i, tab_i = [], []
    for i, t in enumerate(quick):
        full = re.sub(r"\s+", " ", t).upper()
        if (re.search(r"WEEKLY REPORT OF \d* ?IMPORTANT RESERVOIRS|REGION/?STATE ?WISE WEEKLY REPORT", full)
                and "SEASON" not in full and "(STATE)" not in full and "NAME OF BASIN" not in full):
            res_i.append(i)
        elif re.search(r"STATUS OF CURRENT STORAGE|TABLE ?- ?0?1\b|BASINWISE|BASIN WISE|NAME OF BASIN", full):
            tab_i.append(i)
        elif ("SEASON" not in full and "(STATE)" not in full
              and len(MAIN_ROW.findall(_fix("\n" + t + "\n"))) >= 5):
            res_i.append(i)                    # reservoir page printed without the table heading
    with pdfplumber.open(path) as pdf:
        texts = list(quick)
        for i in tab_i:
            try:
                t = pdf.pages[i].extract_text(x_tolerance=1.5) or ""
                if t.count("(cid:") < 20 and i not in ocred:
                    texts[i] = t
            except Exception:
                pass
        pages = []
        for i in res_i:
            try:
                ln = _lines(pdf.pages[i])
            except Exception:
                ln = []
            plain = i in ocred or sum(l["text"].count("(cid:") for l in ln) > 20 or not ln
            if plain:
                # font without a usable ToUnicode map for pdfminer (or a scan): pdfium's / tesseract's text instead
                ln = [{"text": x, "top": 10.0 * k, "bottom": 10.0 * k + 8, "x0": 0.0}
                      for k, x in enumerate(quick[i].split("\n"))]
            pages.append({"lines": ln, "plain": plain})
        rows = parse_reservoir_pages(pages)
        if ocred:
            for r in rows:
                r["ocr"] = 1
    d = bulletin_date(quick[:8] + [quick[i] for i in res_i[:1]], rows)
    if d:
        fix_obs_dates(d, rows)
    tot = parse_totals(texts)
    return d, rows, tot


# ------------------------------------------------------------------------------------------------ storing
def _computed(rows, region=None):
    rs = [r for r in rows if (region is None or r["region"] == region) and r["live_cap_frl_bcm"]]
    cap = sum(r["live_cap_frl_bcm"] for r in rs)
    if not rs or not cap:
        return None
    cur = sum(r["live_storage_bcm"] or 0 for r in rs)
    wl = [(r["live_cap_frl_bcm"], r["pct_last_year"]) for r in rs if r["pct_last_year"] is not None]
    wn = [(r["live_cap_frl_bcm"], r["pct_normal"]) for r in rs if r["pct_normal"] is not None]
    ly = sum(c * p / 100 for c, p in wl)
    nm = sum(c * p / 100 for c, p in wn)
    return {"n": len(rs), "cap": cap, "cur": cur, "pct": 100 * cur / cap, "ly": ly, "normal": nm,
            "pct_ly": 100 * ly / sum(c for c, _ in wl) if wl else None,
            "pct_normal": 100 * nm / sum(c for c, _ in wn) if wn else None, "src": "computed"}


def _vet_ocr(con, rows):
    """Rows OCR'd from a scanned bulletin: keep only those whose FRL + live capacity match a reservoir seen in the
    text-PDF weeks (which also fixes OCR'd name spellings) and whose % of capacity agrees with storage/capacity."""
    keep = []
    for r in rows:
        cap, sto, pct = r["live_cap_frl_bcm"], r["live_storage_bcm"], r["pct_capacity"]
        if not cap or sto is None or pct is None or abs(100 * sto / cap - pct) > 2.5:
            continue
        m = con.execute("SELECT reservoir, name_raw, state, region FROM cwc_reservoir_weekly WHERE source NOT LIKE 'scan%' "
                        "AND ABS(frl_m-?)<0.02 AND ABS(live_cap_frl_bcm-?)<0.0006 AND date BETWEEN ? AND ? "
                        "GROUP BY reservoir ORDER BY COUNT(*) DESC LIMIT 1",
                        (r["frl_m"] or -1, cap, "2015-01-01", "2020-12-31")).fetchone()
        if m:
            r["name_raw"], r["state"], r["region"] = m[1], r["state"] or m[2], r["region"] or m[3]
            keep.append(r)
    return keep


def to_db(d, rows, tot, fname, con=None):
    """Write one bulletin: reservoir rows + national/regional/hydel series. Returns number of reservoir rows."""
    from scrapers.coal_supply import put
    own = con is None
    con = con or connect()
    con.executescript(SCHEMA)
    ocr = any(r.get("ocr") for r in rows)
    if ocr:
        rows = _vet_ocr(con, rows)
    starred = any(r["hydro_flag"] for r in rows)
    recs, seen = [], {}
    for r in rows:
        key = norm_name(r["name_raw"]) if r["name_raw"] else f"UNNAMED {r['sno']} {r['state']}"
        if key in seen:                      # two reservoirs normalising alike: qualify by state
            key = f"{key} ({r['state'] or r['sno']})"
        seen[key] = 1
        recs.append((d, key, r["name_raw"], r["state"], r["region"], r["frl_m"], r["level_m"], r["live_cap_frl_bcm"],
                     r["live_storage_bcm"], r["obs_date"], r["pct_capacity"], r["pct_last_year"], r["pct_normal"],
                     r["irr_cca_th_ha"], r["hydel_mw"], (1 if r["hydro_flag"] else 0) if starred else None, fname))
    with con:
        con.execute("DELETE FROM cwc_reservoir_weekly WHERE date=?", (d,))
        con.executemany("INSERT OR REPLACE INTO cwc_reservoir_weekly VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", recs)
    if own:
        con.close()
    src = f"{SRC} ({fname})"
    ser = []
    for reg in ["AllIndia", "Northern", "Eastern", "Western", "Central", "Southern"]:
        t = tot.get(reg) or (None if ocr else _computed(rows, None if reg == "AllIndia" else reg))
        if not t:
            continue
        s = src if t["src"] != "computed" else src + " [summed from reservoir rows]"
        ser += [(f"cwc_storage_w:{reg}", d, round(t["cur"], 4), "BCM", s),
                (f"cwc_capacity_w:{reg}", d, round(t["cap"], 4), "BCM", s),
                (f"cwc_pct_w:{reg}", d, round(t["pct"], 2), "%", s)]
        if t.get("pct_ly") is not None:
            ser.append((f"cwc_pct_lastyear_w:{reg}", d, round(t["pct_ly"], 2), "%", s))
        if t.get("pct_normal") is not None:
            ser.append((f"cwc_pct_normal_w:{reg}", d, round(t["pct_normal"], 2), "%", s))
        if t["src"] in ("table01", "basin", "note") and t.get("ly") is not None:
            ser += [(f"cwc_storage_lastyear_w:{reg}", d, round(t["ly"], 4), "BCM", s),
                    (f"cwc_storage_normal_w:{reg}", d, round(t["normal"], 4), "BCM", s)]
        if t.get("n") and not ocr:
            ser.append((f"cwc_n_w:{reg}", d, t["n"], "reservoirs", s))
    for grp, mw in (("Hydel", 0), ("Hydel60", 60)):
        hy = [r for r in rows if (r["hydel_mw"] or 0) > mw - (1e-9 if mw else 0) and r["live_cap_frl_bcm"]]
        if not hy or ocr:                     # an OCR'd bulletin has only part of its rows
            continue
        cap = sum(r["live_cap_frl_bcm"] for r in hy)
        cur = sum(r["live_storage_bcm"] or 0 for r in hy)
        s = src + (" [reservoirs with hydel MW > 0]" if not mw else " [reservoirs with hydel >= 60 MW]")
        ser += [(f"cwc_storage_w:{grp}", d, round(cur, 4), "BCM", s), (f"cwc_capacity_w:{grp}", d, round(cap, 4), "BCM", s),
                (f"cwc_pct_w:{grp}", d, round(100 * cur / cap, 2), "%", s),
                (f"cwc_hydel_mw_w:{grp}", d, round(sum(r["hydel_mw"] for r in hy), 1), "MW", s),
                (f"cwc_n_w:{grp}", d, len(hy), "reservoirs", s)]
        wl = [(r["live_cap_frl_bcm"], r["pct_last_year"]) for r in hy if r["pct_last_year"] is not None]
        wn = [(r["live_cap_frl_bcm"], r["pct_normal"]) for r in hy if r["pct_normal"] is not None]
        if wl:
            ser.append((f"cwc_pct_lastyear_w:{grp}", d, round(sum(c * p for c, p in wl) / sum(c for c, _ in wl), 2), "%", s))
        if wn:
            ser.append((f"cwc_pct_normal_w:{grp}", d, round(sum(c * p for c, p in wn) / sum(c for c, _ in wn), 2), "%", s))
    put(ser)
    return len(recs)


def fix_unnamed(con=None):
    """Rows whose name cell is blank in the PDF: identify the reservoir by (state, FRL, live capacity) from other weeks."""
    own = con is None
    con = con or connect()
    fixed = 0
    for d, key, st, frl, cap in con.execute("SELECT date, reservoir, state, frl_m, live_cap_frl_bcm FROM cwc_reservoir_weekly "
                                            "WHERE reservoir LIKE 'UNNAMED %'").fetchall():
        m = con.execute("SELECT reservoir, COUNT(*) FROM cwc_reservoir_weekly WHERE reservoir NOT LIKE 'UNNAMED %' "
                        "AND state IS ? AND ABS(frl_m-?)<0.02 AND ABS(live_cap_frl_bcm-?)<0.0006 "
                        "GROUP BY reservoir ORDER BY 2 DESC LIMIT 1", (st, frl, cap)).fetchone()
        if m and not con.execute("SELECT 1 FROM cwc_reservoir_weekly WHERE date=? AND reservoir=?", (d, m[0])).fetchone():
            with con:
                con.execute("UPDATE cwc_reservoir_weekly SET reservoir=? WHERE date=? AND reservoir=?", (m[0], d, key))
            fixed += 1
    if own:
        con.close()
    return fixed


def merge_variants(con=None):
    """Fold rare name keys (river-column layout of 28.04.2016, OCR, truncated or header-prefixed names) into the
    established key with the same FRL and live capacity."""
    own = con is None
    con = con or connect()
    cnt = dict(con.execute("SELECT reservoir, COUNT(*) FROM cwc_reservoir_weekly GROUP BY reservoir"))
    n = 0
    for key, c in cnt.items():
        if c >= 10:
            continue
        for d, frl, cap in con.execute("SELECT date, frl_m, live_cap_frl_bcm FROM cwc_reservoir_weekly WHERE reservoir=?",
                                       (key,)).fetchall():
            m = con.execute("SELECT reservoir, state, region, COUNT(*) FROM cwc_reservoir_weekly WHERE reservoir != ? "
                            "AND ABS(frl_m-?)<0.06 AND ABS(live_cap_frl_bcm-?)<0.0015 GROUP BY reservoir "
                            "HAVING COUNT(*)>=20 ORDER BY 4 DESC", (key, frl or -1, cap or -1)).fetchall()
            if len(m) == 1 and not con.execute("SELECT 1 FROM cwc_reservoir_weekly WHERE date=? AND reservoir=?",
                                                (d, m[0][0])).fetchone():
                with con:
                    con.execute("UPDATE cwc_reservoir_weekly SET reservoir=?, state=?, region=? WHERE date=? AND reservoir=?",
                                (m[0][0], m[0][1], m[0][2], d, key))
                n += 1
    if own:
        con.close()
    return n


def fill_state(con=None):
    """Rows read from pdfium fallback text lose their state/region headers: take them from the same reservoir's other weeks."""
    own = con is None
    con = con or connect()
    with con:
        n = con.execute("""UPDATE cwc_reservoir_weekly SET
            state = (SELECT w.state FROM cwc_reservoir_weekly w WHERE w.reservoir = cwc_reservoir_weekly.reservoir
                     AND w.state IS NOT NULL GROUP BY w.state ORDER BY COUNT(*) DESC LIMIT 1),
            region = (SELECT w.region FROM cwc_reservoir_weekly w WHERE w.reservoir = cwc_reservoir_weekly.reservoir
                     AND w.region IS NOT NULL GROUP BY w.region ORDER BY COUNT(*) DESC LIMIT 1)
            WHERE state IS NULL OR region IS NULL""").rowcount
    if own:
        con.close()
    return n


def check(d, rows, tot):
    """Sanity checks -> list of warnings."""
    w = []
    if not d:
        w.append("no bulletin date")
    if len(rows) < 80:
        w.append(f"only {len(rows)} reservoir rows")
    a = tot.get("AllIndia")
    if a and rows:
        s = sum(r["live_storage_bcm"] or 0 for r in rows)
        c = sum(r["live_cap_frl_bcm"] or 0 for r in rows)
        if abs(s - a["cur"]) > 0.02 * a["cur"] + 0.05:
            w.append(f"sum storage {s:.3f} vs total {a['cur']:.3f}")
        if abs(c - a["cap"]) > 0.02 * a["cap"] + 0.05:
            w.append(f"sum capacity {c:.3f} vs total {a['cap']:.3f}")
    else:
        w.append("no all-India total")
    if any(r["region"] is None for r in rows):
        w.append(f"{sum(r['region'] is None for r in rows)} rows without region")
    return w


def _store(item, st, bydate):
    f, d, rows, tot = item
    w = check(d, rows, tot)
    if not d or not (rows or tot):
        st["fail"].append((f.name, "; ".join(w)))
        return
    if d in bydate and len(rows) <= bydate[d]:   # same bulletin posted twice (old site + RSMS, re-upload): keep fuller
        st["warn"].append((f.name, d, f"duplicate of {d}, kept the other file"))
        return
    bydate[d] = len(rows)
    n = to_db(d, rows, tot, f.name)
    st["ok"] += 1
    if w:
        st["warn"].append((f.name, d, "; ".join(w)))
    print(f"  {f.name} -> {d} {n} reservoirs  AllIndia {tot.get('AllIndia', {}).get('cur')}"
          f" {'WARN ' + '; '.join(w) if w else ''}", flush=True)


def _parse_safe(f):
    try:
        return parse_pdf(f)
    except Exception as e:
        return f"parse error {e!r}"[:200]


def process(paths, force=False):
    """Parse PDFs and store. Skips bulletins already in the table unless force. Returns stats."""
    con = connect()
    con.executescript(SCHEMA)
    done = {r[0] for r in con.execute("SELECT DISTINCT source FROM cwc_reservoir_weekly")}
    con.close()
    st = {"ok": 0, "skip": 0, "fail": [], "warn": []}
    bydate, deferred = {}, []
    todo = [Path(f) for f in sorted(paths) if force or Path(f).name not in done]
    st["skip"] = len(paths) - len(todo)
    if len(todo) > 8:                          # backfill: parse in parallel, store in order
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as ex:
            results = list(ex.map(_parse_safe, todo, chunksize=4))
    else:
        results = [_parse_safe(f) for f in todo]
    for f, res in zip(todo, results):
        if isinstance(res, str):
            st["fail"].append((f.name, res))
            continue
        d, rows, tot = res
        if any(r.get("ocr") for r in rows):
            # scanned (OCR'd) bulletins go last: their rows are vetted against the text-PDF weeks already stored
            deferred.append((f, d, rows, tot))
        else:
            _store((f, d, rows, tot), st, bydate)
    for item in deferred:
        _store(item, st, bydate)
    st["unnamed_fixed"] = fix_unnamed()
    st["merged"] = merge_variants()
    st["state_filled"] = fill_state()
    return st


def run():
    """Newest bulletins: first RSMS listing page, download any new PDF, parse, store."""
    try:
        items = list_rsms(max_pages=1)
    except Exception as e:
        log("cwc_reservoirs", "error", f"rsms listing: {e!r}")
        items = []
    paths = download(items)
    st = process(paths)
    log("cwc_reservoirs", "ok" if not st["fail"] else "partial",
        f"new {st['ok']} skipped {st['skip']} failed {len(st['fail'])} {st['fail'][:3]}")
    return st


def backfill(reparse=False):
    if reparse:
        paths = sorted(p for p in RAW.glob("*.pdf"))
    else:
        items = list_rsms() + list_old()
        (RAW / "listing.json").write_text(json.dumps(items, indent=0))
        paths = download(items)
    st = process(paths, force=reparse)
    print(f"ok {st['ok']} skipped {st['skip']} failed {len(st['fail'])}")
    for x in st["fail"]:
        print("  FAIL", *x)
    for x in st["warn"]:
        print("  WARN", *x)
    log("cwc_reservoirs", "ok", f"backfill ok {st['ok']} failed {len(st['fail'])} warn {len(st['warn'])}")
    return st


if __name__ == "__main__":
    if "--reparse" in sys.argv:
        backfill(reparse=True)
    elif "--backfill" in sys.argv:
        backfill()
    else:
        print(run())
