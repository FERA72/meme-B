# 🚀 Pump.fun Profit Scanner

Simple scanner for finding profitable token launches on Pump.fun.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scanner
python main_pumpfun.py
```

That's it! The dashboard will show BUY signals for profitable opportunities.

## What It Does

- ✅ Scans Pump.fun for new tokens (every 10 seconds)
- ✅ Analyzes profit potential (momentum indicators)
- ✅ Shows BUY signals with confidence scores
- ✅ Real-time dashboard with links

## Strategy

**Entry:** Fresh tokens (<30 min), $5k-$50k mcap, has activity
**Exit:** 2-3x profit target, -20% to -30% stop loss
**Risk:** Only trade tokens with 50%+ confidence

## Full Guide

See [PUMPFUN_README.md](PUMPFUN_README.md) for:
- Complete strategy explanation
- Risk management rules
- Trading tips
- Position sizing

## Files

- `main_pumpfun.py` - Main runner (START HERE)
- `pumpfun_scanner.py` - Scrapes Pump.fun API
- `profit_analyzer.py` - Analyzes profit potential
- `simple_dashboard.py` - Real-time dashboard

---

**Simple. Focused. Profitable.** 🚀
