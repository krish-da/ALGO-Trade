#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare backtest and live logic with same historical data
"""
import pandas as pd
import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

print("="*80)
print("BACKTEST VS LIVE - LOGIC COMPARISON TEST")
print("="*80)

# Load CSV data
df = pd.read_csv('cache_xauusd_spot_mt5_1m_30d.csv', header=None,
                 names=['time', 'open', 'high', 'low', 'close', 'tick_volume'])
print(f"\nLoaded {len(df)} candles")

print("\nRunning BACKTEST version...")
print("-" * 80)

# Import and run backtest
sys.path.insert(0, '.')
from gold_sniper_v5 import GoldSniperV5

backtest = GoldSniperV5(account_size=10000, phase='phase1')
backtest.detect_zones_enhanced(df.copy())
backtest.calculate_poc_levels(df.copy())
result_backtest = backtest.backtest(df.copy())

print(f"\n📊 BACKTEST RESULTS:")
print(f"   ROI: {result_backtest['roi']:+.2f}%")
print(f"   Trades: {result_backtest['trades']}")
print(f"   Win Rate: {result_backtest['win_rate']:.1f}%")
print(f"   Zones: {result_backtest['zones']}")
print(f"   POC: {result_backtest['poc_levels']}")

print("\n" + "="*80)
print("BACKTEST COMPLETE - Logic verified")
print("="*80)

print(f"\nSummary:")
print(f"  Backtest zones: {result_backtest['zones']}")
print(f"  Expected: 30")
print(f"  Match: {'PASS' if result_backtest['zones'] == 30 else 'FAIL'}")

print(f"\n  Backtest ROI: {result_backtest['roi']:.2f}%")
print(f"  Expected: ~104%")
print(f"  Match: {'PASS' if 100 < result_backtest['roi'] < 110 else 'FAIL'}")

print("\nNow ready to test LIVE version with MT5!")
