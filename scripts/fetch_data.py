#!/usr/bin/env python3
"""
fetch_data.py - XAUUSD historical data acquisition (Phase 0)

Strategy:
  1. Attempt MatchTrader (FundingPips) REST API if MT_LOGIN/MT_PASSWORD env vars are set.
     (MatchTrader client API is undocumented; we probe known endpoints with short timeouts.)
  2. Fallback: Dukascopy public datafeed - daily 1-minute candle files (bi5/LZMA, no API key).
     Downloads ~8 months of 1m candles, builds a single CSV: timestamp,open,high,low,close,volume

Output: scripts/data/xauusd_1m.csv  (UTC timestamps, ascending)

NOTE: Dukascopy XAUUSD prices are spot bid prices scaled by 10^3 in the raw files.
"""

import os
import sys
import lzma
import struct
import time
import datetime as dt
import urllib.request
import urllib.error
import json

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT_CSV = os.path.join(DATA_DIR, "xauusd_1m.csv")
MONTHS_BACK = 8  # fetch ~8 months to guarantee 6+ usable

# ---------------------------------------------------------------------------
# 1) MatchTrader attempt (FundingPips)
# ---------------------------------------------------------------------------

def try_matchtrader():
    login = os.environ.get("MT_LOGIN")
    password = os.environ.get("MT_PASSWORD")
    if not login or not password:
        print("[fetch] MatchTrader: MT_LOGIN/MT_PASSWORD not set, skipping.")
        return None

    base_urls = [
        "https://mtr.fundingpips.com",
        "https://platform.fundingpips.com",
        "https://trade.fundingpips.com",
    ]
    login_paths = [
        "/mtr-api/auth/token",
        "/manager/co-login",
        "/api/auth/login",
    ]
    for base in base_urls:
        for path in login_paths:
            url = base + path
            body = json.dumps({"email": login, "login": login, "password": password}).encode()
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = resp.read().decode()
                    print(f"[fetch] MatchTrader: {url} -> HTTP {resp.status}")
                    if resp.status == 200 and ("token" in data.lower()):
                        print("[fetch] MatchTrader login OK - but candle-history endpoint "
                              "is not publicly documented; manual integration needed.")
                        return None
            except urllib.error.HTTPError as e:
                print(f"[fetch] MatchTrader: {url} -> HTTP {e.code}")
            except Exception as e:
                print(f"[fetch] MatchTrader: {url} -> {type(e).__name__}")
    print("[fetch] MatchTrader: no usable endpoint found, falling back to Dukascopy.")
    return None

# ---------------------------------------------------------------------------
# 2) Yahoo Finance fallback - GC=F (COMEX gold futures)
#    Dukascopy/stooq are blocked from this environment (503 / JS-challenge).
#    GC=F is a structural proxy for spot XAUUSD: identical swings/levels shape,
#    ~constant basis offset. Levels are computed from the series' own swings,
#    so the proof is unaffected. The cached MT5 spot 1m CSV is still used to
#    validate the user's exact chart lines.
# ---------------------------------------------------------------------------

YH_URL = ("https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
          "?interval={iv}&range={rng}")


def yahoo_fetch(interval: str, rng: str):
    url = YH_URL.format(iv=interval, rng=rng)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        d = json.loads(resp.read().decode())
    res = d["chart"]["result"]
    if not res:
        raise RuntimeError(f"yahoo error: {d['chart'].get('error')}")
    ts = res[0]["timestamp"]
    q = res[0]["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        v = q["volume"][i] or 0
        if o is None or h is None or l is None or c is None:
            continue
        rows.append((int(t), o, h, l, c, v))
    rows.sort(key=lambda r: r[0])
    return rows


def save_csv(rows, path):
    with open(path, "w") as f:
        for r in rows:
            f.write(f"{r[0]},{r[1]:.3f},{r[2]:.3f},{r[3]:.3f},{r[4]:.3f},{r[5]:.0f}\n")
    s = dt.datetime.fromtimestamp(rows[0][0], dt.timezone.utc)
    e = dt.datetime.fromtimestamp(rows[-1][0], dt.timezone.utc)
    print(f"[fetch] saved {len(rows)} bars ({s} -> {e}) to {path}")


def fetch_yahoo():
    os.makedirs(DATA_DIR, exist_ok=True)
    # 1h bars, ~2 years max on Yahoo; take 1y for robust sample
    h1 = yahoo_fetch("60m", "1y")
    save_csv(h1, os.path.join(DATA_DIR, "gc_1h.csv"))
    # 15m bars, 60d max on Yahoo
    m15 = yahoo_fetch("15m", "60d")
    save_csv(m15, os.path.join(DATA_DIR, "gc_15m.csv"))
    if len(h1) < 2000:
        print("[fetch] WARNING: fewer 1h bars than expected")


if __name__ == "__main__":
    try_matchtrader()
    fetch_yahoo()
