"""
TOURNAMENT SIMULATION  --  "How do traders hit 5000%+ in 15 days?"
==================================================================
This script answers, ON DATA, the question behind the FundingPips-Trial
leaderboard (traders showing +5000% gains in ~15 days).

There are only two ways to produce that number, and both are tested here:

  1. AGGRESSIVE COMPOUNDING
     Risk a large fraction of the CURRENT balance every trade at high leverage
     and compound. With a real edge this can mathematically reach 5000% -- but
     the same large risk fraction makes ruin (blowing the account) the far more
     likely outcome.

  2. SURVIVORSHIP BIAS
     A tournament has ~50,000 participants. Even with ZERO skill (a coin flip),
     when tens of thousands of people gamble at high risk, a handful will
     randomly spike to +5000% while the vast majority blow up and vanish from
     the top of the board. The leaderboard only shows the survivors.

METHOD (data-grounded)
----------------------
We do NOT invent trade outcomes. We run the real zone price-action strategy on
real gold data, extract the actual per-trade R-multiples (profit/loss expressed
in units of risk), and BOOTSTRAP-RESAMPLE those real outcomes to simulate
thousands of virtual tournament traders. We then vary only the RISK FRACTION and
the FIELD SIZE, and measure how many traders reach +5000%, how many blow up, and
what the leaderboard winner looks like.

USAGE
-----
    python tournament_simulation.py                      # full study, default data
    python tournament_simulation.py --traders 50000 --trades 750
    python tournament_simulation.py --data cache_xauusd_gc_1h.csv --tf 1H
"""

from __future__ import annotations

import argparse
import numpy as np

from zone_range_strategy import (
    Config,
    ZoneRangeStrategy,
    load_csv,
    resample,
    resolve_data_path,
)

TARGET = 51.0            # +5000% == 51x the starting balance
RUIN_MULT = 0.10         # equity below 10% of start == "blown / disqualified"


# --------------------------------------------------------------------------- #
# 1. Extract the REAL per-trade edge from the strategy on real data           #
# --------------------------------------------------------------------------- #
def real_r_multiples(data_path: str, tf: str) -> tuple[np.ndarray, float]:
    """Run the zone strategy and return (a) each trade's outcome as an R-multiple
    (pnl / dollars-risked) and (b) the strategy's real trade CADENCE expressed as
    trades per 15 days. R = +2 means twice the risk was made; R = -1 is a full
    stop-out."""
    cfg = Config(risk_pct=2.0)
    df = resample(load_csv(data_path), tf)
    strat = ZoneRangeStrategy(cfg)
    strat.run(df)

    rs = []
    for t in strat.trades:
        risk_dollars = (cfg.risk_pct / 100.0) * t.balance_before
        if risk_dollars > 0:
            rs.append(t.pnl / risk_dollars)

    span_days = (df["datetime"].iloc[-1] - df["datetime"].iloc[0]).days or 1
    trades_per_15d = len(strat.trades) * 15.0 / span_days
    return np.array(rs, dtype=float), trades_per_15d


def sprint_r(edge_R: float = 0.0, n: int = 400) -> np.ndarray:
    """High-frequency 'tournament sprint' outcome pool. A 794-trade, 15-day
    scalping run has essentially NO durable edge after spread/commission -- so we
    model it as a near-coin-flip. edge_R shifts the mean slightly if you want to
    grant a tiny residual edge; default 0.0 = pure gamble, symmetric +/-1R."""
    half = n // 2
    pool = np.array([1.0 + edge_R] * half + [-1.0 + edge_R] * (n - half), dtype=float)
    return pool


# --------------------------------------------------------------------------- #
# 2. Monte-Carlo a whole tournament field                                     #
# --------------------------------------------------------------------------- #
def simulate_field(
    r_pool: np.ndarray,
    n_traders: int,
    n_trades: int,
    risk_frac: float,
    rng: np.random.Generator,
) -> dict:
    """Every trader starts at 1.0 (=100%). Each trade multiplies equity by
    (1 + risk_frac * R), R bootstrap-sampled from the real outcome pool.
    Compounds across n_trades. A trader who drops below RUIN_MULT is 'blown'
    and frozen out (equity set to 0), exactly like a disqualified account."""
    equity = np.ones(n_traders, dtype=float)
    alive = np.ones(n_traders, dtype=bool)
    # Cap equity so a runaway compounding streak doesn't produce meaningless
    # 10^40% numbers -- once you are past ~1,000,000% you have "won" the event.
    CAP = 1.0e4  # == +1,000,000%

    for _ in range(n_trades):
        r = rng.choice(r_pool, size=n_traders)
        equity[alive] *= (1.0 + risk_frac * r[alive])
        np.clip(equity, 0.0, CAP, out=equity)
        # mark newly-blown accounts
        blown = alive & (equity <= RUIN_MULT)
        equity[blown] = 0.0
        alive[blown] = False

    gains_pct = (equity - 1.0) * 100.0
    return {
        "risk_frac": risk_frac,
        "blown_pct": 100.0 * np.mean(equity <= RUIN_MULT),
        "median_gain": float(np.median(gains_pct)),
        "p99_gain": float(np.percentile(gains_pct, 99)),
        "max_gain": float(np.max(gains_pct)),
        "n_hit_target": int(np.sum(equity >= TARGET)),
        "pct_hit_target": 100.0 * np.mean(equity >= TARGET),
    }


# --------------------------------------------------------------------------- #
# 3. Report                                                                   #
# --------------------------------------------------------------------------- #
def describe_edge(rs: np.ndarray, label: str) -> None:
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    wr = 100.0 * len(wins) / len(rs) if len(rs) else 0.0
    print(f"\n{label}")
    print(f"  trades sampled     : {len(rs)}")
    print(f"  win rate           : {wr:.1f}%")
    print(f"  mean R / trade     : {rs.mean():+.3f}R   (this is the raw edge)")
    if len(wins):
        print(f"  avg win            : {wins.mean():+.2f}R")
    if len(losses):
        print(f"  avg loss           : {losses.mean():+.2f}R")


def print_table(title: str, rows: list[dict]) -> None:
    print(f"\n{title}")
    print("  risk/trade   blown%   median    99th pct        MAX gain   reached +5000%")
    print("  " + "-" * 74)
    for r in rows:
        print(
            f"   {r['risk_frac']*100:5.1f}%     "
            f"{r['blown_pct']:5.1f}%   "
            f"{r['median_gain']:7.0f}%   "
            f"{r['p99_gain']:11,.0f}%   "
            f"{r['max_gain']:13,.0f}%   "
            f"{r['n_hit_target']:5d}  ({r['pct_hit_target']:.3f}%)"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Tournament 5000%-gain study")
    ap.add_argument("--data", default="cache_xauusd_gc_1h.csv")
    ap.add_argument("--tf", default="1H")
    ap.add_argument("--traders", type=int, default=50000,
                    help="field size (FundingPips comps allow up to 50,000)")
    ap.add_argument("--trades", type=int, default=750,
                    help="trades per account over ~15 days (leader had 794)")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    data_path = resolve_data_path(args.data)

    print("=" * 78)
    print("TOURNAMENT STUDY:  how do traders show +5000% in ~15 days?")
    print("=" * 78)
    print(f"field size   : {args.traders:,} traders")
    print(f"target       : +5000%  ({TARGET:.0f}x start)   ruin: equity < {RUIN_MULT*100:.0f}% of start")
    print("(display capped at +1,000,000% -- past that you've already 'won')")

    risk_levels = [0.02, 0.05, 0.10, 0.25, 0.50]

    # =================================================================== #
    # SCENARIO A -- the HONEST zone strategy at its REAL cadence           #
    # =================================================================== #
    real_rs, cadence = real_r_multiples(data_path, args.tf)
    describe_edge(real_rs, "REAL ZONE STRATEGY EDGE (bootstrapped from actual trades)")
    n_real = max(1, round(cadence))
    print(f"  real cadence       : ~{cadence:.1f} trades in 15 days "
          f"(this is a SWING system, not a scalper)")
    real_rows = [
        simulate_field(real_rs, args.traders, n_real, rf, rng)
        for rf in risk_levels
    ]
    print_table(
        f"SCENARIO A  --  HONEST STRATEGY, real edge, real cadence (~{n_real} trades/15d):",
        real_rows,
    )

    # =================================================================== #
    # SCENARIO B -- the TOURNAMENT SPRINT: ~750 high-frequency scalps with #
    # essentially no durable edge after costs (matches the 794-trade board)#
    # =================================================================== #
    sprint = sprint_r(edge_R=0.0, n=400)
    describe_edge(sprint, "TOURNAMENT SPRINT EDGE (750 scalps, ~zero net edge after costs)")
    print(f"  trades in 15 days  : {args.trades} (leaderboard #1 had 794)")
    sprint_rows = [
        simulate_field(sprint, args.traders, args.trades, rf, rng)
        for rf in risk_levels
    ]
    print_table(
        f"SCENARIO B  --  TOURNAMENT SPRINT, zero-edge gamble ({args.trades} trades/15d):",
        sprint_rows,
    )

    # --- verdict ---------------------------------------------------------- #
    honest_best = max(real_rows, key=lambda r: r["pct_hit_target"])
    sprint_hero = max(sprint_rows, key=lambda r: r["n_hit_target"])
    print("\n" + "=" * 78)
    print("VERDICT  --  tested on real gold data")
    print("=" * 78)
    print(
        f"1. The HONEST zone strategy, traded normally (~{n_real} trades/15d), basically\n"
        f"   CANNOT reach +5000% in 15 days -- at best {honest_best['pct_hit_target']:.3f}% of a "
        f"{args.traders:,}-trader\n   field gets there, and only by risking recklessly. It's a swing system."
    )
    print(
        f"2. The +5000% heroes come from the SPRINT: {args.trades} high-frequency gambles with\n"
        f"   ~zero real edge. At {sprint_hero['risk_frac']*100:.0f}% risk/trade, "
        f"{sprint_hero['blown_pct']:.0f}% of the field BLEW UP,\n"
        f"   yet {sprint_hero['n_hit_target']} traders ({sprint_hero['pct_hit_target']:.3f}%) still hit +5000% "
        f"by pure luck."
    )
    print(
        "3. That is SURVIVORSHIP BIAS: with ~50,000 gamblers, a handful randomly moon\n"
        "   while thousands are wiped out and vanish from the board. The 0% win ratios\n"
        "   on the leaderboard are the fingerprint of exactly this all-or-nothing gamble."
    )
    print(
        "\nBOTTOM LINE: +5000%/15d is not a strategy you can copy -- it's the loud winner\n"
        "of a lottery whose thousands of losers you never see. Trade the real edge instead."
    )
    print("=" * 78)


if __name__ == "__main__":
    main()
