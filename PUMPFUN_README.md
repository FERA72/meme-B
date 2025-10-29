# 🚀 PUMP.FUN PROFIT SCANNER

Simple, focused system for finding profitable Pump.fun token launches.

## What It Does

1. **Scans Pump.fun** - Gets new tokens every 10 seconds
2. **Analyzes for profit** - Looks for early momentum signals
3. **Shows BUY signals** - Clean dashboard with opportunities
4. **You trade manually** - Copy the mint address and trade on Pump.fun

## Strategy

### Entry Criteria
- Token age: < 30 minutes (very fresh)
- Market cap: $5k - $50k (early but has interest)
- Activity: ≥ 3 replies (some engagement)
- Has social links (Twitter/Telegram/Website)
- No scam words in name/symbol

### Exit Strategy
- **Take Profit**: 2-3x depending on confidence
- **Stop Loss**: -20% to -30%
- **Time Limit**: Exit within 1-2 hours max

### Confidence Levels
- **70%+**: Strong buy - larger position
- **50-70%**: Good buy - normal position
- **<50%**: Skip

## Quick Start

```bash
# Run the scanner
python main_pumpfun.py
```

That's it! The dashboard will show:
- 🎯 **BUY SIGNALS** - Tokens worth buying (with links)
- 📋 **RECENT TOKENS** - All tokens scanned

## Dashboard

```
┌─── STATS ───────────────────────────────────────┐
│ Runtime: 15.2 minutes                           │
│ Tokens Scanned: 45                              │
│ Buy Signals: 8                                  │
│ Hit Rate: 17.8%                                 │
└─────────────────────────────────────────────────┘

🎯 BUY SIGNALS
┌───┬────────┬──────────┬────────────┬──────────┬─────┬─────────────────┐
│ # │ Symbol │ Name     │ Confidence │ MCap     │ Age │ Links           │
├───┼────────┼──────────┼────────────┼──────────┼─────┼─────────────────┤
│ 1 │ BONK   │ Bonk Inu │    75%     │ $15,000  │ 8m  │ pump.fun/...    │
│   │        │          │            │          │     │ dexscreener...  │
└───┴────────┴──────────┴────────────┴──────────┴─────┴─────────────────┘
```

## How to Trade

1. **Wait for BUY signal** in dashboard
2. **Copy the Pump.fun link** from dashboard
3. **Open link in browser**
4. **Check the token** (verify it looks legit)
5. **Buy on Pump.fun** (enter with caution)
6. **Set stop loss** mentally (-20% to -30%)
7. **Take profits** at 2-3x
8. **Exit quickly** - don't hold for days

## Risk Management

⚠️ **IMPORTANT RULES**

1. **Never risk more than 1-2% per trade**
2. **Always use stop losses**
3. **Take profits quickly** - don't be greedy
4. **Most tokens will fail** - accept it
5. **You need a 30-50% win rate** to be profitable

### Position Sizing Example

If you have $1000:
- **Risk per trade**: $10-20 (1-2%)
- **Stop loss**: -30%
- **Position size**: $33-66 (so -30% = $10-20 loss)

If you hit 3 losers then 1 winner at 3x:
- 3 losses: -$10, -$10, -$10 = -$30
- 1 win: +$100 (3x on $33) = +$100
- **Net**: +$70 profit

## Files

- `main_pumpfun.py` - Main runner (START HERE)
- `pumpfun_scanner.py` - Scrapes Pump.fun API
- `profit_analyzer.py` - Analyzes tokens for profit potential
- `simple_dashboard.py` - Shows tokens + signals

## Tips

- **Run during US hours** (10am-10pm EST) - most activity
- **First 5-15 minutes** are critical - get in early
- **Don't chase pumps** - if mcap > $50k, skip it
- **Trust the system** - if no BUY signal, skip
- **Keep a trade journal** - track what works

## Next Steps

After you validate this works:
1. Add ML to improve signal accuracy
2. Add automated trading (Jupiter API)
3. Add performance tracking
4. Add Telegram alerts

But for now: **Keep it simple. Scan. Analyze. Trade.**

Good luck! 🚀
