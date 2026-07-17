#!/usr/bin/env python3
"""Quick status check for live bot"""

import MetaTrader5 as mt5

MT5_LOGIN = 40000179483
MT5_PASSWORD = "&Ij4-#r3d"
MT5_SERVER = "FundingPips-Trial"

mt5.initialize()
mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

account = mt5.account_info()
tick = mt5.symbol_info_tick("XAUUSD")
positions = mt5.positions_get(symbol="XAUUSD")

print("="*60)
print(f"LIVE BOT STATUS")
print("="*60)
print(f"Balance: ${account.balance:,.2f}")
print(f"Equity: ${account.equity:,.2f}")
print(f"Margin: ${account.margin:,.2f}")
print(f"Free Margin: ${account.margin_free:,.2f}")
print(f"P&L: ${account.profit:+,.2f}")
print(f"\nXAUUSD Price: ${tick.bid:.2f} / ${tick.ask:.2f}")
print(f"Spread: {(tick.ask - tick.bid) * 100:.1f} pips")
print(f"\nOpen Positions: {len(positions) if positions else 0}")

if positions:
    for pos in positions:
        dir_str = "LONG" if pos.type == 0 else "SHORT"
        pnl = pos.profit
        print(f"  [{pos.ticket}] {dir_str} {pos.volume} lots @ ${pos.price_open:.2f}")
        print(f"     Current: ${pos.price_current:.2f} | P&L: ${pnl:+,.2f}")
        print(f"     SL: ${pos.sl:.2f} | TP: ${pos.tp:.2f}")

print("="*60)

mt5.shutdown()
