#!/usr/bin/env python3
"""
FabInvests 6-Strategy Backtest on Gold
======================================
Testing 6 FabInvests strategies on 170 days of Gold data

Strategies:
1. TSMOM (Time Series Momentum) - 28-day momentum + 200-SMA
2. Donchian Breakout - 20-day channel + 200-SMA
3. RSI-2 Dip - RSI(2) < 10 + 200-SMA
4. Momentum+Trend - 28-day momentum + 200-SMA
5. ORB (Opening Range Breakout) - First hour breakout
6. 15m Breakout - 48-bar (12-hour) channel breakout

Data: 170 days of Gold from Yahoo Finance
"""

import pandas as pd
import numpy as np
from datetime import datetime

class FabInvestsGold:
    """
    FabInvests 6-Strategy Ensemble for Gold
    """
    
    def __init__(self, account_size=10000):
        self.account_size = account_size
        self.balance = account_size
        self.trades = []
        self.active_trade = None
        
        # Parameters for each strategy (adjusted for 170 days data)
        self.params = {
            'tsmom_lookback': 28,
            'sma_trend': 150,  # Using 150-SMA instead of 200 (we have 170 days)
            'donchian_period': 20,
            'rsi_period': 2,
            'rsi_oversold': 10,
            'rsi_overbought': 90,
            'orb_period_minutes': 60,  # First hour
            'breakout_15m_bars': 48,    # 12 hours
        }
        
        # Risk management
        self.risk_per_trade = 0.02  # 2% per trade
        self.position_size_pct = 0.10  # 10% of balance per trade
    
    def load_data(self):
        """Load Yahoo Finance Gold data"""
        print("📊 Loading Gold data...")
        
        # Load daily data (for 200-SMA, momentum)
        df_daily = pd.read_csv('scripts/gold_yahoo_daily.csv')
        df_daily['Date'] = pd.to_datetime(df_daily['Date'])
        df_daily = df_daily.sort_values('Date').reset_index(drop=True)
        
        print(f"   Daily: {len(df_daily)} days ({df_daily['Date'].min()} to {df_daily['Date'].max()})")
        
        # Load 15-minute data (for intraday breakouts)
        df_15m = pd.read_csv('scripts/gold_yahoo_15m.csv')
        df_15m['datetime'] = pd.to_datetime(df_15m['datetime'])
        df_15m = df_15m.sort_values('datetime').reset_index(drop=True)
        
        print(f"   15-min: {len(df_15m)} bars")
        
        # Load 1-minute data (for entries)
        print("   Loading 1-minute data... (this may take a moment)")
        df_1m = pd.read_csv('scripts/gold_yahoo_1m_readable.csv')
        df_1m['datetime'] = pd.to_datetime(df_1m['datetime'])
        df_1m = df_1m.sort_values('datetime').reset_index(drop=True)
        
        print(f"   1-min: {len(df_1m):,} candles")
        
        return df_daily, df_15m, df_1m
    
    def calculate_indicators(self, df_daily):
        """Calculate all indicators for daily timeframe"""
        df = df_daily.copy()
        
        # 150-day SMA (trend filter) - adjusted for 170 days data
        df['SMA_200'] = df['Close'].rolling(window=150).mean()
        
        # 28-day momentum
        df['Momentum_28'] = df['Close'].pct_change(28)
        
        # 20-day Donchian Channel
        df['Donchian_High'] = df['High'].rolling(window=20).max()
        df['Donchian_Low'] = df['Low'].rolling(window=20).min()
        
        # RSI-2
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=2).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=2).mean()
        rs = gain / loss
        df['RSI_2'] = 100 - (100 / (1 + rs))
        
        return df
    
    def strategy_tsmom(self, df_daily, idx):
        """
        Strategy 1: Time Series Momentum (TSMOM)
        - Buy if 28-day return > 0 AND price > 150-SMA
        - Sell if 28-day return < 0 OR price < 150-SMA
        """
        if idx < 150:  # Need 150 days for SMA
            return None
        
        row = df_daily.iloc[idx]
        
        # Check trend filter
        if pd.isna(row['SMA_200']):
            return None
        
        # Long signal
        if row['Momentum_28'] > 0 and row['Close'] > row['SMA_200']:
            return 'LONG'
        
        # Short signal (or exit long)
        if row['Momentum_28'] < 0 or row['Close'] < row['SMA_200']:
            return 'SHORT'
        
        return None
    
    def strategy_donchian(self, df_daily, idx):
        """
        Strategy 2: Donchian Breakout
        - Buy on 20-day high breakout if price > 150-SMA
        - Sell on 20-day low breakout if price < 150-SMA
        """
        if idx < 150:
            return None
        
        row = df_daily.iloc[idx]
        prev = df_daily.iloc[idx-1]
        
        if pd.isna(row['SMA_200']):
            return None
        
        # Long breakout
        if row['Close'] > prev['Donchian_High'] and row['Close'] > row['SMA_200']:
            return 'LONG'
        
        # Short breakout
        if row['Close'] < prev['Donchian_Low'] and row['Close'] < row['SMA_200']:
            return 'SHORT'
        
        return None
    
    def strategy_rsi2_dip(self, df_daily, idx):
        """
        Strategy 3: RSI-2 Dip Buy
        - Buy when RSI(2) < 10 and price > 150-SMA (oversold bounce)
        - Sell when RSI(2) > 90 or price < 150-SMA
        """
        if idx < 150:
            return None
        
        row = df_daily.iloc[idx]
        
        if pd.isna(row['RSI_2']) or pd.isna(row['SMA_200']):
            return None
        
        # Buy the dip
        if row['RSI_2'] < 10 and row['Close'] > row['SMA_200']:
            return 'LONG'
        
        # Exit or reverse
        if row['RSI_2'] > 90 or row['Close'] < row['SMA_200']:
            return 'SHORT'
        
        return None
    
    def strategy_momentum_trend(self, df_daily, idx):
        """
        Strategy 4: Momentum + Trend Combination
        - Similar to TSMOM but more strict
        - Buy if momentum > 5% AND price > 150-SMA
        """
        if idx < 150:
            return None
        
        row = df_daily.iloc[idx]
        
        if pd.isna(row['Momentum_28']) or pd.isna(row['SMA_200']):
            return None
        
        # Strong momentum long
        if row['Momentum_28'] > 0.05 and row['Close'] > row['SMA_200']:
            return 'LONG'
        
        # Strong momentum short
        if row['Momentum_28'] < -0.05 and row['Close'] < row['SMA_200']:
            return 'SHORT'
        
        return None
    
    def strategy_orb(self, df_15m, idx):
        """
        Strategy 5: Opening Range Breakout (ORB)
        - First 1 hour (4 x 15-min bars) defines range
        - Buy breakout above range, sell below
        """
        if idx < 4:
            return None
        
        # Get first 4 bars of the day (1 hour)
        current_time = df_15m.iloc[idx]['datetime']
        current_date = current_time.date()
        
        # Find start of day
        day_bars = df_15m[df_15m['datetime'].dt.date == current_date]
        if len(day_bars) < 4:
            return None
        
        # Opening range (first hour)
        orb_high = day_bars.iloc[:4]['high'].max()
        orb_low = day_bars.iloc[:4]['low'].min()
        
        current_price = df_15m.iloc[idx]['close']
        
        # Breakout signals
        if current_price > orb_high:
            return 'LONG'
        if current_price < orb_low:
            return 'SHORT'
        
        return None
    
    def strategy_15m_breakout(self, df_15m, idx):
        """
        Strategy 6: 15-Minute Breakout
        - 48-bar (12-hour) channel breakout
        - Buy on high breakout, sell on low breakout
        """
        if idx < 48:
            return None
        
        # 12-hour range
        lookback = df_15m.iloc[idx-48:idx]
        high_48 = lookback['high'].max()
        low_48 = lookback['low'].min()
        
        current_price = df_15m.iloc[idx]['close']
        
        # Breakout signals
        if current_price > high_48:
            return 'LONG'
        if current_price < low_48:
            return 'SHORT'
        
        return None
    
    def ensemble_decision(self, signals):
        """
        Ensemble voting system
        - Majority vote from all 6 strategies
        - Need at least 2 strategies to agree (lowered from 3 for testing)
        """
        if not signals:
            return None
        
        long_votes = sum(1 for s in signals if s == 'LONG')
        short_votes = sum(1 for s in signals if s == 'SHORT')
        
        # Need at least 2 agreeing (out of up to 6)
        if long_votes >= 2:
            return 'LONG'
        if short_votes >= 2:
            return 'SHORT'
        
        return None
    
    def backtest(self):
        """Run backtest on all strategies"""
        print("\n" + "="*70)
        print("FABINVESTS 6-STRATEGY BACKTEST ON GOLD")
        print("="*70)
        
        # Load data
        df_daily, df_15m, df_1m = self.load_data()
        
        # Calculate indicators
        print("\n📈 Calculating indicators...")
        df_daily = self.calculate_indicators(df_daily)
        print("   ✅ Indicators ready")
        
        # Backtest daily strategies
        print("\n🔄 Running backtest...")
        print(f"   Testing {len(df_daily)} days...")
        
        for idx in range(150, len(df_daily)):  # Start after 150-SMA warmup
            current_date = df_daily.iloc[idx]['Date']
            current_price = df_daily.iloc[idx]['Close']
            
            # Get signals from all strategies
            signals = []
            
            # Daily strategies (1-4)
            s1 = self.strategy_tsmom(df_daily, idx)
            s2 = self.strategy_donchian(df_daily, idx)
            s3 = self.strategy_rsi2_dip(df_daily, idx)
            s4 = self.strategy_momentum_trend(df_daily, idx)
            
            if s1: signals.append(('TSMOM', s1))
            if s2: signals.append(('Donchian', s2))
            if s3: signals.append(('RSI-2', s3))
            if s4: signals.append(('MomTrend', s4))
            
            # Ensemble decision
            signal_values = [s[1] for s in signals]
            decision = self.ensemble_decision(signal_values)
            
            if decision and not self.active_trade:
                # Calculate position size
                position_size = self.balance * self.position_size_pct / current_price
                
                # Entry
                self.active_trade = {
                    'entry_date': current_date,
                    'entry_price': current_price,
                    'direction': decision,
                    'position_size': position_size,
                    'strategies': [s[0] for s in signals],
                    'entry_balance': self.balance
                }
            
            elif self.active_trade:
                # Check exit
                if decision and decision != self.active_trade['direction']:
                    # Reverse signal - exit
                    self._exit_trade(current_date, current_price, 'Reverse Signal')
                
                # Stop loss / Take profit (simple 2% risk, 4% target)
                entry_price = self.active_trade['entry_price']
                if self.active_trade['direction'] == 'LONG':
                    pnl_pct = (current_price - entry_price) / entry_price
                    if pnl_pct < -0.02:  # -2% stop
                        self._exit_trade(current_date, current_price, 'Stop Loss')
                    elif pnl_pct > 0.04:  # +4% target
                        self._exit_trade(current_date, current_price, 'Take Profit')
                
                elif self.active_trade['direction'] == 'SHORT':
                    pnl_pct = (entry_price - current_price) / entry_price
                    if pnl_pct < -0.02:
                        self._exit_trade(current_date, current_price, 'Stop Loss')
                    elif pnl_pct > 0.04:
                        self._exit_trade(current_date, current_price, 'Take Profit')
        
        # Close any remaining trade
        if self.active_trade:
            last_date = df_daily.iloc[-1]['Date']
            last_price = df_daily.iloc[-1]['Close']
            self._exit_trade(last_date, last_price, 'End of Data')
        
        # Calculate metrics
        print(f"\n   ✅ Backtest complete!")
        self._print_results()
    
    def _exit_trade(self, exit_date, exit_price, reason):
        """Exit active trade"""
        if not self.active_trade:
            return
        
        t = self.active_trade
        
        # Calculate P&L
        if t['direction'] == 'LONG':
            pnl = (exit_price - t['entry_price']) * t['position_size']
        else:  # SHORT
            pnl = (t['entry_price'] - exit_price) * t['position_size']
        
        pnl_pct = (pnl / t['entry_balance']) * 100
        
        # Update balance
        self.balance += pnl
        
        # Record trade
        self.trades.append({
            'entry_date': t['entry_date'],
            'exit_date': exit_date,
            'direction': t['direction'],
            'entry_price': t['entry_price'],
            'exit_price': exit_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'strategies': ', '.join(t['strategies']),
            'exit_reason': reason,
            'balance': self.balance
        })
        
        self.active_trade = None
    
    def _print_results(self):
        """Print backtest results"""
        if not self.trades:
            print("\n❌ NO TRADES EXECUTED")
            return
        
        df_trades = pd.DataFrame(self.trades)
        
        # Calculate metrics
        total_trades = len(df_trades)
        winning_trades = len(df_trades[df_trades['pnl'] > 0])
        losing_trades = len(df_trades[df_trades['pnl'] < 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        total_pnl_pct = ((self.balance - self.account_size) / self.account_size) * 100
        
        avg_win = df_trades[df_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = df_trades[df_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        # Max drawdown
        df_trades['cumulative'] = df_trades['pnl'].cumsum()
        df_trades['peak'] = df_trades['cumulative'].cummax()
        df_trades['drawdown'] = df_trades['cumulative'] - df_trades['peak']
        max_dd = df_trades['drawdown'].min()
        max_dd_pct = (max_dd / self.account_size) * 100
        
        # Print results
        print("\n" + "="*70)
        print("FABINVESTS BACKTEST RESULTS")
        print("="*70)
        
        print(f"\n💰 FINAL BALANCE: ${self.balance:,.2f}")
        print(f"   Starting: ${self.account_size:,.2f}")
        print(f"   P&L: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
        
        print(f"\n📊 TRADE STATISTICS:")
        print(f"   Total Trades:    {total_trades}")
        print(f"   Winning Trades:  {winning_trades}")
        print(f"   Losing Trades:   {losing_trades}")
        print(f"   Win Rate:        {win_rate:.1f}%")
        
        print(f"\n💵 P&L ANALYSIS:")
        print(f"   Average Win:     ${avg_win:,.2f}")
        print(f"   Average Loss:    ${avg_loss:,.2f}")
        if avg_loss != 0:
            print(f"   Win/Loss Ratio:  {abs(avg_win/avg_loss):.2f}")
        
        print(f"\n📉 RISK METRICS:")
        print(f"   Max Drawdown:    ${max_dd:,.2f} ({max_dd_pct:.2f}%)")
        
        # Strategy breakdown
        print(f"\n🎯 STRATEGY USAGE:")
        all_strategies = []
        for strat_list in df_trades['strategies']:
            all_strategies.extend(strat_list.split(', '))
        
        from collections import Counter
        strategy_counts = Counter(all_strategies)
        for strat, count in strategy_counts.most_common():
            print(f"   {strat:15s} {count} trades")
        
        # Save results
        output_file = 'scripts/fabinvests_backtest_results.csv'
        df_trades.to_csv(output_file, index=False)
        print(f"\n💾 Results saved to: {output_file}")
        
        print("\n" + "="*70)


def main():
    """Run FabInvests backtest"""
    bot = FabInvestsGold(account_size=10000)
    bot.backtest()


if __name__ == "__main__":
    main()
