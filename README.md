# 🔥 Real-Time Pump.fun Monitor

Monitors Pump.fun for new tokens **EVERY SECOND**. Collects **ALL** data. Shows everything in real-time.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the monitor
python main.py
```

That's it! The dashboard shows every new token as it's created with comprehensive data.

## What It Does

- ✅ Scans Pump.fun **every 1-2 seconds** (ultra-fast)
- ✅ Catches **EVERY** new token the instant it's created
- ✅ Collects **ALL** data:
  - Market Cap, Liquidity, Volume
  - Buy/Sell counts and ratios
  - Holder count and top holders
  - Creator address
  - Price changes (5m, 1h, 6h, 24h)
  - Transaction counts
  - Everything available from Pump.fun, DexScreener, and on-chain
- ✅ Real-time dashboard that updates **live every second**
- ✅ Shows full token table with all metrics
- ✅ Links panel with Pump.fun and DexScreener URLs

## Dashboard

```
┌─── REAL-TIME PUMP.FUN MONITOR ──────────────────┐
│ Runtime: 5.2 minutes (312s)                     │
│ Tokens Discovered: 23                           │
│ Discovery Rate: 4.4 tokens/minute               │
└─────────────────────────────────────────────────┘

📊 NEW TOKENS (Live Feed)
┌───┬────────┬────────────┬────────┬────────┬────────┬───────┬─────────┬──────┬──────────┐
│ # │ Symbol │ Name       │ MCap   │ Liq    │ Vol 1h │ B/S   │ Holders │ Age  │ Creator  │
├───┼────────┼────────────┼────────┼────────┼────────┼───────┼─────────┼──────┼──────────┤
│ 1 │ BONK   │ Bonk Inu   │ $15.0k │ $5.0k  │ $2.0k  │ 10/3  │ 45      │ 2.5m │ 7xKXt... │
│ 2 │ MOON   │ To Moon    │ $8.0k  │ $3.0k  │ $500   │ 5/8   │ 23      │ 15m  │ 9yKXt... │
└───┴────────┴────────────┴────────┴────────┴────────┴───────┴─────────┴──────┴──────────┘

🔗 Latest Token Links (Copy & Paste)
───────────────────────────────────────────────────
1. BONK - Bonk Inu
   Mint: ABC123XYZ...
   Pump.fun: https://pump.fun/coin/ABC123XYZ
   DexScreener: https://dexscreener.com/solana/ABC123XYZ
```

## Data Collected

**From Pump.fun:**
- Symbol, Name, Description
- Creator address and username
- Market cap
- Social links (Twitter, Telegram, Website)
- Reply count, activity metrics
- Bonding curve status
- Creation timestamp

**From DexScreener:**
- Price (USD and native)
- Volume (5m, 1h, 6h, 24h)
- Liquidity (USD, base, quote)
- Price changes (5m, 1h, 6h, 24h)
- Buy/Sell counts (5m, 1h, 6h, 24h)
- FDV, Market Cap
- Pair info

**From Solana RPC (On-chain):**
- Total holder count
- Top 10 holders with percentages
- Top holder percentage
- Token balances

## Files

- `main.py` - Main runner (**START HERE**)
- `realtime_scanner.py` - Real-time Pump.fun scanner (checks every 1-2s)
- `data_collector.py` - Collects all data (DexScreener + on-chain)
- `realtime_dashboard.py` - Live updating dashboard
- `requirements.txt` - Dependencies (aiohttp + rich)

## Old Files (Profit Analysis)

If you want the profit analysis system:
- `main_pumpfun.py` - Profit scanner with BUY signals
- `profit_analyzer.py` - Analyzes tokens for profit potential
- See `PUMPFUN_README.md` for strategy guide

---

**Real-time. Comprehensive. Complete.** 🔥
