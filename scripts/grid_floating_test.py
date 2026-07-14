"""
GRID / FLOATING-POSITION TEST  (XAU/USD)
========================================
Tests the hypothesis behind the "0% win ratio + 794 trades + +5680%" leaderboard:

    A 0% win RATIO with hundreds of trades usually means almost NOTHING is closed.
    The trades are still OPEN -- floating. That is the signature of a GRID /
    MARTINGALE / averaging-in system: keep opening positions, never close a loser,
    and let a strong trend inflate the FLOATING (unrealised) profit. The dashboard
    then shows a huge gain with a 0% closed-win ratio.

WHAT THIS SCRIPT DOES
---------------------
Over every rolling 15-day window of real gold data it runs a leveraged grid:
  * open a fixed-lot LONG at the start, and add another lot every time price
    drops `grid_step` dollars (classic "buy the dip / average down"),
  * NEVER close at a loss (that is what keeps the win ratio at 0%),
  * track floating equity bar by bar; if floating loss ever exceeds the account
    (margin call), the account is BLOWN and that window is a 0.
It then reports, across all windows, how often the floating peak reaches +5000%
versus how often the account blows up.

This is a study of WHY the leaderboard looks the way it does -- NOT a strategy to
copy. The whole point is that the same mechanism that occasionally shows +5000%
floating also wipes the account out most of the time.
"""

from __future__ import annotations

import argparse
import numpy as np

from zone_range_strategy import load_csv, resample


# --------------------------------------------------------------------------- #
def run_grid_window(closes, highs, lows, *, start_equity, leverage,
                    grid_step, lot_frac, take_profit_pct):
    """Run one grid over a single window of prices.

    Returns dict with peak floating gain %, final gain %, and whether it blew up.
    Lot size is a fraction of START equity's notional at the given leverage, so
    every added lot is the same size (a grid, not a true martingale doubling).
    """
    equity0 = start_equity
    # notional per lot = lot_frac * equity0 * leverage ; units = notional / price
    entry_price0 = closes[0]
    lot_notional = lot_frac * equity0 * leverage
    units_per_lot = lot_notional / entry_price0

    positions = [entry_price0]          # entry prices of open long lots
    last_add = entry_price0
    peak_gain = 0.0
    blew_up = False

    for i in range(1, len(closes)):
        price = closes[i]
        low = lows[i]

        # add a lot each time price has dropped another grid_step from last add
        while last_add - price >= grid_step:
            last_add -= grid_step
            positions.append(last_add)

        # floating pnl of all open longs (in $)
        total_units = units_per_lot * len(positions)
        avg_entry = float(np.mean(positions))
        floating = (price - avg_entry) * total_units
        equity = equity0 + floating

        # margin call check against the intrabar LOW (worst case)
        worst_floating = (low - avg_entry) * total_units
        if equity0 + worst_floating <= 0:
            blew_up = True
            peak_gain = -100.0
            break

        gain_pct = (equity / equity0 - 1.0) * 100.0
        peak_gain = max(peak_gain, gain_pct)

        # optional: close everything once floating target hit (locks the win)
        if take_profit_pct > 0 and gain_pct >= take_profit_pct:
            return {"peak": peak_gain, "final": gain_pct, "blew_up": False, "closed": True}

    final_gain = -100.0 if blew_up else (equity / equity0 - 1.0) * 100.0
    return {"peak": peak_gain, "final": final_gain, "blew_up": blew_up, "closed": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="cache_xauusd_gc_1h.csv")
    ap.add_argument("--tf", default="1H")
    ap.add_argument("--window-days", type=int, default=15)
    ap.add_argument("--leverage", type=float, default=100.0)
    ap.add_argument("--grid-step", type=float, default=5.0,
                    help="$ price drop between added lots")
    ap.add_argument("--lot-frac", type=float, default=0.05,
                    help="fraction of start equity (notional at leverage) per lot")
    ap.add_argument("--take-profit", type=float, default=0.0,
                    help="close all at this floating gain %% (0 = never close, pure float)")
    args = ap.parse_args()

    df = resample(load_csv(args.data), args.tf)
    bars_per_day = {"1H": 24, "4H": 6, "15min": 96}.get(args.tf, 24)
    win = args.window_days * bars_per_day

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    n = len(closes)

    step = max(1, bars_per_day)  # slide window one day at a time
    results = []
    for s in range(0, n - win, step):
        e = s + win
        r = run_grid_window(
            closes[s:e], highs[s:e], lows[s:e],
            start_equity=100_000.0, leverage=args.leverage,
            grid_step=args.grid_step, lot_frac=args.lot_frac,
            take_profit_pct=args.take_profit,
        )
        results.append(r)

    peaks = np.array([r["peak"] for r in results])
    finals = np.array([r["final"] for r in results])
    blew = np.array([r["blew_up"] for r in results])

    print("=" * 74)
    print("GRID / FLOATING TEST  --  does 'never close, ride the trend' hit +5000%?")
    print("=" * 74)
    print(f"data              : {args.data}  ({args.tf}, {n} bars)")
    print(f"windows tested    : {len(results)}  rolling {args.window_days}-day windows")
    print(f"leverage          : {args.leverage:.0f}x   grid step: ${args.grid_step:.0f}"
          f"   lot: {args.lot_frac*100:.0f}% notional")
    print(f"take-profit       : {'never (pure float)' if args.take_profit==0 else str(args.take_profit)+'%'}")
    print("-" * 74)
    print(f"blew up (margin call)     : {blew.mean()*100:5.1f}% of windows")
    print(f"floating PEAK >= +5000%   : {(peaks>=5000).mean()*100:5.1f}% of windows")
    print(f"floating PEAK >= +1000%   : {(peaks>=1000).mean()*100:5.1f}% of windows")
    print(f"median floating peak      : {np.median(peaks):8.0f}%")
    print(f"best  floating peak       : {peaks.max():8.0f}%")
    print(f"median FINAL (hold to end): {np.median(finals):8.0f}%")
    print(f"mean   FINAL (hold to end): {finals.mean():8.0f}%")
    print("-" * 74)
    print("READ: a high 'PEAK' with a terrible 'FINAL' + high blow-up rate is the")
    print("whole story -- the account FLASHES a huge floating gain, then the trend")
    print("turns and margin-calls it. The leaderboard screenshots the flash.")
    print("=" * 74)


if __name__ == "__main__":
    main()
