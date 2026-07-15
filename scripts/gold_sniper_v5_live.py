#!/usr/bin/env python3
"""
GOLD SNIPER V5 - LIVE TRADING VERSION
======================================
Connects to MT5 and executes real trades automatically

FEATURES:
- Real-time zone detection
- Live price monitoring
- Automatic order placement
- Position management (TP extensions, trailing SL)
- Funding Pips compliance checks
- Risk management

REQUIREMENTS:
- MetaTrader 5 installed and running
- MT5 account logged in
- pip install MetaTrader5 pandas numpy
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json

class GoldSniperV5Live:
    def __init__(self, account_size=10000, phase='phase1', symbol='XAUUSD'):
        """
        Initialize live trading bot
        
        Args:
            account_size: Fixed capital for position sizing
            phase: 'phase1', 'phase2', or 'master'
            symbol: Trading symbol (default: XAUUSD)
        """
        self.symbol = symbol
        self.account_size = account_size
        self.phase = phase
        
        # Connect to MT5
        if not self._connect_mt5():
            raise Exception("Failed to connect to MT5")
        
        # Get symbol info
        self.symbol_info = mt5.symbol_info(self.symbol)
        if self.symbol_info is None:
            raise Exception(f"Symbol {self.symbol} not found")
        
        # Enable symbol for trading
        if not self.symbol_info.visible:
            if not mt5.symbol_select(self.symbol, True):
                raise Exception(f"Failed to enable {self.symbol}")

        # Trading parameters
        self.leverage = 10.0
        self.risk_pct = 2.0
        self.point = self.symbol_info.point
        self.digits = self.symbol_info.digits
        
        # Zone detection
        self.zone_lookback_15m = 8
        self.zone_lookback_1h = 12
        self.zone_lookback_4h = 6
        self.cluster_distance = 8
        
        # Entry logic
        self.zone_proximity_5m = 15
        self.breakout_lookback_5m = 8
        self.breakout_threshold = 3
        self.min_sl_distance = 3
        self.max_sl_distance = 8
        self.min_rr_ratio = 2.0
        
        # Dynamic TP & Trailing
        self.tp_extension_trigger_pct = 0.7
        self.tp_extension_distance = 15
        self.max_tp_extensions = 5
        self.trail_activation_rr = 1.5
        self.trail_lock_pct = 0.6
        self.trail_step_pips = 5
        
        # Trade filtering
        self.max_trades_per_day = 8
        self.min_5m_candles_between = 10
        
        # Funding Pips rules
        self.fp_rules = self._get_funding_pips_rules()
        
        # State
        self.zones = []
        self.poc_levels = []
        self.active_positions = {}
        self.trades_today = 0
        self.daily_start_balance = 0
        self.peak_balance = 0
        self.last_trade_time = None
        self.current_date = None
        
        print(f"\n{'='*80}")
        print(f"GOLD SNIPER V5 - LIVE TRADING")
        print(f"{'='*80}")
        print(f"Symbol: {self.symbol}")
        print(f"Account Size: ${self.account_size:,.2f} (FIXED)")
        print(f"Phase: {self.phase.upper()}")
        print(f"Risk per trade: {self.risk_pct}%")
        print(f"Connected to MT5: ✅")
        print(f"{'='*80}\n")

    def _connect_mt5(self):
        """Connect to MetaTrader 5"""
        if not mt5.initialize():
            print(f"❌ MT5 initialization failed: {mt5.last_error()}")
            return False
        
        account_info = mt5.account_info()
        if account_info is None:
            print("❌ Failed to get account info")
            return False
        
        print(f"✅ Connected to MT5")
        print(f"   Account: {account_info.login}")
        print(f"   Server: {account_info.server}")
        print(f"   Balance: ${account_info.balance:,.2f}")
        print(f"   Equity: ${account_info.equity:,.2f}")
        
        return True
    
    def _get_funding_pips_rules(self):
        """Get Funding Pips rules based on phase"""
        rules = {
            'phase1': {
                'profit_target_pct': 8.0,
                'max_drawdown_pct': 10.0,
                'daily_loss_limit_pct': 5.0,
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
            },
            'phase2': {
                'profit_target_pct': 5.0,
                'max_drawdown_pct': 10.0,
                'daily_loss_limit_pct': 5.0,
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
            },
            'master': {
                'daily_loss_limit_pct': 5.0,
                'max_drawdown_pct': 8.0,
                'max_loss_per_trade_pct': 3.0 if self.account_size < 50000 else 2.0,
            }
        }
        return rules[self.phase]
    
    def check_compliance(self):
        """Check Funding Pips compliance"""
        account_info = mt5.account_info()
        if account_info is None:
            return False, "Cannot get account info"
        
        # Daily loss check
        if self.daily_start_balance == 0:
            self.daily_start_balance = account_info.balance
        
        daily_loss = self.daily_start_balance - account_info.balance
        daily_loss_pct = (daily_loss / self.account_size) * 100

        if daily_loss_pct >= self.fp_rules['daily_loss_limit_pct']:
            return False, f"❌ Daily loss limit reached: {daily_loss_pct:.2f}%"
        
        # Max drawdown check
        if self.peak_balance == 0:
            self.peak_balance = account_info.balance
        else:
            self.peak_balance = max(self.peak_balance, account_info.balance)
        
        drawdown = self.peak_balance - account_info.balance
        drawdown_pct = (drawdown / self.account_size) * 100
        
        if drawdown_pct >= self.fp_rules['max_drawdown_pct']:
            return False, f"❌ Max drawdown reached: {drawdown_pct:.2f}%"
        
        # Profit target (phases only)
        if self.phase in ['phase1', 'phase2']:
            profit = account_info.balance - self.account_size
            profit_pct = (profit / self.account_size) * 100
            
            if profit_pct >= self.fp_rules['profit_target_pct']:
                return True, f"✅ {self.phase.upper()} TARGET HIT! {profit_pct:.2f}%"
        
        return True, "Compliant"
    
    def get_historical_data(self, timeframe_str, bars=1000):
        """Get historical data from MT5"""
        timeframe_map = {
            '1M': mt5.TIMEFRAME_M1,
            '5M': mt5.TIMEFRAME_M5,
            '15M': mt5.TIMEFRAME_M15,
            '1H': mt5.TIMEFRAME_H1,
            '4H': mt5.TIMEFRAME_H4,
        }
        
        timeframe = timeframe_map.get(timeframe_str)
        if timeframe is None:
            return None
        
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['datetime'] = pd.to_datetime(df['time'], unit='s')
        return df

    def detect_zones(self):
        """Detect support/resistance zones from multiple timeframes"""
        print("\n🔍 Detecting zones...")
        
        # Get historical data
        df_15m = self.get_historical_data('15M', 500)
        df_1h = self.get_historical_data('1H', 500)
        df_4h = self.get_historical_data('4H', 500)
        
        if df_15m is None or df_1h is None or df_4h is None:
            print("❌ Failed to get historical data")
            return False
        
        # Find swing zones
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
        
        # Cluster nearby zones
        self.zones = self._cluster_zones(weighted_zones)
        self.zones.sort()
        
        print(f"✅ Detected {len(self.zones)} zones")
        return True
    
    def _find_swing_zones(self, df, lookback):
        """Find swing highs and lows"""
        zones = []
        for i in range(lookback, len(df) - lookback):
            # Swing high
            if df['high'].iloc[i] == df['high'].iloc[i-lookback:i+lookback+1].max():
                zones.append(df['high'].iloc[i])
            # Swing low
            if df['low'].iloc[i] == df['low'].iloc[i-lookback:i+lookback+1].min():
                zones.append(df['low'].iloc[i])
        return zones

    def _cluster_zones(self, zones):
        """Cluster nearby zones"""
        if not zones:
            return []
        
        zones_sorted = sorted(zones)
        clustered = []
        current_cluster = [zones_sorted[0]]
        
        for z in zones_sorted[1:]:
            if z - current_cluster[-1] <= self.cluster_distance:
                current_cluster.append(z)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [z]
        
        if current_cluster:
            clustered.append(np.mean(current_cluster))
        
        return clustered
    
    def calculate_poc_levels(self):
        """Calculate Point of Control from volume profile"""
        print("📊 Calculating POC levels...")
        
        df_1m = self.get_historical_data('1M', 10000)
        if df_1m is None:
            print("❌ Failed to get 1-minute data")
            return False
        
        df_1m['date'] = df_1m['datetime'].dt.date
        poc_daily = []
        
        for date in df_1m['date'].unique()[-30:]:  # Last 30 days
            day_data = df_1m[df_1m['date'] == date].copy()
            
            if len(day_data) < 100:
                continue
            
            # Volume profile
            price_min = day_data['low'].min()
            price_max = day_data['high'].max()
            price_range = price_max - price_min
            
            if price_range == 0:
                continue
            
            bins = 50
            bin_size = price_range / bins
            volume_profile = {}
            
            for _, candle in day_data.iterrows():
                price = (candle['high'] + candle['low']) / 2
                bin_idx = int((price - price_min) / bin_size)
                bin_idx = min(bin_idx, bins - 1)
                volume_profile[bin_idx] = volume_profile.get(bin_idx, 0) + candle['tick_volume']
            
            poc_bin = max(volume_profile.items(), key=lambda x: x[1])[0]
            poc_price = price_min + (poc_bin * bin_size) + (bin_size / 2)
            poc_daily.append(poc_price)
        
        self.poc_levels = self._cluster_zones(poc_daily)
        print(f"✅ Found {len(self.poc_levels)} POC levels")
        return True

    def check_entry_setup(self):
        """Check if entry conditions are met on 5-min chart"""
        # Get recent 5-min data
        df_5m = self.get_historical_data('5M', 20)
        if df_5m is None or len(df_5m) < self.breakout_lookback_5m + 1:
            return None
        
        current_price = df_5m['close'].iloc[-1]
        
        # Find nearest zone or POC
        all_levels = self.zones + self.poc_levels
        if not all_levels:
            return None
        
        nearest_level = min(all_levels, key=lambda x: abs(x - current_price))
        distance = abs(current_price - nearest_level)
        
        # Is price near a level?
        if distance > self.zone_proximity_5m:
            return None
        
        # Check for structure break
        recent_high = df_5m['high'].iloc[-self.breakout_lookback_5m:].max()
        recent_low = df_5m['low'].iloc[-self.breakout_lookback_5m:].min()
        
        # Bullish breakout?
        if current_price > recent_high + self.breakout_threshold:
            return {
                'direction': 'BUY',
                'level': nearest_level,
                'type': 'ZONE+POC' if nearest_level in self.zones and nearest_level in self.poc_levels else 'ZONE' if nearest_level in self.zones else 'POC',
                'breakout_high': recent_high,
                'breakout_low': recent_low
            }
        
        # Bearish breakout?
        if current_price < recent_low - self.breakout_threshold:
            return {
                'direction': 'SELL',
                'level': nearest_level,
                'type': 'ZONE+POC' if nearest_level in self.zones and nearest_level in self.poc_levels else 'ZONE' if nearest_level in self.zones else 'POC',
                'breakout_high': recent_high,
                'breakout_low': recent_low
            }
        
        return None

    def execute_trade(self, setup):
        """Execute trade based on setup"""
        # Check compliance
        compliant, msg = self.check_compliance()
        if not compliant:
            print(f"\n⚠️  Cannot trade: {msg}")
            return False
        
        # Check daily trade limit
        now = datetime.now()
        if self.current_date != now.date():
            self.current_date = now.date()
            self.trades_today = 0
            self.daily_start_balance = mt5.account_info().balance
        
        if self.trades_today >= self.max_trades_per_day:
            return False
        
        # Check if we can trade (spacing)
        if self.last_trade_time:
            time_since_last = (now - self.last_trade_time).total_seconds() / 60
            if time_since_last < self.min_5m_candles_between * 5:
                return False
        
        # Get current price
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return False
        
        direction = setup['direction']
        entry_price = tick.ask if direction == 'BUY' else tick.bid
        
        # Calculate SL and TP
        if direction == 'BUY':
            sl_price = setup['breakout_low'] - (self.min_sl_distance * self.point)
            tp_distance_pips = self.min_rr_ratio * abs(entry_price - sl_price) / self.point
            tp_price = entry_price + (tp_distance_pips * self.point)
        else:
            sl_price = setup['breakout_high'] + (self.min_sl_distance * self.point)
            tp_distance_pips = self.min_rr_ratio * abs(sl_price - entry_price) / self.point
            tp_price = entry_price - (tp_distance_pips * self.point)
        
        # Verify SL distance
        sl_pips = abs(entry_price - sl_price) / self.point
        if sl_pips < self.min_sl_distance or sl_pips > self.max_sl_distance:
            print(f"   ⚠️  SL distance {sl_pips:.1f}p outside range [{self.min_sl_distance}-{self.max_sl_distance}]")
            return False
        
        # Calculate position size
        risk_usd = self.account_size * (self.risk_pct / 100)
        pip_value = self.symbol_info.trade_tick_value / self.symbol_info.trade_tick_size
        lots = risk_usd / (sl_pips * pip_value)
        lots = round(lots, 2)
        
        # Check max loss per trade (Funding Pips)
        max_loss_pct = self.fp_rules['max_loss_per_trade_pct']
        max_loss_usd = self.account_size * (max_loss_pct / 100)
        potential_loss = lots * sl_pips * pip_value
        
        if potential_loss > max_loss_usd:
            lots = max_loss_usd / (sl_pips * pip_value)
            lots = round(lots, 2)

        # Prepare order request
        order_type = mt5.ORDER_TYPE_BUY if direction == 'BUY' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": lots,
            "type": order_type,
            "price": entry_price,
            "sl": round(sl_price, self.digits),
            "tp": round(tp_price, self.digits),
            "deviation": 10,
            "magic": 12345,
            "comment": f"GoldSniper_{setup['type']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Send order
        result = mt5.order_send(request)
        
        if result is None:
            print(f"❌ Order failed: {mt5.last_error()}")
            return False
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"❌ Order failed: {result.comment}")
            return False
        
        # Success!
        self.trades_today += 1
        self.last_trade_time = now
        
        rr_ratio = tp_distance_pips / sl_pips
        
        print(f"\n{'='*70}")
        print(f"🎯 {direction} @ {setup['type']}")
        print(f"   Entry: ${entry_price:.2f} | SL: ${sl_price:.2f} ({sl_pips:.1f}p)")
        print(f"   TP: ${tp_price:.2f} | R:R = 1:{rr_ratio:.1f}")
        print(f"   Level: ${setup['level']:.2f} | Lots: {lots}")
        print(f"   Ticket: {result.order}")
        print(f"{'='*70}")
        
        # Store position info for management
        self.active_positions[result.order] = {
            'ticket': result.order,
            'direction': direction,
            'entry': entry_price,
            'sl': sl_price,
            'tp': tp_price,
            'lots': lots,
            'best_price': entry_price,
            'tp_extensions': 0,
            'trailing_active': False
        }
        
        return True

    def manage_positions(self):
        """Manage open positions: TP extensions and trailing SL"""
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None or len(positions) == 0:
            return
        
        for pos in positions:
            ticket = pos.ticket
            
            if ticket not in self.active_positions:
                continue
            
            trade_info = self.active_positions[ticket]
            current_price = pos.price_current
            
            # Update best price
            if trade_info['direction'] == 'BUY':
                if current_price > trade_info['best_price']:
                    trade_info['best_price'] = current_price
                    self._check_tp_extension(ticket, trade_info, pos)
                    self._check_trailing_sl(ticket, trade_info, pos)
            else:  # SELL
                if current_price < trade_info['best_price']:
                    trade_info['best_price'] = current_price
                    self._check_tp_extension(ticket, trade_info, pos)
                    self._check_trailing_sl(ticket, trade_info, pos)
    
    def _check_tp_extension(self, ticket, trade_info, pos):
        """Check if TP should be extended"""
        if trade_info['tp_extensions'] >= self.max_tp_extensions:
            return
        
        # Calculate progress toward TP
        if trade_info['direction'] == 'BUY':
            progress = (trade_info['best_price'] - trade_info['entry']) / (trade_info['tp'] - trade_info['entry'])
        else:
            progress = (trade_info['entry'] - trade_info['best_price']) / (trade_info['entry'] - trade_info['tp'])
        
        if progress >= self.tp_extension_trigger_pct:
            # Extend TP
            old_tp = trade_info['tp']
            
            if trade_info['direction'] == 'BUY':
                new_tp = old_tp + (self.tp_extension_distance * self.point)
            else:
                new_tp = old_tp - (self.tp_extension_distance * self.point)
            
            # Modify position
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": self.symbol,
                "position": ticket,
                "sl": pos.sl,
                "tp": round(new_tp, self.digits),
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                trade_info['tp'] = new_tp
                trade_info['tp_extensions'] += 1
                print(f"   📈 TP Extended: ${old_tp:.2f} → ${new_tp:.2f} (Extension #{trade_info['tp_extensions']})")

    def _check_trailing_sl(self, ticket, trade_info, pos):
        """Check if trailing SL should be updated"""
        # Calculate profit in pips
        if trade_info['direction'] == 'BUY':
            profit_pips = (trade_info['best_price'] - trade_info['entry']) / self.point
            risk_pips = (trade_info['entry'] - trade_info['sl']) / self.point
        else:
            profit_pips = (trade_info['entry'] - trade_info['best_price']) / self.point
            risk_pips = (trade_info['sl'] - trade_info['entry']) / self.point
        
        if risk_pips == 0:
            return
        
        rr_achieved = profit_pips / risk_pips
        
        # Activate trailing?
        if rr_achieved >= self.trail_activation_rr:
            if not trade_info['trailing_active']:
                trade_info['trailing_active'] = True
                print(f"   🔒 Trailing SL Activated (R:R = {rr_achieved:.1f})")
            
            # Calculate new SL
            if trade_info['direction'] == 'BUY':
                new_sl = trade_info['entry'] + (profit_pips * self.trail_lock_pct * self.point)
                
                # Only move SL up
                if new_sl > pos.sl + (self.trail_step_pips * self.point):
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": self.symbol,
                        "position": ticket,
                        "sl": round(new_sl, self.digits),
                        "tp": pos.tp,
                    }
                    
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"   🔒 Trail Updated: ${new_sl:.2f} (Locking {self.trail_lock_pct*100:.0f}% profit)")
            
            else:  # SELL
                new_sl = trade_info['entry'] - (profit_pips * self.trail_lock_pct * self.point)
                
                # Only move SL down
                if new_sl < pos.sl - (self.trail_step_pips * self.point):
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": self.symbol,
                        "position": ticket,
                        "sl": round(new_sl, self.digits),
                        "tp": pos.tp,
                    }
                    
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"   🔒 Trail Updated: ${new_sl:.2f} (Locking {self.trail_lock_pct*100:.0f}% profit)")

    def run(self):
        """Main trading loop"""
        print("\n🚀 Starting live trading bot...")
        print("Press Ctrl+C to stop\n")
        
        # Initial setup
        if not self.detect_zones():
            print("❌ Failed to detect zones")
            return
        
        if not self.calculate_poc_levels():
            print("❌ Failed to calculate POC levels")
            return
        
        print(f"\n✅ Setup complete. Monitoring {self.symbol}...\n")
        
        last_zone_update = datetime.now()
        last_check = datetime.now()
        
        try:
            while True:
                now = datetime.now()
                
                # Update zones every hour
                if (now - last_zone_update).total_seconds() > 3600:
                    print("\n🔄 Updating zones...")
                    self.detect_zones()
                    self.calculate_poc_levels()
                    last_zone_update = now
                
                # Check for setups every 30 seconds
                if (now - last_check).total_seconds() >= 30:
                    # Manage existing positions
                    self.manage_positions()
                    
                    # Check for new entry if no positions
                    positions = mt5.positions_get(symbol=self.symbol)
                    if positions is None or len(positions) == 0:
                        setup = self.check_entry_setup()
                        if setup:
                            self.execute_trade(setup)
                    
                    # Check compliance
                    compliant, msg = self.check_compliance()
                    if not compliant:
                        print(f"\n⚠️  STOPPING: {msg}")
                        break
                    
                    last_check = now
                
                # Show status every 5 minutes
                if now.second == 0 and now.minute % 5 == 0:
                    account = mt5.account_info()
                    if account:
                        profit = account.balance - self.account_size
                        profit_pct = (profit / self.account_size) * 100
                        print(f"[{now.strftime('%H:%M')}] Balance: ${account.balance:,.2f} | P&L: ${profit:+,.2f} ({profit_pct:+.2f}%) | Trades today: {self.trades_today}")
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot stopped by user")
        
        finally:
            # Close MT5 connection
            mt5.shutdown()
            print("✅ MT5 connection closed")

if __name__ == "__main__":
    # Configuration
    ACCOUNT_SIZE = 10000  # Your fixed capital
    PHASE = 'phase1'      # 'phase1', 'phase2', or 'master'
    SYMBOL = 'XAUUSD'     # Gold spot
    
    # Create and run bot
    bot = GoldSniperV5Live(
        account_size=ACCOUNT_SIZE,
        phase=PHASE,
        symbol=SYMBOL
    )
    
    bot.run()
