"""A small, factual market snapshot for the cover strip. Numbers come from here, never from a model's memory.

Yahoo first (one batch request: per-symbol bursts get rate-limited), then per-symbol with one retry, then
free fallbacks for the rupee (Frankfurter, ECB reference rates) and Bitcoin (CoinGecko). Missing quotes are
simply left out; the edition never blocks on market data.
"""
from __future__ import annotations

import time
import urllib.parse

import requests

from . import config, sources

QUOTES = [  # (symbol, display name)
    ("^NSEI", "Nifty 50"), ("^BSESN", "Sensex"), ("^NSEBANK", "Bank Nifty"), ("^GSPC", "S&P 500"),
    ("^IXIC", "Nasdaq"), ("USDINR=X", "USD/INR"), ("BZ=F", "Brent crude ($)"), ("GC=F", "Gold ($/oz)"),
    ("BTC-USD", "Bitcoin ($)"), ("^TNX", "US 10-yr yield (%)"),
]
_H = {"User-Agent": sources.USER_AGENT}


def _from_chart(resp: dict) -> dict | None:
    meta = resp.get("meta") or {}
    closes = [c for c in (((resp.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if c is not None]
    last = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
    prev = closes[-2] if len(closes) >= 2 else meta.get("chartPreviousClose")
    if last is None:
        return None
    return {"last": round(float(last), 2),
            "chg_pct": round((float(last) - float(prev)) / float(prev) * 100, 2) if prev else None}


def _yahoo_batch(symbols: list[str]) -> dict[str, dict]:
    url = ("https://query1.finance.yahoo.com/v7/finance/spark?range=5d&interval=1d&symbols="
           + ",".join(urllib.parse.quote(s) for s in symbols))
    r = requests.get(url, timeout=15, headers=_H)
    if r.status_code != 200:
        return {}
    out = {}
    for res in ((r.json().get("spark") or {}).get("result") or []):
        q = _from_chart(((res.get("response") or [{}])[0]))
        if q:
            out[res.get("symbol")] = q
    return out


def _yahoo_one(sym: str) -> dict | None:
    for attempt, host in enumerate(("query1", "query2")):
        r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
                         "?range=5d&interval=1d", timeout=12, headers=_H)
        if r.status_code == 200:
            res = (r.json().get("chart") or {}).get("result") or []
            return _from_chart(res[0]) if res else None
        time.sleep(2 * (attempt + 1))
    return None


def _usd_inr() -> dict | None:
    r = requests.get("https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR", timeout=12, headers=_H)
    if r.status_code != 200:
        return None
    rate = (r.json().get("rates") or {}).get("INR")
    return {"last": round(float(rate), 2), "chg_pct": None} if rate else None


def _btc() -> dict | None:
    r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
                     "&include_24hr_change=true", timeout=12, headers=_H)
    if r.status_code != 200:
        return None
    b = r.json().get("bitcoin") or {}
    if not b.get("usd"):
        return None
    ch = b.get("usd_24h_change")
    return {"last": round(float(b["usd"]), 2), "chg_pct": round(float(ch), 2) if ch is not None else None}


def snapshot() -> tuple[dict, dict]:
    """Returns ({as_of, quotes:[{sym, name, last, chg_pct}]}, health). Never raises."""
    got: dict[str, dict] = {}
    errors: list[str] = []
    try:
        got = _yahoo_batch([s for s, _ in QUOTES])
    except Exception as e:  # noqa: BLE001
        errors.append(f"yahoo batch: {type(e).__name__}")
    fails = 0                                   # two misses in a row = Yahoo is rate-limiting us: stop asking
    for sym, _ in QUOTES:
        if sym in got:
            continue
        try:
            q = None
            if fails < 2:
                q = _yahoo_one(sym)
                fails = 0 if q else fails + 1
            if q is None and sym == "USDINR=X":
                q = _usd_inr()
            if q is None and sym == "BTC-USD":
                q = _btc()
            if q:
                got[sym] = q
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sym}: {type(e).__name__}")
    quotes = [{"sym": s, "name": n, **got[s]} for s, n in QUOTES if s in got]
    health = {"name": "Markets (Yahoo + fallbacks)", "kind": "markets", "ok": bool(quotes), "items": len(quotes),
              "fresh": len(quotes), "ms": 0, "error": "; ".join(errors)[:200] or None}
    return {"as_of": config.iso(config.now_ist()), "quotes": quotes}, health
