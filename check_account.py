import MetaTrader5 as mt5
from datetime import datetime, timedelta
import time

# Initialize
if not mt5.initialize():
    print("Failed to initialize MT5")
    exit()

# Login
if not mt5.login(40000179483, '&Ij4-#r3d', 'FundingPips-Trial'):
    print(f"Login failed: {mt5.last_error()}")
    mt5.shutdown()
    exit()

# Account info
acc = mt5.account_info()
if acc:
    print(f"\n📊 ACCOUNT STATUS:")
    print(f"   Balance: ${acc.balance:,.2f}")
    print(f"   Equity: ${acc.equity:,.2f}")
    print(f"   Profit: ${acc.profit:,.2f}")
    print(f"   Margin: ${acc.margin:,.2f}")
    print(f"   Free Margin: ${acc.margin_free:,.2f}")
else:
    print("No account info")

# Open positions
pos = mt5.positions_get()
if pos:
    print(f"\n📍 OPEN POSITIONS ({len(pos)}):")
    for p in pos:
        print(f"   {p.symbol}: {('BUY' if p.type == 0 else 'SELL')} {p.volume} lots @ ${p.price_open:.2f}")
        print(f"      Current: ${p.price_current:.2f} | P&L: ${p.profit:+,.2f}")
        print(f"      Ticket: {p.ticket}")
else:
    print("\n📍 No open positions")

# Recent deals (last 2 days)
start = int(time.time()) - 86400 * 2
hist = mt5.history_deals_get(start, int(time.time()))

if hist:
    gold_btc = [h for h in hist if h.symbol in ['XAUUSD', 'BTCUSD']]
    print(f"\n📜 RECENT DEALS (last 2 days): {len(gold_btc)} trades")
    for h in gold_btc[-20:]:  # Last 20
        t = datetime.fromtimestamp(h.time).strftime('%m-%d %H:%M')
        type_str = "BUY" if h.type == 0 else "SELL" if h.type == 1 else "CLOSE"
        print(f"   [{t}] {h.symbol}: {type_str} {h.volume} @ ${h.price:.2f} | P&L: ${h.profit:+,.2f}")
        print(f"      Comment: {h.comment} | Ticket: {h.ticket}")
else:
    print("\n📜 No recent deals")

mt5.shutdown()
