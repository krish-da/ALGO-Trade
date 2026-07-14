#!/usr/bin/env python3
"""Generates the Phase 0 proof chart PNG (3 panels) into scripts/reports/."""

import os
import datetime as dt
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import prove_edge as pe

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "reports", "proof_chart.png")


def main():
    res = pe.main()
    trades = res["trades"]
    base = res["baseline"]
    s = res["summary"]
    ms = res["monthly"]

    h1 = pe.load_csv(os.path.join(pe.DATA, "gc_1h.csv"))
    cutoff = h1[-1][0] - 30 * 86400
    recent = [b for b in h1 if b[0] >= cutoff]
    levels = pe.compute_levels([b for b in h1 if b[0] < cutoff][-24 * 45:], 3600)

    fig, axes = plt.subplots(3, 1, figsize=(13, 14))
    fig.suptitle("Phase 0 Proof — Level-Reversal Strategy on Gold (walk-forward, zero lookahead)",
                 fontsize=13)

    # panel 1: price + levels + trades (last 30 days)
    ax = axes[0]
    ts = [dt.datetime.fromtimestamp(b[0], dt.timezone.utc) for b in recent]
    ax.plot(ts, [b[4] for b in recent], lw=0.8, color="#1a1a2e", label="GC=F 1h close")
    lo = min(b[3] for b in recent)
    hi = max(b[2] for b in recent)
    for lv in levels:
        if lo - 5 <= lv <= hi + 5:
            ax.axhline(lv, color="#2563eb", lw=0.7, alpha=0.6)
    for x in trades:
        if x["t"] >= cutoff:
            t0 = dt.datetime.fromtimestamp(x["t"], dt.timezone.utc)
            win = x["pnl"] > 0
            ax.scatter([t0], [x["entry"]],
                       marker="^" if x["side"] == "L" else "v",
                       color="#16a34a" if win else "#dc2626", s=36, zorder=5)
    ax.set_title(f"Last 30 days: engine levels (blue) + trades (green=win, red=loss). "
                 f"Full-year: {s['n']} trades, {s['win_rate']:.0%} win, avg R {s['avg_r']:+.3f}")
    ax.legend(loc="upper left", fontsize=8)

    # panel 2: strategy vs random-level Monte Carlo
    ax = axes[1]
    ax.hist(base, bins=40, color="#94a3b8", edgecolor="white")
    ax.axvline(s["avg_r"], color="#dc2626", lw=2,
               label=f"real levels avg R = {s['avg_r']:+.3f}")
    mu = statistics.mean(base)
    ax.axvline(mu, color="#1a1a2e", lw=1.5, ls="--",
               label=f"random mean = {mu:+.3f}")
    ax.set_title(f"500 random-level runs, identical entry logic — Z = {res['z']:+.2f} "
                 f"(needed >= 2.0). The strategy is indistinguishable from random lines.")
    ax.set_xlabel("avg R per trade")
    ax.legend(fontsize=9)

    # panel 3: monthly avg R
    ax = axes[2]
    months = list(ms.keys())
    vals = [ms[m][1] for m in months]
    colors = ["#16a34a" if v > 0 else "#dc2626" for v in vals]
    ax.bar(months, vals, color=colors)
    ax.axhline(0, color="#1a1a2e", lw=0.8)
    ax.set_title("Month-by-month avg R — 6/13 positive: no stable edge. "
                 "(Jun-2026 +0.68 explains why the last few weeks LOOKED great)")
    ax.tick_params(axis="x", rotation=45, labelsize=8)

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(OUT, dpi=110)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
