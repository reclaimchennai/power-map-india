"""District-wise energy data for Tamil Nadu — TEDA / ENVIS database.

Parses the "Database on Energy Resources in Tamil Nadu" (ENVIS Centre,
Dept. of Environment, GoTN — environment.tn.gov.in) district-wise tables:
  Table 41: district-wise atomic (nuclear) generation statistics
  Table 43: district-wise hydro generation (per power house, by year)
  Table 44: district-wise wind installed capacity (MW)
  Table 45: district-wise solar installed capacity (MW)

These are statistical/annual figures (the database's latest year is ~2016-17)
— the only district-wise breakdown TNEB/TEDA publishes. Stored in table
tn_district (source_table, district, item, capacity_mw, year, value_mu).
"""
import argparse
import re
import sys
from pathlib import Path

import pdfplumber
import requests

from store import connect, log

PDF_URL = ("https://environment.tn.gov.in/assets/report/"
           "Database%20on%20Energy%20Resources%20in%20Tamil%20Nadu.pdf")
NUM = re.compile(r"[\d,]+(?:\.\d+)?")


def _f(v):
    v = (v or "").replace(",", "").strip()
    try:
        return float(v)
    except ValueError:
        return None


def find_pages(pdf_text):
    pages = {}
    for i, p in enumerate(pdf_text):
        for tab in ("Table 41", "Table 43", "Table 44", "Table 45"):
            if tab + ":" in p:
                pages[tab] = i   # last occurrence wins (TOC also matches)
    return pages


def parse(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        texts = [p.extract_text() or "" for p in pdf.pages]
        pages = find_pages(texts)
        if len(pages) < 4:
            raise ValueError(f"tables not found, got {list(pages)}")
        rows = []

        def add(source, district, item, cap, year, mu):
            rows.append(dict(source_table=source, district=district,
                             item=item, capacity_mw=cap, year=year, value_mu=mu))

        # Table 41: atomic — capacity header row then yearly MU rows
        t = texts[pages["Table 41"]]
        district = None
        for line in t.split("\n"):
            if "District" in line and ("Kancheepuram" in line or "Tirunelveli" in line):
                district = None
            m = re.match(r"^(\d{4}-\d{4})\s+([\d.]+|NA)\s+([\d.]+|NA)\s*$", line.strip())
            if m:
                for d, v in (("Kancheepuram", m.group(2)), ("Tirunelveli", m.group(3))):
                    if v != "NA":
                        add("41_atomic_gen", d, "nuclear generation", None, m.group(1), _f(v))
            m2 = re.match(r"^Installed Capacity\s+(\d+)\s+(\d+)", line.strip())
            if m2:
                add("41_atomic_gen", "Kancheepuram", "MAPS capacity", _f(m2.group(1)), None, None)
                add("41_atomic_gen", "Tirunelveli", "Kudankulam capacity", _f(m2.group(2)), None, None)

        # Table 44: wind capacity — "S.No District Capacity"
        t = texts[pages["Table 44"]]
        for line in t.split("\n"):
            m = re.match(r"^\d+\s+([A-Za-z][A-Za-z ]+?)\s+([\d,]+(?:\.\d+)?)\s*$", line.strip())
            if m and _f(m.group(2)) is not None:
                add("44_wind_cap", m.group(1).strip(), "wind installed capacity",
                    _f(m.group(2)), None, None)

        # Table 45: solar capacity — "S.No District MW [Private]"
        t = texts[pages["Table 45"]]
        for i in range(pages["Table 45"], pages["Table 45"] + 3):
            for line in texts[i].split("\n"):
                m = re.match(r"^\d+\s+([A-Za-z][A-Za-z ]+?)\s+([\d.]+)\s+(Private|Government)?\s*$",
                             line.strip())
                if m and _f(m.group(2)) is not None:
                    add("45_solar_cap", m.group(1).strip(), "solar installed capacity",
                        _f(m.group(2)), None, m.group(3) and None)

        # Table 43: hydro — "District PowerHouse Year gens..." (last col = 2016-17)
        for i in range(pages["Table 43"], pages["Table 44"]):
            for line in texts[i].split("\n"):
                m = re.match(r"^[A-Z][a-z]+\s+(.+?)\s+(\d{4})\s+([\d.]+ .+)$", line.strip())
                if m:
                    nums = NUM.findall(m.group(3))
                    if nums:
                        add("43_hydro_gen", m.group(1).split()[0].strip(),
                            "hydro: " + m.group(2), None, "2016-2017", _f(nums[-1]))
    return rows


def save(rows):
    con = connect()
    with con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS tn_district (
            source_table TEXT, district TEXT, item TEXT,
            capacity_mw REAL, year TEXT, value_mu REAL);
        """)
        con.execute("DELETE FROM tn_district")
        con.executemany(
            """INSERT INTO tn_district
            (source_table, district, item, capacity_mw, year, value_mu)
            VALUES (:source_table,:district,:item,:capacity_mw,:year,:value_mu)""",
            rows)
    con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/downloads/tn_energy_database.pdf")
    ap.add_argument("--url", default=PDF_URL)
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        r = requests.get(args.url, timeout=120, verify=False,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        path.write_bytes(r.content)
    rows = parse(path)
    save(rows)
    print(f"{len(rows)} district rows")
    log("tn_district", "ok", f"{len(rows)} rows")


if __name__ == "__main__":
    main()
