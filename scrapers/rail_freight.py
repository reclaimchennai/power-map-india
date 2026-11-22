"""Indian Railways freight loading by commodity (FOIS RailSAHAY "Dristi" figures), million tonnes.

    python -m scrapers.rail_freight

RailSAHAY's commodity pages show loading Yesterday / Last 7 days / Month to date / Year to date (financial year) for every
commodity group, from one JSON call. Coal & coke is about half of everything the railways load and covers ALL coal on rail
(Coal India, Singareni, captive and commercial mines, imported coal from the ports, coke), where the CIL rakes page covers
Coal India alone. The call has no date and no history, so we snapshot it every hour:

  rail_loading_snap   every distinct set of figures and when it was first seen (the raw record)
  coal_supply         rail_load_d:<group>  (yesterday), rail_load_7d, rail_load_mtd, rail_load_ytd, dated by the day loaded

Dating: the figures are for "yesterday", the IST day before the one on which a new set of figures first appears. Each new day is
checked against the month to date (previous MTD + yesterday = new MTD); a mismatch is logged, so a skipped or late update shows.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from store import connect, log
from scrapers.netfetch import get

URL = "https://www.fois.indianrail.gov.in/RailSAHAY/GG_CmdtViewJson?Help=DRISTI_DATA"
SRC = "Indian Railways FOIS RailSAHAY (commodity loading)"
IST = timezone(timedelta(hours=5, minutes=30))
FIELDS = {"d": "LdngTngeDlyC", "7d": "LdngTngeWklyC", "mtd": "LdngTngeMnthC", "ytd": "LdngTngeYrC"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS rail_loading_snap (
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, day TEXT NOT NULL, cmdt TEXT NOT NULL,
    d_mt REAL, w7_mt REAL, mtd_mt REAL, ytd_mt REAL,
    PRIMARY KEY (day, cmdt, d_mt, mtd_mt, ytd_mt)
);
"""


def group(name):
    """'COAL AND COKE' -> 'Coal and coke'; 'OTHERS*' -> 'Others'."""
    return re.sub(r"[^A-Za-z ,]", "", name).strip().capitalize()


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch():
    r = get(URL, method="POST", timeout=60, verify=False,
            headers={"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest",
                     "Referer": "https://www.fois.indianrail.gov.in/RailSAHAY/index.jsp"})
    d = json.loads(r.text)
    if d.get("Stts") != "S" or not d.get("DristiData"):
        raise ValueError(f"RailSAHAY: {d.get('Stts')} {d.get('ErorMesg')!r}")
    out = {}
    for x in d["DristiData"]:
        v = {k: num(x.get(f)) for k, f in FIELDS.items()}
        if v["d"] is None or v["mtd"] is None:
            continue
        out[group(x["Cmdt"])] = v
    if "Coal and coke" not in out:
        raise ValueError(f"RailSAHAY: no coal row in {list(out)}")
    return out


def run():
    now = datetime.now(timezone.utc)
    figs = fetch()
    con = connect()
    con.executescript(SCHEMA)
    coal = figs["Coal and coke"]
    # the set of figures already stored, if this is the same one: just mark it seen
    prev = con.execute("SELECT day, d_mt, mtd_mt, ytd_mt FROM rail_loading_snap WHERE cmdt='Coal and coke' "
                       "ORDER BY first_seen DESC LIMIT 1").fetchone()
    same = bool(prev) and (prev[1], prev[2], prev[3]) == (coal["d"], coal["mtd"], coal["ytd"])
    day = prev[0] if same else (now.astimezone(IST).date() - timedelta(days=1)).isoformat()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    with con:
        for g, v in figs.items():
            con.execute("""INSERT INTO rail_loading_snap VALUES (?,?,?,?,?,?,?,?)
                           ON CONFLICT(day, cmdt, d_mt, mtd_mt, ytd_mt) DO UPDATE SET last_seen=excluded.last_seen""",
                        (ts, ts, day, g, v["d"], v["7d"], v["mtd"], v["ytd"]))
            for k, val in v.items():
                if val is not None:
                    con.execute("INSERT OR REPLACE INTO coal_supply VALUES (?,?,?,?,?)", (f"rail_load_{k}:{g}", day, val, "Mt", SRC))
    con.close()
    note = ""
    if not same and prev:
        # consistency: same month -> MTD grows by yesterday's loading; a new month -> MTD restarts at yesterday's
        pday = datetime.fromisoformat(prev[0]).date()
        nday = datetime.fromisoformat(day).date()
        expect = coal["d"] if nday.month != pday.month else prev[2] + coal["d"]
        if (nday - pday).days != 1 or abs(coal["mtd"] - expect) > 0.06:
            note = f"; check: previous set {prev[0]} MTD {prev[2]}, expected MTD {expect:.2f} got {coal['mtd']} ({(nday - pday).days} days apart)"
    if note:  # kept apart from the job's own "ok", which paces the hourly runs
        log("rail_freight_check", "info", f"{day}{note}")
    log("rail_freight", "ok",
        f"{day}: coal {coal['d']} Mt, 7d {coal['7d']}, MTD {coal['mtd']}, FY {coal['ytd']}" + (" (unchanged)" if same else " (new)") + note)
    return day, coal, same


if __name__ == "__main__":
    print(run())
