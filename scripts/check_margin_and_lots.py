#!/usr/bin/env python3
"""Check actual margin requirements and max lots for XAUUSD"""
import MetaTrader5 as mt5

LOGIN = 1840535
PASSWORD = "%Yv11M*k"
SERVER = "FTTrading-Server"

mt5.initialize()
mt5.login(login=LOGIN, password=PASSWORD, server=SERVER)

account = mt5.account_info()
symbol_info = mt5.symbol_info("XAUUSD")
tick = mt5.symbol_info_tick("XAUUSD")

print("="*60)
print("MARGIN CALCULATION TEST")
print("="*60)

print(f"\nAccount Info:")
print(f"  Balance: ${account.balance:,.2f}")
print(f"  Free Margin: ${account.margin_free:,.2f}")
print(f"  Account Leverage: 1:{account.leverage}")

print(f"\nSymbol Info (XAUUSD):")
print(f"  Current Price: ${tick.ask:.2f}")
print(f"  Contract Size: {symbol_info.trade_contract_size}")
print(f"  Min Lot: {symbol_info.volume_min}")
print(f"  Max Lot: {symbol_info.volume_max}")
print(f"  Lot Step: {symbol_info.volume_step}")

# Test different lot sizes
test_lots = [0.01, 0.1, 1.0, 10.0]

print(f"\n{'='*60}")
print("MARGIN REQUIREMENTS (using mt5.order_calc_margin):")
print(f"{'='*60}")

for lots in test_lots:
    # Calculate margin required
    margin = mt5.order_calc_margin(
        mt5.ORDER_TYPE_BUY,
        "XAUUSD",
        lots,
        tick.ask
    )
    
    if margin is not None:
        margin_pct = (margin / account.balance) * 100
        can_open = "✅" if margin <= account.margin_free else "❌"
        
        print(f"\nLot: {lots:>6.2f}")
        print(f"  Margin Required: ${margin:>12,.2f} ({margin_pct:>5.2f}% of balance)")
        print(f"  Can Open: {can_open}")
        print(f"  Position Value: ${lots * symbol_info.trade_contract_size * tick.ask:>12,.2f}")
        
        # Calculate effective leverage
        position_value = lots * symbol_info.trade_contract_size * tick.ask
        effective_leverage = position_value / margin if margin > 0 else 0
        print(f"  Effective Leverage: 1:{effective_leverage:.1f}")
    else:
        print(f"\nLot: {lots:>6.2f} - ❌ Failed to calculate margin")

# Find max lots we can actually trade
print(f"\n{'='*60}")
print("CALCULATING MAX LOTS:")
print(f"{'='*60}")

max_possible = account.margin_free / (tick.ask * symbol_info.trade_contract_size / 10)  # Assuming 1:10
print(f"\nEstimated max lots (1:10 leverage): {max_possible:.2f}")

# Binary search for actual max
low, high = 0.01, 100.0
max_lot = 0.01

while high - low > 0.01:
    mid = (low + high) / 2
    margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, "XAUUSD", mid, tick.ask)
    
    if margin and margin <= account.margin_free * 0.95:  # 95% safety margin
        max_lot = mid
        low = mid
    else:
        high = mid

print(f"Actual max lots (with 5% safety): {max_lot:.2f}")

margin_for_max = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, "XAUUSD", max_lot, tick.ask)
if margin_for_max:
    print(f"Margin for max: ${margin_for_max:,.2f} ({(margin_for_max/account.balance)*100:.1f}%)")

mt5.shutdown()

print(f"\n✅ DONE!")
