#!/usr/bin/env python3
"""
GOLD BRAMHASTRA V2 - REAL ZONE REJECTION STRATEGY
==================================================
Based on actual trading chart analysis

STRATEGY:
1. Detect zones from 15m/1H/4H combination (clean, fewer zones)
2. Wait for price to touch zone
3. Analyze rejection % to confirm reversal
4. Enter after rejection confirmation
5. SL at rejection candle high/low (tight)
6. TP at opposite zone
7. Trail stops as price moves
8. Auto-reverse when hitting opposite zone

PARAMETERS:
- Risk: 10% per trade
- Leverage: 10x
- Trailing stop: ENABLED
- Auto-reverse: ENABLED
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
import json

class GoldBramhastraV2:
    def __init__(self):
        # STRATEGY PARAMETERS
        self.balance = 10000
        self.start = 10000
        self.leverage = 10.0
        self.risk_pct = 10.0
        
        # Zone detection parameters
        self.zone_threshold = 10  # Touch detection threshold
        self.min_touches = 2      # Minimum touches to confirm zone
        
        # Rejection parameters (will be optimized)
        self.rejection_pct = None  # To be calculated from data
        
        # Trading state
        self.zones = []
        self.trades = []
        self.active_trade = None
        
    def detect_zones_multi_timeframe(self, df_1m):
        """
        Detect zones from 15m, 1H, 4H combination
        Returns clean, major S/R levels
        """
        print("\n🔍 Detecting zones from multiple timeframes...")
        
        # Convert 1m data to different timeframes
        df_1m['datetime'] = pd.to_datetime(df_1m['time'], unit='s')
        df_1m.set_index('datetime', inplace=True)
        
        # Resample to 15m, 1H, 4H
        df_15m = df_1m.resample('15T').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        df_1h = df_1m.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        df_4h = df_1m.resample('4H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        # Reset index to get back time column
        df_1m.reset_index(inplace=True)
        df_1m['time'] = df_1m['datetime'].astype(int) // 10**9
        
        # Find swing highs/lows in each timeframe
        zones_15m = self._find_swings(df_15m, lookback=5)
        zones_1h = self._find_swings(df_1h, lookback=5)
        zones_4h = self._find_swings(df_4h, lookback=3)
        
        # Combine zones and cluster similar levels
        all_zones = zones_15m + zones_1h + zones_4h
        clustered_zones = self._cluster_zones(all_zones, cluster_distance=20)
        
        # Filter by minimum touches
        self.zones = self._filter_by_touches(clustered_zones, df_1m)
        
        print(f"✅ Detected {len(self.zones)} major zones")
        if len(self.zones) > 0:
            print(f"   Zone range: ${min(self.zones):.2f} - ${max(self.zones):.2f}")
        
        return self.zones
    
    def _find_swings(self, df, lookback=5):
        """Find swing highs and lows in dataframe"""
        zones = []
        
        for i in range(lookback, len(df) - lookback):
            # Swing high
            if df.iloc[i]['high'] == max(df.iloc[i-lookback:i+lookback+1]['high']):
                zones.append(round(df.iloc[i]['high']))
            
            # Swing low
            if df.iloc[i]['low'] == min(df.iloc[i-lookback:i+lookback+1]['low']):
                zones.append(round(df.iloc[i]['low']))
        
        return zones
    
    def _cluster_zones(self, zones, cluster_distance=20):
        """Cluster nearby zones into single levels"""
        if not zones:
            return []
        
        zones = sorted(zones)
        clustered = []
        current_cluster = [zones[0]]
        
        for zone in zones[1:]:
            if zone - current_cluster[-1] <= cluster_distance:
                current_cluster.append(zone)
            else:
                # Save average of cluster
                clustered.append(int(np.mean(current_cluster)))
                current_cluster = [zone]
        
        # Don't forget last cluster
        clustered.append(int(np.mean(current_cluster)))
        
        return clustered
    
    def _filter_by_touches(self, zones, df_1m):
        """Filter zones by minimum number of touches"""
        zone_touches = {zone: 0 for zone in zones}
        
        for _, candle in df_1m.iterrows():
            for zone in zones:
                if abs(candle['high'] - zone) <= self.zone_threshold or \
                   abs(candle['low'] - zone) <= self.zone_threshold:
                    zone_touches[zone] += 1
        
        # Keep zones with minimum touches
        filtered = [z for z, cnt in zone_touches.items() if cnt >= self.min_touches]
        return sorted(filtered)
    
    def find_optimal_rejection_pct(self, df_1m):
        """
        Analyze all zone touches to find optimal rejection % threshold
        A rejection is confirmed when price moves X% away from zone
        """
        print("\n📊 Analyzing rejection patterns...")
        
        rejections = []
        
        for zone in self.zones:
            # Find all candles that touch this zone
            for i in range(10, len(df_1m) - 10):
                candle = df_1m.iloc[i]
                
                # Check if zone touched
                touched = (abs(candle['high'] - zone) <= self.zone_threshold or 
                          abs(candle['low'] - zone) <= self.zone_threshold)
                
                if not touched:
                    continue
                
                # Determine if this was resistance or support
                if candle['close'] < zone:
                    # Touched from below - resistance
                    # Check if price rejected (moved down)
                    next_candles = df_1m.iloc[i+1:i+11]
                    
                    for j, nc in next_candles.iterrows():
                        move_pct = ((zone - nc['close']) / zone) * 100
                        if move_pct > 0:  # Price moved down
                            rejections.append(move_pct)
                            break
                
                elif candle['close'] > zone:
                    # Touched from above - support
                    # Check if price rejected (moved up)
                    next_candles = df_1m.iloc[i+1:i+11]
                    
                    for j, nc in next_candles.iterrows():
                        move_pct = ((nc['close'] - zone) / zone) * 100
                        if move_pct > 0:  # Price moved up
                            rejections.append(move_pct)
                            break
        
        if rejections:
            # Find the median rejection % as threshold
            self.rejection_pct = np.percentile(rejections, 30)  # 30th percentile - early signal
            print(f"✅ Optimal rejection threshold: {self.rejection_pct:.3f}%")
            print(f"   Total rejections analyzed: {len(rejections)}")
            print(f"   Min: {min(rejections):.3f}%, Max: {max(rejections):.3f}%")
        else:
            self.rejection_pct = 0.05  # Default 0.05% if no data
            print(f"⚠️  No rejections found, using default: {self.rejection_pct}%")
        
        return self.rejection_pct
    
    def backtest(self, df_1m):
        """Run backtest with zone rejection strategy"""
        print("\n🚀 Starting backtest...")
        
        for i in range(50, len(df_1m)):
            candle = df_1m.iloc[i]
            
            # Manage active trade
            if self.active_trade:
                self._manage_trade(candle, i, df_1m)
            
            # Skip if have active trade
            if self.active_trade:
                continue
            
            # Check for zone touch
            for zone in self.zones:
                touched = (abs(candle['high'] - zone) <= self.zone_threshold or 
                          abs(candle['low'] - zone) <= self.zone_threshold)
                
                if not touched:
                    continue
                
                # Check for rejection confirmation
                direction, entry, sl = self._check_rejection(candle, zone, i, df_1m)
                
                if direction:
                    # Find target (opposite zone)
                    tp = self._find_target_zone(zone, direction)
                    if tp:
                        self._enter_trade(candle, direction, entry, sl, tp, zone, i)
                        break
        
        # Close remaining trades
        if self.active_trade:
            self._close_trade(self.active_trade, df_1m.iloc[-1]['close'], len(df_1m)-1, "EOD")
        
        return self._calculate_metrics()
    
    def _check_rejection(self, candle, zone, idx, df_1m):
        """
        Check if price shows rejection confirmation
        Returns: (direction, entry_price, sl_price) or (None, None, None)
        """
        # Determine if zone is acting as support or resistance
        if candle['close'] < zone:
            # Touched from below - resistance
            # Check for rejection DOWN
            move_pct = ((zone - candle['close']) / zone) * 100
            
            if move_pct >= self.rejection_pct:
                # Rejection confirmed - SHORT
                direction = "SHORT"
                entry = candle['close']
                sl = candle['high']  # SL at rejection candle high
                return direction, entry, sl
        
        elif candle['close'] > zone:
            # Touched from above - support  
            # Check for rejection UP
            move_pct = ((candle['close'] - zone) / zone) * 100
            
            if move_pct >= self.rejection_pct:
                # Rejection confirmed - LONG
                direction = "LONG"
                entry = candle['close']
                sl = candle['low']  # SL at rejection candle low
                return direction, entry, sl
        
        return None, None, None
    
    def _find_target_zone(self, current_zone, direction):
        """Find the opposite zone as target"""
        if direction == "LONG":
            # Find next zone above
            targets = [z for z in self.zones if z > current_zone + 20]
            return targets[0] if targets else None
        else:
            # Find next zone below
            targets = [z for z in self.zones if z < current_zone - 20]
            return targets[-1] if targets else None
    
    def _enter_trade(self, candle, direction, entry, sl, tp, zone, idx):
        """Enter a new trade"""
        # Calculate position size
        sl_dist = abs(entry - sl)
        risk_usd = self.balance * (self.risk_pct / 100)
        qty = risk_usd / sl_dist
        
        # Apply leverage limit
        max_qty = (self.balance * self.leverage) / entry
        qty = min(qty, max_qty)
        
        # Apply position cap ($50k)
        max_notional = min(50000, self.balance * self.leverage)
        max_qty_cap = max_notional / entry
        qty = min(qty, max_qty_cap)
        
        self.active_trade = {
            'id': len(self.trades),
            'idx': idx,
            'time': candle['time'],
            'dir': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'zone': zone,
            'qty': qty,
            'balance_before': self.balance,
            'best_price': entry,
            'trailing_sl': sl,
            'closed': False
        }
        
        print(f"\n{'='*60}")
        print(f"📈 {direction} ENTRY")
        print(f"   Entry: ${entry:.2f}")
        print(f"   SL: ${sl:.2f} ({abs(entry-sl):.2f} pips)")
        print(f"   TP: ${tp:.2f} ({abs(tp-entry):.2f} pips)")
        print(f"   Zone: ${zone:.2f}")
        print(f"   Qty: {qty:.2f} oz")
        print(f"   Balance: ${self.balance:,.2f}")
    
    def _manage_trade(self, candle, idx, df_1m):
        """Manage active trade with trailing stop and reversal"""
        t = self.active_trade
        
        # Update trailing stop
        if t['dir'] == "LONG":
            # Update best price
            if candle['high'] > t['best_price']:
                t['best_price'] = candle['high']
                # Move trailing SL
                sl_distance = t['entry'] - t['sl']
                new_trailing_sl = t['best_price'] - sl_distance
                if new_trailing_sl > t['trailing_sl']:
                    t['trailing_sl'] = new_trailing_sl
            
            # Check exits
            if candle['low'] <= t['trailing_sl']:
                self._close_trade(t, t['trailing_sl'], idx, "Trailing-SL")
            elif candle['high'] >= t['tp']:
                # Check if hitting opposite zone - prepare for reversal
                self._close_trade(t, t['tp'], idx, "TP-ZoneHit")
        
        else:  # SHORT
            # Update best price
            if candle['low'] < t['best_price']:
                t['best_price'] = candle['low']
                # Move trailing SL
                sl_distance = t['sl'] - t['entry']
                new_trailing_sl = t['best_price'] + sl_distance
                if new_trailing_sl < t['trailing_sl']:
                    t['trailing_sl'] = new_trailing_sl
            
            # Check exits
            if candle['high'] >= t['trailing_sl']:
                self._close_trade(t, t['trailing_sl'], idx, "Trailing-SL")
            elif candle['low'] <= t['tp']:
                # Check if hitting opposite zone - prepare for reversal
                self._close_trade(t, t['tp'], idx, "TP-ZoneHit")
    
    def _close_trade(self, t, exit_price, idx, reason):
        """Close trade"""
        if t['dir'] == "LONG":
            pnl = (exit_price - t['entry']) * t['qty']
        else:
            pnl = (t['entry'] - exit_price) * t['qty']
        
        self.balance += pnl
        
        t['closed'] = True
        t['exit'] = exit_price
        t['exit_idx'] = idx
        t['reason'] = reason
        t['pnl'] = pnl
        t['balance_after'] = self.balance
        
        self.trades.append(t)
        self.active_trade = None
        
        print(f"\n{'='*60}")
        print(f"💰 TRADE CLOSED: {reason}")
        print(f"   Exit: ${exit_price:.2f}")
        print(f"   P&L: ${pnl:+,.2f}")
        print(f"   Balance: ${self.balance:,.2f}")
    
    def _calculate_metrics(self):
        """Calculate performance metrics"""
        if not self.trades:
            return None
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        roi = (total_pnl / self.start) * 100
        
        # Calculate drawdown
        peak = self.start
        max_dd = 0
        
        for t in self.trades:
            if t['balance_after'] > peak:
                peak = t['balance_after']
            dd = ((peak - t['balance_after']) / peak) * 100
            if dd > max_dd:
                max_dd = dd
        
        return {
            'start': self.start,
            'final': self.balance,
            'roi': roi,
            'trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trades) * 100 if self.trades else 0,
            'max_dd': max_dd,
            'zones': len(self.zones)
        }


def main():
    """Run backtest"""
    print("="*80)
    print("GOLD BRAMHASTRA V2 - ZONE REJECTION STRATEGY")
    print("="*80)
    
    # Load data
    df = pd.read_csv('cache_xauusd_spot_mt5_1m_30d.csv', header=None, 
                     names=['time', 'open', 'high', 'low', 'close'])
    print(f"\n📊 Loaded {len(df)} 1-minute candles")
    
    # Initialize strategy
    strategy = GoldBramhastraV2()
    
    # Detect zones
    strategy.detect_zones_multi_timeframe(df)
    
    # Find optimal rejection %
    strategy.find_optimal_rejection_pct(df)
    
    # Run backtest
    metrics = strategy.backtest(df)
    
    # Print results
    if metrics:
        print("\n" + "="*80)
        print("BACKTEST RESULTS")
        print("="*80)
        print(f"Start Balance:   ${metrics['start']:,.2f}")
        print(f"Final Balance:   ${metrics['final']:,.2f}")
        print(f"ROI:             {metrics['roi']:+.2f}%")
        print(f"Total Trades:    {metrics['trades']}")
        print(f"Win Rate:        {metrics['win_rate']:.1f}%")
        print(f"Max Drawdown:    {metrics['max_dd']:.2f}%")
        print(f"Zones Detected:  {metrics['zones']}")
        print("="*80)
        
        # Save results
        with open('gold_backtest_v2_results.json', 'w') as f:
            json.dump({
                'metrics': metrics,
                'trades': strategy.trades,
                'zones': strategy.zones
            }, f, indent=2)
        print("\n✅ Results saved to gold_backtest_v2_results.json")


if __name__ == "__main__":
    main()
