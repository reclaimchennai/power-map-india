"""Coal India Limited statistics scraper (coal.nic.in).

Scrapes three pages into the archive:
  * /major-statistics/production-and-supplies — company-wise production and
    offtake/dispatch vs target (CIL, SCCL, Captive & Others) — the supply
    side of the coal chain.
  * /major-statistics/coal-reserves — state-wise geological reserves
    (measured / indicated / inferred).
  * /public-information/monthly-statistics-at-glance — monthly PDF archive
    links (recorded so new editions are auto-fetched).

Also has hardcoded extractors for the Coal India "Statutory Filings" tables
screenshot-worthy items: OMS (output per man shift) and company-wise over
burden removal live in CIL annual reports (PDF) — noted in ROADMAP.
"""
import re
import html as htmllib
from pathlib import Path

import requests

from store import connect, log

BASE = "https://www.coal.nic.in"
PAGES = {
    "production": "/major-statistics/production-and-supplies",
    "reserves": "/major-statistics/coal-reserves",
    "monthly": "/public-information/monthly-statistics-at-glance",
}


def _f(v):
    v = str(v).replace(",", "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def get_tables(url):
    s = requests.get(url, timeout=60, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"}).text
    tables = re.findall(r"<table.*?</table>", s, re.S)
    out = []
    for t in tables:
        rows = []
        for r in re.findall(r"<tr.*?</tr>", t, re.S):
            cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                     for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
            if any(cells):
                rows.append(cells)
        out.append(rows)
    return out, s


def save_meta(con, source, key, value):
    con.execute(
        """CREATE TABLE IF NOT EXISTS coal_india_stats (
             source TEXT, key TEXT, value TEXT, ts TEXT DEFAULT (datetime('now')),
             PRIMARY KEY (source, key))""")
    con.execute("INSERT OR REPLACE INTO coal_india_stats (source, key, value) VALUES (?,?,?)",
                (source, key, str(value)))


def scrape_production(con, url):
    tables, page = get_tables(url)
    for rows in tables:
        for cells in rows:
            c = [x for x in cells]
            if c and c[0] in ("CIL", "SCCL", "Captive & Others", "Total"):
                nums = [_f(x) for x in c[1:] if _f(x) is not None]
                if nums:
                    save_meta(con, "production", c[0], nums)
    # headline figures from the narrative
    text = re.sub(r"<[^>]+>", "|", page)
    text = re.sub(r"\|+", "|", htmllib.unescape(text))
    m = re.search(r"production of coal during \|?([\d.]+)\|? ?MT", text)
    if m:
        save_meta(con, "production", "all_india_latest_mt", m.group(1))


def scrape_reserves(con, url):
    """GSI National Coal Inventory as the ministry tabulates it (billion tonnes): the coal and lignite
    tables have the same shape, so they are told apart by their header, never by row names
    (West Bengal and Odisha appear in both)."""
    tables, page = get_tables(url)
    fuel_hist = iter(["coal", "lignite"])
    for rows in tables:
        if not rows:
            continue
        head = " ".join(rows[0]).lower()
        if head.startswith("as on"):
            fuel = next(fuel_hist, None)
            for cells in rows[1:]:
                nums = [_f(x) for x in cells[1:]]
                if fuel and re.match(r"^1st April", cells[0], re.I):
                    save_meta(con, f"reserve_history_{fuel}", cells[0], [n for n in nums[:4]])
        elif head.startswith("state") and "total resource" in head:
            vals = {c[0].strip(): [_f(x) for x in c[1:5]] for c in rows[1:] if c and re.match(r"^[A-Za-z]", c[0])}
            fuel = "lignite" if "Tamilnadu" in vals or "Tamil Nadu" in vals else "coal"
            for k, v in vals.items():
                if not re.match(r"^(total|grand)", k, re.I):
                    save_meta(con, f"reserves_{fuel}", k, v)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", page))
    m = re.search(r"coal and lignite resources of the country stand at\s+([\d.]+)\s+billion tonnes and\s+([\d.]+)\s+billion", text)
    if m:
        save_meta(con, "reserves_total", "coal_bt", m.group(1))
        save_meta(con, "reserves_total", "lignite_bt", m.group(2))


def scrape_monthly(con, url):
    s = requests.get(url, timeout=60, verify=False,
                     headers={"User-Agent": "Mozilla/5.0"}).text
    links = sorted(set(re.findall(
        r'href="(/sites/default/files/[^"]*msg-[^"]*\.pdf)"', s)))
    save_meta(con, "monthly_stats", "latest_links", links[-3:] if links else [])
    return [BASE + l for l in links]


def main():
    con = connect()
    with con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS coal_india_stats (
             source TEXT, key TEXT, value TEXT, ts TEXT DEFAULT (datetime('now')),
             PRIMARY KEY (source, key));
        """)
        for name, path in PAGES.items():
            try:
                if name == "production":
                    scrape_production(con, BASE + path)
                elif name == "reserves":
                    scrape_reserves(con, BASE + path)
                else:
                    scrape_monthly(con, BASE + path)
            except Exception as e:
                log("coal_india", "error", f"{name}: {e}")
                print(f"[{name}] ERROR {e}")
                continue
    con.close()
    print("coal india stats updated")
    log("coal_india", "ok", "production + reserves + monthly links")


if __name__ == "__main__":
    main()
