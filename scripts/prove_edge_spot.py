#!/usr/bin/env python3
"""
prove_edge_spot.py - Re-run the Phase 0 proof battery on REAL SPOT XAUUSD only.

Addresses the user's concern that the year-long proof used GC=F futures.

Part A: PROXY VALIDATION
    Overlap window (user's MT5 spot 1m cache vs GC=F 15m):
    - correlation of 15m log returns
    - basis (GC=F - spot) mean and standard deviation
    If returns correlate ~1 and the basis is near-constant, levels/swings on
    GC=F are structurally identical to spot, validating the 1-year result.

Part B: SPOT-ONLY WALK-FORWARD PROOF
    The user's full method (levels -> touch -> confirmation close -> SL beyond
    spike -> TP next level), walk-forward with zero lookahead, on the user's
    OWN broker spot 1m data (resampled to 15m), plus a 300-run random-level
    Monte Carlo on the same spot data for the Z-score.

Everything here is real traded market data. Nothing synthetic.
"""

import os
import csv
import math
import random
import statistics

from prove_edge import (load_csv, resample, walk_forward_trades, summarize,
                        compute_levels, monthly_stability)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SPOT_CSV = os.path.join(HERE, "cache_xauusd_spot_mt5_1m_30d.csv")

random.seed(11)


def part_a_proxy_validation():
    print("=" * 70)
    print("[A] PROXY VALIDATION: GC=F futures vs user's REAL MT5 spot")
    print("=" * 70)
    spot_1m = load_csv(SPOT_CSV)
    gc_15m = load_csv(os.path.join(DATA, "gc_15m.csv"))
    spot_15m = resample(spot_1m, 900)

    spot_map = {t: c for t, o, h, l, c in spot_15m}
    pairs = [(c, spot_map[t]) for t, o, h, l, c in gc_15m if t in spot_map]
    print(f"    overlapping 15m bars: {len(pairs)}")
    if len(pairs) < 300:
        print("    insufficient overlap")
        return

    # log-return correlation
    rf = [math.log(pairs[i][0] / pairs[i - 1][0]) for i in range(1, len(pairs))]
    rs = [math.log(pairs[i][1] / pairs[i - 1][1]) for i in range(1, len(pairs))]
    mf, ms_ = statistics.mean(rf), statistics.mean(rs)
    cov = sum((a - mf) * (b - ms_) for a, b in zip(rf, rs)) / (len(rf) - 1)
    corr = cov / (statistics.stdev(rf) * statistics.stdev(rs))

    basis = [f - s for f, s in pairs]
    print(f"    15m log-return correlation : {corr:.4f}")
    print(f"    basis (GC=F - spot)        : mean ${statistics.mean(basis):.2f}"
          f"  stdev ${statistics.stdev(basis):.2f}")
    print(f"    => futures is a {'VALID' if corr > 0.95 else 'QUESTIONABLE'}"
          f" structural proxy for spot swings/levels")
    return corr


def part_b_spot_proof():
    print()
    print("=" * 70)
    print("[B] SPOT-ONLY WALK-FORWARD PROOF (user's own MT5 broker data)")
    print("=" * 70)
    spot_1m = load_csv(SPOT_CSV)
    spot_15m = resample(spot_1m, 900)
    print(f"    spot 15m bars: {len(spot_15m)}")

    # walk-forward on 15m spot; levels recomputed every 8h from trailing 15 days
    kw = dict(recompute_every=32, lookback_bars=96 * 15, warm=96 * 5)
    trades = walk_forward_trades(spot_15m, 900, **kw)
    s = summarize(trades)
    if not s:
        print("    no trades generated")
        return
    for k, val in s.items():
        print(f"    {k:12s}: {val:,.3f}" if isinstance(val, float)
              else f"    {k:12s}: {val}")

    # every single trade, so the user can verify against their charts
    print("\n    trade list (UTC):")
    import datetime as dt
    for x in trades:
        ts = dt.datetime.fromtimestamp(x["t"], dt.timezone.utc)
        print(f"      {ts:%m-%d %H:%M} {x['side']} lvl={x['level']:8.2f} "
              f"entry={x['entry']:8.2f} sl={x['sl']:8.2f} tp={x['tp']:8.2f} "
              f"pnl={x['pnl']:+7.2f} R={x['r']:+.2f} mfe=${x['mfe']:.1f}")

    # random-level Monte Carlo on the SAME spot data
    print("\n    random-level Monte Carlo (300 runs, same entry logic):")
    base = []
    for run in range(300):
        rng = random.Random(2000 + run)

        def rand_levels(past, bsec, tol=1.5, min_weight=4):
            plo = min(b[3] for b in past)
            phi = max(b[2] for b in past)
            return sorted(round(rng.uniform(plo, phi), 2) for _ in range(8))

        tr = walk_forward_trades(spot_15m, 900, level_fn=rand_levels, **kw)
        if tr:
            base.append(statistics.mean([x["r"] for x in tr]))
    if base:
        mu, sd = statistics.mean(base), statistics.stdev(base)
        z = (s["avg_r"] - mu) / sd if sd > 0 else 0
        pct = sum(1 for b in base if b >= s["avg_r"]) / len(base)
        print(f"    baseline avg R : {mu:+.3f} +/- {sd:.3f}")
        print(f"    strategy avg R : {s['avg_r']:+.3f}")
        print(f"    Z-score        : {z:+.2f}  (need >= 2.0)")
        print(f"    empirical p    : {pct:.3f}")
    print()
    print("=" * 70)
    n = s["n"]
    # minimum n for a Z>=2 detection given observed effect size
    print(f"NOTE: with only {n} trades on 25 days of spot data, even a real "
          f"edge of +0.2R would need ~{math.ceil((2.0 / 0.2) ** 2)} trades "
          f"to clear Z>=2. Small-sample results are directional, not final.")
    print("=" * 70)


if __name__ == "__main__":
    part_a_proxy_validation()
    part_b_spot_proof()
