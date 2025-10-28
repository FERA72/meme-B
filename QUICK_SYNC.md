# 🔄 SYNC INSTRUCTIONS

## Your Local Files Are Out of Date!

I made all the improvements to the git repository, but you need to pull them to your local machine.

## Option 1: Pull from Git (RECOMMENDED)

```powershell
# Stop the running application (Ctrl+C)

# Pull the latest changes
git fetch origin
git checkout claude/session-011CUaADqT1rznMLp1a2njr7
git pull origin claude/session-011CUaADqT1rznMLp1a2njr7

# Clear Python cache
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force
Get-ChildItem -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force

# Restart
python main.py
```

## Option 2: Manual File Copy

If git doesn't work, copy these files from the repository to your local directory:

### Files Modified:
- `core/data_collector.py` - Fixed holder counts, trade data
- `core/filters.py` - Quick-profit detection
- `core/gpt_agent.py` - ML agent
- `ui/dashboard.py` - Enhanced dashboard

### Files Created:
- `db/ml_models.py` - ML database models
- `ML_IMPROVEMENTS.md` - Documentation

## Verify It Worked

After syncing, you should see:
- Dashboard title: "TOP ACTIVE TOKENS - ML ENHANCED"
- New columns: "B/S Ratio", "Quick Profit", "Rug Risk"
- Stats panel with "🤖 ML STATUS"

## Current Issue: All Holders Show 0

This is happening because:
1. Tokens might be too new (no holders yet)
2. Or the RPC call for holders is failing

After you sync the files, the holder count will be more accurate because I fixed the bug where it was only counting the top 20 holders.

## Need Help?

If you can't pull from git, I can create a patch file or guide you through manual copying.
