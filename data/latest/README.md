# Latest daily series

Updated 2026-10-23 (UTC) from the live collector. Plain CSV, one row per day / week / month, sorted, so each day's commit shows only the new rows. Full tables in CSV.gz / Parquet and the whole SQLite database: the [`data-latest` release](https://github.com/reclaimchennai/power-map-india/releases/tag/data-latest), refreshed daily.

| File | Rows |
|---|---|
| [`coal_stock_national_daily.csv`](coal_stock_national_daily.csv) | 2,937 |
| [`coal_rakes_daily.csv`](coal_rakes_daily.csv) | 13,497 |
| [`coal_production_daily.csv`](coal_production_daily.csv) | 10,373 |
| [`coal_supply_monthly.csv`](coal_supply_monthly.csv) | 15,385 |
| [`reservoirs_weekly.csv`](reservoirs_weekly.csv) | 4,677 |

- `coal_stock_national_daily`: CEA Daily Coal Stock Report summed over operating plants. `days_of_coal_at_requirement` = stock of plants that state a requirement ÷ that daily requirement (85% PLF), comparable across the whole record. CEA widened the report on 2021-11-14 (about 27 more plants). Receipt from 2021-09, consumption from 2021-11. Rows with an obvious typo (over 3 Mt and four times the plant's normative stock) are left out.
- `coal_rakes_daily`: CIL's Rakes Data page (FOIS); CIL is the sum of its subsidiaries. Loaded from 2022-03-27.
- `coal_production_daily`: CIL MOC dashboard, on-day production and offtake in thousand tonnes (CIL, subsidiaries, SCCL).
- `coal_supply_monthly`: series names are `<measure>:<entity>`; see `data/coal/coal_supply` in the data dictionary.
- `reservoirs_weekly`: CWC weekly bulletin totals (BCM and % of live capacity), dated by bulletin.
