# Gold Sniper V5 - Live Trading Guide

## 🚀 Live Trading Setup

The live trading version (`gold_sniper_v5_live.py`) connects to MetaTrader 5 and executes trades automatically based on the same strategy as the backtest.

---

## 📋 Prerequisites

### 1. MetaTrader 5 Installation
- Download and install MetaTrader 5 from your broker
- Log in to your trading account
- Keep MT5 running while the bot is active

### 2. Python Dependencies
```bash
pip install MetaTrader5 pandas numpy
```

### 3. Symbol Availability
- Ensure XAUUSD (or your chosen symbol) is available in Market Watch
- Right-click Market Watch → Show All (if symbol is hidden)

---

## ⚙️ Configuration

Edit the configuration at the bottom of `gold_sniper_v5_live.py`:

```python
# Configuration
ACCOUNT_SIZE = 10000  # Your fixed capital (for position sizing)
PHASE = 'phase1'      # 'phase1', 'phase2', or 'master'
SYMBOL = 'XAUUSD'     # Trading symbol
```

### Account Size
- Use your actual account balance for proper risk management
- The bot uses FIXED capital (no compounding)
- Example: $10,000 account → set ACCOUNT_SIZE = 10000

### Phase Selection
- **phase1**: 8% profit target, 10% max DD, 5% daily loss
- **phase2**: 5% profit target, 10% max DD, 5% daily loss  
- **master**: No profit target, 8% trailing DD, 5% daily loss

### Symbol
- Default: 'XAUUSD' (Gold Spot)
- Change if your broker uses different symbol name
- Examples: 'GOLD', 'XAU/USD', 'XAUUSD.a'

---

## 🏃 Running the Bot

### Start Trading
```bash
cd scripts
python gold_sniper_v5_live.py
```

### What Happens
1. **Connects to MT5** - Verifies connection and account info
2. **Detects Zones** - Analyzes 15m, 1H, 4H charts for support/resistance
3. **Calculates POC** - Finds volume profile points of control
4. **Starts Monitoring** - Checks for setups every 30 seconds
5. **Executes Trades** - Places orders automatically when setups appear
6. **Manages Positions** - Extends TP and trails SL dynamically

### Stop Trading
- Press **Ctrl+C** to stop the bot gracefully
- All open positions remain (manage manually or let bot close them)

---

## 📊 What the Bot Does

### Entry Logic
1. **5-Minute Analysis**:
   - Scans for price near zones/POC (±15 pips)
   - Waits for structure break (recent 8-candle high/low)
   - Confirms breakout (+3 pips beyond)

2. **1-Minute Execution**:
   - Executes at current price
   - Sets tight SL (3-8 pips)
   - Sets initial TP based on 1:2 R:R minimum

### Position Management
- **Dynamic TP Extension**: When 70% to TP, extends by 15 pips (max 5 times)
- **Aggressive Trailing**: Activates at 1.5:1 R:R, locks 60% profit
- **Trail Updates**: Every 5 pips of favorable movement

### Risk Management
- **Fixed Capital**: Always trades with ACCOUNT_SIZE, never compounds
- **Risk per Trade**: 2% of account size
- **Max SL**: 3-8 pips (sniper entries)
- **Funding Pips Compliance**: Enforces daily loss, max DD, profit targets

### Trade Filtering
- **Max 8 trades per day**
- **Minimum spacing**: 10 five-minute candles between trades (50 minutes)
- **Quality over quantity**: Only takes confirmed setups

---

## 🔔 Bot Output

### Startup
```
================================================================================
GOLD SNIPER V5 - LIVE TRADING
================================================================================
Symbol: XAUUSD
Account Size: $10,000.00 (FIXED)
Phase: PHASE1
Risk per trade: 2%
Connected to MT5: ✅
================================================================================

🔍 Detecting zones...
✅ Detected 30 zones
📊 Calculating POC levels...
✅ Found 17 POC levels

✅ Setup complete. Monitoring XAUUSD...
```

### Trade Execution
```
======================================================================
🎯 BUY @ ZONE+POC
   Entry: $4285.68 | SL: $4282.68 (3.0p)
   TP: $4304.59 | R:R = 1:6.3
   Level: $4304.59 | Lots: 0.23
   Ticket: 123456789
======================================================================
```

### Position Management
```
   📈 TP Extended: $4304.59 → $4319.59 (Extension #1)
   🔒 Trail Updated: $4288.88 (Locking 60% profit)
```

### Status Updates (Every 5 Minutes)
```
[14:05] Balance: $10,245.00 | P&L: $+245.00 (+2.45%) | Trades today: 3
```

---

## ⚠️ Important Notes

### Risk Warnings
- **Real Money**: This bot trades with real money on live accounts
- **Test First**: Run on demo account before live trading
- **Monitor Regularly**: Check bot status and positions frequently
- **Internet Connection**: Stable connection required (VPS recommended)
- **Broker Slippage**: Real markets have slippage not in backtests

### Funding Pips Compliance
The bot automatically stops if:
- Daily loss limit reached (5%)
- Max drawdown reached (10% Phase 1/2, 8% Master)
- Profit target hit (Phase 1: 8%, Phase 2: 5%)

### Best Practices
1. ✅ Start with demo account
2. ✅ Run on VPS for 24/7 operation
3. ✅ Monitor first few trades closely
4. ✅ Keep MT5 logged in
5. ✅ Check logs regularly
6. ✅ Have stop-loss on every trade

### What to Monitor
- **Trade execution**: Are entries at good prices?
- **SL distances**: Should be 3-8 pips
- **TP extensions**: Are they triggering correctly?
- **Trail updates**: Is SL moving to lock profits?
- **Daily P&L**: Staying within Funding Pips limits?

---

## 🐛 Troubleshooting

### Bot Won't Start
```
❌ MT5 initialization failed
```
**Solution**: Make sure MT5 is running and you're logged in

### No Zones Detected
```
❌ Failed to get historical data
```
**Solution**: Ensure symbol is correct and has enough history

### Orders Fail
```
❌ Order failed: Invalid stops
```
**Solution**: Check broker's minimum stop distance for XAUUSD

### Symbol Not Found
```
❌ Symbol XAUUSD not found
```
**Solution**: Check your broker's symbol name (might be 'GOLD', 'XAU/USD', etc.)

---

## 📞 Support

### Check These First
1. Is MT5 running and logged in?
2. Is the symbol showing in Market Watch?
3. Do you have enough margin for trades?
4. Is your internet connection stable?

### Common Issues
- **"Invalid volume"**: Check broker's minimum lot size
- **"Market closed"**: XAUUSD only trades Mon-Fri
- **"Not enough money"**: Reduce ACCOUNT_SIZE or increase account balance
- **"Off quotes"**: Price moved, bot will retry on next check

---

## 📈 Performance Expectations

Based on backtest results:
- **ROI**: ~100%+ over 25 days
- **Win Rate**: ~83%
- **Max DD**: ~3%
- **Avg Trade**: 3-8 pips SL, dynamic TP

**Remember**: Past performance ≠ future results. Always trade with risk capital only.

---

## 🔐 Safety Features

The bot includes multiple safety checks:
- ✅ Funding Pips compliance monitoring
- ✅ Daily loss limits
- ✅ Max drawdown protection
- ✅ Trade spacing (prevents overtrading)
- ✅ Position size limits
- ✅ Automatic stop on rule breach

---

## 💡 Tips for Success

1. **Start Small**: Begin with minimum lot sizes
2. **Demo First**: Test on demo account for 1-2 weeks
3. **VPS Recommended**: Run 24/7 without interruptions
4. **Monitor Regularly**: Check bot 2-3 times per day
5. **Keep Logs**: Save console output for analysis
6. **Respect Rules**: Don't override Funding Pips limits

---

**Disclaimer**: Trading involves risk. This bot is for educational purposes. Always use proper risk management and never trade more than you can afford to lose.

**Good luck trading! 🚀**
