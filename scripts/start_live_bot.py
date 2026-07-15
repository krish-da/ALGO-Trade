#!/usr/bin/env python3
"""
START LIVE BOT - Simple wrapper to start and monitor Gold Sniper V5 Live
"""

import subprocess
import sys
import time
from datetime import datetime

def main():
    print("="*80)
    print("GOLD SNIPER V5 - LIVE BOT STARTER")
    print("="*80)
    print(f"\nStarting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nThis will:")
    print("  1. Start the live trading bot")
    print("  2. Monitor for 5 minutes")
    print("  3. Show status every minute")
    print("\nThe bot will continue running after this script exits.")
    print("Use Ctrl+C to stop the bot.\n")
    
    input("Press ENTER to start...")
    
    try:
        # Start the bot
        print("\n🚀 Starting Gold Sniper V5 Live Bot...")
        process = subprocess.Popen(
            [sys.executable, "gold_sniper_v5_live.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        print("✅ Bot started!\n")
        print("="*80)
        print("LIVE OUTPUT:")
        print("="*80 + "\n")
        
        # Monitor for 5 minutes
        start_time = time.time()
        monitor_duration = 300  # 5 minutes
        
        while True:
            # Read output
            line = process.stdout.readline()
            if line:
                print(line, end='')
            
            # Check if process ended
            if process.poll() is not None:
                print("\n⚠️  Bot process ended")
                break
            
            # Check if monitoring period is over
            elapsed = time.time() - start_time
            if elapsed >= monitor_duration:
                print("\n" + "="*80)
                print("✅ 5-minute monitoring complete!")
                print("="*80)
                print("\nBot is still running in background.")
                print("You can close this window or press Ctrl+C to stop the bot.")
                print("="*80 + "\n")
                
                # Continue showing output but slower
                while True:
                    line = process.stdout.readline()
                    if line:
                        print(line, end='')
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
                break
    
    except KeyboardInterrupt:
        print("\n\n⏹️  Stopping bot...")
        process.terminate()
        process.wait()
        print("✅ Bot stopped")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if 'process' in locals():
            process.terminate()
            process.wait()

if __name__ == "__main__":
    main()
