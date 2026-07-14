#!/usr/bin/env python3
"""
prove_edge.py - Phase 0 statistical proof of the level-reversal strategy.

Fresh implementation (existing repo scripts are reference-only, per user).

Pipeline:
  1. LEVEL ENGINE  - fractal swings on higher TFs -> weighted cross-TF clustering
                     -> round-$5 confluence bonus. Recomputed walk-forward:
                     at any bar, levels use ONLY past data (zero lookahead).
  2. VALIDATION    - engine must reproduce the user's hand-drawn chart lines
                     (4096.09 / 4080.43 / 4070.74 / 4051.11) on the cached
                     MT5 spot window within $1.5.
  3. STRATEGY      - user's method: price touches a level -> candle CLOSES back
                     away from it (rejection confirmation) -> enter, SL beyond
                     spike extreme + buffer, TP = next level (line-to-line).
  4. PROOF BATTERY - expectancy vs 500-run random-level Monte Carlo (Z-score),
                     month-by-month stability, parameter sensitivity sweep,
                     and a quantitative test of each user claim.
  5. REPORT        - scripts/reports/proof_report.md + chart PNG.

Datasets:
  data/gc_1h.csv   - 1 year GC=F 1h   (main proof set)
  data/gc_15m.csv  - 60 days GC=F 15m (confirmation-TF validation)
  cache_xauusd_spot_mt5_1m_30d.csv - user's spot data (chart-line validation)
"""

import csv
import os
import math
import random
import statistics
import datetime as dt
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
REPORTS = os.path.join(HERE, "reports")
os.makedirs(REPORTS, exist_ok=True)

random.seed(7)

USER_LINES = [4096.09, 4080.43, 4070.74, 4051.11]

# ---------------------------------------------------------------------------
# data utils
# ---------------------------------------------------------------------------

def load_csv(path):
    rows = []
    with open(path) as f:
        for r in csv.reader(f):
            rows.append((int(float(r[0])), float(r[1]), float(r[2]),
                         float(r[3]), float(r[4])))
    rows.sort(key=lambda x: x[0])
    return rows


def resample(rows, sec):
    out = {}
    for t, o, h, l, c in rows:
        k = t // sec * sec
        if k not in out:
            out[k] = [o, h, l, c]
        else:
            out[k][1] = max(out[k][1], h)
            out[k][2] = min(out[k][2], l)
            out[k][3] = c
    return [(k, *v) for k, v in sorted(out.items())]

# ---------------------------------------------------------------------------
# 1) LEVEL ENGINE (fresh)
# ---------------------------------------------------------------------------

def fractal_swings(bars, lb):
    """Swing highs/lows: bar whose high(low) is the extreme of +/- lb bars."""
    out = []
    n = len(bars)
    for i in range(lb, n - lb):
        win = bars[i - lb:i + lb + 1]
        h = bars[i][2]
        l = bars[i][3]
        if h == max(b[2] for b in win):
            out.append(("H", bars[i][0], h))
        if l == min(b[3] for b in win):
            out.append(("L", bars[i][0], l))
    return out


def compute_levels(bars_1m_or_base, base_sec, tol=1.5, min_weight=4,
                   round5_bonus=1, tf_spec=None):
    """
    Build levels from PAST bars only (caller guarantees no future data).
    tf_spec: list of (resample_sec, fractal_lb, weight). Defaults chosen so it
    works from either 1m spot data or 1h futures data as base.
    """
    if tf_spec is None:
        if base_sec <= 900:
            tf_spec = [(900, 6, 1), (3600, 4, 2), (14400, 3, 3)]
        else:
            tf_spec = [(3600, 4, 2), (14400, 3, 3)]
    pts = []
    for sec, lb, w in tf_spec:
        bars = resample(bars_1m_or_base, sec) if sec != base_sec else list(bars_1m_or_base)
        for _, _, price in fractal_swings(bars, lb):
            pts.extend([price] * w)
    if not pts:
        return []
    pts.sort()
    levels = []
    cur = [pts[0]]
    for p in pts[1:]:
        if p - cur[-1] <= tol:
            cur.append(p)
        else:
            levels.append(cur)
            cur = [p]
    levels.append(cur)
    out = []
    for grp in levels:
        w = len(grp)
        center = statistics.mean(grp)
        # round-$5 confluence: snap + bonus if within $1 of a $5 multiple
        near5 = round(center / 5) * 5
        if abs(center - near5) <= 1.0:
            w += round5_bonus
        if w >= min_weight:
            out.append(round(center, 2))
    return out

# ---------------------------------------------------------------------------
# 2) chart-line validation on the user's cached spot data
# ---------------------------------------------------------------------------

def validate_chart_lines():
    path = os.path.join(HERE, "cache_xauusd_spot_mt5_1m_30d.csv")
    if not os.path.exists(path):
        return None
    spot = load_csv(path)
    levels = compute_levels(spot, 60, tol=1.5, min_weight=4)
    results = []
    for target in USER_LINES:
        best = min(levels, key=lambda x: abs(x - target)) if levels else None
        dist = abs(best - target) if best is not None else float("inf")
        results.append((target, best, dist, dist <= 1.5))
    return levels, results

# ---------------------------------------------------------------------------
# 3) STRATEGY - walk-forward confirmation entries
# ---------------------------------------------------------------------------

def walk_forward_trades(bars, base_sec, tol=1.0, sl_buffer=0.5,
                        recompute_every=24, lookback_bars=24 * 45,
                        min_rr=0.8, level_fn=None, warm=300):
    """
    bars: base-TF bars (e.g. 1h). At each recompute step, levels come only
    from the trailing lookback window ENDING at the current bar (no future).
    Returns list of trade dicts.
    """
    n = len(bars)
    trades = []
    levels = []
    last_recompute = -10**9
    i = warm
    while i < n - 1:
        if i - last_recompute >= recompute_every:
            past = bars[max(0, i - lookback_bars):i]
            levels = (level_fn or compute_levels)(past, base_sec, tol=1.5,
                                                  min_weight=4)
            last_recompute = i
        if not levels:
            i += 1
            continue
        t, o, h, l, c = bars[i]
        sig = None
        for lv in levels:
            if h >= lv - tol and c < lv - tol * 0.3 and o < lv:
                sig = ("S", lv, h)      # spiked into resistance, closed below
                break
            if l <= lv + tol and c > lv + tol * 0.3 and o > lv:
                sig = ("L", lv, l)      # spiked into support, closed above
                break
        if not sig:
            i += 1
            continue
        side, lv, spike = sig
        entry = c
        sl = spike + sl_buffer if side == "S" else spike - sl_buffer
        below = [x for x in levels if x < lv - 2]
        above = [x for x in levels if x > lv + 2]
        tp = (max(below) if below else lv - 15) if side == "S" \
            else (min(above) if above else lv + 15)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk < 0.5 or reward / risk < min_rr:
            i += 1
            continue
        # simulate bar-by-bar; also track MFE for claim tests
        res = None
        mfe = 0.0
        exit_j = None
        for j in range(i + 1, n):
            _, _, h2, l2, _ = bars[j]
            if side == "S":
                mfe = max(mfe, entry - l2)
                if h2 >= sl:
                    res = -risk
                    exit_j = j
                    break
                if l2 <= tp:
                    res = reward
                    exit_j = j
                    break
            else:
                mfe = max(mfe, h2 - entry)
                if l2 <= sl:
                    res = -risk
                    exit_j = j
                    break
                if h2 >= tp:
                    res = reward
                    exit_j = j
                    break
        if res is None:
            break
        trades.append({
            "t": t, "side": side, "level": lv, "entry": entry, "sl": sl,
            "tp": tp, "risk": risk, "pnl": res, "r": res / risk, "mfe": mfe,
            "exit_t": bars[exit_j][0],
        })
        i = exit_j
    return trades

# ---------------------------------------------------------------------------
# 4) PROOF BATTERY
# ---------------------------------------------------------------------------

def summarize(trades):
    if not trades:
        return {}
    wins = [x for x in trades if x["pnl"] > 0]
    rs = [x["r"] for x in trades]
    return {
        "n": len(trades),
        "win_rate": len(wins) / len(trades),
        "avg_r": statistics.mean(rs),
        "total_pnl": sum(x["pnl"] for x in trades),
        "avg_win": statistics.mean([x["pnl"] for x in wins]) if wins else 0,
        "avg_loss": statistics.mean([abs(x["pnl"]) for x in trades
                                     if x["pnl"] <= 0]) if len(wins) < len(trades) else 0,
        "avg_mfe": statistics.mean([x["mfe"] for x in trades]),
    }


def random_level_baseline(bars, base_sec, n_levels_typical, runs=500, **kw):
    """Same strategy code, random levels regenerated per recompute window."""
    lo = min(b[3] for b in bars)
    hi = max(b[2] for b in bars)

    results = []
    for run in range(runs):
        rng = random.Random(1000 + run)

        def rand_levels(past, bsec, tol=1.5, min_weight=4):
            plo = min(b[3] for b in past)
            phi = max(b[2] for b in past)
            k = max(3, n_levels_typical)
            return sorted(round(rng.uniform(plo, phi), 2) for _ in range(k))

        tr = walk_forward_trades(bars, base_sec, level_fn=rand_levels, **kw)
        if tr:
            results.append(statistics.mean([x["r"] for x in tr]))
    return results


def monthly_stability(trades):
    by_m = defaultdict(list)
    for x in trades:
        m = dt.datetime.fromtimestamp(x["t"], dt.timezone.utc).strftime("%Y-%m")
        by_m[m].append(x["r"])
    return {m: (len(v), statistics.mean(v)) for m, v in sorted(by_m.items())}


def sensitivity_sweep(bars, base_sec):
    grid = []
    for tol in (0.7, 1.0, 1.5):
        for slb in (0.3, 0.5, 1.0):
            tr = walk_forward_trades(bars, base_sec, tol=tol, sl_buffer=slb)
            s = summarize(tr)
            if s:
                grid.append((tol, slb, s["n"], s["avg_r"], s["win_rate"]))
    return grid


def claim_tests(trades, bars, base_sec):
    """Quantify the user's specific claims."""
    out = {}
    if trades:
        # claim: "$50-60 avg move in our favour"
        out["avg_mfe"] = statistics.mean([x["mfe"] for x in trades])
        out["mfe_ge_50"] = sum(1 for x in trades if x["mfe"] >= 50) / len(trades)
        # claim: "SL from spike high mostly never touched after confirmation"
        out["sl_hit_rate"] = sum(1 for x in trades if x["pnl"] <= 0) / len(trades)
    # claim: "direction change mostly at $5 multiples"
    swings = fractal_swings(resample(bars, 3600 * 4), 3)
    if swings:
        d5 = [min(abs(p - round(p / 5) * 5), 5 - abs(p - round(p / 5) * 5))
              for _, _, p in swings]
        # distance from nearest $5 multiple; uniform expectation = 1.25
        out["swing_dist_5"] = statistics.mean(d5)
        out["swing_dist_5_expected_random"] = 1.25
        out["n_swings"] = len(swings)
    return out

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("PHASE 0 PROOF - fresh level engine, walk-forward, zero lookahead")
    print("=" * 70)

    # ---- chart line validation (user's spot data)
    print("\n[1] CHART-LINE VALIDATION (user's MT5 spot cache)")
    v = validate_chart_lines()
    if v:
        levels, results = v
        print(f"    engine produced {len(levels)} levels on that window")
        for target, best, dist, ok in results:
            print(f"    user line {target:9.2f} -> nearest engine level "
                  f"{best:9.2f} (dist ${dist:.2f}) {'MATCH' if ok else 'MISS'}")
    else:
        print("    cached spot CSV not found - skipped")

    # ---- main proof on 1 year of 1h data
    print("\n[2] WALK-FORWARD STRATEGY, 1h GC=F, 1 year")
    h1 = load_csv(os.path.join(DATA, "gc_1h.csv"))
    trades = walk_forward_trades(h1, 3600)
    s = summarize(trades)
    for k, val in s.items():
        print(f"    {k:12s}: {val:,.3f}" if isinstance(val, float) else f"    {k:12s}: {val}")

    # ---- random baseline
    print("\n[3] RANDOM-LEVEL MONTE CARLO (500 runs, identical entry logic)")
    typical_n = 8
    base = random_level_baseline(h1, 3600, typical_n, runs=500)
    if base and s:
        mu = statistics.mean(base)
        sd = statistics.stdev(base)
        z = (s["avg_r"] - mu) / sd if sd > 0 else 0
        pct = sum(1 for b in base if b >= s["avg_r"]) / len(base)
        print(f"    baseline avg R: {mu:+.3f} +/- {sd:.3f}")
        print(f"    strategy avg R: {s['avg_r']:+.3f}")
        print(f"    Z-score       : {z:+.2f}   (need >= 2.0)")
        print(f"    p (empirical) : {pct:.3f}  share of random runs >= strategy")
    else:
        z = 0

    # ---- monthly stability
    print("\n[4] MONTH-BY-MONTH STABILITY")
    ms = monthly_stability(trades)
    pos = 0
    for m, (n, avg_r) in ms.items():
        flag = "+" if avg_r > 0 else "-"
        pos += avg_r > 0
        print(f"    {m}: n={n:3d}  avg R {avg_r:+.2f}  {flag}")
    if ms:
        print(f"    positive months: {pos}/{len(ms)}")

    # ---- sensitivity
    print("\n[5] PARAMETER SENSITIVITY (tol x SL buffer)")
    grid = sensitivity_sweep(h1, 3600)
    pos_cells = 0
    for tol, slb, n, avg_r, wr in grid:
        pos_cells += avg_r > 0
        print(f"    tol={tol:.1f} slb={slb:.1f}: n={n:3d} avgR={avg_r:+.3f} wr={wr:.0%}")
    print(f"    positive cells: {pos_cells}/{len(grid)}")

    # ---- 15m confirmation validation (60 days)
    print("\n[6] 15m CONFIRMATION TF (60 days)")
    m15 = load_csv(os.path.join(DATA, "gc_15m.csv"))
    tr15 = walk_forward_trades(m15, 900, recompute_every=96,
                               lookback_bars=96 * 30, warm=500)
    s15 = summarize(tr15)
    for k, val in s15.items():
        print(f"    {k:12s}: {val:,.3f}" if isinstance(val, float) else f"    {k:12s}: {val}")

    # ---- user claim tests
    print("\n[7] USER CLAIM TESTS")
    ct = claim_tests(trades, h1, 3600)
    for k, val in ct.items():
        print(f"    {k:28s}: {val:,.3f}" if isinstance(val, float) else f"    {k:28s}: {val}")

    # ---- verdict
    print("\n" + "=" * 70)
    stable = ms and pos >= math.ceil(len(ms) * 0.6)
    robust = grid and pos_cells >= math.ceil(len(grid) * 0.6)
    go = z >= 2.0 and stable and robust
    print(f"GATE: Z>=2.0 [{z >= 2.0}]  stability [{bool(stable)}]  "
          f"robustness [{bool(robust)}]")
    print(f"VERDICT: {'GO' if go else 'NO-GO'}")
    print("=" * 70)

    return {
        "chart_validation": v, "summary": s, "z": z, "baseline": base,
        "monthly": ms, "grid": grid, "s15": s15, "claims": ct, "go": go,
        "trades": trades,
    }


if __name__ == "__main__":
    main()
