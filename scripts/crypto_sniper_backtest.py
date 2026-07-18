"""
Crypto Sniper Strategy - BTC/ETH Backtest
Adapted from Gold Sniper V5 with crypto-optimized parameters
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import time
import json

class CryptoSniperBacktest:
    def __init__(self, symbol, account_size=10000, risk_pct=2.0):
        self.symbol = symbol  # 'BTCUSDT' or 'ETHUSDT'
        self.account_size = account_size
        self.balance = account_size
        self.risk_pct = risk_pct
        
        # CRYPTO-OPTIMIZED PARAMETERS V2
        if 'BTC' in symbol:
            # BTC - OPTIMIZED FOR WIN RATE & ROI
            self.zone_lookback_15m = 10  # More responsive zones
            self.zone_lookback_1h = 14
            self.zone_lookback_4h = 6
            self.cluster_distance = 80  # Tighter clustering = more zones
            
            self.zone_proximity_5m = 120  # Closer to zone = better entries
            self.breakout_lookback_5m = 8  # Faster breakout detection
            self.breakout_threshold = 40  # Lower threshold = more trades
            
            self.entry_zone_touch = 60
            self.max_sl_distance = 150  # Tighter SL = better R:R
            self.min_sl_distance = 50   # Minimum stop
            
            self.min_rr_ratio = 2.5  # Higher R:R = better quality
            self.max_trade_distance = 600  # Reasonable TP distance
            
        else:  # ETH - OPTIMIZED FOR MORE TRADES
            self.zone_lookback_15m = 8  # More zones
            self.zone_lookback_1h = 12
            self.zone_lookback_4h = 5
            self.cluster_distance = 10  # Tighter clustering
            
            self.zone_proximity_5m = 25  # Wider proximity = more setups
            self.breakout_lookback_5m = 8
            self.breakout_threshold = 6  # Lower threshold = more breakouts
            
            self.entry_zone_touch = 10
            self.max_sl_distance = 25  # Tighter SL
            self.min_sl_distance = 8
            
            self.min_rr_ratio = 2.5  # Higher quality
            self.max_trade_distance = 100  # Reasonable TP
        
        # Dynamic TP & Trailing - OPTIMIZED
        self.initial_tp_multiplier = 3.5  # More aggressive initial TP
        self.tp_extension_trigger_pct = 0.75  # Extend later = lock more profit
        self.tp_extension_distance = self.breakout_threshold * 2
        self.max_tp_extensions = 3  # Fewer extensions = take profit faster
        
        self.trail_activation_rr = 1.8  # Trail later = more profit
        self.trail_lock_pct = 0.7  # Lock more profit (70%)
        self.trail_step_pips = self.breakout_threshold * 0.5
        
        # Trade filtering - BALANCED
        self.min_5m_candles_between = 8  # Allow more trades
        self.max_trades_per_day = 15  # Increased daily limit
        
        # State
        self.zones = []
        self.poc_levels = []
        self.trades = []
        self.active_trade = None
        self.last_trade_5m_idx = -999
        self.trades_today = 0
        self.current_date = None
        
    def fetch_binance_data(self, interval='1m', days=90):
        """Fetch historical data from Binance"""
        print(f"\n📥 Fetching {days} days of {interval} data for {self.symbol}...")
        
        # Binance intervals: 1m, 5m, 15m, 1h, 4h
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        url = f"https://api.binance.com/api/v3/klines"
        
        all_data = []
        current_start = start_time
        
        while current_start < end_time:
            params = {
                'symbol': self.symbol,
                'interval': interval,
                'startTime': current_start,
                'endTime': end_time,
                'limit': 1000
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    break
                
                all_data.extend(data)
                current_start = data[-1][0] + 1
                
                print(f"   Fetched {len(all_data)} candles...", end='\r')
                time.sleep(0.1)
                
            except Exception as e:
                print(f"\n❌ Error fetching data: {e}")
                break
        
        print(f"\n✅ Fetched {len(all_data)} total candles")
        
        # Convert to DataFrame
        df = pd.DataFrame(all_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        return df
    
    def _cluster_zones(self, levels):
        """Cluster nearby levels"""
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
    
    def detect_zones(self, df_1m):
        """Detect support/resistance zones from multiple timeframes"""
        print("\n🔍 Detecting zones...")
        
        # Create higher timeframes
        df_1m_copy = df_1m.copy()
        df_1m_copy.set_index('timestamp', inplace=True)
        
        df_15m = df_1m_copy.resample('15min').agg({
            'open': 'first', 'high': 'max', 'low': 'min', 
            'close': 'last', 'volume': 'sum'
        }).dropna()
        
        df_1h = df_1m_copy.resample('1h').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna()
        
        df_4h = df_1m_copy.resample('4h').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna()
        
        df_1m_copy.reset_index(inplace=True)
        
        all_zones = []
        
        # 15m zones
        for i in range(self.zone_lookback_15m, len(df_15m)):
            window = df_15m.iloc[i-self.zone_lookback_15m:i]
            high_idx = window['high'].idxmax()
            low_idx = window['low'].idxmin()
            all_zones.extend([window.loc[high_idx, 'high'], window.loc[low_idx, 'low']])
        
        # 1h zones
        for i in range(self.zone_lookback_1h, len(df_1h)):
            window = df_1h.iloc[i-self.zone_lookback_1h:i]
            high_idx = window['high'].idxmax()
            low_idx = window['low'].idxmin()
            all_zones.extend([window.loc[high_idx, 'high'], window.loc[low_idx, 'low']])
        
        # 4h zones
        for i in range(self.zone_lookback_4h, len(df_4h)):
            window = df_4h.iloc[i-self.zone_lookback_4h:i]
            high_idx = window['high'].idxmax()
            low_idx = window['low'].idxmin()
            all_zones.extend([window.loc[high_idx, 'high'], window.loc[low_idx, 'low']])
        
        self.zones = self._cluster_zones(all_zones)
        print(f"✅ Detected {len(self.zones)} zones")
        
        # Calculate POC levels (volume profile)
        print("\n📊 Calculating POC levels...")
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
        
        # Find top POC levels
        top_indices = np.argsort(volume_profile)[-10:]
        poc_levels = [price_range[i] for i in top_indices]
        
        self.poc_levels = self._cluster_zones(poc_levels)
        print(f"✅ Found {len(self.poc_levels)} POC levels")
    
    def analyze_5m_setup(self, idx_5m, df_5m):
        """Analyze 5-minute chart for setup"""
        if idx_5m < self.breakout_lookback_5m + 5:
            return None, None, False
        
        current = df_5m.iloc[idx_5m]
        
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
        
        # Check 5-min structure break
        recent = df_5m.iloc[idx_5m - self.breakout_lookback_5m:idx_5m]
        recent_high = recent['high'].max()
        recent_low = recent['low'].min()
        
        # LONG: Break above
        if current['close'] > recent_high + self.breakout_threshold:
            return 'LONG', level, is_confluence
        
        # SHORT: Break below
        if current['close'] < recent_low - self.breakout_threshold:
            return 'SHORT', level, is_confluence
        
        return None, None, False
    
    def execute_1m_entry(self, idx_1m, df_1m, direction, zone_level):
        """Execute precise entry on 1-minute"""
        current = df_1m.iloc[idx_1m]
        entry = current['close']
        
        # SL: Tight stop based on direction
        if direction == 'LONG':
            recent_low = df_1m.iloc[max(0, idx_1m-5):idx_1m]['low'].min()
            sl_option1 = recent_low - self.min_sl_distance
            sl_option2 = zone_level - self.max_sl_distance
            sl = max(sl_option1, sl_option2)
            
            sl_dist = entry - sl
            if sl_dist > self.max_sl_distance:
                sl = entry - self.max_sl_distance
            elif sl_dist < self.min_sl_distance:
                sl = entry - self.min_sl_distance
        
        else:  # SHORT
            recent_high = df_1m.iloc[max(0, idx_1m-5):idx_1m]['high'].max()
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
    
    def _enter_trade(self, candle, direction, entry, sl, tp, level, is_confluence, idx_1m, idx_5m):
        """Enter new trade"""
        risk_usd = self.account_size * (self.risk_pct / 100)
        sl_distance = abs(entry - sl)
        position_size = risk_usd / sl_distance
        
        self.active_trade = {
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'tp_original': tp,
            'position_size': position_size,
            'entry_time': candle['timestamp'],
            'entry_idx': idx_1m,
            'zone': level,
            'is_confluence': is_confluence,
            'tp_extensions': 0,
            'trailing_active': False,
            'highest_profit': 0
        }
        
        print(f"\n{'🟢 LONG' if direction == 'LONG' else '🔴 SHORT'} @ ${entry:,.2f} | SL: ${sl:,.2f} | TP: ${tp:,.2f} | Size: {position_size:.4f}")
    
    def _manage_trade(self, candle, idx_1m):
        """Manage active trade"""
        if not self.active_trade:
            return
        
        trade = self.active_trade
        current_price = candle['close']
        
        # Check SL
        if trade['direction'] == 'LONG':
            if current_price <= trade['sl']:
                self._close_trade(trade, trade['sl'], idx_1m, 'SL')
                return
        else:
            if current_price >= trade['sl']:
                self._close_trade(trade, trade['sl'], idx_1m, 'SL')
                return
        
        # Check TP
        if trade['direction'] == 'LONG':
            if current_price >= trade['tp']:
                self._close_trade(trade, trade['tp'], idx_1m, 'TP')
                return
        else:
            if current_price <= trade['tp']:
                self._close_trade(trade, trade['tp'], idx_1m, 'TP')
                return
        
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
        
        # Trailing SL
        risk = abs(trade['entry'] - trade['sl'])
        if trade['direction'] == 'LONG':
            profit = current_price - trade['entry']
        else:
            profit = trade['entry'] - current_price
        
        if profit / risk >= self.trail_activation_rr:
            if not trade['trailing_active']:
                trade['trailing_active'] = True
            
            locked_profit = profit * self.trail_lock_pct
            if trade['direction'] == 'LONG':
                new_sl = trade['entry'] + locked_profit
                if new_sl > trade['sl']:
                    trade['sl'] = new_sl
            else:
                new_sl = trade['entry'] - locked_profit
                if new_sl < trade['sl']:
                    trade['sl'] = new_sl
    
    def _close_trade(self, trade, exit_price, idx_1m, reason):
        """Close active trade"""
        if trade['direction'] == 'LONG':
            pnl = (exit_price - trade['entry']) * trade['position_size']
        else:
            pnl = (trade['entry'] - exit_price) * trade['position_size']
        
        self.balance += pnl
        
        self.trades.append({
            'entry_time': trade['entry_time'],
            'direction': trade['direction'],
            'entry': trade['entry'],
            'exit': exit_price,
            'sl': trade['sl'],
            'tp': trade['tp_original'],
            'pnl': pnl,
            'reason': reason,
            'zone': trade['zone'],
            'confluence': trade['is_confluence']
        })
        
        print(f"   ✅ Closed @ ${exit_price:,.2f} | PnL: ${pnl:+,.2f} | Reason: {reason}")
        self.active_trade = None
    
    def backtest(self, df_1m):
        """Run backtest"""
        print(f"\n🚀 Starting backtest for {self.symbol}...")
        
        # Detect zones
        self.detect_zones(df_1m)
        
        # Create 5-min dataframe
        df_1m_copy = df_1m.copy()
        df_1m_copy.set_index('timestamp', inplace=True)
        
        df_5m = df_1m_copy.resample('5min').agg({
            'open': 'first', 'high': 'max', 'low': 'min',
            'close': 'last', 'volume': 'sum'
        }).dropna()
        
        df_1m_copy.reset_index(inplace=True)
        
        # Map 1m to 5m indices
        df_1m_copy['5m_idx'] = -1
        for i in range(len(df_5m)):
            time_5m = df_5m.index[i]
            mask = (df_1m_copy['timestamp'] >= time_5m) & (df_1m_copy['timestamp'] < time_5m + pd.Timedelta(minutes=5))
            df_1m_copy.loc[mask, '5m_idx'] = i
        
        # Backtest loop
        for i in range(100, len(df_1m_copy)):
            candle_1m = df_1m_copy.iloc[i]
            idx_5m = int(candle_1m['5m_idx'])
            
            if idx_5m < 0:
                continue
            
            # Reset daily trade count
            current_date = candle_1m['timestamp'].date()
            if current_date != self.current_date:
                self.current_date = current_date
                self.trades_today = 0
                print(f"\n📅 {current_date} | Balance: ${self.balance:,.2f}")
            
            # Manage active trade
            if self.active_trade:
                self._manage_trade(candle_1m, i)
            
            if self.active_trade:
                continue
            
            # Check trade spacing
            if idx_5m - self.last_trade_5m_idx < self.min_5m_candles_between:
                continue
            
            # Check daily limit
            if self.trades_today >= self.max_trades_per_day:
                continue
            
            # Analyze 5-min setup
            direction, zone_level, is_confluence = self.analyze_5m_setup(idx_5m, df_5m)
            
            if not direction:
                continue
            
            # Execute on 1-min
            entry, sl, tp = self.execute_1m_entry(i, df_1m_copy, direction, zone_level)
            
            if entry is None:
                continue
            
            # Enter trade
            self._enter_trade(candle_1m, direction, entry, sl, tp, zone_level, is_confluence, i, idx_5m)
            self.last_trade_5m_idx = idx_5m
            self.trades_today += 1
        
        # Close remaining
        if self.active_trade:
            self._close_trade(self.active_trade, df_1m_copy.iloc[-1]['close'], len(df_1m_copy)-1, 'EOD')
        
        return self._calculate_metrics()
    
    def _calculate_metrics(self):
        """Calculate backtest metrics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'total_pnl': 0,
                'roi': 0
            }
        
        df_trades = pd.DataFrame(self.trades)
        
        wins = df_trades[df_trades['pnl'] > 0]
        losses = df_trades[df_trades['pnl'] <= 0]
        
        total_trades = len(df_trades)
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        roi = (total_pnl / self.account_size) * 100
        
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        
        # Max drawdown
        cumulative = (df_trades['pnl'].cumsum() + self.account_size)
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        return {
            'symbol': self.symbol,
            'total_trades': total_trades,
            'wins': win_count,
            'losses': loss_count,
            'win_rate': win_rate,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'profit_factor': profit_factor,
            'total_pnl': total_pnl,
            'roi': roi,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'max_drawdown': max_drawdown,
            'final_balance': self.balance
        }


if __name__ == "__main__":
    print("="*80)
    print("CRYPTO SNIPER BACKTEST - BTC & ETH")
    print("="*80)
    
    results = []
    
    for symbol in ['BTCUSDT', 'ETHUSDT']:
        print(f"\n\n{'='*80}")
        print(f"Testing {symbol}")
        print('='*80)
        
        bot = CryptoSniperBacktest(symbol=symbol, account_size=10000, risk_pct=2.0)
        
        # Fetch 3 months data
        df_1m = bot.fetch_binance_data(interval='1m', days=90)
        
        if df_1m is not None and len(df_1m) > 0:
            metrics = bot.backtest(df_1m)
            results.append(metrics)
    
    # Print summary
    print("\n\n" + "="*80)
    print("BACKTEST SUMMARY")
    print("="*80)
    
    for metrics in results:
        print(f"\n{metrics['symbol']}:")
        print(f"  Total Trades: {metrics['total_trades']}")
        print(f"  Win Rate: {metrics['win_rate']:.1f}%")
        print(f"  Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"  Total P&L: ${metrics['total_pnl']:+,.2f}")
        print(f"  ROI: {metrics['roi']:+.2f}%")
        print(f"  Max Drawdown: {metrics['max_drawdown']:.2f}%")
        print(f"  Final Balance: ${metrics['final_balance']:,.2f}")
    
    # Save results
    with open('scripts/crypto_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n✅ Results saved to crypto_backtest_results.json")
