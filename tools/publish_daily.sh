#!/usr/bin/env bash
# Daily publish of the open data (run by a systemd --user timer on the collector host).
#   1. data/latest/*.csv: small plain CSVs of the daily series, committed and pushed when they changed
#   2. every table (CSV.gz + Parquet) and the whole SQLite database, replaced as assets of the rolling
#      `data-latest` release, so the multi-MB files never accumulate in git history
#
#   3. the live site's JSON (web/data/coal and web/data/live: the Coal Tracker and the map), as a third asset
#
#   POWER_DB=/path/to/power.db PYTHON=/path/to/python [WEB_DATA=/path/to/web/data] tools/publish_daily.sh
# PYTHON needs pandas + pyarrow; gh must be logged in and the repo's push key usable without a prompt.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
DB="${POWER_DB:?set POWER_DB to the collector database}"
PY="${PYTHON:-python3}"
TAG=data-latest
WEB_DATA="${WEB_DATA:-$(dirname "$(dirname "$DB")")/web/data}"   # default: the collector checkout next to the database
cd "$REPO"
git pull --ff-only -q

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# a consistent copy while the collector keeps writing (WAL-safe online backup)
"$PY" -I -c 'import sqlite3, sys
s = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True); d = sqlite3.connect(sys.argv[2])
s.backup(d); d.close(); s.close()' "$DB" "$WORK/power.db"

"$PY" -I tools/export_latest.py --db "$WORK/power.db"
"$PY" -I tools/export_open_data.py --db "$WORK/power.db" --out "$WORK/data" >/dev/null
(cd "$WORK" && zip -qr power-map-india-tables.zip data && zip -qj power-map-india-sqlite.zip power.db)
ASSETS=("$WORK/power-map-india-tables.zip" "$WORK/power-map-india-sqlite.zip")
if [ -d "$WEB_DATA/coal" ]; then
  (cd "$WEB_DATA/.." && zip -qr "$WORK/power-map-india-dashboard-json.zip" data/coal data/live)
  ASSETS+=("$WORK/power-map-india-dashboard-json.zip")
fi

DAY="$(date -u +%F)"
NOTES="Refreshed daily from the live collector; last refresh ${DAY} (UTC).

- power-map-india-tables.zip: every table in data/ as CSV (gzipped over 5 MB) and Parquet, with MANIFEST.csv and DICTIONARY.md
- power-map-india-sqlite.zip: the whole SQLite database
- power-map-india-dashboard-json.zip: the JSON behind the live site (data/coal: Coal Tracker; data/live: the map)

Dated snapshots with the raw source reports are the vYYYY.MM.DD releases."
if ! gh release view "$TAG" >/dev/null 2>&1; then
  gh release create "$TAG" --title "Data, refreshed daily" --notes "$NOTES" --latest=false
fi
gh release upload "$TAG" "${ASSETS[@]}" --clobber
gh release edit "$TAG" --notes "$NOTES" >/dev/null

git add data/latest
if ! git diff --cached --quiet; then
  git commit -q -m "Daily data ${DAY}"
  git push -q
fi
echo "published ${DAY}"
