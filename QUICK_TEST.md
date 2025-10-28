# 🧪 QUICK TEST - Add Tokens Manually

## Stop RPC Mode (It's Not Working Yet)

Press `Ctrl+C` to stop the RPC scanner.

---

## Start Normal Mode Instead

```powershell
python main.py
```

This starts the webhook server so we can test manually.

---

## Test in New PowerShell Window

**Open a NEW PowerShell window** (keep the first one running) and run these commands one by one:

### Test 1: Add Bonk (Popular Memecoin)
```powershell
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263\"}"
```

### Test 2: Add USDC  
```powershell
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v\"}"
```

### Test 3: Add Jupiter (JUP)
```powershell
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN\"}"
```

### Test 4: Add WIF (Dogwifhat)
```powershell
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm\"}"
```

### Test 5: Add POPCAT
```powershell
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr\"}"
```

**Watch your first PowerShell window - you'll see tokens being processed!**

---

## What You Should See

In your **first PowerShell window** (running main.py):

```
============================================================
🔍 NEW MINT DETECTED: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
============================================================
📊 Collecting token data...
Collecting data for DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263...
✓ Data collected for Bonk
🔒 Running safety filters...
💾 Saving to database...

            ✓ PROCESSED: Bonk (Bonk)
            - Address: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
            - Safety: ✓ SAFE
            - Score: 5/7
            - Risk Level: MEDIUM
            - Liquidity: $794,900.00
            - Holders: 617847
```

**Your dashboard will update with the new token!**

---

## Why This Works

- ✅ Tests your system end-to-end
- ✅ Proves data collection works
- ✅ Proves filters work
- ✅ Proves database works
- ✅ You can see exactly what happens

**After testing this way, we'll fix the RPC scanner!**

---

## More Tokens to Test

Want more? Try these popular Solana memecoins:

```powershell
# Myro
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"HhJpBhRRn4g56VsyLuT8DL5Bv31HkXqsrahTTUCZeZg4\"}"

# Wen
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk\"}"

# Ponke  
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"5z3EqYQo9HiCEs3R84RCDMu2n7anpDMxRhdK8PSWmrRC\"}"
```

---

## Next Step

**After you see these tokens working, read `FIX_RPC_SCANNER.md` to fix the automatic scanner!**
