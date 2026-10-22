#!/usr/bin/env python3
"""Write data/latest/: small, plain (uncompressed, sorted) CSVs of the series that move every day, committed daily.

    python tools/export_latest.py --db /path/to/power.db

The full tables (CSV.gz / Parquet) and the SQLite database are refreshed daily as assets of the rolling
`data-latest` release instead of in git (re-committing ~60 MB of compressed files a day would bloat the
history). These files are plain text in a stable order, so a day's commit is only the new rows.

  coal_stock_national_daily.csv  all-India coal at power stations per CEA report day (2017-08 on)
  coal_rakes_daily.csv           coal trains supplied / loaded per day by Coal India subsidiary (FOIS, 2022-03 on)
  coal_production_daily.csv      production and offtake per day by company, '000 t (CIL MOC dashboard, 2023-10 on)
  coal_supply_monthly.csv        every monthly series in coal_supply (production, dispatch, rakes, ports, imports, gas...)
  reservoirs_weekly.csv          all-India and regional reservoir storage (CWC, 2015 on)
"""
import argparse, csv, sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "latest"
# a plant row over 3 Mt and four times its normative stock is a typo in CEA's report (same rule as the site)
GOOD = "NOT (stock_total_kt > 3000 AND stock_total_kt > 4 * coalesce(norm_stock_kt, 0))"


def dump(con, name, sql, header):
    rows = con.execute(sql).fetchall()
    with open(OUT / name, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return name, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    db = ap.parse_args().db
    OUT.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    done = [
        dump(con, "coal_stock_national_daily.csv", f"""
            SELECT date, count(*), round(sum(stock_total_kt)/1000, 3), round(sum(stock_import_kt)/1000, 3),
                   round(sum(daily_req_kt), 1), round(sum(CASE WHEN daily_req_kt > 0 THEN stock_total_kt END) / sum(daily_req_kt), 2),
                   sum(critical), round(sum(receipt_kt), 1), round(sum(consumption_kt), 1), round(sum(capacity_mw))
            FROM coal_plants_daily WHERE section NOT LIKE 'C.%' AND {GOOD}
            GROUP BY date HAVING count(*) >= 90 ORDER BY date""",
             ["date", "plants", "stock_mt", "import_stock_mt", "requirement_kt_per_day", "days_of_coal_at_requirement",
              "critical_plants", "receipt_kt", "consumption_kt", "capacity_mw"]),
        dump(con, "coal_rakes_daily.csv", """
            SELECT period, substr(series, instr(series, ':') + 1) co,
                   max(CASE WHEN series LIKE 'rakes_supplied_d:%' THEN value END),
                   max(CASE WHEN series LIKE 'rakes_loaded_d:%' THEN value END)
            FROM coal_supply WHERE series LIKE 'rakes_supplied_d:%' OR series LIKE 'rakes_loaded_d:%'
            GROUP BY period, co ORDER BY period, co""", ["date", "company", "rakes_supplied", "rakes_loaded"]),
        dump(con, "coal_production_daily.csv", """
            SELECT period, substr(series, instr(series, ':') + 1) co,
                   max(CASE WHEN series LIKE 'prod_d:%' THEN value END),
                   max(CASE WHEN series LIKE 'offtake_d:%' THEN value END)
            FROM coal_supply WHERE series LIKE 'prod_d:%' OR series LIKE 'offtake_d:%'
            GROUP BY period, co ORDER BY period, co""", ["date", "company", "production_kt", "offtake_kt"]),
        dump(con, "coal_supply_monthly.csv", """
            SELECT series, period, value, unit, source FROM coal_supply
            WHERE length(period) = 7 ORDER BY series, period""", ["series", "month", "value", "unit", "source"]),
        dump(con, "reservoirs_weekly.csv", """
            SELECT period, substr(series, instr(series, ':') + 1) region,
                   max(CASE WHEN series LIKE 'cwc_storage_w:%' THEN value END),
                   max(CASE WHEN series LIKE 'cwc_capacity_w:%' THEN value END),
                   max(CASE WHEN series LIKE 'cwc_pct_w:%' THEN value END),
                   max(CASE WHEN series LIKE 'cwc_pct_lastyear_w:%' THEN value END),
                   max(CASE WHEN series LIKE 'cwc_pct_normal_w:%' THEN value END)
            FROM coal_supply WHERE series LIKE 'cwc_%_w:%' AND series NOT LIKE 'cwc_n_w:%'
            GROUP BY period, region ORDER BY period, region""",
             ["date", "region", "live_storage_bcm", "live_capacity_bcm", "pct_of_capacity", "pct_same_week_last_year", "pct_10yr_normal"]),
    ]
    con.close()
    lines = "\n".join(f"| [`{n}`]({n}) | {r:,} |" for n, r in done)
    (OUT / "README.md").write_text(
        "# Latest daily series\n\n"
        f"Updated {datetime.now(timezone.utc):%Y-%m-%d} (UTC) from the live collector. Plain CSV, one row per day / week / month, "
        "sorted, so each day's commit shows only the new rows. Full tables in CSV.gz / Parquet and the whole SQLite database: "
        "the [`data-latest` release](https://github.com/reclaimchennai/power-map-india/releases/tag/data-latest), refreshed daily.\n\n"
        "| File | Rows |\n|---|---|\n" + lines + "\n\n"
        "- `coal_stock_national_daily`: CEA Daily Coal Stock Report summed over operating plants. `days_of_coal_at_requirement` = stock of "
        "plants that state a requirement ÷ that daily requirement (85% PLF), comparable across the whole record. CEA widened the report on "
        "2021-11-14 (about 27 more plants). Receipt from 2021-09, consumption from 2021-11. Rows with an obvious typo (over 3 Mt and four "
        "times the plant's normative stock) are left out.\n"
        "- `coal_rakes_daily`: CIL's Rakes Data page (FOIS); CIL is the sum of its subsidiaries. Loaded from 2022-03-27.\n"
        "- `coal_production_daily`: CIL MOC dashboard, on-day production and offtake in thousand tonnes (CIL, subsidiaries, SCCL).\n"
        "- `coal_supply_monthly`: series names are `<measure>:<entity>`; see `data/coal/coal_supply` in the data dictionary.\n"
        "- `reservoirs_weekly`: CWC weekly bulletin totals (BCM and % of live capacity), dated by bulletin.\n")
    for n, r in done:
        print(n, r)


if __name__ == "__main__":
    main()
