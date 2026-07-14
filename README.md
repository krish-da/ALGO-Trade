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

Three scenarios are simulated:

| Scenario | What it models | Can it hit +5000%? |
| --- | --- | --- |
| **A — Honest strategy** | Real zone edge (+0.29R/trade) at its real swing cadence (~1 trade/15d) | **No** — 0% of a 50k field, even risking 50%/trade |
| **B — Tournament sprint** | 750 high-frequency scalps with ~zero net edge, high risk/trade | **Yes, by luck** — at 10% risk, **83% blow up** but ~0.27% (≈137 traders) still moon |
| **C — July rules (below)** | 10% static floor + 5% daily + 1:100, real edge, house-money sizing | **Yes, rarely** — ~0.02% (≈10 traders) hit +5000%, **87% disqualified** |

## Does the strategy fit the FundingPips **July** tournament rules?

The July competition rules (up to 50,000 entrants, top-20 + lucky-dip prizes):

- **10% max loss — STATIC** (fixed at 90% of the *starting* balance; does **not** trail up with profit)
- **5% daily loss limit** (counts closed + floating, resets 00:00 UTC+3)
- **Leverage up to 1:100**, **no Expert Advisors**, **one account per person**, no unrealistic fills

**Rule fit:** the strategy's aggressive mode uses ~10x leverage (well under 1:100), trades
manually-drawn zones (not an EA), and can respect the 10% / 5% limits — so the **method is
tournament-legal**. Legal, however, does **not** make +5000% repeatable.

**How the +5000% is actually made under these exact rules (Scenario C, tested on data):**

1. **The static floor is the secret.** Because max-loss is fixed at 90% of the *start* and
   never trails up, every dollar of profit becomes a permanent cushion. Size each bet off the
   **distance to that floor** ("house money") and you can bet big once ahead while **never**
   breaching the max-loss rule — the simulation confirms a **0.0% static-floor DQ** rate.
2. **The 5% daily limit is the real killer.** With house-money sizing, **~87% are disqualified**,
   almost entirely by the daily limit during the first few days *before* a cushion exists.
   (A 50-trades/day zero-edge gambler is daily-DQ'd ~100% of the time — hyper-scalping can't
   survive these rules.)
3. **The winner is a rule-compliant survivor.** Of 50,000 traders, only **~0.02% (≈10)** reach
   +5000% — by catching a hot early streak, converting it to house money, then riding gold's
   trend at high leverage. The thousands who caught a cold streak were DQ'd on day 1–3 and
   vanish from the board. That's the same survivorship story, now *inside the rules*.

**Bottom line:** yes, +5000% can happen legally within the July rules — but as the loud
1-in-thousands survivor of a legal lottery, **not** a copyable edge. Trade the real zone edge
for real money and treat the leaderboard number as survivorship.

## The "0% win ratio" clue — grid / floating test (`grid_floating_test.py`)

A **0% win ratio next to 794 trades** is a huge tell: it almost certainly means the
trades were **never closed** — they are **open, floating** positions. That is the
signature of a **grid / martingale / averaging-in** system: keep opening lots, never
realise a loss, and let a strong trend inflate the *floating* (unrealised) profit. The
dashboard then shows a giant gain with a 0% *closed*-win ratio.

This script runs exactly that on real gold data, over every rolling 15-day window:

```bash
cd scripts
python grid_floating_test.py --leverage 400 --grid-step 3 --lot-frac 0.30
```

Results across 463 windows (never-close grid on 2yr gold):

| Aggression | Blows up (margin call) | Flashes ≥ +5000% floating | Best flash | Median FINAL |
| --- | --- | --- | --- | --- |
| 100x, moderate lots | 44% | 0.0% | +1,633% | +17% |
| 200x, big lots | 83% | 0.0% | +4,454% | **−100%** |
| 400x, huge lots | **87%** | 0.2% | **+6,383%** | **−100%** |

**Your hint was right** — and it completes the picture. To make the account *flash*
+5000%+ floating in 15 days you must grid at extreme leverage, and when you do, the
account **blows up ~87% of the time** and the **median outcome is −100% (total wipeout)**.
The leaderboard is screenshotting the rare *floating flash* of the survivors; the
identical mechanism wiped out most of the field. Same lottery, same survivorship — the
0% win ratio just tells you the winners hadn't closed (and mostly never would).

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
