# Backtest vs Live - Logic Comparison

## ✅ Present in Both
- `__init__` - Initialization with same parameters
- `_get_funding_pips_rules()` - Funding Pips rules
- `check_funding_pips_compliance()` / `check_compliance()` - Compliance checks
- `_find_swing_zones()` - Swing high/low detection
- `_cluster_zones()` - Zone clustering

## ❌ MISSING in Live Version

### Critical Functions from Backtest:
1. **`_calculate_zone_strength()`** - Calculates how strong each zone is based on touches and wicks
2. **`calculate_poc_levels()`** - Volume profile POC calculation (PRESENT but different implementation)
3. **`analyze_5m_setup()`** - **CRITICAL** - Analyzes 5-min chart for entry setup
4. **`execute_1m_entry()`** - **CRITICAL** - Executes precise entry on 1-min with SL/TP calculation
5. **`_enter_trade()`** - Trade entry logic with position sizing
6. **`_manage_trade()`` - **CRITICAL** - Dynamic TP extension + aggressive trailing
7. **`_close_trade()` - Trade closing with P&L tracking
8. **`_calculate_metrics()`** - Performance metrics calculation

### Live Version Issues:
1. `check_entry_setup()` - Simplified version, missing detailed 5-min analysis
2. `execute_trade()` - Basic execution, missing 1-min precision logic
3. `manage_positions()` - Has TP extension and trailing but needs verification against backtest
4. Missing zone strength calculation
5. Missing detailed setup analysis

## 🔧 Required Updates

### Must Add to Live:
1. **Zone strength calculation** - Weight zones by touch count and wick rejections
2. **5-min setup analysis** - Exact same logic as backtest
3. **1-min entry precision** - Calculate SL/TP same way as backtest
4. **Position management** - Ensure TP extension and trailing match exactly

### Must Verify:
1. TP extension trigger (70% progress)
2. TP extension distance (15 pips)
3. Max extensions (5)
4. Trailing activation (1.5:1 R:R)
5. Trailing lock percentage (60%)
6. Trail step (5 pips)
