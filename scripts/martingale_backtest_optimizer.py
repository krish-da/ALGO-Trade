#!/usr/bin/env python3
"""
MARTINGALE STRATEGY BACKTEST & OPTIMIZER
========================================
Test different parameters to find optimal 1000%+ ROI configuration
WITHOUT breaking Funding Pips rules

Goal: Find configuration that achieves 1000%+ in 30 days consistently
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from itertools import product

class MartingaleBacktest:
    def __init__(self, account_size=100000, 
                 base_position=100,
                 multiplier=2.0,
                 max_steps=5,
                 sl_pips=10,
                 tp_pips=10,
                 win_rate=0.60):
        
        self.account_size = account_size
        self.balance = account_size
        self.start_balance = account_size
        self.peak_balance = account_size
        self.daily_start_balance = account_size
        
        # Martingale parameters
        self.base_position = base_position
        self.multiplier = multiplier
        self.max_steps = max_steps
        self.sl_pips = sl_pips
        self.tp_pips = tp_pips
        self.win_rate = win_rate
        
        # Position sizes
        self.position_sizes = [
            base_position * (multiplier ** i) 
            for i in range(max_steps)
        ]
        
        # Funding Pips limits
        self.daily_loss_limit = 5000
        self.max_drawdown_limit = 10000
        self.daily_stop_loss = 4000  # Safety buffer
        
        # State
        self.current_step = 0
        self.sequences_today = 0
        self.daily_pnl = 0
        self.trades = []
        self.breached = False
        self.breach_reason = None
        
    def simulate_trade(self):
        """Simulate a single trade based on win rate"""
        # Simulate win/loss based on win rate
        is_win = np.random.random() < self.win_rate
        
        # Get position size for current step
        if self.current_step >= len(self.position_sizes):
            # Max sequence reached, reset
            self.current_step = 0
            self.sequences_today += 1
            return None
        
        risk = self.position_sizes[self.current_step]
        
        if is_win:
            # Win: Profit = risk (1:1 R:R)
            pnl = risk
            self.balance += pnl
            self.daily_pnl += pnl
            
            # Reset sequence
            self.current_step = 0
            self.sequences_today += 1
        else:
            # Loss: Lose = risk
            pnl = -risk
            self.balance += pnl
            self.daily_pnl += pnl
            
            # Move to next step
            self.current_step += 1
        
        # Update peak
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        
        # Record trade
        trade = {
            'pnl': pnl,
            'balance': self.balance,
            'step': self.current_step if not is_win else 0,
            'risk': risk,
            'result': 'WIN' if is_win else 'LOSS'
        }
        self.trades.append(trade)
        
        return trade
    
    def check_breach(self):
        """Check if Funding Pips rules breached"""
        # Daily loss limit
        if self.daily_pnl <= -self.daily_loss_limit:
            self.breached = True
            self.breach_reason = f"Daily loss limit: ${self.daily_pnl:.2f}"
            return True
        
        # Max drawdown
        drawdown = self.peak_balance - self.balance
        if drawdown >= self.max_drawdown_limit:
            self.breached = True
            self.breach_reason = f"Max drawdown: ${drawdown:.2f}"
            return True
        
        return False
    
    def simulate_day(self, max_sequences=20):
        """Simulate one trading day"""
        self.daily_start_balance = self.balance
        self.daily_pnl = 0
        self.sequences_today = 0
        
        while self.sequences_today < max_sequences:
            if self.check_breach():
                break
            
            # Stop if approaching daily limit
            if self.daily_pnl <= -self.daily_stop_loss:
                break
            
            trade = self.simulate_trade()
            if trade is None:
                continue
        
        return self.daily_pnl
    
    def simulate_tournament(self, days=30, max_sequences_per_day=20):
        """Simulate 30-day tournament"""
        print(f"\n{'='*70}")
        print(f"SIMULATING TOURNAMENT")
        print(f"{'='*70}")
        print(f"Starting Balance: ${self.start_balance:,.0f}")
        print(f"Base Position: ${self.base_position}")
        print(f"Multiplier: {self.multiplier}x")
        print(f"Max Steps: {self.max_steps}")
        print(f"Win Rate: {self.win_rate*100:.1f}%")
        print(f"Position Sizes: {[f'${p:.0f}' for p in self.position_sizes]}")
        print(f"{'='*70}\n")
        
        daily_results = []
        
        for day in range(1, days + 1):
            day_pnl = self.simulate_day(max_sequences_per_day)
            
            roi = ((self.balance - self.start_balance) / self.start_balance) * 100
            daily_results.append({
                'day': day,
                'balance': self.balance,
                'daily_pnl': day_pnl,
                'roi': roi,
                'sequences': self.sequences_today
            })
            
            if day % 5 == 0 or self.breached:
                print(f"Day {day:2d}: Balance: ${self.balance:>10,.0f} | Daily P&L: ${day_pnl:>8,.0f} | ROI: {roi:>7.2f}% | Seq: {self.sequences_today}")
            
            if self.breached:
                print(f"\n❌ BREACHED on Day {day}: {self.breach_reason}")
                break
        
        # Results
        final_roi = ((self.balance - self.start_balance) / self.start_balance) * 100
        wins = len([t for t in self.trades if t['pnl'] > 0])
        losses = len([t for t in self.trades if t['pnl'] < 0])
        actual_win_rate = wins / len(self.trades) * 100 if self.trades else 0
        
        max_daily_loss = min([d['daily_pnl'] for d in daily_results])
        max_drawdown = self.peak_balance - min([d['balance'] for d in daily_results])
        
        print(f"\n{'='*70}")
        print(f"FINAL RESULTS")
        print(f"{'='*70}")
        print(f"Final Balance: ${self.balance:,.0f}")
        print(f"Profit: ${self.balance - self.start_balance:+,.0f}")
        print(f"ROI: {final_roi:+.2f}%")
        print(f"")
        print(f"Trades: {len(self.trades)} ({wins}W / {losses}L)")
        print(f"Win Rate: {actual_win_rate:.1f}%")
        print(f"Sequences: {sum([d['sequences'] for d in daily_results])}")
        print(f"")
        print(f"Max Daily Loss: ${max_daily_loss:,.0f}")
        print(f"Max Drawdown: ${max_drawdown:,.0f}")
        print(f"")
        print(f"Status: {'✅ PASSED' if not self.breached else '❌ BREACHED'}")
        if self.breached:
            print(f"Reason: {self.breach_reason}")
        print(f"{'='*70}\n")
        
        return {
            'final_balance': self.balance,
            'roi': final_roi,
            'total_trades': len(self.trades),
            'wins': wins,
            'losses': losses,
            'win_rate': actual_win_rate,
            'max_daily_loss': max_daily_loss,
            'max_drawdown': max_drawdown,
            'breached': self.breached,
            'breach_reason': self.breach_reason,
            'daily_results': daily_results
        }


def run_optimization():
    """Test multiple parameter combinations to find optimal 1000%+ ROI"""
    print("\n" + "="*80)
    print("MARTINGALE PARAMETER OPTIMIZATION")
    print("Target: 1000%+ ROI without breach")
    print("="*80)
    
    # Parameters to test
    base_positions = [50, 100, 150, 200, 250, 300]
    win_rates = [0.55, 0.60, 0.65, 0.70]
    max_steps_options = [4, 5, 6]
    max_sequences = [15, 20, 25, 30]
    
    results = []
    best_roi = -100
    best_config = None
    
    total_tests = len(base_positions) * len(win_rates) * len(max_steps_options) * len(max_sequences)
    test_num = 0
    
    print(f"\nTesting {total_tests} configurations...")
    print(f"This will take a few minutes...\n")
    
    for base_pos, win_rate, max_steps, max_seq in product(base_positions, win_rates, max_steps_options, max_sequences):
        test_num += 1
        
        # Run 5 simulations and average (Monte Carlo)
        rois = []
        breaches = 0
        
        for sim in range(5):
            np.random.seed(42 + sim + test_num)  # Reproducible but varied
            
            bt = MartingaleBacktest(
                account_size=100000,
                base_position=base_pos,
                multiplier=2.0,
                max_steps=max_steps,
                win_rate=win_rate
            )
            
            result = bt.simulate_tournament(days=30, max_sequences_per_day=max_seq)
            rois.append(result['roi'])
            if result['breached']:
                breaches += 1
        
        avg_roi = np.mean(rois)
        breach_rate = breaches / 5
        
        config = {
            'base_position': base_pos,
            'win_rate': win_rate,
            'max_steps': max_steps,
            'max_sequences': max_seq,
            'avg_roi': avg_roi,
            'roi_std': np.std(rois),
            'breach_rate': breach_rate
        }
        
        results.append(config)
        
        # Update best if ROI > 1000% and no breaches
        if avg_roi >= 1000 and breach_rate == 0 and avg_roi > best_roi:
            best_roi = avg_roi
            best_config = config
        
        # Progress
        if test_num % 10 == 0:
            print(f"Progress: {test_num}/{total_tests} tests completed...")
    
    # Sort by ROI
    results.sort(key=lambda x: x['avg_roi'], reverse=True)
    
    # Display top 10 configurations
    print(f"\n{'='*80}")
    print(f"TOP 10 CONFIGURATIONS (by ROI)")
    print(f"{'='*80}")
    print(f"{'Rank':<5} {'Base':<6} {'Win%':<6} {'Steps':<6} {'Seq/D':<6} {'ROI%':<10} {'Breach%':<10}")
    print(f"{'-'*80}")
    
    for i, config in enumerate(results[:10], 1):
        print(f"{i:<5} ${config['base_position']:<5.0f} {config['win_rate']*100:<6.1f} {config['max_steps']:<6} {config['max_sequences']:<6} {config['avg_roi']:<10.1f} {config['breach_rate']*100:<10.1f}")
    
    # Best 1000%+ config
    if best_config:
        print(f"\n{'='*80}")
        print(f"🏆 BEST 1000%+ ROI CONFIGURATION (No Breaches)")
        print(f"{'='*80}")
        print(f"Base Position: ${best_config['base_position']}")
        print(f"Win Rate: {best_config['win_rate']*100:.1f}%")
        print(f"Max Steps: {best_config['max_steps']}")
        print(f"Max Sequences/Day: {best_config['max_sequences']}")
        print(f"Average ROI: {best_config['avg_roi']:.2f}%")
        print(f"ROI Std Dev: {best_config['roi_std']:.2f}%")
        print(f"Breach Rate: {best_config['breach_rate']*100:.1f}%")
        print(f"{'='*80}\n")
        
        # Run detailed simulation with best config
        print("\n🔬 DETAILED SIMULATION WITH BEST CONFIG:\n")
        np.random.seed(42)
        bt_best = MartingaleBacktest(
            account_size=100000,
            base_position=best_config['base_position'],
            multiplier=2.0,
            max_steps=best_config['max_steps'],
            win_rate=best_config['win_rate']
        )
        final_result = bt_best.simulate_tournament(days=30, max_sequences_per_day=best_config['max_sequences'])
    else:
        print(f"\n⚠️  No configuration achieved 1000%+ ROI without breaches!")
        print(f"Best achieved: {results[0]['avg_roi']:.2f}% (Breach rate: {results[0]['breach_rate']*100:.1f}%)")
    
    # Save all results
    with open('martingale_optimization_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Full results saved to martingale_optimization_results.json")
    
    return best_config


if __name__ == "__main__":
    # Run optimization
    best = run_optimization()
    
    if best:
        print(f"\n✅ READY TO DEPLOY!")
        print(f"Update martingale_gold_tournament.py with these parameters:")
        print(f"   base_position_usd = {best['base_position']}")
        print(f"   max_sequence_steps = {best['max_steps']}")
        print(f"   max_sequences_per_day = {best['max_sequences']}")
        print(f"   Target win rate: {best['win_rate']*100:.1f}%\n")
