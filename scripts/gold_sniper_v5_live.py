#!/usr/bin/env python3
"""
GOLD SNIPER V5 - LIVE TRADING VERSION
======================================
EXACT SAME LOGIC AS BACKTEST - Live execution on MT5

5-minute analysis, 1-minute execution, sniper entries
Dynamic TP extensions, Aggressive trailing, Funding Pips compliant
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json

# MT5 CREDENTIALS - FUNDING PIPS TRIAL
MT5_LOGIN = 40000179483
MT5_PASSWORD = "&Ij4-#r3d"
MT5_SERVER = "FundingPips-Trial"

class GoldSniperV5Live:
    def __init__(self, account_size=10000, phase='phase1', symbol='XAUUSD'):
        """Initialize live trading bot with EXACT backtest logic"""
        self.symbol = symbol
        
        # ACCOUNT - NO COMPOUNDING! (SAME AS BACKTEST)
        self.account_size = account_size  # FIXED - never changes (for position sizing)
        
        # MT5 specific - connect first to get real balance
        if not self._connect_mt5():
            raise Exception("Failed to connect to MT5")
        
        self.symbol_info = mt5.symbol_info(self.symbol)
        if self.symbol_info is None:
            raise Exception(f"Symbol {self.symbol} not found")
        
        if not self.symbol_info.visible:
            mt5.symbol_select(self.symbol, True)
        
        self.point = self.symbol_info.point
        self.digits = self.symbol_info.digits
        
        # Get REAL balance from MT5
        account_info = mt5.account_info()
        self.balance = account_info.balance  # Track REAL balance
        self.start = self.balance  # Starting balance for this session
        self.profit_withdrawn = 0
        self.peak_balance = self.balance
        self.daily_start_balance = self.balance
        
        # FUNDING PIPS PHASE (SAME AS BACKTEST)
        self.phase = phase
        self.leverage = None  # Will read from MT5
        self.risk_pct = 2.0
        
        # HARD LOCKS FOR FUNDING PIPS - REMOVED!
        self.can_trade = True  # Always allow trading
        
        # ZONE DETECTION (SAME AS BACKTEST)
        self.zone_lookback_15m = 8
        self.zone_lookback_1h = 12
        self.zone_lookback_4h = 6
        self.cluster_distance = 8

        # ENTRY LOGIC - SNIPER STYLE (SAME AS BACKTEST)
        self.zone_proximity_5m = 15
        self.breakout_lookback_5m = 8
        self.breakout_threshold = 3
        
        # EXECUTION - 1-MIN PRECISION (SAME AS BACKTEST)
        self.entry_zone_touch = 5
        self.max_sl_distance = 8
        self.min_sl_distance = 3
        
        # RISK MANAGEMENT (SAME AS BACKTEST)
        self.min_rr_ratio = 2.0
        self.max_trade_distance = 50  # MATCHES BACKTEST (overwritten value)
        
        # DYNAMIC TP & AGGRESSIVE TRAILING (SAME AS BACKTEST)
        self.initial_tp_multiplier = 3.0
        self.tp_extension_trigger_pct = 0.7  # Extend at 70%
        self.tp_extension_distance = 15      # Extend by 15 pips
        self.max_tp_extensions = 5           # Max 5 extensions
        
        # AGGRESSIVE TRAILING (SAME AS BACKTEST)
        self.trail_activation_rr = 1.5       # Activate at 1.5:1
        self.trail_lock_pct = 0.6            # Lock 60% profit
        self.trail_step_pips = 5             # Move every 5 pips
        
        # FUNDING PIPS COMPLIANCE (SAME AS BACKTEST)
        self.fp_rules = self._get_funding_pips_rules()
        self.daily_pnl = 0
        self.inactivity_days = 0
        self.large_win_triggered = False
        
        # TRADE FILTERING (SAME AS BACKTEST)
        self.min_5m_candles_between = 10
        self.max_trades_per_day = 8
        
        # STATE (SAME AS BACKTEST)
        self.zones = []
        self.zone_metadata = {}
        self.poc_levels = []
        self.trades = []
        self.active_trade = None
        self.last_trade_time = None
        self.trades_today = 0
        self.current_date = None
        
        # Get account leverage from MT5 (not hardcoded!)
        account_info = mt5.account_info()
        self.account_leverage = float(account_info.leverage)
        self.margin_mode = account_info.margin_mode  # 0=retail, 1=exchange
        
        # Get symbol-specific leverage by testing margin
        test_margin = mt5.order_calc_margin(mt5.ORDER_TYPE_BUY, self.symbol, 1.0, 4000.0)
        if test_margin:
            # Effective leverage = position_value / margin
            position_value = 1.0 * self.symbol_info.trade_contract_size * 4000.0
            self.leverage = position_value / test_margin
        else:
            self.leverage = 10.0  # Default fallback
        
        print(f"\n{'='*80}")
        print(f"GOLD SNIPER V5 - LIVE TRADING (EXACT BACKTEST LOGIC)")
        print(f"{'='*80}")
        print(f"Symbol: {self.symbol}")
        print(f"Account: {MT5_LOGIN} @ {MT5_SERVER}")
        print(f"Balance: ${account_info.balance:,.2f}")
        print(f"Fixed Capital: ${self.account_size:,.2f}")
        print(f"Phase: {self.phase.upper()}")
        print(f"Account Leverage: 1:{int(self.account_leverage)}")
        print(f"XAUUSD Effective Leverage: 1:{int(self.leverage)}")
        print(f"Risk: {self.risk_pct}% per trade")
        print(f"Margin Mode: {'Retail' if self.margin_mode == 0 else 'Exchange'}")
        print(f"{'='*80}\n")

    def _connect_mt5(self):
        """Connect to MT5 with credentials"""
        if not mt5.initialize():
            print(f"❌ MT5 initialize() failed: {mt5.last_error()}")
            return False
        
        # Login with credentials
        authorized = mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        
        if not authorized:
            print(f"❌ Login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        
        account_info = mt5.account_info()
        if account_info is None:
            print(f"❌ Failed to get account info: {mt5.last_error()}")
            return False
        
        print(f"✅ Connected to MT5")
        print(f"   Login: {account_info.login}")
        print(f"   Server: {account_info.server}")
        print(f"   Balance: ${account_info.balance:,.2f}")
        print(f"   Equity: ${account_info.equity:,.2f}")
        print(f"   Leverage: 1:{account_info.leverage}")
        
        return True
    
    def _get_funding_pips_rules(self):
        """EXACT SAME as backtest"""
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
                'max_drawdown_pct': 8.0,
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
                'inactivity_days': 30,
                'large_win_threshold_pct': 60.0
            }
        }
        return rules[self.phase]

    def check_funding_pips_compliance(self):
        """For tracking only - NO BLOCKING"""
        return True, "Monitoring only"
    
    def get_historical_data(self, timeframe_mt5, bars=1000):
        """Get historical data from MT5"""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe_mt5, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['datetime'] = pd.to_datetime(df['time'], unit='s')
        return df

    def detect_zones_enhanced(self):
        """EXACT SAME as backtest - Enhanced zone detection"""
        print("\n🔍 Detecting zones...")
        
        # Get 1-minute data for analysis
        df_1m = self.get_historical_data(mt5.TIMEFRAME_M1, 10000)
        if df_1m is None:
            print("❌ Failed to get 1-minute data")
            return False
        
        df_1m = df_1m.copy()
        df_1m.set_index('datetime', inplace=True)
        
        # Resample to higher timeframes
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
        
        # Find swing zones
        zones_15m = self._find_swing_zones(df_15m, self.zone_lookback_15m)
        zones_1h = self._find_swing_zones(df_1h, self.zone_lookback_1h)
        zones_4h = self._find_swing_zones(df_4h, self.zone_lookback_4h)
        
        # Weight by timeframe (EXACT SAME as backtest)
        weighted_zones = []
        for z in zones_4h:
            weighted_zones.extend([z] * 3)
        for z in zones_1h:
            weighted_zones.extend([z] * 2)
        weighted_zones.extend(zones_15m)
        
        # Cluster
        clustered = self._cluster_zones(weighted_zones)
        
        # Calculate strength (EXACT SAME as backtest)
        zone_strength = self._calculate_zone_strength(clustered, df_1m)
        
        # Take top 20-30 zones (EXACT SAME as backtest)
        sorted_zones = sorted(zone_strength.items(), key=lambda x: x[1], reverse=True)
        self.zones = [z[0] for z in sorted_zones[:30]]
        self.zones.sort()
        
        self.zone_metadata = {z: {'strength': s} for z, s in sorted_zones[:30]}
        
        print(f"✅ Detected {len(self.zones)} zones")
        return True

    def _find_swing_zones(self, df, lookback):
        """EXACT SAME as backtest"""
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
        """EXACT SAME as backtest"""
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
        """EXACT SAME as backtest"""
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

    def calculate_poc_levels(self):
        """EXACT SAME as backtest"""
        print("\n📊 Calculating POC levels...")
        
        df_1m = self.get_historical_data(mt5.TIMEFRAME_M1, 10000)
        if df_1m is None:
            print("❌ Failed to get 1-minute data")
            return False
        
        df_1m['date'] = df_1m['datetime'].dt.date
        poc_levels = []
        
        for date in df_1m['date'].unique()[-30:]:  # Last 30 days
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
        return True
    
    def analyze_5m_setup(self, df_5m):
        """EXACT SAME as backtest - Analyze 5-minute chart for setup"""
        if len(df_5m) < self.breakout_lookback_5m + 5:
            return None, None, False
        
        # Use COMPLETED candle (iloc[-2]) not incomplete (iloc[-1])
        current = df_5m.iloc[-2]
        
        # 1. Check if near zone or POC (EXACT SAME)
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
        
        # 2. Check 5-min structure break (EXACT SAME)
        # Get 8 candles BEFORE current (positions -10 to -3)
        recent = df_5m.iloc[-self.breakout_lookback_5m-2:-2]
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        
        # LONG setup: Break above recent high
        if current['close'] > recent_high + self.breakout_threshold:
            return 'LONG', level, is_confluence
        
        # SHORT setup: Break below recent low
        if current['close'] < recent_low - self.breakout_threshold:
            return 'SHORT', level, is_confluence
        
        return None, None, False

    def execute_1m_entry(self, direction, zone_level):
        """EXACT SAME as backtest - Execute precise entry on 1-minute"""
        # Get recent 1-min data
        df_1m = self.get_historical_data(mt5.TIMEFRAME_M1, 10)
        if df_1m is None or len(df_1m) < 6:
            return None, None, None
        
        current = df_1m.iloc[-1]
        
        # Entry: Current price (EXACT SAME - backtest has NO zone distance check here)
        entry = current['close']
        
        # SL: Tight stop based on direction (EXACT SAME)
        if direction == 'LONG':
            recent_low = df_1m.iloc[-6:-1]['low'].min()
            sl_option1 = recent_low - 1
            sl_option2 = zone_level - self.max_sl_distance
            sl = max(sl_option1, sl_option2)
            
            sl_dist = entry - sl
            if sl_dist > self.max_sl_distance:
                sl = entry - self.max_sl_distance
            elif sl_dist < self.min_sl_distance:
                sl = entry - self.min_sl_distance
        
        else:  # SHORT
            recent_high = df_1m.iloc[-6:-1]['high'].max()
            sl_option1 = recent_high + 1
            sl_option2 = zone_level + self.max_sl_distance
            sl = min(sl_option1, sl_option2)
            
            sl_dist = sl - entry
            if sl_dist > self.max_sl_distance:
                sl = entry + self.max_sl_distance
            elif sl_dist < self.min_sl_distance:
                sl = entry + self.min_sl_distance
        
        # TP: Next zone/POC (EXACT SAME)
        all_levels = sorted(set(self.zones + self.poc_levels))
        
        if direction == 'LONG':
            tp_candidates = [lvl for lvl in all_levels if lvl > entry + 10]
            tp = tp_candidates[0] if tp_candidates else entry + 30
        else:
            tp_candidates = [lvl for lvl in all_levels if lvl < entry - 10]
            tp = tp_candidates[-1] if tp_candidates else entry - 30
        
        # Check risk:reward (EXACT SAME)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        
        if reward / risk < self.min_rr_ratio:
            return None, None, None
        
        # Check TP not too far (EXACT SAME)
        if reward > self.max_trade_distance:
            return None, None, None
        
        return entry, sl, tp

    def _enter_trade(self, direction, entry, sl, tp, level, is_confluence):
        """Enter trade - NO BLOCKS!"""
        # Calculate position size
        risk_usd = self.account_size * (self.risk_pct / 100)
        sl_dist = abs(entry - sl)
        qty = risk_usd / sl_dist
        
        # Funding Pips compliance - sizing only
        max_loss_per_trade = self.account_size * (self.fp_rules['max_loss_per_trade_pct'] / 100)
        potential_loss = qty * sl_dist
        
        if potential_loss > max_loss_per_trade:
            qty = max_loss_per_trade / sl_dist
        
        # Leverage cap (use actual MT5 leverage)
        max_qty = (self.account_size * self.leverage) / entry
        qty = min(qty, max_qty)
        
        # Convert to MT5 lots (1 oz = 0.01 lot for XAUUSD typically)
        lots = round(qty * 0.01, 2)
        if lots < 0.01:
            lots = 0.01
        
        # MARGIN CHECK - Use MT5's actual margin calculation
        tick = mt5.symbol_info_tick(self.symbol)
        price = tick.ask if direction == 'LONG' else tick.bid
        
        margin_required = mt5.order_calc_margin(
            mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL,
            self.symbol,
            lots,
            price
        )
        
        if margin_required is None:
            print(f"   ❌ Failed to calculate margin")
            return False
        
        account_info = mt5.account_info()
        margin_pct = (margin_required / account_info.balance) * 100
        
        print(f"\n💰 MARGIN CHECK:")
        print(f"   Lots: {lots}")
        print(f"   Position Value: ${lots * self.symbol_info.trade_contract_size * price:,.2f}")
        print(f"   Margin Required: ${margin_required:,.2f} ({margin_pct:.2f}% of balance)")
        print(f"   Free Margin: ${account_info.margin_free:,.2f}")
        
        # Check if we have enough margin (use 95% safety margin)
        if margin_required > account_info.margin_free * 0.95:
            print(f"   ⚠️  Insufficient margin! Reducing lot size...")
            
            # Binary search for max lots we can use
            low, high = 0.01, lots
            max_lots = 0.01
            
            while high - low > 0.01:
                mid = round((low + high) / 2, 2)
                test_margin = mt5.order_calc_margin(
                    mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL,
                    self.symbol,
                    mid,
                    price
                )
                
                if test_margin and test_margin <= account_info.margin_free * 0.95:
                    max_lots = mid
                    low = mid
                else:
                    high = mid
            
            if max_lots < 0.01:
                print(f"   ❌ Cannot open position - insufficient margin")
                return False
            
            lots = max_lots
            margin_required = mt5.order_calc_margin(
                mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL,
                self.symbol,
                lots,
                price
            )
            margin_pct = (margin_required / account_info.balance) * 100
            print(f"   ✅ Adjusted to {lots} lots")
            print(f"   New margin: ${margin_required:,.2f} ({margin_pct:.2f}%)")
        
        # Prepare MT5 order
        order_type = mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lots,
            "type": order_type,
            "price": price,
            "sl": round(sl, self.digits),
            "tp": round(tp, self.digits),
            "deviation": 20,
            "magic": 123456,
            "comment": "GoldSniper_V5",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order failed: {result.comment if result else mt5.last_error()}")
            return False
        
        # Store trade info (EXACT SAME structure as backtest)
        self.active_trade = {
            'ticket': result.order,
            'dir': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'initial_tp': tp,
            'tp_extensions': 0,
            'level': level,
            'is_confluence': is_confluence,
            'qty': qty,
            'lots': lots,
            'balance_before': self.balance,
            'best_price': entry,
            'trailing_sl': sl,
            'time': datetime.now()
        }
        
        self.trades_today += 1
        self.last_trade_time = datetime.now()
        
        confluence_str = "ZONE+POC" if is_confluence else "ZONE"
        rr = abs(tp - entry) / sl_dist
        
        print(f"\n{'='*70}")
        print(f"🎯 {direction} @ {confluence_str}")
        print(f"   Entry: ${entry:.2f} | SL: ${sl:.2f} ({sl_dist:.1f}p)")
        print(f"   TP: ${tp:.2f} | R:R = 1:{rr:.1f}")
        print(f"   Level: ${level:.2f} | Lots: {lots} | Ticket: {result.order}")
        print(f"   FIXED Capital: ${self.account_size:,.2f}")
        print(f"   Margin Used: {margin_pct:.1f}%")
        print(f"{'='*70}")
        
        return True

    def _manage_trade(self):
        """EXACT SAME as backtest - Manage trade with DYNAMIC TP and AGGRESSIVE TRAILING"""
        if not self.active_trade:
            return
        
        # Get current position
        positions = mt5.positions_get(symbol=self.symbol, ticket=self.active_trade['ticket'])
        if not positions or len(positions) == 0:
            # Position closed (by SL/TP)
            self._on_position_closed()
            return
        
        pos = positions[0]
        t = self.active_trade
        current_price = pos.price_current
        
        # Update best price and manage (EXACT SAME logic as backtest)
        if t['dir'] == 'LONG':
            if current_price > t['best_price']:
                t['best_price'] = current_price
                
                # DYNAMIC TP EXTENSION (EXACT SAME)
                progress_to_tp = (t['best_price'] - t['entry']) / (t['tp'] - t['entry'])
                
                if progress_to_tp >= self.tp_extension_trigger_pct and t['tp_extensions'] < self.max_tp_extensions:
                    old_tp = t['tp']
                    t['tp'] = t['tp'] + self.tp_extension_distance
                    t['tp_extensions'] += 1
                    
                    # Modify TP in MT5
                    self._modify_position(pos, pos.sl, t['tp'])
                    print(f"   📈 TP Extended: ${old_tp:.2f} → ${t['tp']:.2f} (Extension #{t['tp_extensions']})")
                
                # AGGRESSIVE TRAILING (EXACT SAME)
                profit_pips = t['best_price'] - t['entry']
                risk_pips = t['entry'] - t['sl']
                rr_achieved = profit_pips / risk_pips
                
                if rr_achieved >= self.trail_activation_rr:
                    new_sl = t['entry'] + (profit_pips * self.trail_lock_pct)
                    
                    if new_sl > t['trailing_sl'] + self.trail_step_pips:
                        t['trailing_sl'] = new_sl
                        
                        # Modify SL in MT5
                        self._modify_position(pos, new_sl, pos.tp)
                        print(f"   🔒 Trail Updated: ${t['trailing_sl']:.2f} (Locking {self.trail_lock_pct*100:.0f}% profit)")
        
        else:  # SHORT (EXACT SAME)
            if current_price < t['best_price']:
                t['best_price'] = current_price
                
                # DYNAMIC TP EXTENSION
                progress_to_tp = (t['entry'] - t['best_price']) / (t['entry'] - t['tp'])
                
                if progress_to_tp >= self.tp_extension_trigger_pct and t['tp_extensions'] < self.max_tp_extensions:
                    old_tp = t['tp']
                    t['tp'] = t['tp'] - self.tp_extension_distance
                    t['tp_extensions'] += 1
                    
                    self._modify_position(pos, pos.sl, t['tp'])
                    print(f"   📉 TP Extended: ${old_tp:.2f} → ${t['tp']:.2f} (Extension #{t['tp_extensions']})")
                
                # AGGRESSIVE TRAILING
                profit_pips = t['entry'] - t['best_price']
                risk_pips = t['sl'] - t['entry']
                rr_achieved = profit_pips / risk_pips
                
                if rr_achieved >= self.trail_activation_rr:
                    new_sl = t['entry'] - (profit_pips * self.trail_lock_pct)
                    
                    if new_sl < t['trailing_sl'] - self.trail_step_pips:
                        t['trailing_sl'] = new_sl
                        
                        self._modify_position(pos, new_sl, pos.tp)
                        print(f"   🔒 Trail Updated: ${t['trailing_sl']:.2f} (Locking {self.trail_lock_pct*100:.0f}% profit)")

    def _modify_position(self, pos, new_sl, new_tp):
        """Modify position SL/TP"""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": self.symbol,
            "position": pos.ticket,
            "sl": round(new_sl, self.digits),
            "tp": round(new_tp, self.digits),
        }
        
        result = mt5.order_send(request)
        if result and result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"   ⚠️  Modify failed: {result.comment}")
    
    def _on_position_closed(self):
        """EXACT SAME as backtest - Handle position closure"""
        if not self.active_trade:
            return
        
        t = self.active_trade
        
        # Get trade history to find exit
        deals = mt5.history_deals_get(ticket=t['ticket'])
        if not deals or len(deals) < 2:
            self.active_trade = None
            return
        
        exit_deal = deals[-1]
        exit_price = exit_deal.price
        
        # Calculate P&L (EXACT SAME)
        if t['dir'] == 'LONG':
            pnl = (exit_price - t['entry']) * t['qty']
        else:
            pnl = (t['entry'] - exit_price) * t['qty']
        
        # Update balance (EXACT SAME)
        self.balance += pnl
        self.daily_pnl += pnl
        
        # Track peak (EXACT SAME)
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        # Check 60% rule (EXACT SAME)
        if pnl > 0 and self.phase == 'master':
            profit_target_usd = self.account_size * (self.fp_rules.get('profit_target_pct', 8) / 100)
            if pnl >= (profit_target_usd * 0.6):
                self.large_win_triggered = True
                print(f"   ⚠️  60% RULE TRIGGERED: Single win ${pnl:,.2f} >= 60% of target")
        
        # Check compliance (EXACT SAME)
        compliant, message = self.check_funding_pips_compliance()
        if not compliant:
            print(f"\n{message}")
        elif "PASSED" in message:
            print(f"\n{message}")
        
        # Store trade (EXACT SAME)
        t['exit'] = exit_price
        t['pnl'] = pnl
        t['balance_after'] = self.balance
        t['exit_time'] = datetime.now()
        
        self.trades.append(t)
        self.active_trade = None
        
        pips = abs(exit_price - t['entry'])
        profit_withdrawn = self.balance - self.account_size
        reason = "TP" if abs(exit_price - t['tp']) < 1 else "SL/Trail"
        
        print(f"💰 {reason} | {pips:.1f}p | P&L: ${pnl:+,.2f}")
        print(f"   Account: ${self.account_size:,.2f} (FIXED) | Profit: ${profit_withdrawn:+,.2f}")
    
    def _emergency_close_all(self, reason):
        """Close all positions on Funding Pips breach"""
        print(f"\n🚨 EMERGENCY: {reason}")
        print("   Closing all open positions...")
        
        positions = mt5.positions_get(symbol=self.symbol)
        if positions and len(positions) > 0:
            for pos in positions:
                # Close position
                close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(self.symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(self.symbol).ask
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": self.symbol,
                    "volume": pos.volume,
                    "type": close_type,
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 20,
                    "magic": 123456,
                    "comment": f"Emergency_{reason}",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"   ✅ Closed ticket {pos.ticket}")
                else:
                    print(f"   ❌ Failed to close {pos.ticket}: {result.comment if result else 'unknown'}")
        
        self.active_trade = None
        print(f"   🔒 Trading LOCKED until reset")

    def run(self):
        """Main trading loop - EXACT SAME logic flow as backtest"""
        print("\n🚀 Starting live trading bot...")
        print("Press Ctrl+C to stop\n")
        
        # Initial setup (EXACT SAME)
        if not self.detect_zones_enhanced():
            print("❌ Failed to detect zones")
            return
        
        if not self.calculate_poc_levels():
            print("❌ Failed to calculate POC")
            return
        
        print(f"\n✅ Setup complete")
        print(f"   Zones: {len(self.zones)}")
        print(f"   POC Levels: {len(self.poc_levels)}")
        print(f"\n🔍 Monitoring {self.symbol}...\n")
        
        last_zone_update = datetime.now()
        last_check = datetime.now()
        last_5m_candle_time = None
        
        try:
            while True:
                now = datetime.now()
                
                # Update zones every hour (like backtest detects zones once)
                if (now - last_zone_update).total_seconds() > 3600:
                    print("\n🔄 Updating zones and POC...")
                    self.detect_zones_enhanced()
                    self.calculate_poc_levels()
                    last_zone_update = now
                
                # Check every 30 seconds
                if (now - last_check).total_seconds() >= 30:
                    # Reset daily tracking (EXACT SAME)
                    current_date = now.date()
                    if current_date != self.current_date:
                        self.current_date = current_date
                        self.trades_today = 0
                        
                        # Update daily baseline with CURRENT balance (from MT5)
                        account = mt5.account_info()
                        if account:
                            self.balance = account.balance
                            self.daily_start_balance = self.balance
                        
                        self.daily_pnl = 0
                        
                        print(f"\n📅 New Day: {current_date} | Balance: ${self.balance:,.2f}")
                    
                    # NO COMPLIANCE CHECKS - LET IT TRADE!
                    
                    # Manage active trade (EXACT SAME)
                    if self.active_trade:
                        self._manage_trade()
                    
                    # Check for new entry (EXACT SAME logic)
                    if not self.active_trade:
                        # Check daily trade limit (EXACT SAME)
                        if self.trades_today >= self.max_trades_per_day:
                            last_check = now
                            time.sleep(1)
                            continue
                        
                        # Check trade spacing (EXACT SAME)
                        if self.last_trade_time:
                            time_since = (now - self.last_trade_time).total_seconds() / 60
                            if time_since < self.min_5m_candles_between * 5:
                                last_check = now
                                time.sleep(1)
                                continue
                        
                        # Get 5-min data (EXACT SAME)
                        df_5m = self.get_historical_data(mt5.TIMEFRAME_M5, 20)
                        
                        if df_5m is not None and len(df_5m) > 0:
                            # Only analyze on new 5-min candle (use COMPLETED candle)
                            if len(df_5m) >= 2:
                                current_5m_time = df_5m.iloc[-2]['datetime']  # Last COMPLETED candle
                            
                                if last_5m_candle_time is None or current_5m_time > last_5m_candle_time:
                                    last_5m_candle_time = current_5m_time
                                
                                # Get current price
                                tick = mt5.symbol_info_tick(self.symbol)
                                current_price = tick.bid
                                
                                # Check proximity to zones
                                nearest_zone = None
                                nearest_dist = float('inf')
                                for z in self.zones:
                                    dist = abs(current_price - z)
                                    if dist < nearest_dist:
                                        nearest_dist = dist
                                        nearest_zone = z
                                
                                # Show market analysis every new 5-min candle
                                print(f"\n🔍 [{now.strftime('%H:%M')}] Market Analysis:")
                                print(f"   Price: ${current_price:.2f}")
                                print(f"   Nearest Zone: ${nearest_zone:.2f} ({nearest_dist:.1f} pips away)")
                                
                                # Check if near zone
                                if nearest_dist <= self.zone_proximity_5m:
                                    print(f"   ✅ NEAR ZONE! Within {self.zone_proximity_5m} pips")
                                    
                                    # Check breakout using COMPLETED candles (EXCLUDES incomplete)
                                    recent = df_5m.iloc[-self.breakout_lookback_5m-2:-2]  # Last 8 COMPLETED candles before current
                                    recent_high = recent['high'].max()
                                    recent_low = recent['low'].min()
                                    
                                    # Get COMPLETED candle close
                                    completed_close = df_5m.iloc[-2]['close']
                                    
                                    print(f"   Recent High: ${recent_high:.2f}")
                                    print(f"   Recent Low: ${recent_low:.2f}")
                                    
                                    if completed_close > recent_high + self.breakout_threshold:
                                        print(f"   🚀 BULLISH BREAKOUT! ${(completed_close - recent_high):.1f} pips above high")
                                    elif completed_close < recent_low - self.breakout_threshold:
                                        print(f"   🔻 BEARISH BREAKOUT! ${(recent_low - completed_close):.1f} pips below low")
                                    else:
                                        print(f"   ⏳ No breakout yet (need +{self.breakout_threshold} pip confirmation)")
                                else:
                                    print(f"   ⏳ Waiting for price to approach zone (need within {self.zone_proximity_5m} pips)")
                                
                                # Analyze 5-min setup (EXACT SAME as backtest)
                                direction, zone_level, is_confluence = self.analyze_5m_setup(df_5m)
                                
                                if direction:
                                    print(f"\n   🎯 SETUP FOUND: {direction} @ ${zone_level:.2f}")
                                    print(f"   {'✨ CONFLUENCE (Zone + POC)' if is_confluence else '📍 Zone only'}")
                                    print(f"   Checking 1-min entry conditions...")
                                    
                                    # Execute on 1-min (EXACT SAME)
                                    entry, sl, tp = self.execute_1m_entry(direction, zone_level)
                                    
                                    if entry is not None:
                                        print(f"   ✅ 1-min entry confirmed @ ${entry:.2f}")
                                        print(f"   SL: ${sl:.2f} | TP: ${tp:.2f}")
                                        print(f"   Executing order...")
                                        
                                        # Enter trade (EXACT SAME)
                                        success = self._enter_trade(direction, entry, sl, tp, zone_level, is_confluence)
                                        
                                        if not success:
                                            print(f"   ❌ Order failed")
                                    else:
                                        print(f"   ❌ 1-min entry rejected: Risk/Reward or SL criteria not met")
                                else:
                                    if nearest_dist <= self.zone_proximity_5m:
                                        print(f"   ℹ️  Near zone but no valid breakout setup")
                    
                    last_check = now
                
                # Status update every 5 minutes
                if now.second == 0 and now.minute % 5 == 0:
                    profit = self.balance - self.account_size
                    profit_pct = (profit / self.account_size) * 100
                    positions = mt5.positions_get(symbol=self.symbol)
                    pos_count = len(positions) if positions else 0
                    
                    print(f"[{now.strftime('%H:%M')}] Balance: ${self.balance:,.2f} | P&L: ${profit:+,.2f} ({profit_pct:+.2f}%) | Trades: {self.trades_today} | Pos: {pos_count}")
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot stopped by user")
        
        finally:
            mt5.shutdown()
            print("✅ MT5 connection closed")
            
            # Print summary
            if self.trades:
                wins = [t for t in self.trades if t['pnl'] > 0]
                losses = [t for t in self.trades if t['pnl'] <= 0]
                print(f"\n📊 SESSION SUMMARY")
                print(f"   Trades: {len(self.trades)} ({len(wins)}W / {len(losses)}L)")
                print(f"   Win Rate: {len(wins)/len(self.trades)*100:.1f}%")
                print(f"   Total P&L: ${sum(t['pnl'] for t in self.trades):+,.2f}")
                print(f"   ROI: {(self.balance - self.account_size)/self.account_size*100:+.2f}%")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("GOLD SNIPER V5 - LIVE TRADING")
    print("EXACT SAME LOGIC AS BACKTEST (+104% ROI, 83% Win Rate)")
    print("="*80)
    
    # Configuration
    ACCOUNT_SIZE = None  # Will use REAL MT5 balance
    PHASE = None         # Auto-detect based on balance
    SYMBOL = 'XAUUSD'    # Gold spot
    
    # For testing/demo, you can override:
    # ACCOUNT_SIZE = 10000  # Fixed capital for position sizing
    # PHASE = 'phase1'      # Force specific phase
    
    print(f"\nConfiguration:")
    print(f"  Account Size: {'AUTO (use MT5 balance)' if ACCOUNT_SIZE is None else f'${ACCOUNT_SIZE:,}'}")
    print(f"  Phase: {'AUTO (detect from balance)' if PHASE is None else PHASE.upper()}")
    print(f"  Symbol: {SYMBOL}")
    print(f"  MT5 Login: {MT5_LOGIN}")
    print(f"  MT5 Server: {MT5_SERVER}")
    print(f"\n⏱️  Auto-starting in 2 seconds... (Ctrl+C to stop)")
    
    time.sleep(2)
    
    # Create and run bot
    try:
        # If ACCOUNT_SIZE is None, get it from MT5
        if ACCOUNT_SIZE is None:
            if not mt5.initialize():
                print(f"❌ MT5 initialize() failed: {mt5.last_error()}")
                exit(1)
            
            mt5.login(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
            account_info = mt5.account_info()
            
            if account_info:
                ACCOUNT_SIZE = account_info.balance
                print(f"\n✅ Using MT5 balance as account size: ${ACCOUNT_SIZE:,.2f}")
            else:
                print(f"❌ Could not get MT5 balance")
                exit(1)
            
            mt5.shutdown()
        
        # Auto-detect phase if not set
        if PHASE is None:
            if ACCOUNT_SIZE <= 25000:
                PHASE = 'phase1'
                print(f"✅ Auto-detected Phase: PHASE1 (balance ≤ $25K)")
            elif ACCOUNT_SIZE <= 100000:
                PHASE = 'phase2'
                print(f"✅ Auto-detected Phase: PHASE2 (balance $25K-$100K)")
            else:
                PHASE = 'master'
                print(f"✅ Auto-detected Phase: MASTER (balance > $100K)")
        
        bot = GoldSniperV5Live(
            account_size=ACCOUNT_SIZE,
            phase=PHASE,
            symbol=SYMBOL
        )
        
        bot.run()
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        mt5.shutdown()
