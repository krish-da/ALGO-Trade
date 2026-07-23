# Algorithmic Trading Scripts

High-performance zone-based trading algorithms for Gold (XAU/USD) and Bitcoin (BTC/USD) on MT5.

## 📊 Strategy Overview

**Zone Detection System:**
- Multi-timeframe analysis (15m, 1h, 4h)
- Supply/Demand zone clustering
- Point of Control (POC) levels
- Confluence-based entries

**Proven Results:**
- **Gold:** 68.2% win rate, 122% ROI in 30 days
- **Bitcoin:** Optimized for crypto volatility

## 🚀 Scripts

### Gold (XAU/USD)
1. **`gold_sniper_v5.py`** - Backtest engine with zone detection
2. **`gold_sniper_v5_live.py`** - Live trading on MT5

### Bitcoin (BTC/USD)
3. **`crypto_sniper_backtest.py`** - BTC backtest engine
4. **`btc_sniper_live_mt5.py`** - Live BTC trading on MT5

### Data
- **`cache_xauusd_spot_mt5_1m_30d.csv`** - 30 days Gold 1-minute historical data

## ⚙️ Setup

### Requirements
```bash
pip install MetaTrader5 pandas numpy
```

### MT5 Configuration
```python
login = YOUR_ACCOUNT_NUMBER
password = "YOUR_PASSWORD"
server = "FundingPips-Trial"
```

## 🎯 Usage

### Run Backtest
```bash
# Gold backtest
python scripts/gold_sniper_v5.py

# Bitcoin backtest
python scripts/crypto_sniper_backtest.py
```

### Start Live Trading
```bash
# Gold live
python scripts/gold_sniper_v5_live.py

# Bitcoin live
python scripts/btc_sniper_live_mt5.py
```

## 📈 Performance

**Gold Sniper V5 (30 days backtest):**
- Win Rate: 68.2%
- Total Trades: 22
- Wins/Losses: 15W / 7L
- ROI: +122%
- Max Drawdown: 8.8%

**Entry Criteria:**
- Zone + POC confluence required
- Volume 20% above average
- 3 consecutive momentum candles
- Minimum R:R 1:2.5

## ⚠️ Risk Management

**Funding Pips Tournament Rules:**
- Daily Loss Limit: $5,000
- Max Drawdown: $10,000
- Position sizing: 2% risk per trade
- Leverage: 1:100 (Gold), 1:2 (BTC)

## 🔧 Configuration

Edit strategy parameters in each script:

```python
# Zone detection
zone_lookback_15m = 8
zone_lookback_1h = 12
zone_lookback_4h = 6

# Entry filters
zone_proximity_5m = 10
breakout_threshold = 5
min_rr_ratio = 2.5

# Risk management
risk_pct = 2.0
max_sl_distance = 6
```

## 📝 License

MIT License - Free to use and modify

## 🤝 Contributing

Pull requests welcome. For major changes, please open an issue first.

---

**Disclaimer:** Trading involves substantial risk. Past performance does not guarantee future results. Use at your own risk.
