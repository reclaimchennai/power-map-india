"""requests.get with retries, backoff and an optional proxy fallback.

Some sources rate-limit (open-meteo 429/503), flake (vidyutpravah.in 500s) or block datacenter IPs
(tnebsldc.org). Policy: retry transient failures with backoff; when a retry still fails, or the
failure is a rate limit / connect error, try once through the SOCKS5 proxy named in the
POWERMAP_SOCKS5_URI environment variable (e.g. socks5h://user:pass@host:1080). Unset = no proxy.
"""
import os
import time

import requests

TRANSIENT = {429, 500, 502, 503, 504}


def proxy_uri():
    """Optional socks5h:// URI from the POWERMAP_SOCKS5_URI environment variable (unset = no proxy)."""
    return os.environ.get("POWERMAP_SOCKS5_URI") or None


def get(url, retries=3, backoff=4, use_proxy=True, **kw):
    """GET url; raises the last error. Extra kwargs go to requests.get (timeout defaults to 60)."""
    kw.setdefault("timeout", 60)
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, **kw)
            if r.status_code not in TRANSIENT:
                r.raise_for_status()
                return r
            last = requests.HTTPError(f"{r.status_code} for url: {url[:120]}", response=r)
            if r.status_code == 429 and use_proxy:
                break  # rate-limited per IP: waiting here rarely helps, a different IP does
        except requests.HTTPError:
            raise  # 403/404 etc: not transient
        except requests.RequestException as e:
            last = e
        time.sleep(backoff * (attempt + 1))
    uri = proxy_uri() if use_proxy else None
    if uri:
        r = requests.get(url, proxies={"http": uri, "https": uri}, **kw)
        r.raise_for_status()
        return r
    raise last
