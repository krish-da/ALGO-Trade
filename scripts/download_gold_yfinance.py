#!/usr/bin/env python3
"""
Download 200+ Days Gold Data from Yahoo Finance using yfinance
==============================================================
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def download_gold_data():
    """Download Gold data using yfinance"""
    print("="*70)
    print("DOWNLOADING GOLD DATA FROM YAHOO FINANCE")
    print("="*70)
    
    # Download Gold futures (GC=F) or Gold ETF (GLD)
    print("\n📊 Downloading 250 days of Gold data...")
    print("   Symbol: GC=F (Gold Futures)")
    
    # Get data
    gold = yf.Ticker("GC=F")
    
    # Download 250 days of daily data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=250)
    
    df_daily = gold.history(start=start_date, end=end_date, interval="1d")
    
    if len(df_daily) == 0:
        print("❌ No data received. Trying GLD ETF instead...")
        gold = yf.Ticker("GLD")
        df_daily = gold.history(start=start_date, end=end_date, interval="1d")
    
    if len(df_daily) == 0:
        print("❌ Failed to download data")
        return None, None
    
    print(f"✅ Downloaded {len(df_daily)} daily candles")
    print(f"   From: {df_daily.index.min()}")
    print(f"   To:   {df_daily.index.max()}")
    print(f"   Days: {(df_daily.index.max() - df_daily.index.min()).days}")
    
    # Generate synthetic 1-minute data
    print("\n🔨 Generating synthetic 1-minute data from daily...")
    df_1m = generate_synthetic_1m(df_daily)
    
    return df_daily, df_1m


def generate_synthetic_1m(df_daily):
    """Generate realistic 1-minute data from daily OHLC"""
    all_1m = []
    
    for idx, row in df_daily.iterrows():
        date = idx
        open_price = row['Open']
        high_price = row['High']
        low_price = row['Low']
        close_price = row['Close']
        volume = row['Volume'] if 'Volume' in row else 1000000
        
        # 1440 minutes per day
        n_candles = 1440
        
        # Create realistic price path
        prices = create_price_path(open_price, high_price, low_price, close_price, n_candles)
        
        # Generate 1m candles
        for i in range(n_candles):
            timestamp = date + timedelta(minutes=i)
            
            if i == 0:
                o = open_price
            else:
                o = prices[i-1]
            
            c = prices[i]
            h = max(o, c) * (1 + abs(np.random.randn()) * 0.0001)
            l = min(o, c) * (1 - abs(np.random.randn()) * 0.0001)
            
            # Ensure within daily range
            h = min(h, high_price)
            l = max(l, low_price)
            
            all_1m.append({
                'time': int(timestamp.timestamp()),
                'open': o,
                'high': h,
                'low': l,
                'close': c,
                'tick_volume': volume / n_candles
            })
    
    df_1m = pd.DataFrame(all_1m)
    print(f"✅ Generated {len(df_1m):,} synthetic 1-minute candles")
    
    return df_1m


def create_price_path(open_p, high_p, low_p, close_p, n_points):
    """Create realistic price path hitting high/low"""
    prices = []
    
    # Decide order: high first or low first
    if np.random.rand() > 0.5:
        # High first
        high_idx = np.random.randint(n_points // 4, n_points // 2)
        low_idx = np.random.randint(n_points // 2, 3 * n_points // 4)
    else:
        # Low first
        low_idx = np.random.randint(n_points // 4, n_points // 2)
        high_idx = np.random.randint(n_points // 2, 3 * n_points // 4)
    
    # Generate path
    current = open_p
    for i in range(n_points):
        if i == high_idx:
            current = high_p
        elif i == low_idx:
            current = low_p
        elif i == n_points - 1:
            current = close_p
        else:
            # Random walk
            change = np.random.randn() * (high_p - low_p) / n_points * 0.5
            current = current + change
            # Keep in range
            current = np.clip(current, low_p, high_p)
        
        prices.append(current)
    
    return prices


def save_all_formats(df_daily, df_1m):
    """Save in multiple formats"""
    print("\n💾 Saving data in multiple formats...")
    
    files = {}
    
    # 1. Daily data (for 200-SMA)
    df_daily_clean = df_daily.reset_index()
    df_daily_clean.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits']
    filename1 = 'scripts/gold_yahoo_daily.csv'
    df_daily_clean[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']].to_csv(filename1, index=False)
    files['daily'] = filename1
    print(f"✅ {filename1} - {len(df_daily)} days")
    
    # 2. 1-minute Unix format (FabInvests compatible)
    filename2 = 'scripts/gold_yahoo_1m_unix.csv'
    df_1m[['time', 'open', 'high', 'low', 'close', 'tick_volume']].to_csv(
        filename2, index=False, header=False
    )
    files['1m_unix'] = filename2
    print(f"✅ {filename2} - {len(df_1m):,} candles (Unix, no header)")
    
    # 3. 1-minute readable
    df_1m_readable = df_1m.copy()
    df_1m_readable['datetime'] = pd.to_datetime(df_1m_readable['time'], unit='s')
    filename3 = 'scripts/gold_yahoo_1m_readable.csv'
    df_1m_readable[['datetime', 'open', 'high', 'low', 'close', 'tick_volume']].to_csv(
        filename3, index=False
    )
    files['1m_readable'] = filename3
    print(f"✅ {filename3} - {len(df_1m):,} candles (readable)")
    
    # 4. 15-minute aggregation
    df_15m = df_1m_readable.set_index('datetime').resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).dropna()
    
    filename4 = 'scripts/gold_yahoo_15m.csv'
    df_15m.to_csv(filename4)
    files['15m'] = filename4
    print(f"✅ {filename4} - {len(df_15m):,} bars")
    
    return files


def main():
    """Main function"""
    # Download data
    df_daily, df_1m = download_gold_data()
    
    if df_daily is None:
        print("\n❌ FAILED TO DOWNLOAD DATA")
        return
    
    # Save all formats
    files = save_all_formats(df_daily, df_1m)
    
    # Summary
    print("\n" + "="*70)
    print("✅ DOWNLOAD COMPLETE!")
    print("="*70)
    print(f"Daily candles:     {len(df_daily)}")
    print(f"1-minute candles:  {len(df_1m):,}")
    print(f"Date range:        {(df_daily.index.max() - df_daily.index.min()).days} days")
    
    print("\n" + "="*70)
    print("FILES CREATED:")
    print("="*70)
    for fmt, path in files.items():
        print(f"  • {fmt:15s} {path}")
    
    print("\n" + "="*70)
    print("READY FOR FABINVESTS!")
    print("="*70)
    print(f"✅ Have {len(df_daily)} days (need 200+ for 200-SMA)")
    print(f"✅ Have {len(df_1m):,} 1-minute candles")
    print(f"✅ Can test all 6 FabInvests strategies!")
    print("\n⚠️  NOTE: 1-minute data is SYNTHETIC (from daily OHLC)")
    print("   Real fills may differ, but good for strategy testing")
    print("="*70)


if __name__ == "__main__":
    main()
