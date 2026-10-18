"""Vidyut PRAVAH (Ministry of Power, vidyutpravah.in): demand met per 15-minute time block.

The freshest public figure for Tamil Nadu. The SLDC peakdet.pdf is issued about once a day (around
noon IST), but Vidyut Pravah shows each state's demand met for the *current* 15-minute block, plus
yesterday's peak, power bought on the exchange and the exchange price. The homepage carries the
all-India demand met (current / yesterday), the average market clearing price and surplus on the
exchange.

  homepage          every pass (≈3 s)
  Tamil Nadu page   every pass (≈17 s: the site is slow, not us)
  other states      every 60 min, 6 at a time

Table vp_blocks (ts, block, state, demand_mw, demand_yday_mw, exch_mw, exch_yday_mw, price, price_yday);
state '__INDIA__' holds the homepage figures (demand in MW, surplus in exch_mw).
"""
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
import urllib3

from scrapers import netfetch
from store import connect, log

urllib3.disable_warnings()
BASE = "https://vidyutpravah.in"
UA = {"User-Agent": "Mozilla/5.0 (reclaimchennai power map; +https://power.reclaimchennai.city)"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS vp_blocks (
    ts TEXT NOT NULL, block TEXT NOT NULL, state TEXT NOT NULL,
    demand_mw REAL, demand_yday_mw REAL, exch_mw REAL, exch_yday_mw REAL, price REAL, price_yday REAL,
    PRIMARY KEY (block, state)
);
"""


def text_of(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", html, flags=re.S)
    t = t.replace("&nbsp;", " ").replace("&#x20B9;", "₹").replace("&amp;", "&").replace("&#39;", "'")
    return re.sub(r"\s+", " ", t)


def num(s):
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError, AttributeError):
        return None


def block_of(t):
    m = re.search(r"TIME BLOCK (\d{1,2}:\d{2}) - (\d{1,2}:\d{2}) DATED (\d{1,2} \w{3} \d{4})", t)
    if not m:
        return None
    d = datetime.strptime(m.group(3), "%d %b %Y").date().isoformat()
    return f"{d} {m.group(1)}-{m.group(2)}"


def get(path, timeout=90):
    r = netfetch.get(BASE + path, retries=4, backoff=3, use_proxy=False, headers=UA, timeout=timeout, verify=False)
    return text_of(r.text)


def parse_state(t):
    g = lambda rx: num((re.search(rx, t) or [None, None])[1])
    return {
        "block": block_of(t),
        "demand_yday_mw": g(r"Demand Met YESTERDAY : ([\d,.]+)"),
        "demand_mw": g(r"Demand Met YESTERDAY : [\d,.]+ MW CURRENT : ([\d,.]+)"),
        "exch_yday_mw": g(r"Purchased From Exchange YESTERDAY : ([\d,.]+)"),
        "exch_mw": g(r"Purchased From Exchange YESTERDAY : [\d,.]+ MW CURRENT : ([\d,.]+)"),
        "price_yday": g(r"Exchange Price YESTERDAY : ([\d,.]+)"),
        "price": g(r"Exchange Price YESTERDAY : [\d,.]+ ₹/Unit CURRENT : ([\d,.]+)"),
    }


def parse_home(t):
    g = lambda rx: num((re.search(rx, t) or [None, None])[1])
    return {
        "block": block_of(t),
        "exch_mw": g(r"([\d,.]+) MW SURPLUS POWER AT POWER EXCHANGE"),     # surplus offered on the exchange
        "price": g(r"([\d,.]+) ₹/Unit AVG MARKET CLEARING PRICE"),
        "demand_mw": (g(r"([\d,.]+) GW DEMAND MET \(CURRENT\)") or 0) * 1000 or None,
        "demand_yday_mw": (g(r"([\d,.]+) GW DEMAND MET \(YESTERDAY\)") or 0) * 1000 or None,
    }


def save(con, state, rec):
    if not rec.get("block") or rec.get("demand_mw") is None:
        return False
    con.execute("INSERT OR REPLACE INTO vp_blocks VALUES (?,?,?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), rec["block"], state,
                 rec.get("demand_mw"), rec.get("demand_yday_mw"), rec.get("exch_mw"), rec.get("exch_yday_mw"),
                 rec.get("price"), rec.get("price_yday")))
    return True


def state_slugs(home_html):
    return sorted(set(re.findall(r'href="/state-data/([A-Za-z-]+)"', home_html)))


def run(all_states=False):
    con = connect()
    con.executescript(SCHEMA)
    r = netfetch.get(BASE + "/", retries=4, backoff=3, use_proxy=False, headers=UA, timeout=60, verify=False)
    r.raise_for_status()
    n = 0
    with con:
        n += save(con, "__INDIA__", parse_home(text_of(r.text)))
    slugs = state_slugs(r.text) if all_states else ["tamil-nadu"]

    def one(slug):
        try:
            return slug, parse_state(get(f"/state-data/{slug}"))
        except Exception as e:
            return slug, {"error": str(e)}
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(one, slugs))
    with con:
        for slug, rec in results:
            name = slug.replace("-", " ").title().replace("And ", "and ")
            n += save(con, name, rec)
    con.close()
    log("vidyut_pravah_all" if all_states else "vidyut_pravah", "ok", f"{n} rows")
    return n


if __name__ == "__main__":
    import sys
    t0 = time.time()
    print(run(all_states="--all" in sys.argv), f"{time.time() - t0:.0f}s")
