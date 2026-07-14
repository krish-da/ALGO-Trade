#!/usr/bin/env python3
"""
ZONE PRICE-ACTION STRATEGY  (XAU/USD)
=====================================
A clean, working rebuild of the "zone lines + price action" method from the
trading charts.

WHAT THE CHARTS ACTUALLY SHOW  (corrected)
------------------------------------------
Horizontal support/resistance ("zone") lines. At a zone the trader reads the
candle and enters in the direction PRICE COMMITS TO -- following the move, not
fading it. A decisive bullish candle off/through a zone -> LONG toward the next
zone up; a decisive bearish candle -> SHORT toward the next zone down. This
captures BOTH bounces and breakouts ("go where price moves"). Stops sit behind
the confirmation candle / zone; the position trails to the next zone (or rides
the trend when there is no next zone). Repeating these sniper entries with
leverage and compounding is what produced the large percentage gains.

TWO SIGNAL MODES
----------------
  price_action (default) : follow the committed direction (the real method).
  reversion              : fade the zone (buy support / sell resistance) -- kept
                           only for comparison.

WHY THIS IS A REWRITE, NOT THE OLD SCRIPT
-----------------------------------------
The previous script's only reliable part was ZONE DETECTION. Its entry logic
depended on a fragile "rejection percentile" that did not generalize. This file
keeps clean zone detection and rebuilds the entry logic around price action.

HONESTY NOTE
------------
The 5000%+ tournament leaderboard numbers come from free demo contests with
tens of thousands of entrants, max leverage, and survivorship bias. They are
NOT a repeatable edge. This engine models the REAL zone strategy and reports
drawdown and a "ruin" flag so you can see the true risk of the aggressive,
high-leverage compounding profile.

USAGE
-----
    python zone_range_strategy.py                          # default data, both modes
    python zone_range_strategy.py --data cache_xauusd_gc_1h.csv --tf 1h
    python zone_range_strategy.py --mode aggressive
    python zone_range_strategy.py --mode conservative --risk 2 --leverage 5

Requires: pandas, numpy   (pip install pandas numpy)
"""

import argparse
import json
import os
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Configuration                                                               #
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    # account / risk
    start_balance: float = 10_000.0
    leverage: float = 10.0
    risk_pct: float = 10.0          # % of CURRENT balance risked per trade (compounding)
    max_risk_frac_of_equity: float = 0.95  # never risk more than this fraction of equity

    # zone detection -- tuned for a FEW MAJOR levels (like the chart), not noise
    swing_lookback: int = 8         # bars each side for a swing pivot (bigger = major swings)
    cluster_dist: float = 15.0      # $ distance to merge pivots into one zone
    min_touches: int = 4            # min touches to keep a zone
    max_zones: int = 8              # keep only the N strongest zones by touch count
    round_step: float = 0.0         # snap zones to nearest $step (0 = off)
    rebuild_every: int = 500        # re-detect zones every N bars (rolling, walk-forward)
    build_window: int = 2000        # bars of history used to (re)build zones

    # entry / exit
    signal_mode: str = "price_action"  # "price_action" (follow the move) or "reversion" (fade)
    touch_buffer: float = 3.0       # $ proximity that counts as "touching" a zone
    sl_buffer: float = 2.5          # $ beyond the zone / candle for the stop
    min_sl_dist: float = 3.0        # floor on stop distance ($) to avoid noise-tight stops
    min_rr: float = 1.2             # skip trades whose target/stop ratio is below this
    confirm_rejection: bool = True  # (reversion mode) require the bar to close back off the zone
    body_frac: float = 0.5          # (price_action) min candle body / range to call it "decisive"
    tp_fallback_rr: float = 2.0     # (price_action) target = this * risk when no next zone exists
    trail: bool = True              # trail the stop as price moves to target
    cooldown_bars: int = 2          # bars to wait after a trade before re-entering

    # realistic trading costs (gold / XAU-USD)
    spread: float = 0.30            # $ bid/ask spread paid on entry AND exit
    slippage: float = 0.20          # $ extra adverse fill on stop-outs

    # misc
    verbose: bool = False


PROFILES = {
    # Realistic, survivable settings.
    "conservative": dict(risk_pct=2.0, leverage=5.0, min_touches=3, min_rr=1.5),
    # Mirrors the chart notes: 10% risk, 10x leverage, compound hard.
    "aggressive": dict(risk_pct=10.0, leverage=10.0, min_touches=3, min_rr=1.2),
}


# --------------------------------------------------------------------------- #
# Data loading / resampling                                                   #
# --------------------------------------------------------------------------- #
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, header=None, names=["time", "open", "high", "low", "close"])
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.dropna().reset_index(drop=True)
    return df


def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Resample raw candles to a target timeframe (e.g. '1H', '4H', '15min')."""
    # pandas >= 3.0 uses lowercase hour/minute aliases ('h', 'min').
    tf = tf.replace("H", "h").replace("T", "min").replace("MIN", "min")
    tmp = df.set_index("datetime")
    out = (
        tmp.resample(tf)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
        .reset_index()
    )
    out["time"] = out["datetime"].astype("int64") // 10**9
    return out


# --------------------------------------------------------------------------- #
# Zone detection (the part that works)                                        #
# --------------------------------------------------------------------------- #
def find_swings(df: pd.DataFrame, lookback: int) -> list[float]:
    highs = df["high"].values
    lows = df["low"].values
    n = len(df)
    pivots: list[float] = []
    for i in range(lookback, n - lookback):
        window_hi = highs[i - lookback : i + lookback + 1]
        window_lo = lows[i - lookback : i + lookback + 1]
        if highs[i] == window_hi.max():
            pivots.append(float(highs[i]))
        if lows[i] == window_lo.min():
            pivots.append(float(lows[i]))
    return pivots


def cluster_levels(levels: list[float], cluster_dist: float) -> list[float]:
    if not levels:
        return []
    levels = sorted(levels)
    clusters: list[list[float]] = [[levels[0]]]
    for lv in levels[1:]:
        if lv - clusters[-1][-1] <= cluster_dist:
            clusters[-1].append(lv)
        else:
            clusters.append([lv])
    return [float(np.mean(c)) for c in clusters]


def count_touches(level: float, df: pd.DataFrame, buffer: float) -> int:
    hi = df["high"].values
    lo = df["low"].values
    near = (np.abs(hi - level) <= buffer) | (np.abs(lo - level) <= buffer)
    return int(near.sum())


def detect_zones(df: pd.DataFrame, cfg: Config) -> list[float]:
    """Build a FEW clean major S/R zones from swing pivots + clustering, keeping
    only the strongest levels by touch count (like the handful of lines drawn on
    the chart)."""
    pivots = find_swings(df, cfg.swing_lookback)
    if cfg.round_step > 0:
        pivots = [round(p / cfg.round_step) * cfg.round_step for p in pivots]
    clustered = cluster_levels(pivots, cfg.cluster_dist)
    scored = [
        (z, count_touches(z, df, cfg.touch_buffer))
        for z in clustered
    ]
    scored = [(z, t) for z, t in scored if t >= cfg.min_touches]
    # keep the strongest N zones, then return them sorted by price
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[: cfg.max_zones]
    return sorted(z for z, _ in top)


# --------------------------------------------------------------------------- #
# Trade & result containers                                                   #
# --------------------------------------------------------------------------- #
@dataclass
class Trade:
    idx: int
    time: int
    direction: str
    entry: float
    sl: float
    tp: float
    zone: float
    qty: float
    balance_before: float
    exit: float = 0.0
    exit_idx: int = 0
    reason: str = ""
    pnl: float = 0.0
    balance_after: float = 0.0


# --------------------------------------------------------------------------- #
# Backtest engine                                                             #
# --------------------------------------------------------------------------- #
class ZoneRangeStrategy:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.balance = cfg.start_balance
        self.equity_peak = cfg.start_balance
        self.max_dd = 0.0
        self.trades: list[Trade] = []
        self.active: Trade | None = None
        self.zones: list[float] = []
        self.last_exit_idx = -10_000
        self.ruined = False

    # -- zone helpers ------------------------------------------------------- #
    def _nearest_zone(self, price: float):
        best, best_d = None, 1e18
        for z in self.zones:
            d = abs(price - z)
            if d < best_d:
                best, best_d = z, d
        return best, best_d

    def _target_above(self, zone: float):
        ups = [z for z in self.zones if z > zone + self.cfg.touch_buffer]
        return ups[0] if ups else None

    def _target_below(self, zone: float):
        downs = [z for z in self.zones if z < zone - self.cfg.touch_buffer]
        return downs[-1] if downs else None

    # -- sizing ------------------------------------------------------------- #
    def _position_size(self, entry: float, sl: float) -> float:
        sl_dist = abs(entry - sl)
        if sl_dist <= 0:
            return 0.0
        risk_usd = self.balance * (self.cfg.risk_pct / 100.0)
        risk_usd = min(risk_usd, self.balance * self.cfg.max_risk_frac_of_equity)
        qty = risk_usd / sl_dist
        # leverage cap on notional
        max_qty = (self.balance * self.cfg.leverage) / entry
        return max(0.0, min(qty, max_qty))

    # -- entries ------------------------------------------------------------ #
    def _try_enter(self, bar, idx: int):
        if idx - self.last_exit_idx < self.cfg.cooldown_bars:
            return
        zone, dist = self._nearest_zone(bar["close"])
        if zone is None or dist > self.cfg.touch_buffer:
            return
        if self.cfg.signal_mode == "reversion":
            self._reversion_enter(bar, idx, zone)
        else:
            self._price_action_enter(bar, idx, zone)

    def _price_action_enter(self, bar, idx: int, zone: float):
        """Follow the move. At a zone, read the candle and go WHERE PRICE COMMITS
        (bounce OR breakout), confirmed by a decisive candle. This mirrors the
        chart method: sniper entry in the direction of price action, then ride to
        the next zone."""
        c, h, l, o = bar["close"], bar["high"], bar["low"], bar["open"]
        rng = h - l
        if rng <= 0:
            return
        body = abs(c - o)
        decisive = body >= self.cfg.body_frac * rng   # strong, committed candle

        if not decisive:
            return

        # bullish commit -> LONG toward next zone up (works for a bounce off
        # support AND a breakout above resistance). Sniper stop just BELOW the
        # zone we launched from -> tight risk, big reward to the next zone.
        if c > o and c > zone:
            tp = self._target_above(zone)
            entry = c
            sl = zone - self.cfg.sl_buffer
            if tp is None:                             # no zone above -> ride the trend
                tp = entry + self.cfg.tp_fallback_rr * (entry - sl)
            self._open("LONG", entry, sl, tp, zone, idx, bar)
            return

        # bearish commit -> SHORT toward next zone down (rejection off resistance
        # AND breakdown below support). Sniper stop just ABOVE the zone.
        if c < o and c < zone:
            tp = self._target_below(zone)
            entry = c
            sl = zone + self.cfg.sl_buffer
            if tp is None:                             # no zone below -> ride the trend
                tp = entry - self.cfg.tp_fallback_rr * (sl - entry)
            self._open("SHORT", entry, sl, tp, zone, idx, bar)

    def _reversion_enter(self, bar, idx: int, zone: float):
        """Original fade-the-zone logic (kept for comparison)."""
        c, h, l = bar["close"], bar["high"], bar["low"]

        # SUPPORT rejection -> LONG: bar dipped to/below zone but closed above it
        if l <= zone + self.cfg.touch_buffer and c > zone:
            if self.cfg.confirm_rejection and not (c > bar["open"]):
                return
            tp = self._target_above(zone)
            if tp is None:
                return
            entry = c
            sl = zone - self.cfg.sl_buffer
            self._open("LONG", entry, sl, tp, zone, idx, bar)
            return

        # RESISTANCE rejection -> SHORT: bar poked to/above zone but closed below it
        if h >= zone - self.cfg.touch_buffer and c < zone:
            if self.cfg.confirm_rejection and not (c < bar["open"]):
                return
            tp = self._target_below(zone)
            if tp is None:
                return
            entry = c
            sl = zone + self.cfg.sl_buffer
            self._open("SHORT", entry, sl, tp, zone, idx, bar)

    def _open(self, direction, entry, sl, tp, zone, idx, bar):
        half = self.cfg.spread / 2.0
        # fill at the adverse side of the spread
        if direction == "LONG":
            entry = entry + half
            sl = min(sl, entry - self.cfg.min_sl_dist)   # enforce a realistic stop floor
        else:  # SHORT
            entry = entry - half
            sl = max(sl, entry + self.cfg.min_sl_dist)
        reward = abs(tp - entry)
        risk = abs(entry - sl)
        if risk <= 0 or reward / risk < self.cfg.min_rr:
            return
        qty = self._position_size(entry, sl)
        if qty <= 0:
            return
        self.active = Trade(
            idx=idx,
            time=int(bar["time"]),
            direction=direction,
            entry=entry,
            sl=sl,
            tp=tp,
            zone=zone,
            qty=qty,
            balance_before=self.balance,
        )
        if self.cfg.verbose:
            print(f"  {direction:5s} @ {entry:8.2f}  SL {sl:8.2f}  TP {tp:8.2f}  "
                  f"zone {zone:8.2f}  qty {qty:8.3f}  bal {self.balance:12.2f}")

    # -- management --------------------------------------------------------- #
    def _manage(self, bar, idx: int):
        t = self.active
        assert t is not None
        h, l = bar["high"], bar["low"]

        if t.direction == "LONG":
            if self.cfg.trail:
                gain = h - t.entry
                if gain > 0:
                    new_sl = t.entry + gain - abs(t.entry - t.sl)
                    if new_sl > t.sl:
                        t.sl = new_sl
            # stop first (conservative: assume worst intrabar order)
            if l <= t.sl:
                self._close(t.sl, idx, "SL/Trail")
            elif h >= t.tp:
                self._close(t.tp, idx, "TP")
        else:  # SHORT
            if self.cfg.trail:
                gain = t.entry - l
                if gain > 0:
                    new_sl = t.entry - gain + abs(t.sl - t.entry)
                    if new_sl < t.sl:
                        t.sl = new_sl
            if h >= t.sl:
                self._close(t.sl, idx, "SL/Trail")
            elif l <= t.tp:
                self._close(t.tp, idx, "TP")

    def _close(self, price, idx, reason):
        t = self.active
        assert t is not None
        half = self.cfg.spread / 2.0
        slip = self.cfg.slippage if reason.startswith("SL") else 0.0
        # fill at the adverse side of the spread (+ slippage on stop-outs)
        if t.direction == "LONG":
            price = price - half - slip
            pnl = (price - t.entry) * t.qty
        else:
            price = price + half + slip
            pnl = (t.entry - price) * t.qty
        self.balance += pnl
        t.exit = price
        t.exit_idx = idx
        t.reason = reason
        t.pnl = pnl
        t.balance_after = self.balance
        self.trades.append(t)
        self.active = None
        self.last_exit_idx = idx

        # equity / drawdown / ruin tracking
        if self.balance > self.equity_peak:
            self.equity_peak = self.balance
        dd = (self.equity_peak - self.balance) / self.equity_peak * 100 if self.equity_peak > 0 else 0
        self.max_dd = max(self.max_dd, dd)
        if self.balance <= self.cfg.start_balance * 0.02:  # <=2% left == blown
            self.ruined = True

    # -- main loop ---------------------------------------------------------- #
    def run(self, df: pd.DataFrame) -> dict:
        n = len(df)
        cfg = self.cfg
        # initial zone build: use the configured window, but for short datasets
        # warm up on at most a third of the data so trading can actually begin.
        first_build = min(cfg.build_window, max(50, n // 3))
        first_build = min(first_build, n - 1)
        self.zones = detect_zones(df.iloc[:first_build], cfg)

        for i in range(first_build, n):
            bar = df.iloc[i]

            # rolling walk-forward zone refresh (no lookahead)
            if cfg.rebuild_every and i % cfg.rebuild_every == 0:
                lo = max(0, i - cfg.build_window)
                self.zones = detect_zones(df.iloc[lo:i], cfg)

            if self.ruined:
                break

            if self.active is not None:
                self._manage(bar, i)
            if self.active is None:
                self._try_enter(bar, i)

        # close any dangling position at last price
        if self.active is not None:
            self._close(float(df.iloc[-1]["close"]), n - 1, "EOD")

        return self._metrics(df)

    def _metrics(self, df: pd.DataFrame) -> dict:
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        total = len(self.trades)
        gross_win = sum(t.pnl for t in wins)
        gross_loss = -sum(t.pnl for t in losses)
        roi = (self.balance - self.cfg.start_balance) / self.cfg.start_balance * 100
        return {
            "start_balance": round(self.cfg.start_balance, 2),
            "final_balance": round(self.balance, 2),
            "roi_pct": round(roi, 2),
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / total * 100, 2) if total else 0.0,
            "profit_factor": round(gross_win / gross_loss, 3) if gross_loss > 0 else None,
            "avg_win": round(gross_win / len(wins), 2) if wins else 0.0,
            "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0.0,
            "max_drawdown_pct": round(self.max_dd, 2),
            "account_blown": self.ruined,
            "zones_last": len(self.zones),
            "bars": len(df),
            "period": f"{df['datetime'].iloc[0].date()} -> {df['datetime'].iloc[-1].date()}",
        }


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #
def resolve_data_path(path: str) -> str:
    if os.path.isabs(path) and os.path.exists(path):
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.join(here, path)
    if os.path.exists(cand):
        return cand
    if os.path.exists(path):
        return path
    raise FileNotFoundError(f"Data file not found: {path}")


def print_report(mode: str, cfg: Config, m: dict):
    print("\n" + "=" * 66)
    print(f"  ZONE RANGE STRATEGY  |  mode = {mode.upper()}")
    print("=" * 66)
    print(f"  Data period      : {m['period']}  ({m['bars']} bars)")
    print(f"  Leverage / Risk  : {cfg.leverage:g}x  /  {cfg.risk_pct:g}% per trade (compounded)")
    print("-" * 66)
    print(f"  Start balance    : ${m['start_balance']:,.2f}")
    print(f"  Final balance    : ${m['final_balance']:,.2f}")
    print(f"  ROI              : {m['roi_pct']:+,.2f}%")
    print(f"  Trades           : {m['total_trades']}  "
          f"(W {m['wins']} / L {m['losses']}, win rate {m['win_rate_pct']}%)")
    print(f"  Profit factor    : {m['profit_factor']}")
    print(f"  Avg win / loss   : ${m['avg_win']:,.2f} / ${m['avg_loss']:,.2f}")
    print(f"  Max drawdown     : {m['max_drawdown_pct']}%")
    print(f"  Account blown    : {'YES  <-- wiped out' if m['account_blown'] else 'no'}")
    print(f"  Zones (last set) : {m['zones_last']}")
    print("=" * 66)


def main():
    ap = argparse.ArgumentParser(description="Zone range backtest for XAU/USD.")
    ap.add_argument("--data", default="cache_xauusd_gc_1h.csv",
                    help="CSV of time,open,high,low,close (default free GC=F 1h)")
    ap.add_argument("--tf", default="1H", help="resample timeframe (e.g. 1H, 4H, 15min)")
    ap.add_argument("--mode", default="both",
                    choices=["both", "aggressive", "conservative"],
                    help="risk profile to run")
    ap.add_argument("--risk", type=float, default=None, help="override risk %% per trade")
    ap.add_argument("--leverage", type=float, default=None, help="override leverage")
    ap.add_argument("--balance", type=float, default=10_000.0, help="start balance")
    ap.add_argument("--verbose", action="store_true", help="print every trade")
    ap.add_argument("--out", default="zone_range_results.json", help="results JSON path")
    args = ap.parse_args()

    path = resolve_data_path(args.data)
    raw = load_csv(path)
    df = resample(raw, args.tf)
    print(f"Loaded {len(raw)} raw candles -> {len(df)} {args.tf} bars from {os.path.basename(path)}")

    modes = ["conservative", "aggressive"] if args.mode == "both" else [args.mode]
    all_results = {}
    for mode in modes:
        cfg = Config(start_balance=args.balance, verbose=args.verbose)
        for k, v in PROFILES[mode].items():
            setattr(cfg, k, v)
        if args.risk is not None:
            cfg.risk_pct = args.risk
        if args.leverage is not None:
            cfg.leverage = args.leverage

        strat = ZoneRangeStrategy(cfg)
        metrics = strat.run(df)
        print_report(mode, cfg, metrics)
        all_results[mode] = {
            "config": asdict(cfg),
            "metrics": metrics,
            "zones": strat.zones,
        }

    here = os.path.dirname(os.path.abspath(__file__))
    out_path = args.out if os.path.isabs(args.out) else os.path.join(here, args.out)
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSaved detailed results -> {out_path}")


if __name__ == "__main__":
    main()
