# Gold Sniper Trading Strategy

## 🎯 Strategy Overview

Algorithmic trading strategy for XAU/USD (Gold Spot) that uses multi-timeframe zone detection and volume profile POC (Point of Control) for sniper-style entries.

**Key Features:**
- Multi-timeframe zone detection (15m, 1H, 4H)
- Volume Profile POC analysis
- 5-minute setup identification
- 1-minute precise execution
- Dynamic TP extensions
- Aggressive profit trailing
- Funding Pips 2-Step Standard compliant

---

## 🔧 Strategy Components

### 1. Multi-Timeframe Zone Detection
- Analyzes 15-minute, 1-hour, and 4-hour charts
- Identifies swing highs and lows
- Weights by timeframe importance (4H > 1H > 15M)
- Clusters nearby zones to remove noise
- Result: ~30 clean support/resistance zones

### 2. Volume Profile POC
- Calculates Point of Control from 1-day volume profile
- POC = price level with highest trading activity
- Acts as strong support/resistance
- Best setups occur at Zone + POC confluence

### 3. Entry Logic
**5-Minute Analysis:**
- Monitors for price near zone or POC (±15 pips)
- Confirms breakout of recent structure (8-candle high/low)
- Requires minimum breakout confirmation (+3 pips)
- Quality filters: max 5 trades/day, proper spacing

**1-Minute Execution:**
- Precise entry on 1-minute candles
- Tight stop loss: 3-8 pips (median 3 pips)
- SL below recent low (LONG) or above recent high (SHORT)
- Dynamic TP: Extends as price moves, captures full trends

### 4. Trade Management
- **Dynamic TP**: Extends by 15 pips when 70% reached (max 5 extensions)
- **Aggressive Trailing**: Activates at 1.5:1 R:R, locks 60% profit
- **Trailing Updates**: Every 5 pips of favorable movement
- **Risk**: 2% per trade (Funding Pips compliant)

### 5. Funding Pips Compliance
- **Phase 1**: 8% profit target, 10% max DD, 5% daily loss
- **Phase 2**: 5% profit target, 10% max DD, 5% daily loss
- **Master**: 5% daily loss, 8% trailing DD
- **60% Rule**: Tracks if single trade makes >60% of profit
- **Fixed Capital**: No profit reinvestment (trade with account_size)

---

## 📁 Repository Contents

```
scripts/
├── gold_sniper_v5.py              # Main trading strategy
└── cache_xauusd_spot_mt5_1m_30d.csv   # XAU/USD SPOT 1-min data (25 days)
```

---

## 🚀 How to Run

### Prerequisites
```bash
pip install pandas numpy matplotlib
```

### Run Backtest
```bash
cd scripts
python gold_sniper_v5.py
```

**Output:**
- Console: Performance metrics, trade log, Funding Pips compliance
- File: `backtest_results.json` (if enabled)

---

## 📈 How It Works

### Trading Flow

1. **Initialization**
   - Load 1-minute OHLC data
   - Detect zones from 15m, 1H, 4H timeframes
   - Calculate POC levels from daily volume profile
   - Result: ~30 zones + ~17 POC levels

2. **Real-Time Loop** (Every 1-Minute Candle)
   
   **Step 1: Check for Setup (5-Min)**
   - Is price near zone/POC?
   - Has recent structure broken?
   - Breakout confirmed?
   
   **Step 2: Execute Entry (1-Min)**
   - Enter at 1-min close
   - Set tight SL (3-8 pips)
   - Set initial TP at next zone/POC
   - Verify minimum 1:2 R:R
   
   **Step 3: Manage Position**
   - Monitor every 1-min candle
   - Extend TP dynamically as price moves
   - Activate trailing at 1.5:1 R:R
   - Update trail every 5 pips
   - Exit on SL/TP hit

---

## 🔍 Key Insights

### Why This Works

1. **True Sniper Entries**
   - 5-min identifies quality setups
   - 1-min executes at precise points
   - Tight SL (3-8 pips) = low risk
   - If wrong, small loss; if right, big gain

2. **Dynamic Profit Capture**
   - No fixed TP cap
   - Extends TP as price moves
   - Captures extended trends (60%+ more profit)
   - Aggressive trailing locks gains

3. **Quality Filters**
   - Not every zone touch = trade
   - Requires structure confirmation
   - Max 5 trades/day (prevents overtrading)
   - Proper trade spacing (10 candles minimum)

4. **Risk Management**
   - Funding Pips compliant (2% per trade)
   - Fixed capital (no compounding risk)
   - Daily loss limits enforced
   - Max drawdown protection

---

## ⚠️ Important Notes

### Backtest Limitations
- **Period**: 25 days (June-July 2026)
- **Slippage**: Not modeled
- **Spread**: Not included (SPOT data)
- **Commission**: Not included

### Recommendations
1. Test on longer time periods
2. Test different market conditions (trending, ranging, volatile)
3. Add realistic slippage/commission for live
4. Start with demo account
5. Follow proper risk management

---

## 🎓 Strategy Philosophy

### What Makes a Good Entry
❌ **Bad**: "Price touched zone, enter immediately"  
✅ **Good**: "Price near zone + 5-min structure break + 1-min confirmation"

### Why Tight Stops Work
- Correct setup = price runs immediately
- Wrong setup = exit fast with small loss
- No "room to breathe" = no room to lose money

### Quality Over Quantity
- 95 quality trades >> 137 mediocre trades
- Better to wait for perfect setup than force trades

---

## 📜 License

Open source - use for your own trading research and development.

---

## ⚡ Quick Start

```bash
# Clone repository
git clone https://github.com/krish-da/ALGO-Trade.git
cd ALGO-Trade/scripts

# Run backtest
python gold_sniper_v5.py
```

---

**Disclaimer**: Past performance does not guarantee future results. This is for educational purposes only. Always use proper risk management when trading live.

**Data**: XAU/USD SPOT from MetaTrader 5  
**Strategy**: Zone + POC + Momentum Breakout  
**Execution**: 5-min analysis, 1-min entry  
**Compliance**: Funding Pips 2-Step Standard
