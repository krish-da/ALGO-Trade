# Gold Zone Price-Action Strategy (XAU/USD)

Backtesting research for the **horizontal "zone line" + price-action method** — at a
zone, read the candle and enter in the direction **price commits to** (bounce *or*
breakout), then ride to the next zone. Sniper entries: tight stop at the zone, big
target, leverage and compounding on top.

## What's in here

| File | Purpose |
| --- | --- |
| `scripts/zone_range_strategy.py` | **Main engine.** Major-zone detection + price-action (direction-following) entries + compounding risk modes. |
| `scripts/fetch_gold_data.py` | Downloads free historical gold data (Yahoo `GC=F`) into a CSV. |
| `scripts/cache_xauusd_gc_1h.csv` | 2 years of hourly gold candles (fetched, free source). |
| `scripts/cache_xauusd_spot_mt5_1m_30d.csv` | 30 days of 1-minute XAU/USD from MT5 (kept as a shorter, range-bound sample). |
| `scripts/gold_bramhastra_v2.py` | **Old script, kept for reference only.** Its rejection-percentile entry logic did not generalize; only its zone detection was reliable. Do not rely on it. |
| `scripts/zone_range_results.json` | Latest backtest output (metrics + config + zones per mode). |

## The strategy

1. **Zone detection** (the part that works): find swing-pivot highs/lows, cluster
   nearby pivots into single levels, keep only levels touched enough times, and retain
   just the **few strongest major zones** (`max_zones`, default 8) — like the handful of
   lines drawn on the chart, not dozens of noise levels. Zones are rebuilt on a rolling
   window as the backtest walks forward (no lookahead).
2. **Entries — follow the move (`price_action`, default):** when price is at a zone and
   prints a *decisive* candle (body ≥ `body_frac` of its range), enter in that direction:
   - decisive **bullish** candle off/through a zone → **LONG**, target the next zone up
   - decisive **bearish** candle off/through a zone → **SHORT**, target the next zone down

   This deliberately captures **both** bounces *and* breakouts — "go where price moves."
   A `reversion` mode (fade the zone: buy support / sell resistance) is kept only for
   comparison via `signal_mode`.
3. **Stops (sniper):** just beyond the zone you launched from (tight), with a realistic
   minimum distance and spread/slippage applied.
4. **Exits:** target = the next zone in the trade's direction; if there is no next zone
   (price broke into open space), target a measured `tp_fallback_rr × risk` and let the
   **trailing stop** ride the trend.
5. **Sizing:** risk a % of the *current* balance at a set leverage, so wins compound.

### Risk profiles

| Mode | Risk / trade | Leverage | Notes |
| --- | --- | --- | --- |
| `conservative` | 2% | 5x | Survivable, realistic. |
| `aggressive` | 10% | 10x | Mirrors the "10x + compound" chart notes. High variance. |

## Setup

```bash
pip install pandas numpy yfinance
```

## Usage

```bash
cd scripts

# 1. (optional) refresh the free data
python fetch_gold_data.py --interval 1h --period 2y

# 2. run the backtest (both risk profiles)
python zone_range_strategy.py --data cache_xauusd_gc_1h.csv --tf 1H --mode both

# other examples
python zone_range_strategy.py --mode aggressive --tf 4H
python zone_range_strategy.py --mode conservative --risk 3 --leverage 5 --verbose
```

Results print to the console and save to `zone_range_results.json`.

## What the backtests actually show

All runs include **spread + slippage costs**. The edge is the *shape* of the returns:
a ~45-70% win rate but **winners ~3x bigger than losers** (tight sniper stop, ride to
the next zone) — a profit factor well above 1.

| Data / timeframe | Mode | ROI | Win rate | Profit factor | Max DD |
| --- | --- | --- | --- | --- | --- |
| 2yr hourly, 1H | aggressive | ~ +26% | 45% | 2.7 | ~6% |
| 2yr hourly, 4H | aggressive | ~ +31% | 83% | ~28 | ~1% |
| 30-day ranging, 15min | aggressive | ~ +12% | 69% | ~5.9 | ~1% |

The direction-following method stays **positive even on the choppy 30-day range** — the
version that only faded zones lost money there. Numbers vary with timeframe and the
rolling zone set; treat them as indicative, not guarantees.

### Read this before trusting any number

- **Not the 5000% fantasy.** This is a legitimate positive-expectancy system returning
  tens of percent, not thousands. Chasing the tournament numbers means max-leverage
  gambling, not this.
- **Trend still helps.** Following breakouts benefits from gold's strong trends. Expect
  lower returns and more chop losses in a genuinely directionless market.
- **Optimistic fills.** Even with modeled spread/slippage, tight stops at zones assume
  cleaner fills than a live, leveraged account gets (weekend gaps, news spikes).
- **`GC=F` ≠ true broker XAU/USD.** COMEX futures track spot closely but are not your
  broker's exact feed, spread, or swap.
- **The 5000%+ leaderboard is not an edge.** Those FundingPips-Trial tournament numbers
  come from free demo contests with tens of thousands of entrants using max leverage.
  A handful spike by luck (survivorship bias); most blow up. Do not size a live/funded
  account around reproducing them.

## The "+5000% in 15 days" study (`tournament_simulation.py`)

You asked how the FundingPips-Trial leaderboard traders (e.g. +5680%, 794 trades,
**0% win ratio**) get those numbers. This script answers it *on data* with a Monte
Carlo of a full ~50,000-trader field, bootstrapping the **real** per-trade outcomes
of our zone strategy.

```bash
cd scripts
python tournament_simulation.py --traders 50000 --trades 750
```

Two scenarios are simulated:

| Scenario | What it models | Can it hit +5000%? |
| --- | --- | --- |
| **A — Honest strategy** | Real zone edge (+0.29R/trade) at its real swing cadence (~1 trade/15d) | **No** — 0% of a 50k field, even risking 50%/trade |
| **B — Tournament sprint** | 750 high-frequency scalps with ~zero net edge, high risk/trade | **Yes, by luck** — at 10% risk, **83% blow up** but ~0.27% (≈137 traders) still moon |

**Conclusion (data-backed):** +5000%/15d is **not a copyable strategy**. It is the
loud survivor of a lottery — with tens of thousands gambling all-or-nothing at high
leverage, a few randomly spike while thousands are wiped out and disappear from the
board. The **0% win ratios** on that leaderboard are the fingerprint of exactly this
all-or-nothing behavior. The honest positive-expectancy edge (Scenario A / the main
backtest) is what actually survives.

## MetaTrader 5 data

The MetaTrader5 Python API is **Windows-only**, so it cannot run on the Linux backtest
host — that's why this repo uses free Yahoo data instead. To use real broker data,
export a CSV from MT5 and point `--data` at it. The loader expects rows of
`time,open,high,low,close` (unix seconds, no header).

**Security:** never commit or paste account credentials. If a password has been shared
anywhere, rotate it immediately.

## Disclaimer

Educational backtesting only. Past performance does not predict future results.
Leverage can wipe out an account faster than it grows it.
