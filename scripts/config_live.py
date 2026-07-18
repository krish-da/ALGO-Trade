"""
BINANCE LIVE TRADING CONFIGURATION
Update your API credentials here
"""

# =============================================================================
# BINANCE API CREDENTIALS
# Get these from: https://www.binance.com/en/my/settings/api-management
# =============================================================================

# PASTE YOUR BINANCE API KEYS HERE:
API_KEY = "YOUR_BINANCE_API_KEY_HERE"
API_SECRET = "YOUR_BINANCE_API_SECRET_HERE"

# =============================================================================
# TRADING PARAMETERS
# =============================================================================

# Account size (None = use full balance, or set specific amount like 1000)
ACCOUNT_SIZE = None

# Risk per trade (% of account)
RISK_PCT = 2.0

# =============================================================================
# SAFETY SETTINGS
# =============================================================================

# Enable testnet mode (True = paper trading, False = real money)
TESTNET = False

# Maximum daily trades
MAX_TRADES_PER_DAY = 15

# Minimum time between trades (minutes)
MIN_TRADE_SPACING = 40

# =============================================================================
# VALIDATION CHECKLIST
# =============================================================================
"""
Before running with real money, verify:

✓ API Keys have correct permissions:
  - Enable Futures Trading
  - Enable Reading
  - NO withdrawal permissions needed
  
✓ Binance Futures account is activated

✓ You have USDT in your Futures wallet

✓ You understand the risks:
  - This uses leverage (futures)
  - Can lose money quickly
  - Start with small capital
  
✓ Validation test passed (run validate_live_logic.py)

✓ You've reviewed all code logic

✓ You're monitoring the first trades
"""
