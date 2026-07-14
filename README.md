# Gold Zone Range Strategy (XAU/USD)

Backtesting research for the **horizontal "zone line" strategy** — buying rejections
at support zones and selling rejections at resistance zones, riding price between
them with leverage and compounding.

## What's in here

| File | Purpose |
| --- | --- |
| `scripts/zone_range_strategy.py` | **Main engine.** Clean zone detection + range-rejection entries + compounding risk modes. |
| `scripts/fetch_gold_data.py` | Downloads free historical gold data (Yahoo `GC=F`) into a CSV. |
| `scripts/cache_xauusd_gc_1h.csv` | 2 years of hourly gold candles (fetched, free source). |
| `scripts/cache_xauusd_spot_mt5_1m_30d.csv` | 30 days of 1-minute XAU/USD from MT5 (kept as a shorter, range-bound sample). |
| `scripts/gold_bramhastra_v2.py` | **Old script, kept for reference only.** Its rejection-percentile entry logic did not generalize; only its zone detection was reliable. Do not rely on it. |
| `scripts/zone_range_results.json` | Latest backtest output (metrics + config + zones per mode). |

## The strategy

1. **Zone detection** (the part that works): find swing-pivot highs/lows, cluster
   nearby pivots into single levels, and keep only levels touched enough times.
   Zones are rebuilt on a rolling window as the backtest walks forward (no lookahead).
2. **Entries**: when price *rejects* a zone
   - reject a **support** zone → **LONG**, target the next zone up
   - reject a **resistance** zone → **SHORT**, target the next zone down
3. **Stops**: just beyond the zone (with a realistic minimum distance).
4. **Exits**: target = the opposite zone, with an optional trailing stop.
5. **Sizing**: risk a % of the *current* balance at a set leverage, so wins compound.

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

Run on 2 years of hourly gold (2024-07 → 2026-07), **with spread + slippage costs**:

- **Conservative (2% / 5x):** grows the account strongly with a low (~4-5%) drawdown.
- **Aggressive (10% / 10x):** enormous headline ROI — but note this is compounding on
  top of a period where gold rose from ~$2,400 to ~$5,600. The leverage cap (not the
  10% risk figure) is what keeps it alive.

Run on the **30-day, range-bound MT5 sample**, the same aggressive settings **lose money**
(~ -1.6%, sub-40% win rate).

### Read this before trusting any number

- **Trend tailwind.** The 2-year window was a historic gold bull run. A buy-the-dip
  zone strategy looks spectacular in a trend and struggles when price chops sideways —
  exactly what the 30-day sample demonstrates.
- **Optimistic fills.** Even with modeled spread/slippage, tight stops at zones assume
  cleaner fills than a live, leveraged account gets (weekend gaps, news spikes).
- **`GC=F` ≠ true broker XAU/USD.** COMEX futures track spot closely but are not your
  broker's exact feed, spread, or swap.
- **The 5000%+ leaderboard is not an edge.** Those FundingPips-Trial tournament numbers
  come from free demo contests with tens of thousands of entrants using max leverage.
  A handful spike by luck (survivorship bias); most blow up. Do not size a live/funded
  account around reproducing them.

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
