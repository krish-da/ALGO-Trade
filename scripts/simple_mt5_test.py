#!/usr/bin/env python3
import MetaTrader5 as mt5
import time
import sys

try:
    print("Attempting MT5 connection...")
    print(f"MT5 version: {mt5.__version__}")

    # Try initialize
    result = mt5.initialize()
    print(f"Initialize result: {result}")

    if not result:
        error = mt5.last_error()
        print(f"Error: {error}")
        print("\nTrying with explicit path...")
        
        # Try with explicit path
        result = mt5.initialize(path="C:\\Program Files\\MetaTrader 5\\terminal64.exe")
        print(f"Initialize with path result: {result}")
        
        if not result:
            error = mt5.last_error()
            print(f"Error: {error}")
            sys.exit(1)

    print("✅ MT5 initialized")
    time.sleep(1)

    # Try login
    print("\nAttempting login...")
    print(f"Login: 40000134945")
    print(f"Server: FundingPips-Trial")

    authorized = mt5.login(
        login=40000134945,
        password="5AV^(1*lV",
        server="FundingPips-Trial"
    )

    print(f"Login result: {authorized}")

    if not authorized:
        error = mt5.last_error()
        print(f"Error code: {error[0]}, Message: {error[1]}")
        
        # List available servers
        print("\nChecking available servers...")
        # This might not work, but let's try
        
    else:
        print("✅ Login successful!")
        account = mt5.account_info()
        if account:
            print(f"\nBalance: ${account.balance:,.2f}")
            print(f"Server: {account.server}")
            print(f"Leverage: 1:{account.leverage}")

    mt5.shutdown()
    
except Exception as e:
    print(f"\n❌ Exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
