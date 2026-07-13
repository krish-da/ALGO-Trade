# XAUUSD Multi-Timeframe Line Research

A causal research backtester for testing horizontal XAUUSD lines derived from closed 15-minute, 1-hour, and 4-hour candles. It models both rejection reversals and close-through/retest continuations around prices ending in `0` or `5`.

This project is research software only. It does not place live MT5 orders, and historical win rate or return does not guarantee future performance.

## Method

- Validates and chronologically resamples 1-minute OHLC data.
- Confirms swing candidates only after right-side candles close, avoiding pivot look-ahead.
- Snaps candidates to the nearest $5 level and strengthens lines through timeframe agreement and later touches.
- Keeps each line active until two confirmed 15-minute closes invalidate it beyond the configured buffer.
- Tests two independent setups:
  - **Reversal:** touch and candle rejection, followed by a 15-minute structure break away from the line.
  - **Continuation:** close through the line, followed by a hold/retest from the opposite side.
- Places stops beyond the setup spike and targets the next active line. Setups without a valid target are recorded and skipped.
- Trails behind confirmed 15-minute swings and assumes the stop is hit first when both stop and target occur inside one candle.
- Applies configurable spread, slippage, commission, account risk, leverage, and notional limits.

## Install and run

```bash
python -m pip install -r requirements.txt
python scripts/gold_bramhastra_v2.py
```

Optional arguments:

```bash
python scripts/gold_bramhastra_v2.py \
  --data scripts/cache_xauusd_spot_mt5_1m_30d.csv \
  --annotations scripts/manual_zones_template.csv \
  --output scripts/backtest_output \
  --risk-pct 1 \
  --spread 0.30 \
  --slippage 0.10
```

The defaults use 1% account risk per position, 10x maximum leverage, and one open position at a time. Strategy thresholds are centralized in the `Config` dataclass.

## Manual annotations

Populate `scripts/manual_zones_template.csv` to compare detected lines with manually drawn ground truth:

```csv
line_id,created_at,timeframe,price,side,notes
manual-001,2026-07-10T08:00:00Z,4h,4050,support,repeated direction changes
manual-002,2026-07-11T12:00:00Z,1h,4070,resistance,chart-confirmed line
```

- `created_at` must be the time the line became knowable, not an earlier pivot chosen with hindsight.
- `timeframe` should be `15m`, `1h`, or `4h`.
- `side` may be `support`, `resistance`, or blank.
- An empty template is valid; the algorithm runs without manual calibration.

## Artifacts

The output directory contains:

- `summary.json`: return, win rate, expectancy, profit factor, drawdown, setup split, and annotation coverage.
- `zones.csv`: complete line lifecycle, score, source timeframes, touches, and invalidation.
- `events.csv`: auditable zone touches, updates, invalidations, skipped setups, and entries.
- `trades.csv`: entries, spike stops, targets, sizing, costs, exits, P&L, and R-multiples.

Fewer than 30 trades produces a small-sample warning. Compare longer chronological periods and reserve later data for true out-of-sample evaluation before changing thresholds.

## Tests

```bash
cd scripts
python -m unittest -v test_gold_bramhastra_v2.py
```

The synthetic tests cover closed-bar resampling, delayed swing confirmation, $5 snapping, two-close invalidation, conservative ambiguous fills, and empty annotation fallback.

## Important limitations

OHLC candles cannot reveal the exact intrabar path, so ambiguous stop/target candles are treated pessimistically. The provided 30-day sample is too short to support claims of near-100% win rate or stable high ROI; validation should include more market regimes, broker-specific costs, walk-forward testing, and manually annotated lines.
