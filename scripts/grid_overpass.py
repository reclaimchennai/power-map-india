"""Polite Overpass fetcher with caching + endpoint fallback.

Raw responses are cached under raw/osm/<name>.json so re-runs do not hit the API.
"""
import json
import os
import sys
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw", "osm")
ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
if os.environ.get("OVERPASS_FIRST"):  # e.g. run two workers, each preferring a different mirror
    ENDPOINTS.sort(key=lambda e: os.environ["OVERPASS_FIRST"] not in e)
UA = "electric-india-power-map/0.1 (research; python-requests)"
SLEEP = 4


def fetch(name, query, timeout=300, force=False):
    os.makedirs(RAW, exist_ok=True)
    path = os.path.join(RAW, name + ".json")
    if os.path.exists(path) and not force:
        with open(path) as f:
            return json.load(f)
    q = query if query.lstrip().startswith("[out:json]") else f"[out:json][timeout:{timeout}];" + query
    last = None
    for attempt in range(6):
        ep = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            r = requests.post(ep, data={"data": q}, headers={"User-Agent": UA}, timeout=timeout + 60)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                d = r.json()
                rem = d.get("remark", "")
                if rem and ("runtime error" in rem or "timed out" in rem or "out of memory" in rem):
                    last = rem
                    print(f"  [{name}] remark from {ep}: {rem[:120]}", file=sys.stderr)
                else:
                    with open(path, "w") as f:
                        json.dump(d, f)
                    print(f"  [{name}] {len(d.get('elements', []))} elements via {ep}", file=sys.stderr)
                    time.sleep(SLEEP)
                    return d
            else:
                last = f"HTTP {r.status_code}: {r.text[:200]}"
                print(f"  [{name}] {ep} -> {last[:160]}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            print(f"  [{name}] {ep} -> {last[:160]}", file=sys.stderr)
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"overpass failed for {name}: {last}")
