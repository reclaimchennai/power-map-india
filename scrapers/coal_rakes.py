"""Coal rakes (trains) supplied and loaded each day at the sidings of every CIL subsidiary.

Source: CIL "CoYLA" Oracle APEX app 119, page "Rakes Data" (https://apps.coalindia.in/ords/safety/r/coyla/rakes-data),
"FOIS Rake Data: CIL Subsidiaries date-wise data" (FOIS = Indian Railways' Freight Operations Information System).
The table region loads by APEX AJAX whose item values are checksum-protected, so the page is driven in a real
browser: set P18_FROM_DATE / P18_TO_DATE without firing change events, refresh the region, read the table.
Values are summed over the date range, so we ask for one day at a time. Data exist from about Jan-Mar 2022
(earlier days come back as rows of zeros, which are not stored).

Rows go to coal_supply (see coal_supply.py) as
  rakes_loaded_d:<CO>    rakes loaded on the day (CO = MCL, NCL, SECL, CCL, ECL, WCL, BCCL, NEC; CIL = sum)
  rakes_supplied_d:<CO>  empty rakes placed by the railways at the company's sidings on the day
The page also shows "Rakes Sanctioned" (a running indent figure, not a daily flow): not stored.
No sector split (power / non-power) is offered anywhere in the app (menu: India Overall, company production /
offtake, lignite, major mines, rakes data + its siding-wise dialog, units lagging), so there is no rakes_power_d.

    python -m scrapers.coal_rakes               # last 3 days
    python -m scrapers.coal_rakes --backfill    # yesterday back to 2022-01-01, skipping stored days
"""
import html as htmllib
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote_plus

from scrapers.coal_supply import put, SCHEMA
from store import connect, log

URL = "https://apps.coalindia.in/ords/safety/r/coyla/rakes-data"
REGION = "R979029914913255862"
SRC = "CIL Rakes Data (FOIS), apps.coalindia.in"
CHROME = os.path.expanduser("~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome")
START = date(2022, 1, 1)          # the table has rows of zeros before ~Mar 2022
COS = ("MCL", "NCL", "SECL", "CCL", "ECL", "WCL", "BCCL", "NEC")



def table_rows(page):
    """Cells of every row of the first table in an HTML fragment."""
    m = re.search(r"<table.*?</table>", page, re.S | re.I)
    if not m:
        return []
    out = []
    for tr in re.findall(r"<tr.*?</tr>", m.group(0), re.S | re.I):
        cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
        if cells:
            out.append(cells)
    return out


class Rakes:
    """One browser page on the Rakes Data page, reused for many days."""

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._p = sync_playwright().start()
        kw = {"headless": True, "args": ["--no-sandbox"]}
        if Path(CHROME).exists():
            kw["executable_path"] = CHROME
        self.browser = None
        try:
            self.browser = self._p.chromium.launch(**kw)
            self.page = None
            self.reload()
        except Exception:
            # the CoYLA page often times out; stop Playwright here, or its event loop stays alive and every later
            # sync_playwright() in the same collect pass (cwc_reservoirs) fails with "Sync API inside the asyncio loop"
            self.close()
            raise

    def reload(self):
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
        self.page = self.browser.new_page(ignore_https_errors=True)
        self.page.goto(URL, wait_until="networkidle", timeout=120000)
        self.page.wait_for_function("() => window.apex && apex.region && apex.region(%r)" % REGION, timeout=60000)

    def close(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            self._p.stop()

    def day(self, d):
        """{company: (supplied, loaded)} for day d; {} when the page has no rows."""
        pg, s = self.page, d.strftime("%d-%m-%Y")
        pg.evaluate("""(s) => { apex.item('P18_FROM_DATE').setValue(s, null, true);
                               apex.item('P18_TO_DATE').setValue(s, null, true); }""", s)
        # read the region's AJAX reply itself (the DOM can lag a refresh behind), and only the reply to
        # the request that submitted this very date
        want = lambda r: ("wwv_flow.ajax" in r.url and r.request.post_data
                          and s in unquote_plus(r.request.post_data))
        with pg.expect_response(want, timeout=60000) as ri:
            pg.evaluate("(rid) => { apex.region(rid).refresh(); }", REGION)
        resp = ri.value
        if resp.status != 200:
            raise RuntimeError(f"ajax status {resp.status}")
        js = resp.json()
        if js.get("status") != "success":
            raise RuntimeError(f"ajax reply {str(js)[:200]}")
        body = js.get("content") or ""
        if unquote_plus(resp.request.post_data).count(s) < 2:
            raise RuntimeError("request did not carry both dates")
        rows = table_rows(body)
        if not rows:
            return {}
        head = [c.lower() for c in rows[0]]
        try:
            i_sup = next(i for i, c in enumerate(head) if "supplied" in c)
            i_load = next(i for i, c in enumerate(head) if "loaded" in c)
        except StopIteration:
            if any("no data" in " ".join(r).lower() for r in rows):
                return {}
            raise RuntimeError(f"unexpected table header {rows[0]}")
        out = {}
        for r in rows[1:]:
            co = r[0].strip().upper()
            if co not in COS or len(r) <= max(i_sup, i_load):
                continue
            try:
                out[co] = (float(r[i_sup].replace(",", "") or 0), float(r[i_load].replace(",", "") or 0))
            except ValueError:
                continue
        return out


def to_rows(d, data):
    """Rows for one day. A measure that is zero for every company is treated as missing, not stored (before the
    feed started the page returns rows of zeros; on its first day, 2022-03-26, only 'supplied' was filled)."""
    p = d.isoformat()
    rows = []
    for k, measure in ((0, "rakes_supplied_d"), (1, "rakes_loaded_d")):
        if not any(v[k] for v in data.values()):
            continue
        rows += [(f"{measure}:{co}", p, v[k], "rakes", SRC) for co, v in data.items()]
        rows.append((f"{measure}:CIL", p, sum(v[k] for v in data.values()), "rakes", SRC))
    return rows


def stored_days():
    con = connect()
    con.executescript(SCHEMA)
    try:
        return {r[0] for r in con.execute("SELECT period FROM coal_supply WHERE series IN ('rakes_loaded_d:CIL', 'rakes_supplied_d:CIL')")}
    finally:
        con.close()


def run(days=3):
    """The last `days` days (yesterday backwards) in one browser session; overwrites (FOIS revises the latest day)."""
    r, n, got = Rakes(), 0, 0
    try:
        for k in range(1, days + 1):
            d = date.today() - timedelta(days=k)
            try:
                rows = to_rows(d, r.day(d))
            except Exception as e:
                print(d, "error", e, flush=True)
                r.reload()
                continue
            put(rows)
            n += len(rows)
            got += bool(rows)
    finally:
        r.close()
    log("coal_rakes", "ok" if n else "empty", f"{got}/{days} days, {n} rows")
    return n


def backfill(start=START, reload_every=100, pause=1.0):
    have = stored_days()
    todo = []
    d = date.today() - timedelta(days=1)
    while d >= start:
        if d.isoformat() not in have:
            todo.append(d)
        d -= timedelta(days=1)
    print(f"{len(todo)} days to fetch", flush=True)
    r = Rakes()
    done = empty = errors = 0
    t0 = time.time()
    try:
        for i, d in enumerate(todo):
            if i and i % reload_every == 0:
                r.reload()
            for attempt in range(3):
                try:
                    rows = to_rows(d, r.day(d))
                    break
                except Exception as e:
                    print(d, "error", attempt, str(e)[:200], flush=True)
                    time.sleep(5 * (attempt + 1))
                    try:
                        r.reload()
                    except Exception as e2:
                        print("reload failed", e2, flush=True)
            else:
                errors += 1
                continue
            if rows:
                put(rows)
                done += 1
                tot = next((v for s, _, v, _, _ in rows if s == "rakes_loaded_d:CIL"), None)
                print(d, "loaded", tot, f"[{i + 1}/{len(todo)} {time.time() - t0:.0f}s]", flush=True)
            else:
                empty += 1
                print(d, "no data", flush=True)
            time.sleep(pause)
    finally:
        r.close()
    log("coal_rakes", "ok", f"backfill {done} days stored, {empty} empty, {errors} errors")
    return done, empty, errors


if __name__ == "__main__":
    if "--backfill" in sys.argv:
        start = START
        if "--start" in sys.argv:
            start = datetime.strptime(sys.argv[sys.argv.index("--start") + 1], "%Y-%m-%d").date()
        print(backfill(start))
    else:
        print(run(int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 3))
