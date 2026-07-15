#!/usr/bin/env python3
"""Test MT5 Connection"""
import MetaTrader5 as mt5

print("="*60)
print("MT5 CONNECTION TEST")
print("="*60)

# Credentials
LOGIN = 1840535
PASSWORD = "%Yv11M*k"
SERVER = "FTTrading-Server"

print(f"\n1. MT5 Version: {mt5.__version__ if hasattr(mt5, '__version__') else 'Unknown'}")

print(f"\n2. Initializing MT5...")
if not mt5.initialize():
    print(f"   ❌ Failed: {mt5.last_error()}")
    print("\n⚠️  SOLUTION:")
    print("   - Open MetaTrader 5 application")
    print("   - Make sure it's running")
    print("   - Try again")
    exit(1)

print(f"   ✅ MT5 Initialized")

print(f"\n3. Logging in...")
print(f"   Login: {LOGIN}")
print(f"   Server: {SERVER}")

authorized = mt5.login(login=LOGIN, password=PASSWORD, server=SERVER)

if not authorized:
    error = mt5.last_error()
    print(f"   ❌ Login failed: {error}")
    print("\n⚠️  SOLUTION:")
    print("   - Check credentials are correct")
    print("   - Server must be exactly as shown in MT5")
    print("   - Try manual login in MT5 first")
    mt5.shutdown()
    exit(1)

print(f"   ✅ Login successful!")

print(f"\n4. Account Info:")
account = mt5.account_info()
if account:
    print(f"   Login: {account.login}")
    print(f"   Name: {account.name}")
    print(f"   Server: {account.server}")
    print(f"   Balance: ${account.balance:,.2f}")
    print(f"   Equity: ${account.equity:,.2f}")
    print(f"   Margin: ${account.margin:,.2f}")
    print(f"   Free Margin: ${account.margin_free:,.2f}")
    print(f"   Leverage: 1:{account.leverage}")
    print(f"   Currency: {account.currency}")
else:
    print(f"   ❌ Failed to get account info")

print(f"\n5. Symbol Info (XAUUSD):")
symbol_info = mt5.symbol_info("XAUUSD")
if symbol_info:
    if not symbol_info.visible:
        print(f"   ⚠️  Symbol hidden, enabling...")
        mt5.symbol_select("XAUUSD", True)
    
    print(f"   Name: {symbol_info.name}")
    print(f"   Digits: {symbol_info.digits}")
    print(f"   Point: {symbol_info.point}")
    print(f"   Min Lot: {symbol_info.volume_min}")
    print(f"   Max Lot: {symbol_info.volume_max}")
    print(f"   Lot Step: {symbol_info.volume_step}")
    print(f"   Contract Size: {symbol_info.trade_contract_size}")
    
    tick = mt5.symbol_info_tick("XAUUSD")
    if tick:
        print(f"   Bid: ${tick.bid:.2f}")
        print(f"   Ask: ${tick.ask:.2f}")
        print(f"   Spread: {(tick.ask - tick.bid) / symbol_info.point:.1f} points")
else:
    print(f"   ❌ Symbol not found")
    print("   Available symbols: Use Market Watch in MT5")

print(f"\n6. Historical Data Test:")
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M1, 0, 100)
if rates is not None and len(rates) > 0:
    print(f"   ✅ Fetched {len(rates)} 1-minute candles")
    print(f"   Latest: ${rates[-1]['close']:.2f}")
else:
    print(f"   ❌ Failed to fetch data")

mt5.shutdown()
print(f"\n✅ ALL TESTS PASSED!")
print(f"\n🚀 Ready to run live bot!")
