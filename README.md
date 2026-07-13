# Gold Algorithmic Trading Strategy

## 🎯 Overview

This repository contains an algorithmic trading strategy for Gold (XAU/USD) based on multi-timeframe zone detection and rejection analysis.

## 📊 Strategy: Gold Bramhastra V2

### Core Concept
The strategy identifies key support and resistance zones using multiple timeframes (15m, 1H, 4H) and trades based on price rejection patterns at these zones.

### Key Features

- **Multi-Timeframe Zone Detection**: Analyzes 15-minute, 1-hour, and 4-hour timeframes to identify major support and resistance levels
- **Zone Clustering**: Combines nearby zones to create clean, major S/R levels
- **Rejection Pattern Analysis**: Waits for confirmed price rejection at zones before entering trades
- **Dynamic Risk Management**: 
  - 10% risk per trade
  - 10x leverage
  - Trailing stop loss enabled
  - Tight SL at rejection candle high/low
- **Target Selection**: Automatically targets opposite zones
- **Auto-Reverse**: Can reverse positions when hitting opposite zones

### Parameters

```python
Balance: $10,000
Leverage: 10x
Risk per Trade: 10%
Zone Touch Threshold: 10 pips
Minimum Touches: 2 touches to confirm zone
Rejection Threshold: Calculated dynamically from data (30th percentile)
```

## 📁 Repository Contents

- `scripts/gold_bramhastra_v2.py` - Main trading strategy script
- `scripts/cache_xauusd_spot_mt5_1m_30d.csv` - Historical 1-minute OHLC data for XAU/USD (30 days)

## 🚀 Usage

### Prerequisites

```bash
pip install pandas numpy
```

### Running the Backtest

```bash
cd scripts
python gold_bramhastra_v2.py
```

### Output

The script will:
1. Detect zones from the historical data
2. Calculate optimal rejection threshold
3. Run backtest simulation
4. Print performance metrics
5. Save detailed results to `gold_backtest_v2_results.json`

### Expected Metrics

- Start Balance
- Final Balance
- ROI (Return on Investment)
- Total Trades
- Win Rate
- Maximum Drawdown
- Number of Zones Detected

## 📈 How It Works

1. **Zone Detection**: 
   - Converts 1-minute data to 15m, 1H, and 4H timeframes
   - Identifies swing highs and lows in each timeframe
   - Clusters nearby zones (within 20 pips)
   - Filters zones requiring minimum 2 touches

2. **Rejection Analysis**:
   - Analyzes all historical zone touches
   - Calculates rejection percentage (how much price moved away)
   - Uses 30th percentile as optimal entry threshold

3. **Trade Execution**:
   - Waits for price to touch a zone
   - Confirms rejection meets threshold percentage
   - Enters trade with tight SL at rejection candle
   - Sets TP at opposite zone
   - Trails stop as price moves favorably

4. **Risk Management**:
   - Position sizing based on 10% account risk
   - Maximum position capped at $50k or 10x leverage
   - Trailing stops to protect profits
   - Auto-closes at opposite zones

## ⚠️ Disclaimer

This is a backtesting script for educational purposes only. Past performance does not guarantee future results. Always test thoroughly and use proper risk management when trading live.

## 📝 License

Open source - feel free to modify and use for your own trading research.

## 🤝 Contributing

Feel free to fork, improve, and submit pull requests!

---

**Note**: This strategy is based on zone rejection principles observed in actual trading charts. The zone detection matches real trading zones for more realistic backtest results.
