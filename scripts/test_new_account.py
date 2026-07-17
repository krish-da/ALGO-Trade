#!/usr/bin/env python3
"""Test connection to new FundingPips account"""

import MetaTrader5 as mt5

MT5_LOGIN = 40000134945
MT5_PASSWORD = "5AV^(1*lV"
MT5_SERVER = "FundingPips-Trial"

print("="*70)
print("TESTING FUNDINGPIPS TRIAL ACCOUNT CONNECTION")
print("="*70)

if not mt5.initialize():
    print(f"❌ MT5 initialize() failed: {mt5.last_error()}")
    exit(1)

print("✅ MT5 initialized")

# Try to login
authorized = mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)

if not authorized:
    error = mt5.last_error()
    print(f"❌ Login failed: {error}")
    print(f"\nPlease check:")
    print(f"  1. MT5 is installed and running")
    print(f"  2. Server '{MT5_SERVER}' is configured in MT5")
    print(f"  3. Credentials are correct")
    mt5.shutdown()
    exit(1)

print("✅ Login successful!")

# Get account info
account_info = mt5.account_info()

if account_info is None:
    print(f"❌ Failed to get account info: {mt5.last_error()}")
    mt5.shutdown()
    exit(1)

print("\n" + "="*70)
print("ACCOUNT DETAILS")
print("="*70)
print(f"Login: {account_info.login}")
print(f"Server: {account_info.server}")
print(f"Name: {account_info.name}")
print(f"Company: {account_info.company}")
print(f"Currency: {account_info.currency}")
print(f"\nBALANCE:")
print(f"  Balance: ${account_info.balance:,.2f}")
print(f"  Equity: ${account_info.equity:,.2f}")
print(f"  Margin: ${account_info.margin:,.2f}")
print(f"  Free Margin: ${account_info.margin_free:,.2f}")
print(f"  Margin Level: {account_info.margin_level:.2f}%" if account_info.margin > 0 else "  Margin Level: N/A (no positions)")
print(f"  Profit: ${account_info.profit:+,.2f}")

print(f"\nLEVERAGE:")
print(f"  Account Leverage: 1:{account_info.leverage}")
print(f"  Margin Mode: {'Retail' if account_info.margin_mode == 0 else 'Exchange'}")

# Check XAUUSD
symbol_info = mt5.symbol_info("XAUUSD")

if symbol_info is None:
    print(f"\n❌ XAUUSD not found on this account")
    mt5.shutdown()
    exit(1)

if not symbol_info.visible:
    print(f"\n⚠️  XAUUSD not visible, enabling...")
    mt5.symbol_select("XAUUSD", True)

tick = mt5.symbol_info_tick("XAUUSD")

print(f"\nXAUUSD:")
print(f"  Bid: ${tick.bid:.2f}")
print(f"  Ask: ${tick.ask:.2f}")
print(f"  Spread: {(tick.ask - tick.bid) * 100:.1f} pips")
print(f"  Contract Size: {symbol_info.trade_contract_size}")
print(f"  Min Volume: {symbol_info.volume_min}")
print(f"  Max Volume: {symbol_info.volume_max}")
print(f"  Volume Step: {symbol_info.volume_step}")

# Test margin calculation
test_margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, "XAUUSD", 1.0, tick.ask)

if test_margin:
    position_value = 1.0 * symbol_info.trade_contract_size * tick.ask
    effective_leverage = position_value / test_margin
    print(f"\nMARGIN TEST (1.0 lot @ ${tick.ask:.2f}):")
    print(f"  Position Value: ${position_value:,.2f}")
    print(f"  Margin Required: ${test_margin:,.2f}")
    print(f"  Effective Leverage: 1:{effective_leverage:.1f}")
else:
    print(f"\n⚠️  Could not calculate margin")

# Determine phase based on balance
print(f"\n" + "="*70)
print("RECOMMENDED CONFIGURATION")
print("="*70)

balance = account_info.balance

if balance <= 25000:
    phase = "phase1"
    target = 8.0
elif balance <= 100000:
    phase = "phase2"
    target = 5.0
else:
    phase = "master"
    target = "none"

print(f"Phase: {phase.upper()}")
print(f"Profit Target: {target}%" if target != "none" else "Profit Target: None (funded account)")
print(f"Max Drawdown: {'10%' if phase != 'master' else '8%'}")
print(f"Daily Loss Limit: 5%")
print(f"Risk per Trade: 2%")

print(f"\n" + "="*70)
print("✅ ACCOUNT READY FOR TRADING")
print("="*70)

mt5.shutdown()
