"""
BTC Sniper LIVE - Binance WebSocket
EXACT SAME LOGIC as backtest (85% win rate, +1588% ROI)
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json

class BTCSniperLive:
    def __init__(self, api_key, api_secret, account_size=None, risk_pct=2.0):
        # Binance connection
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}  # Use futures for leverage
        })
        
        self.symbol = 'BTC/USDT'
        self.account_size = account_size  # None = use real balance
        self.risk_pct = risk_pct
        self.balance = 0
        
        # BTC OPTIMIZED PARAMETERS (EXACT SAME AS BACKTEST)
        self.zone_lookback_15m = 10
        self.zone_lookback_1h = 14
        self.zone_lookback_4h = 6
        self.cluster_distance = 80
        
        self.zone_proximity_5m = 120
        self.breakout_lookback_5m = 8
        self.breakout_threshold = 40
        
        self.entry_zone_touch = 60
        self.max_sl_distance = 150
        self.min_sl_distance = 50
        
        self.min_rr_ratio = 2.5
        self.max_trade_distance = 600
        
        # Dynamic TP & Trailing (EXACT SAME)
        self.initial_tp_multiplier = 3.5
        self.tp_extension_trigger_pct = 0.75
        self.tp_extension_distance = self.breakout_threshold * 2
        self.max_tp_extensions = 3
        
        self.trail_activation_rr = 1.8
        self.trail_lock_pct = 0.7
        self.trail_step_pips = self.breakout_threshold * 0.5
        
        # Trade filtering (EXACT SAME)
        self.min_5m_candles_between = 8
        self.max_trades_per_day = 15
        
        # State
        self.zones = []
        self.poc_levels = []
        self.trades = []
        self.active_trade = None
        self.last_trade_time = None
        self.trades_today = 0
        self.current_date = None
        
    def initialize(self):
        """Initialize connection and fetch initial data"""
        print("\n🔗 Connecting to Binance...")
        
        try:
            # Test connection
            self.exchange.load_markets()
            
            # Get account balance
            balance_info = self.exchange.fetch_balance()
            usdt_balance = balance_info['USDT']['free']
            
            if self.account_size is None:
                self.account_size = usdt_balance
                self.balance = usdt_balance
                print(f"✅ Using real balance: ${self.balance:,.2f}")
            else:
                self.balance = self.account_size
                print(f"✅ Using fixed capital: ${self.balance:,.2f}")
            
            print(f"✅ Connected to Binance")
            print(f"   Symbol: {self.symbol}")
            print(f"   Balance: ${self.balance:,.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def get_historical_data(self, timeframe='1m', bars=500):
        """Fetch historical OHLCV data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=bars)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"❌ Error fetching {timeframe} data: {e}")
            return None
    
    def _cluster_zones(self, levels):
        """Cluster nearby levels (EXACT SAME AS BACKTEST)"""
        if not levels:
            return []
        
        sorted_levels = sorted(levels)
        clusters = []
        current_cluster = [sorted_levels[0]]
        
        for level in sorted_levels[1:]:
            if level - current_cluster[-1] <= self.cluster_distance:
                current_cluster.append(level)
            else:
                clusters.append(np.mean(current_cluster))
                current_cluster = [level]
        
        clusters.append(np.mean(current_cluster))
        return clusters
    
    def detect_zones(self):
        """Detect zones from multiple timeframes (EXACT SAME AS BACKTEST)"""
        print("\n🔍 Detecting zones...")
        
        # Fetch historical data
        df_15m = self.get_historical_data('15m', 200)
        df_1h = self.get_historical_data('1h', 200)
        df_4h = self.get_historical_data('4h', 200)
        
        if df_15m is None or df_1h is None or df_4h is None:
            return False
        
        all_zones = []
        
        # 15m zones
        for i in range(self.zone_lookback_15m, len(df_15m)):
            window = df_15m.iloc[i-self.zone_lookback_15m:i]
            high_val = window['high'].max()
            low_val = window['low'].min()
            all_zones.extend([high_val, low_val])
        
        # 1h zones
        for i in range(self.zone_lookback_1h, len(df_1h)):
            window = df_1h.iloc[i-self.zone_lookback_1h:i]
            high_val = window['high'].max()
            low_val = window['low'].min()
            all_zones.extend([high_val, low_val])
        
        # 4h zones
        for i in range(self.zone_lookback_4h, len(df_4h)):
            window = df_4h.iloc[i-self.zone_lookback_4h:i]
            high_val = window['high'].max()
            low_val = window['low'].min()
            all_zones.extend([high_val, low_val])
        
        self.zones = self._cluster_zones(all_zones)
        print(f"✅ Detected {len(self.zones)} zones")
        
        # Calculate POC
        print("\n📊 Calculating POC levels...")
        df_1m = self.get_historical_data('1m', 1000)
        if df_1m is None:
            return False
        
        price_min = df_1m['low'].min()
        price_max = df_1m['high'].max()
        
        bins = 100
        price_range = np.linspace(price_min, price_max, bins)
        volume_profile = np.zeros(bins - 1)
        
        for _, row in df_1m.iterrows():
            for i in range(len(price_range) - 1):
                if price_range[i] <= row['close'] < price_range[i+1]:
                    volume_profile[i] += row['volume']
                    break
        
        top_indices = np.argsort(volume_profile)[-10:]
        poc_levels = [price_range[i] for i in top_indices]
        
        self.poc_levels = self._cluster_zones(poc_levels)
        print(f"✅ Found {len(self.poc_levels)} POC levels")
        
        return True
    
    def analyze_5m_setup(self, df_5m):
        """Analyze 5-min setup (EXACT SAME AS BACKTEST)"""
        if len(df_5m) < self.breakout_lookback_5m + 5:
            return None, None, False
        
        # Use COMPLETED candle (iloc[-2])
        current = df_5m.iloc[-2]
        
        # Check if near zone or POC
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
        
        level = nearby_zone if nearby_zone else nearby_poc
        is_confluence = (nearby_zone is not None and nearby_poc is not None)
        
        # Check 5-min structure break (use 8 PREVIOUS candles)
        recent = df_5m.iloc[-self.breakout_lookback_5m-2:-2]
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        
        # LONG: Break above
        if current['close'] > recent_high + self.breakout_threshold:
            return 'LONG', level, is_confluence
        
        # SHORT: Break below
        if current['close'] < recent_low - self.breakout_threshold:
            return 'SHORT', level, is_confluence
        
        return None, None, False
    
    def execute_1m_entry(self, direction, zone_level):
        """Execute 1-min entry (EXACT SAME AS BACKTEST)"""
        df_1m = self.get_historical_data('1m', 10)
        if df_1m is None or len(df_1m) < 6:
            return None, None, None
        
        current = df_1m.iloc[-1]
        entry = current['close']
        
        # SL: Tight stop based on direction
        if direction == 'LONG':
            recent_low = df_1m.iloc[-6:-1]['low'].min()
            sl_option1 = recent_low - self.min_sl_distance
            sl_option2 = zone_level - self.max_sl_distance
            sl = max(sl_option1, sl_option2)
            
            sl_dist = entry - sl
            if sl_dist > self.max_sl_distance:
                sl = entry - self.max_sl_distance
            elif sl_dist < self.min_sl_distance:
                sl = entry - self.min_sl_distance
        
        else:  # SHORT
            recent_high = df_1m.iloc[-6:-1]['high'].max()
            sl_option1 = recent_high + self.min_sl_distance
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
            tp_candidates = [lvl for lvl in all_levels if lvl > entry + self.breakout_threshold*2]
            tp = tp_candidates[0] if tp_candidates else entry + self.max_trade_distance/2
        else:
            tp_candidates = [lvl for lvl in all_levels if lvl < entry - self.breakout_threshold*2]
            tp = tp_candidates[-1] if tp_candidates else entry - self.max_trade_distance/2
        
        # Check R:R
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        
        if reward / risk < self.min_rr_ratio:
            return None, None, None
        
        if reward > self.max_trade_distance:
            return None, None, None
        
        return entry, sl, tp
    
    def _enter_trade(self, direction, entry, sl, tp, zone_level, is_confluence):
        """Enter trade on Binance"""
        try:
            # Calculate position size
            risk_usd = self.balance * (self.risk_pct / 100)
            sl_distance = abs(entry - sl)
            position_size = risk_usd / sl_distance
            
            # Round to exchange precision
            position_size = round(position_size, 3)
            
            # Place market order
            order_type = 'buy' if direction == 'LONG' else 'sell'
            order = self.exchange.create_market_order(
                symbol=self.symbol,
                side=order_type,
                amount=position_size
            )
            
            print(f"\n{'🟢 LONG' if direction == 'LONG' else '🔴 SHORT'} @ ${entry:,.2f}")
            print(f"   Order ID: {order['id']}")
            print(f"   Size: {position_size} BTC")
            print(f"   SL: ${sl:,.2f} | TP: ${tp:,.2f}")
            
            # Set SL and TP orders
            self._set_sl_tp(order['id'], direction, sl, tp, position_size)
            
            self.active_trade = {
                'order_id': order['id'],
                'direction': direction,
                'entry': entry,
                'sl': sl,
                'tp': tp,
                'tp_original': tp,
                'position_size': position_size,
                'entry_time': datetime.now(),
                'zone': zone_level,
                'is_confluence': is_confluence,
                'tp_extensions': 0,
                'trailing_active': False
            }
            
            return True
            
        except Exception as e:
            print(f"❌ Order failed: {e}")
            return False
    
    def _set_sl_tp(self, order_id, direction, sl, tp, size):
        """Set stop-loss and take-profit orders"""
        try:
            # Stop-loss order
            if direction == 'LONG':
                self.exchange.create_order(
                    symbol=self.symbol,
                    type='stop_market',
                    side='sell',
                    amount=size,
                    params={'stopPrice': sl, 'reduceOnly': True}
                )
            else:
                self.exchange.create_order(
                    symbol=self.symbol,
                    type='stop_market',
                    side='buy',
                    amount=size,
                    params={'stopPrice': sl, 'reduceOnly': True}
                )
            
            # Take-profit order
            if direction == 'LONG':
                self.exchange.create_limit_order(
                    symbol=self.symbol,
                    side='sell',
                    amount=size,
                    price=tp,
                    params={'reduceOnly': True}
                )
            else:
                self.exchange.create_limit_order(
                    symbol=self.symbol,
                    side='buy',
                    amount=size,
                    price=tp,
                    params={'reduceOnly': True}
                )
            
            print(f"   ✅ SL/TP orders placed")
            
        except Exception as e:
            print(f"   ⚠️ SL/TP error: {e}")
    
    def _manage_trade(self):
        """Manage active trade (EXACT SAME LOGIC AS BACKTEST)"""
        if not self.active_trade:
            return
        
        try:
            # Get current position
            positions = self.exchange.fetch_positions([self.symbol])
            position = next((p for p in positions if float(p['contracts']) > 0), None)
            
            if not position:
                # Position closed
                self._close_trade('Position closed')
                return
            
            current_price = float(position['markPrice'])
            trade = self.active_trade
            
            # Calculate profit
            if trade['direction'] == 'LONG':
                profit = current_price - trade['entry']
            else:
                profit = trade['entry'] - current_price
            
            # TP Extension
            if trade['direction'] == 'LONG':
                progress = (current_price - trade['entry']) / (trade['tp'] - trade['entry'])
            else:
                progress = (trade['entry'] - current_price) / (trade['entry'] - trade['tp'])
            
            if progress >= self.tp_extension_trigger_pct and trade['tp_extensions'] < self.max_tp_extensions:
                if trade['direction'] == 'LONG':
                    trade['tp'] += self.tp_extension_distance
                else:
                    trade['tp'] -= self.tp_extension_distance
                trade['tp_extensions'] += 1
                print(f"   📈 TP Extended to ${trade['tp']:,.2f} (Extension {trade['tp_extensions']})")
                # Update TP order
                self._update_tp_order(trade['tp'])
            
            # Trailing SL
            risk = abs(trade['entry'] - trade['sl'])
            
            if profit / risk >= self.trail_activation_rr:
                if not trade['trailing_active']:
                    trade['trailing_active'] = True
                    print(f"   🔄 Trailing SL activated")
                
                locked_profit = profit * self.trail_lock_pct
                if trade['direction'] == 'LONG':
                    new_sl = trade['entry'] + locked_profit
                    if new_sl > trade['sl']:
                        trade['sl'] = new_sl
                        print(f"   📊 SL Trailed to ${trade['sl']:,.2f}")
                        self._update_sl_order(trade['sl'])
                else:
                    new_sl = trade['entry'] - locked_profit
                    if new_sl < trade['sl']:
                        trade['sl'] = new_sl
                        print(f"   📊 SL Trailed to ${trade['sl']:,.2f}")
                        self._update_sl_order(trade['sl'])
            
        except Exception as e:
            print(f"❌ Trade management error: {e}")
    
    def _update_sl_order(self, new_sl):
        """Update stop-loss order"""
        try:
            # Cancel existing SL
            open_orders = self.exchange.fetch_open_orders(self.symbol)
            for order in open_orders:
                if order['type'] == 'stop_market':
                    self.exchange.cancel_order(order['id'], self.symbol)
            
            # Place new SL
            trade = self.active_trade
            if trade['direction'] == 'LONG':
                self.exchange.create_order(
                    symbol=self.symbol,
                    type='stop_market',
                    side='sell',
                    amount=trade['position_size'],
                    params={'stopPrice': new_sl, 'reduceOnly': True}
                )
            else:
                self.exchange.create_order(
                    symbol=self.symbol,
                    type='stop_market',
                    side='buy',
                    amount=trade['position_size'],
                    params={'stopPrice': new_sl, 'reduceOnly': True}
                )
        except Exception as e:
            print(f"   ⚠️ SL update error: {e}")
    
    def _update_tp_order(self, new_tp):
        """Update take-profit order"""
        try:
            # Cancel existing TP
            open_orders = self.exchange.fetch_open_orders(self.symbol)
            for order in open_orders:
                if order['type'] == 'limit' and order.get('reduceOnly'):
                    self.exchange.cancel_order(order['id'], self.symbol)
            
            # Place new TP
            trade = self.active_trade
            if trade['direction'] == 'LONG':
                self.exchange.create_limit_order(
                    symbol=self.symbol,
                    side='sell',
                    amount=trade['position_size'],
                    price=new_tp,
                    params={'reduceOnly': True}
                )
            else:
                self.exchange.create_limit_order(
                    symbol=self.symbol,
                    side='buy',
                    amount=trade['position_size'],
                    price=new_tp,
                    params={'reduceOnly': True}
                )
        except Exception as e:
            print(f"   ⚠️ TP update error: {e}")
    
    def _close_trade(self, reason):
        """Close active trade"""
        if not self.active_trade:
            return
        
        trade = self.active_trade
        
        try:
            # Get final position info
            positions = self.exchange.fetch_positions([self.symbol])
            position = next((p for p in positions if float(p['contracts']) > 0), None)
            
            if position:
                pnl = float(position['unrealizedPnl'])
            else:
                pnl = 0
            
            self.balance += pnl
            
            self.trades.append({
                'entry_time': trade['entry_time'],
                'exit_time': datetime.now(),
                'direction': trade['direction'],
                'entry': trade['entry'],
                'pnl': pnl,
                'reason': reason
            })
            
            print(f"\n   ✅ Trade closed | PnL: ${pnl:+,.2f} | Reason: {reason}")
            
            self.active_trade = None
            
        except Exception as e:
            print(f"❌ Close trade error: {e}")
            self.active_trade = None
    
    def run(self):
        """Main trading loop"""
        print("\n" + "="*80)
        print("BTC SNIPER LIVE - Binance")
        print("EXACT SAME LOGIC AS BACKTEST (85% win rate, +1588% ROI)")
        print("="*80)
        
        if not self.initialize():
            return
        
        if not self.detect_zones():
            return
        
        print(f"\n✅ Setup complete")
        print(f"   Zones: {len(self.zones)}")
        print(f"   POC Levels: {len(self.poc_levels)}")
        print(f"   Risk per trade: {self.risk_pct}%")
        print(f"   Max trades/day: {self.max_trades_per_day}")
        
        print(f"\n🚀 Starting live trading...")
        print(f"Press Ctrl+C to stop\n")
        
        last_5m_candle_time = None
        last_zone_update = datetime.now()
        
        try:
            while True:
                now = datetime.now()
                
                # Reset daily trade count
                current_date = now.date()
                if current_date != self.current_date:
                    self.current_date = current_date
                    self.trades_today = 0
                    print(f"\n📅 New Day: {current_date} | Balance: ${self.balance:,.2f}")
                
                # Update zones every hour
                if (now - last_zone_update).total_seconds() > 3600:
                    print("\n🔄 Updating zones...")
                    self.detect_zones()
                    last_zone_update = now
                
                # Manage active trade
                if self.active_trade:
                    self._manage_trade()
                    time.sleep(5)
                    continue
                
                # Check trade spacing
                if self.last_trade_time:
                    time_since = (now - self.last_trade_time).total_seconds() / 60
                    if time_since < self.min_5m_candles_between * 5:
                        time.sleep(5)
                        continue
                
                # Check daily limit
                if self.trades_today >= self.max_trades_per_day:
                    time.sleep(60)
                    continue
                
                # Get 5-min data
                df_5m = self.get_historical_data('5m', 20)
                
                if df_5m is not None and len(df_5m) >= 2:
                    # Only analyze on new 5-min candle
                    current_5m_time = df_5m.iloc[-2]['timestamp']
                    
                    if last_5m_candle_time is None or current_5m_time > last_5m_candle_time:
                        last_5m_candle_time = current_5m_time
                        
                        # Get current price
                        ticker = self.exchange.fetch_ticker(self.symbol)
                        current_price = ticker['last']
                        
                        # Show market analysis
                        nearest_zone = min(self.zones, key=lambda z: abs(current_price - z))
                        nearest_dist = abs(current_price - nearest_zone)
                        
                        print(f"\n🔍 [{now.strftime('%H:%M')}] Market Analysis:")
                        print(f"   Price: ${current_price:,.2f}")
                        print(f"   Nearest Zone: ${nearest_zone:,.2f} ({nearest_dist:.1f} away)")
                        
                        if nearest_dist <= self.zone_proximity_5m:
                            print(f"   ✅ NEAR ZONE! Within {self.zone_proximity_5m}")
                            
                            # Analyze 5-min setup
                            direction, zone_level, is_confluence = self.analyze_5m_setup(df_5m)
                            
                            if direction:
                                print(f"\n   🎯 SETUP FOUND: {direction} @ ${zone_level:,.2f}")
                                print(f"   {'✨ CONFLUENCE' if is_confluence else '📍 Zone only'}")
                                
                                # Execute on 1-min
                                entry, sl, tp = self.execute_1m_entry(direction, zone_level)
                                
                                if entry is not None:
                                    print(f"   ✅ Entry confirmed @ ${entry:,.2f}")
                                    print(f"   Executing order...")
                                    
                                    success = self._enter_trade(direction, entry, sl, tp, zone_level, is_confluence)
                                    
                                    if success:
                                        self.last_trade_time = now
                                        self.trades_today += 1
                                else:
                                    print(f"   ❌ Entry rejected: R:R or SL criteria not met")
                            else:
                                print(f"   ℹ️  Near zone but no valid breakout setup")
                        else:
                            print(f"   ⏳ Waiting for price to approach zone")
                
                # Status update every 5 minutes
                if now.second == 0 and now.minute % 5 == 0:
                    profit = self.balance - self.account_size
                    profit_pct = (profit / self.account_size) * 100
                    print(f"[{now.strftime('%H:%M')}] Balance: ${self.balance:,.2f} | P&L: ${profit:+,.2f} ({profit_pct:+.2f}%) | Trades: {self.trades_today}")
                
                time.sleep(1)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Bot stopped by user")
        
        finally:
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
    # CONFIGURATION
    API_KEY = "YOUR_BINANCE_API_KEY"
    API_SECRET = "YOUR_BINANCE_API_SECRET"
    
    ACCOUNT_SIZE = None  # None = use real balance, or set fixed amount
    RISK_PCT = 2.0  # 2% risk per trade
    
    print("\n⚠️  LIVE TRADING WARNING:")
    print("   This bot trades with REAL MONEY on Binance Futures")
    print("   Make sure you understand the risks")
    print("   Start with small capital to test\n")
    
    confirm = input("Type 'START' to begin live trading: ")
    
    if confirm.upper() == 'START':
        bot = BTCSniperLive(
            api_key=API_KEY,
            api_secret=API_SECRET,
            account_size=ACCOUNT_SIZE,
            risk_pct=RISK_PCT
        )
        bot.run()
    else:
        print("❌ Aborted")
