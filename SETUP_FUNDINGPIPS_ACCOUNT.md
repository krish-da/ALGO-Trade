# FundingPips Trial Account Setup

## STEP 1: Add FundingPips Server to MT5

You need to manually add the FundingPips-Trial server to MetaTrader 5:

1. **Open MetaTrader 5**
2. **Click** `File` → `Open an Account`
3. **Search** for "FundingPips" or "FundingPips-Trial"
4. **Select** the FundingPips-Trial server
5. **Choose** "Login to an existing account"
6. **Enter credentials:**
   - Login: `40000134945`
   - Password: `5AV^(1*lV`
   - Server: `FundingPips-Trial`
7. **Click** `Finish`

## STEP 2: Verify Connection

Once added, you should see:
- Account balance displayed in MT5
- XAUUSD symbol available in Market Watch
- Server status shows "Connected" (green icon in bottom right)

## STEP 3: Test Python Connection

Run this test:
```bash
cd "c:\Users\krish\OneDrive\Attachments\Desktop\funding pips Algo\algorithmic-trading-script\scripts"
python test_new_account.py
```

If successful, you'll see:
```
✅ Login successful!
Balance: $XXXXX
Server: FundingPips-Trial
Leverage: 1:XX
```

## STEP 4: Start Live Bot

Once connection is confirmed:
```bash
python gold_sniper_v5_live.py
```

The bot will:
1. Auto-detect your account balance
2. Set appropriate phase (phase1/phase2/master based on balance)
3. Start monitoring for trade setups
4. Execute trades automatically when conditions are met

## Troubleshooting

### "Login failed" Error
- **Check**: MT5 is running and logged into the FundingPips account
- **Try**: Restart MT5 and login manually first
- **Verify**: Credentials are correct (copy-paste to avoid typos)

### "Server not found" Error
- **Check**: Server is added to MT5 (Step 1)
- **Try**: Search for "FundingPips" in server list when adding account
- **Contact**: FundingPips support if server isn't available

### "XAUUSD not found" Error
- **Check**: Symbol is visible in Market Watch
- **Try**: Right-click Market Watch → Symbols → Search for "XAUUSD" → Enable

### Python Can't Connect
- **Check**: Only ONE instance of MT5 is running
- **Try**: Close all MT5 windows, restart ONE instance
- **Verify**: You're logged into the correct account in MT5

## Phase Configuration

Based on your account balance, the bot will use:

| Balance | Phase | Profit Target | Max DD | Daily Loss |
|---------|-------|---------------|---------|------------|
| < $25K | Phase 1 | 8% | 10% | 5% |
| $25K-$100K | Phase 2 | 5% | 10% | 5% |
| > $100K | Master | None | 8% | 5% |

The bot auto-detects which phase you're in based on your starting balance.

## Next Steps

After successful connection:
1. Let bot run for 5-10 minutes to detect zones
2. Monitor terminal output for status updates
3. Check `check_bot_status.py` anytime for current status
4. Bot will enter trades automatically when setups appear

Good luck with your trial! 🚀
