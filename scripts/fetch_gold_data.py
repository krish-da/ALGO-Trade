#!/usr/bin/env python3
"""
FETCH GOLD DATA
===============
Downloads free historical Gold (XAU/USD) data for backtesting.

Source: Yahoo Finance ticker "GC=F" (COMEX Gold Futures).
        GC=F tracks spot XAU/USD very closely (usually within a few dollars),
        which is more than accurate enough for zone / range backtesting.

Why not the MetaTrader5 API?
    The MetaTrader5 Python package is Windows-only, so it cannot run on the
    Linux backtest host. This script gives us a reproducible, free data source
    instead. If you want true broker data, export a CSV from MT5
    (File > Symbols / or right-click chart > Export) and drop it in this folder.

Output CSV format (matches the engine loader, no header):
    time,open,high,low,close
    <unix_seconds>,<open>,<high>,<low>,<close>

Usage:
    python fetch_gold_data.py                 # 2y of 1h candles -> cache_xauusd_gc_1h.csv
    python fetch_gold_data.py --interval 1d --period max
    python fetch_gold_data.py --interval 1h --period 2y --out my_gold.csv
"""

import argparse
import sys
import os


def fetch(ticker: str, period: str, interval: str):
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance is not installed. Run: pip install yfinance")
        sys.exit(1)

    print(f"Downloading {ticker}  period={period}  interval={interval} ...")
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        progress=False,
        auto_adjust=False,
    )

    if df is None or len(df) == 0:
        print("ERROR: no data returned. Try a different --period/--interval.")
        sys.exit(1)

    # yfinance can return a MultiIndex column layout for a single ticker.
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
        }
    )
    df = df[["open", "high", "low", "close"]].dropna()

    # Unix seconds column to match the existing MT5 cache format.
    df = df.reset_index()
    ts_col = "Datetime" if "Datetime" in df.columns else "Date"
    # Robust across pandas versions / tz-aware datetime64[s]: use per-value
    # timestamp() rather than a bulk astype("int64") (which misbehaves on
    # tz-aware second-resolution datetimes in pandas 3.0).
    import pandas as pd

    ts = pd.to_datetime(df[ts_col], utc=True)
    df["time"] = ts.apply(lambda x: int(x.timestamp()))

    out = df[["time", "open", "high", "low", "close"]]
    return out


def main():
    ap = argparse.ArgumentParser(description="Fetch free Gold (XAU/USD) OHLC data.")
    ap.add_argument("--ticker", default="GC=F", help="Yahoo ticker (default GC=F)")
    ap.add_argument("--period", default="2y", help="1mo,3mo,6mo,1y,2y,5y,10y,max")
    ap.add_argument("--interval", default="1h", help="1m,5m,15m,1h,1d")
    ap.add_argument("--out", default=None, help="output CSV path")
    args = ap.parse_args()

    df = fetch(args.ticker, args.period, args.interval)

    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"cache_xauusd_gc_{args.interval}.csv",
    )
    df.to_csv(out, header=False, index=False)

    lo = df["low"].min()
    hi = df["high"].max()
    print(f"Saved {len(df)} candles -> {out}")
    print(f"  price range: ${lo:,.2f} - ${hi:,.2f}")
    print(f"  first: {df['time'].iloc[0]}  last: {df['time'].iloc[-1]}")


if __name__ == "__main__":
    main()
