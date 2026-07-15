#!/usr/bin/env python3
"""
GOLD SNIPER V5 - CORRECT EXECUTION LOGIC
==========================================
5-minute analysis, 1-minute execution, sniper entries

KEY FIXES:
1. Analyze setup on 5-min candles (zone + POC + structure)
2. Wait for 5-min confirmation
3. Execute entry on 1-min precise touch
4. TIGHT SL (3-5 pips) - sniper entry means price shouldn't retrace
5. If hits SL = setup was wrong, move on

ENTRY LOGIC:
- 5-min shows: Price near zone/POC + recent high/low break
- 1-min shows: Precise entry point
- Enter with momentum, tight SL
- If setup correct, price runs immediately
"""

import pandas as pd
import numpy as np
from datetime import datetime
import json

class GoldSniperV5:
    def __init__(self, account_size=10000, phase='phase1'):
        # ACCOUNT - NO COMPOUNDING!
        self.account_size = account_size  # FIXED - never changes
        self.balance = account_size
        self.start = account_size
        self.profit_withdrawn = 0  # Track profits separately
        self.peak_balance = account_size
        self.daily_start_balance = account_size
        
        # FUNDING PIPS PHASE
        self.phase = phase  # 'phase1', 'phase2', 'master'
        self.leverage = 10.0
        self.risk_pct = 2.0  # LOWER for Funding Pips (2% max per trade)
        
        # ZONE DETECTION (same as V4 - works well)
        self.zone_lookback_15m = 8
        self.zone_lookback_1h = 12
        self.zone_lookback_4h = 6
        self.cluster_distance = 8
        
        # ENTRY LOGIC - SNIPER STYLE
        self.zone_proximity_5m = 15     # 5-min: Near zone?
        self.breakout_lookback_5m = 8   # 5-min: Structure break
        self.breakout_threshold = 3     # 5-min: Breakout confirmation (pips)
        
        # EXECUTION - 1-MIN PRECISION
        self.entry_zone_touch = 5       # 1-min: How close to zone for entry
        self.max_sl_distance = 8        # TIGHT SL - 3-8 pips max
        self.min_sl_distance = 3        # Minimum SL
        
        # RISK MANAGEMENT
        self.min_rr_ratio = 2.0         # Minimum 1:2 risk:reward
        self.max_trade_distance = 100   # Max TP distance (extended from 50)
        
        # DYNAMIC TP & AGGRESSIVE TRAILING
        self.initial_tp_multiplier = 3.0    # Start with 1:3 R:R
        self.tp_extension_trigger_pct = 0.7 # Extend TP when 70% there
        self.tp_extension_distance = 15     # Extend by 15 pips each time
        self.max_tp_extensions = 5          # Max 5 extensions
        
        # AGGRESSIVE TRAILING
        self.trail_activation_rr = 1.5      # Activate at 1.5:1 profit
        self.trail_lock_pct = 0.6           # Lock 60% of profit
        self.trail_step_pips = 5            # Move trail every 5 pips
        
        # FUNDING PIPS COMPLIANCE
        self.fp_rules = self._get_funding_pips_rules()
        self.daily_pnl = 0
        self.inactivity_days = 0
        self.large_win_triggered = False  # Track 60% rule
        self.max_trade_distance = 50    # Don't enter if TP too far
        
        # TRAILING
        self.trail_activation_pips = 8  # Start trailing after 8 pips profit
        self.trail_lock_pct = 0.5       # Lock 50% of profit
        
        # TRADE FILTERING - QUALITY OVER QUANTITY
        self.min_5m_candles_between = 10  # Wait 10 5-min candles between trades
        self.max_trades_per_day = 8       # Increased from 5 for Funding Pips
        
        # STATE
        self.zones = []
        self.zone_metadata = {}
        self.poc_levels = []
        self.trades = []
        self.active_trade = None
        self.last_trade_5m_idx = -999
        self.trades_today = 0
        self.current_date = None
    
    def _get_funding_pips_rules(self):
        """Get Funding Pips 2-Step Standard rules based on phase"""
        rules = {
            'phase1': {
                'profit_target_pct': 8.0,
                'max_drawdown_pct': 10.0,
                'daily_loss_limit_pct': 5.0,
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
                'inactivity_days': 30
            },
            'phase2': {
                'profit_target_pct': 5.0,
                'max_drawdown_pct': 10.0,
                'daily_loss_limit_pct': 5.0,
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
                'inactivity_days': 30
            },
            'master': {
                'daily_loss_limit_pct': 5.0,
                'max_drawdown_pct': 8.0,  # Trailing, locks at 97% after 5% profit
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
                'inactivity_days': 30,
                'large_win_threshold_pct': 60.0  # 60% rule
            }
        }
        return rules[self.phase]
    
    def check_funding_pips_compliance(self):
        """Check compliance with Funding Pips rules"""
        # Daily loss check
        daily_loss_usd = self.daily_start_balance - self.balance
        daily_loss_pct = (daily_loss_usd / self.account_size) * 100
        
        if daily_loss_pct >= self.fp_rules['daily_loss_limit_pct']:
            return False, f"❌ BREACH: Daily loss {daily_loss_pct:.2f}% >= {self.fp_rules['daily_loss_limit_pct']}%"
        
        # Max drawdown check  
        drawdown_usd = self.peak_balance - self.balance
        drawdown_pct = (drawdown_usd / self.account_size) * 100
        
        if drawdown_pct >= self.fp_rules['max_drawdown_pct']:
            return False, f"❌ BREACH: Max DD {drawdown_pct:.2f}% >= {self.fp_rules['max_drawdown_pct']}%"
        
        # Profit target check (phases only)
        if self.phase in ['phase1', 'phase2']:
            profit_usd = self.balance - self.account_size
            profit_pct = (profit_usd / self.account_size) * 100
            
            if profit_pct >= self.fp_rules['profit_target_pct']:
                return True, f"✅ {self.phase.upper()} PASSED! Profit: {profit_pct:.2f}%"
        
        return True, "Compliant"
        
    def detect_zones_enhanced(self, df_1m):
        """Enhanced zone detection (same as V4)"""
        print("\n🔍 Detecting zones...")
        
        df_1m['datetime'] = pd.to_datetime(df_1m['time'], unit='s')
        df_1m.set_index('datetime', inplace=True)
        
        df_15m = df_1m.resample('15min').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'tick_volume': 'sum'
        }).dropna()
        
        df_1h = df_1m.resample('1h').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'tick_volume': 'sum'
        }).dropna()
        
        df_4h = df_1m.resample('4h').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'tick_volume': 'sum'
        }).dropna()
        
        df_1m.reset_index(inplace=True)
        df_1m['time'] = df_1m['datetime'].astype(int) // 10**9
        
        # Find swings
        zones_15m = self._find_swing_zones(df_15m, self.zone_lookback_15m)
        zones_1h = self._find_swing_zones(df_1h, self.zone_lookback_1h)
        zones_4h = self._find_swing_zones(df_4h, self.zone_lookback_4h)
        
        # Weight by timeframe
        weighted_zones = []
        for z in zones_4h:
            weighted_zones.extend([z] * 3)
        for z in zones_1h:
            weighted_zones.extend([z] * 2)
        weighted_zones.extend(zones_15m)
        
        # Cluster
        clustered = self._cluster_zones(weighted_zones)
        
        # Calculate strength
        zone_strength = self._calculate_zone_strength(clustered, df_1m)
        
        # Take top 20-30 zones
        sorted_zones = sorted(zone_strength.items(), key=lambda x: x[1], reverse=True)
        self.zones = [z[0] for z in sorted_zones[:30]]
        self.zones.sort()
        
        self.zone_metadata = {z: {'strength': s} for z, s in sorted_zones[:30]}
        
        print(f"✅ Detected {len(self.zones)} zones")
        return self.zones
    
    def _find_swing_zones(self, df, lookback):
        """Find swing highs and lows"""
        zones = []
        for i in range(lookback, len(df) - lookback):
            # Swing high
            if df.iloc[i]['high'] == df.iloc[i-lookback:i+lookback+1]['high'].max():
                zones.append(round(df.iloc[i]['high'], 2))
            # Swing low
            if df.iloc[i]['low'] == df.iloc[i-lookback:i+lookback+1]['low'].min():
                zones.append(round(df.iloc[i]['low'], 2))
        return zones
    
    def _cluster_zones(self, zones):
        """Cluster nearby zones"""
        if not zones:
            return []
        zones = sorted(zones)
        clusters = {}
        
        for z in zones:
            z_rounded = round(z, 1)
            if z_rounded not in clusters:
                clusters[z_rounded] = []
            clusters[z_rounded].append(z)
        
        final_zones = []
        processed = set()
        
        for zone in sorted(clusters.keys()):
            if zone in processed:
                continue
            nearby = [z for z in clusters.keys()
                     if abs(z - zone) <= self.cluster_distance and z not in processed]
            if nearby:
                all_values = []
                for nz in nearby:
                    all_values.extend(clusters[nz])
                    processed.add(nz)
                final_zones.append(round(np.mean(all_values), 2))
        
        return final_zones
    
    def _calculate_zone_strength(self, zones, df_1m):
        """Calculate zone strength"""
        strength = {z: 0 for z in zones}
        for _, candle in df_1m.iterrows():
            for zone in zones:
                if abs(candle['high'] - zone) <= 15 or abs(candle['low'] - zone) <= 15:
                    strength[zone] += 1
                    
                    # Bonus for wicks
                    body_top = max(candle['open'], candle['close'])
                    body_bottom = min(candle['open'], candle['close'])
                    
                    if candle['high'] > body_top + 5 and abs(candle['high'] - zone) <= 10:
                        strength[zone] += 2
                    if candle['low'] < body_bottom - 5 and abs(candle['low'] - zone) <= 10:
                        strength[zone] += 2
        return strength
    
    def calculate_poc_levels(self, df_1m):
        """Calculate POC levels"""
        print("\n📊 Calculating POC levels...")
        
        df_1m['date'] = pd.to_datetime(df_1m['time'], unit='s').dt.date
        poc_levels = []
        
        for date in df_1m['date'].unique():
            day_data = df_1m[df_1m['date'] == date]
            price_volume = {}
            
            for _, candle in day_data.iterrows():
                price = round(candle['close'], 0)
                vol = candle['tick_volume']
                if price not in price_volume:
                    price_volume[price] = 0
                price_volume[price] += vol
            
            if price_volume:
                poc = max(price_volume.items(), key=lambda x: x[1])[0]
                poc_levels.append(poc)
        
        self.poc_levels = self._cluster_zones(poc_levels)
        print(f"✅ Found {len(self.poc_levels)} POC levels")
        return self.poc_levels
    
    def analyze_5m_setup(self, idx_5m, df_5m):
        """
        Analyze 5-minute chart for setup
        Returns: (direction, zone_level, is_confluence)
        """
        if idx_5m < self.breakout_lookback_5m + 5:
            return None, None, False
        
        current = df_5m.iloc[idx_5m]
        
        # 1. Check if near zone or POC
        nearby_zone = None
        nearby_poc = None
        
        for zone in self.zones:
            if abs(current['close'] - zone) <= self.zone_proximity_5m:
                nearby_zone = zone
                break
        
        for poc in self.poc_levels:
            if abs(current['close'] - poc) <= self.zone_proximity_5m:
                nearby_poc = poc
                break
        
        if not nearby_zone and not nearby_poc:
            return None, None, False
        
        # Choose level (prefer confluence)
        level = nearby_zone if nearby_zone else nearby_poc
        is_confluence = (nearby_zone is not None and nearby_poc is not None)
        
        # 2. Check 5-min structure break
        recent = df_5m.iloc[idx_5m - self.breakout_lookback_5m:idx_5m]
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        
        # LONG setup: Break above recent high
        if current['close'] > recent_high + self.breakout_threshold:
            return 'LONG', level, is_confluence
        
        # SHORT setup: Break below recent low
        if current['close'] < recent_low - self.breakout_threshold:
            return 'SHORT', level, is_confluence
        
        return None, None, False
    
    def execute_1m_entry(self, idx_1m, df_1m, direction, zone_level):
        """
        Execute precise entry on 1-minute chart
        Returns: (entry_price, sl_price, tp_price)
        """
        current = df_1m.iloc[idx_1m]
        
        # Entry: Current price (already confirmed on 5-min)
        entry = current['close']
        
        # SL: Tight stop based on direction
        if direction == 'LONG':
            # SL below recent low or zone
            recent_low = df_1m.iloc[max(0, idx_1m-5):idx_1m]['low'].min()
            sl_option1 = recent_low - 1
            sl_option2 = zone_level - self.max_sl_distance
            sl = max(sl_option1, sl_option2)  # Use closer SL
            
            # Ensure SL distance is reasonable
            sl_dist = entry - sl
            if sl_dist > self.max_sl_distance:
                sl = entry - self.max_sl_distance
            elif sl_dist < self.min_sl_distance:
                sl = entry - self.min_sl_distance
        
        else:  # SHORT
            # SL above recent high or zone
            recent_high = df_1m.iloc[max(0, idx_1m-5):idx_1m]['high'].max()
            sl_option1 = recent_high + 1
            sl_option2 = zone_level + self.max_sl_distance
            sl = min(sl_option1, sl_option2)
            
            sl_dist = sl - entry
            if sl_dist > self.max_sl_distance:
                sl = entry + self.max_sl_distance
            elif sl_dist < self.min_sl_distance:
                sl = entry + self.min_sl_distance
        
        # TP: Next zone/POC
        all_levels = sorted(set(self.zones + self.poc_levels))
        
        if direction == 'LONG':
            tp_candidates = [lvl for lvl in all_levels if lvl > entry + 10]
            tp = tp_candidates[0] if tp_candidates else entry + 30
        else:
            tp_candidates = [lvl for lvl in all_levels if lvl < entry - 10]
            tp = tp_candidates[-1] if tp_candidates else entry - 30
        
        # Check risk:reward
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        
        if reward / risk < self.min_rr_ratio:
            return None, None, None
        
        # Check TP not too far
        if reward > self.max_trade_distance:
            return None, None, None
        
        return entry, sl, tp
    
    def backtest(self, df_1m):
        """Run backtest with correct logic"""
        print("\n🚀 Starting backtest (5-min analysis, 1-min execution)...")
        
        # Create 5-min dataframe
        df_1m['datetime'] = pd.to_datetime(df_1m['time'], unit='s')
        df_1m.set_index('datetime', inplace=True)
        
        df_5m = df_1m.resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'tick_volume': 'sum'
        }).dropna()
        
        df_1m.reset_index(inplace=True)
        df_1m['time'] = df_1m['datetime'].astype(int) // 10**9
        
        print(f"   1-min candles: {len(df_1m)}")
        print(f"   5-min candles: {len(df_5m)}")
        
        # Map 1m to 5m indices
        df_1m['5m_idx'] = -1
        for i in range(len(df_5m)):
            time_5m = df_5m.index[i]
            # Find 1m candles in this 5m period
            mask = (df_1m['datetime'] >= time_5m) & (df_1m['datetime'] < time_5m + pd.Timedelta(minutes=5))
            df_1m.loc[mask, '5m_idx'] = i
        
        # Track trades per day
        setup_count = 0
        
        for i in range(100, len(df_1m)):
            candle_1m = df_1m.iloc[i]
            idx_5m = int(candle_1m['5m_idx'])
            
            if idx_5m < 0:
                continue
            
            # Reset daily trade count and tracking
            current_date = candle_1m['datetime'].date()
            if current_date != self.current_date:
                self.current_date = current_date
                self.trades_today = 0
                self.daily_start_balance = self.balance  # Reset daily baseline
                self.daily_pnl = 0
                print(f"\n📅 New Day: {current_date} | Balance: ${self.balance:,.2f}")
            
            # Check Funding Pips compliance before trading
            compliant, message = self.check_funding_pips_compliance()
            if not compliant:
                print(f"\n{message}")
                print("🛑 Trading stopped - Funding Pips breach")
                break
            
            # Manage active trade
            if self.active_trade:
                self._manage_trade(candle_1m, i)
            
            if self.active_trade:
                continue
            
            # Check if too soon after last trade
            if idx_5m - self.last_trade_5m_idx < self.min_5m_candles_between:
                continue
            
            # Check daily trade limit
            if self.trades_today >= self.max_trades_per_day:
                continue
            
            # Analyze 5-min setup
            direction, zone_level, is_confluence = self.analyze_5m_setup(idx_5m, df_5m)
            
            if not direction:
                continue
            
            setup_count += 1
            
            # Execute on 1-min
            entry, sl, tp = self.execute_1m_entry(i, df_1m, direction, zone_level)
            
            if entry is None:
                continue
            
            # Enter trade
            self._enter_trade(candle_1m, direction, entry, sl, tp, zone_level, is_confluence, i, idx_5m)
            self.last_trade_5m_idx = idx_5m
            self.trades_today += 1
        
        # Close remaining
        if self.active_trade:
            self._close_trade(self.active_trade, df_1m.iloc[-1]['close'], len(df_1m)-1, 'EOD')
        
        print(f"\n📊 Total 5-min setups found: {setup_count}")
        print(f"   Trades executed: {len(self.trades)}")
        
        return self._calculate_metrics()
    
    def _enter_trade(self, candle, direction, entry, sl, tp, level, is_confluence, idx_1m, idx_5m):
        """Enter new trade - FIXED CAPITAL (no compounding!)"""
        # Calculate position size based on ACCOUNT SIZE (not current balance!)
        risk_usd = self.account_size * (self.risk_pct / 100)
        sl_dist = abs(entry - sl)
        qty = risk_usd / sl_dist
        
        # Funding Pips compliance: Check max loss per trade
        max_loss_per_trade = self.account_size * (self.fp_rules['max_loss_per_trade_pct'] / 100)
        potential_loss = qty * sl_dist
        
        if potential_loss > max_loss_per_trade:
            qty = max_loss_per_trade / sl_dist
        
        # Leverage cap
        max_qty = (self.account_size * self.leverage) / entry
        qty = min(qty, max_qty)
        
        self.active_trade = {
            'id': len(self.trades),
            'idx_1m': idx_1m,
            'idx_5m': idx_5m,
            'time': candle['time'],
            'dir': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'initial_tp': tp,  # Track initial TP
            'tp_extensions': 0,  # Count extensions
            'level': level,
            'is_confluence': is_confluence,
            'qty': qty,
            'balance_before': self.balance,
            'best_price': entry,
            'trailing_sl': sl,
            'closed': False
        }
        
        confluence_str = "ZONE+POC" if is_confluence else "ZONE"
        rr = abs(tp - entry) / sl_dist
        
        print(f"\n{'='*70}")
        print(f"🎯 {direction} @ {confluence_str}")
        print(f"   Entry: ${entry:.2f} | SL: ${sl:.2f} ({sl_dist:.1f}p)")
        print(f"   TP: ${tp:.2f} | R:R = 1:{rr:.1f}")
        print(f"   Level: ${level:.2f} | Qty: {qty:.2f} oz")
        print(f"   FIXED Capital: ${self.account_size:,.2f}")
    
    def _manage_trade(self, candle, idx):
        """Manage trade with DYNAMIC TP and AGGRESSIVE TRAILING"""
        t = self.active_trade
        
        if t['dir'] == 'LONG':
            # Update best price
            if candle['high'] > t['best_price']:
                t['best_price'] = candle['high']
                
                # DYNAMIC TP EXTENSION
                progress_to_tp = (t['best_price'] - t['entry']) / (t['tp'] - t['entry'])
                
                if progress_to_tp >= self.tp_extension_trigger_pct and t['tp_extensions'] < self.max_tp_extensions:
                    old_tp = t['tp']
                    t['tp'] = t['tp'] + self.tp_extension_distance
                    t['tp_extensions'] += 1
                    print(f"   📈 TP Extended: ${old_tp:.2f} → ${t['tp']:.2f} (Extension #{t['tp_extensions']})")
                
                # AGGRESSIVE TRAILING
                profit_pips = t['best_price'] - t['entry']
                risk_pips = t['entry'] - t['sl']
                rr_achieved = profit_pips / risk_pips
                
                if rr_achieved >= self.trail_activation_rr:
                    # Lock 60% of profit, update every 5 pips
                    new_sl = t['entry'] + (profit_pips * self.trail_lock_pct)
                    
                    if new_sl > t['trailing_sl'] + self.trail_step_pips:
                        t['trailing_sl'] = new_sl
                        print(f"   🔒 Trail Updated: ${t['trailing_sl']:.2f} (Locking {self.trail_lock_pct*100:.0f}% profit)")
            
            # Check exits
            if candle['low'] <= t['trailing_sl']:
                self._close_trade(t, t['trailing_sl'], idx, 'TrailingSL')
            elif candle['high'] >= t['tp']:
                self._close_trade(t, t['tp'], idx, 'TP')
        
        else:  # SHORT
            if candle['low'] < t['best_price']:
                t['best_price'] = candle['low']
                
                # DYNAMIC TP EXTENSION
                progress_to_tp = (t['entry'] - t['best_price']) / (t['entry'] - t['tp'])
                
                if progress_to_tp >= self.tp_extension_trigger_pct and t['tp_extensions'] < self.max_tp_extensions:
                    old_tp = t['tp']
                    t['tp'] = t['tp'] - self.tp_extension_distance
                    t['tp_extensions'] += 1
                    print(f"   📉 TP Extended: ${old_tp:.2f} → ${t['tp']:.2f} (Extension #{t['tp_extensions']})")
                
                # AGGRESSIVE TRAILING
                profit_pips = t['entry'] - t['best_price']
                risk_pips = t['sl'] - t['entry']
                rr_achieved = profit_pips / risk_pips
                
                if rr_achieved >= self.trail_activation_rr:
                    new_sl = t['entry'] - (profit_pips * self.trail_lock_pct)
                    
                    if new_sl < t['trailing_sl'] - self.trail_step_pips:
                        t['trailing_sl'] = new_sl
                        print(f"   🔒 Trail Updated: ${t['trailing_sl']:.2f} (Locking {self.trail_lock_pct*100:.0f}% profit)")
            
            # Check exits
            if candle['high'] >= t['trailing_sl']:
                self._close_trade(t, t['trailing_sl'], idx, 'TrailingSL')
            elif candle['low'] <= t['tp']:
                self._close_trade(t, t['tp'], idx, 'TP')
    
    def _close_trade(self, t, exit_price, idx, reason):
        """Close trade - NO REINVESTMENT! Profits saved separately"""
        if t['dir'] == 'LONG':
            pnl = (exit_price - t['entry']) * t['qty']
        else:
            pnl = (t['entry'] - exit_price) * t['qty']
        
        # Update balance SEPARATELY from account size
        self.balance += pnl
        self.daily_pnl += pnl
        
        # Track peak for drawdown
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        # Check 60% rule (Funding Pips)
        if pnl > 0 and self.phase == 'master':
            profit_target_usd = self.account_size * (self.fp_rules.get('profit_target_pct', 8) / 100)
            if pnl >= (profit_target_usd * 0.6):
                self.large_win_triggered = True
                print(f"   ⚠️  60% RULE TRIGGERED: Single win ${pnl:,.2f} >= 60% of target")
                print(f"   → Minimum 4 profitable days required on Master account")
        
        # Check Funding Pips compliance
        compliant, message = self.check_funding_pips_compliance()
        if not compliant:
            print(f"\n{message}")
        elif "PASSED" in message:
            print(f"\n{message}")
        
        t['closed'] = True
        t['exit'] = exit_price
        t['exit_idx'] = idx
        t['reason'] = reason
        t['pnl'] = pnl
        t['balance_after'] = self.balance
        t['tp_extensions'] = t.get('tp_extensions', 0)
        
        self.trades.append(t)
        self.active_trade = None
        
        pips = abs(exit_price - t['entry'])
        profit_withdrawn = self.balance - self.account_size
        
        print(f"💰 {reason} | {pips:.1f}p | P&L: ${pnl:+,.2f}")
        print(f"   Account: ${self.account_size:,.2f} (FIXED) | Profit: ${profit_withdrawn:+,.2f}")
    
    def _calculate_metrics(self):
        """Calculate metrics"""
        if not self.trades:
            return None
        
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in self.trades)
        roi = (total_pnl / self.start) * 100
        
        # Drawdown
        peak = self.start
        max_dd = 0
        for t in self.trades:
            if t['balance_after'] > peak:
                peak = t['balance_after']
            dd = ((peak - t['balance_after']) / peak) * 100
            max_dd = max(max_dd, dd)
        
        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0
        profit_factor = abs(avg_win * len(wins) / (avg_loss * len(losses))) if losses else 999
        
        return {
            'start': self.start,
            'final': self.balance,
            'roi': roi,
            'trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(self.trades) * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_dd': max_dd,
            'zones': len(self.zones),
            'poc_levels': len(self.poc_levels)
        }


def main():
    """Run backtest with Funding Pips compliance"""
    print("="*80)
    print("GOLD SNIPER V5 - FUNDING PIPS COMPLIANT")
    print("="*80)
    print("✅ NO PROFIT REINVESTMENT - Fixed capital trading")
    print("✅ Dynamic TP with extensions")
    print("✅ Aggressive trailing (60% lock)")
    print("✅ Funding Pips 2-Step Standard rules enforced")
    print("="*80)
    
    # Load data
    df = pd.read_csv('cache_xauusd_spot_mt5_1m_30d.csv', header=None,
                     names=['time', 'open', 'high', 'low', 'close', 'tick_volume'])
    print(f"\n📊 Loaded {len(df)} 1-minute candles")
    
    # Initialize with Phase 1 rules
    strategy = GoldSniperV5(account_size=10000, phase='phase1')
    
    print(f"\n📋 Funding Pips Rules (Phase 1):")
    print(f"   Profit Target: {strategy.fp_rules['profit_target_pct']}%")
    print(f"   Max Drawdown: {strategy.fp_rules['max_drawdown_pct']}%")
    print(f"   Daily Loss Limit: {strategy.fp_rules['daily_loss_limit_pct']}%")
    print(f"   Max Loss Per Trade: {strategy.fp_rules['max_loss_per_trade_pct']}%")
    
    # Detect zones
    strategy.detect_zones_enhanced(df)
    
    # Calculate POC
    strategy.calculate_poc_levels(df)
    
    # Run backtest
    metrics = strategy.backtest(df)
    
    # Results
    if metrics:
        print("\n" + "="*80)
        print("BACKTEST RESULTS - FUNDING PIPS COMPLIANT")
        print("="*80)
        print(f"Account Size:     ${metrics['start']:,.2f} (FIXED)")
        print(f"Final Balance:    ${metrics['final']:,.2f}")
        print(f"Profit:           ${metrics['final'] - metrics['start']:+,.2f}")
        print(f"ROI:              {metrics['roi']:+.2f}%")
        print(f"")
        print(f"Total Trades:     {metrics['trades']}")
        print(f"Wins / Losses:    {metrics['wins']} / {metrics['losses']}")
        print(f"Win Rate:         {metrics['win_rate']:.1f}%")
        print(f"Avg Win:          ${metrics['avg_win']:,.2f}")
        print(f"Avg Loss:         ${metrics['avg_loss']:,.2f}")
        print(f"Profit Factor:    {metrics['profit_factor']:.2f}")
        print(f"Max Drawdown:     {metrics['max_dd']:.2f}%")
        print(f"")
        print(f"Zones:            {metrics['zones']}")
        print(f"POC Levels:       {metrics['poc_levels']}")
        
        # Funding Pips status
        if metrics['roi'] >= strategy.fp_rules['profit_target_pct']:
            print(f"\n🎉 PHASE 1 PASSED! Target: {strategy.fp_rules['profit_target_pct']}%")
        else:
            print(f"\n📊 Phase 1 Progress: {metrics['roi']:.2f}% / {strategy.fp_rules['profit_target_pct']}%")
        
        if strategy.large_win_triggered:
            print(f"⚠️  60% Rule Triggered - 4 profitable days required on Master")
        
        print("="*80)
    
    # Load data
    df = pd.read_csv('cache_xauusd_spot_mt5_1m_30d.csv', header=None,
                     names=['time', 'open', 'high', 'low', 'close', 'tick_volume'])
    print(f"\n📊 Loaded {len(df)} 1-minute candles")
    
    # Initialize
    strategy = GoldSniperV5()
    
    # Detect zones
    strategy.detect_zones_enhanced(df)
    
    # Calculate POC
    strategy.calculate_poc_levels(df)
    
    # Run backtest
    metrics = strategy.backtest(df)
    
    # Results
    if metrics:
        print("\n" + "="*80)
        print("BACKTEST RESULTS - SNIPER V5")
        print("="*80)
        print(f"Start Balance:    ${metrics['start']:,.2f}")
        print(f"Final Balance:    ${metrics['final']:,.2f}")
        print(f"ROI:              {metrics['roi']:+.2f}%")
        print(f"")
        print(f"Total Trades:     {metrics['trades']}")
        print(f"Wins / Losses:    {metrics['wins']} / {metrics['losses']}")
        print(f"Win Rate:         {metrics['win_rate']:.1f}%")
        print(f"Avg Win:          ${metrics['avg_win']:,.2f}")
        print(f"Avg Loss:         ${metrics['avg_loss']:,.2f}")
        print(f"Profit Factor:    {metrics['profit_factor']:.2f}")
        print(f"Max Drawdown:     {metrics['max_dd']:.2f}%")
        print(f"")
        print(f"Zones:            {metrics['zones']}")
        print(f"POC Levels:       {metrics['poc_levels']}")
        print("="*80)
        
        # Save
        trades_serializable = []
        for t in strategy.trades:
            trade_dict = {}
            for k, v in t.items():
                if isinstance(v, (np.integer, np.floating)):
                    trade_dict[k] = float(v)
                else:
                    trade_dict[k] = v
            trades_serializable.append(trade_dict)
        
        with open('gold_sniper_v5_results.json', 'w') as f:
            json.dump({
                'metrics': metrics,
                'trades': trades_serializable,
                'zones': [float(z) for z in strategy.zones],
                'poc_levels': [float(p) for p in strategy.poc_levels]
            }, f, indent=2)
        
        print("\n✅ Results saved to gold_sniper_v5_results.json")


if __name__ == "__main__":
    main()
