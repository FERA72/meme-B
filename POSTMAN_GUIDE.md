# 🧪 TESTING YOUR SYSTEM WITH POSTMAN

## Why Use Postman?

Postman makes it easy to test your webhook server by sending HTTP requests manually. It's like clicking a button to say "hey, I found a new token!"

---

## 📥 SETUP POSTMAN

### Step 1: Download Postman
1. Go to: https://www.postman.com/downloads/
2. Download and install Postman
3. Open Postman (no account needed for basic use)

---

## 🧪 TESTING YOUR SYSTEM

### Test 1: Health Check

**Check if your server is running:**

- **Method:** GET
- **URL:** `http://localhost:5000/health`
- **Click:** Send

**Expected Response:**
```json
{
  "status": "healthy",
  "service": "meme-beta.5"
}
```

✅ If you see this = server is working!

---

### Test 2: Get Statistics

**See how many tokens you have:**

- **Method:** GET
- **URL:** `http://localhost:5000/stats`
- **Click:** Send

**Expected Response:**
```json
{
  "processed_count": 2,
  "total_tokens": 2,
  "safe_tokens": 2,
  "graduated_tokens": 0
}
```

---

### Test 3: Process a Real Token (USDC)

**This is the main test - process a real Solana token:**

- **Method:** POST
- **URL:** `http://localhost:5000/webhook/test`
- **Headers Tab:**
  - Key: `Content-Type`
  - Value: `application/json`
- **Body Tab:**
  - Select: "raw"
  - Type: "JSON"
  - Content:
    ```json
    {
      "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
    }
    ```
- **Click:** Send

**What happens:**
1. Your console shows processing messages
2. System collects token data from blockchain
3. Runs safety filters
4. Saves to database
5. Dashboard updates!

**Watch your PowerShell window** - you'll see:
```
============================================================
🔍 NEW MINT DETECTED: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
============================================================
📊 Collecting token data...
Collecting data for EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v...
✓ Data collected for USDC
🔒 Running safety filters...
💾 Saving to database...

            ✓ PROCESSED: USDC (USD Coin)
            - Address: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
            - Safety: ✓ SAFE
            - Score: 5/7
            - Risk Level: MEDIUM
            - Liquidity: $289,350,000.00
            - Holders: 0
```

---

## 🎯 MORE TOKENS TO TEST

### Popular Solana Tokens:

**1. USDT (Tether):**
```json
{
  "mint": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
}
```

**2. Bonk (Memecoin):**
```json
{
  "mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
}
```

**3. Wrapped SOL:**
```json
{
  "mint": "So11111111111111111111111111111111111111112"
}
```

**4. Jupiter (JUP):**
```json
{
  "mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"
}
```

**5. Pyth (PYTH):**
```json
{
  "mint": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"
}
```

**Send each one and watch your dashboard grow!** 📈

---

## 📊 SAVE AS POSTMAN COLLECTION

**To save your tests:**

1. Create new Collection (click "New" → "Collection")
2. Name it: "Meme-Beta.5 Tests"
3. Add each request above:
   - Click "Add Request" in your collection
   - Configure method, URL, headers, body
   - Save with a name (e.g., "Test USDC")
4. Now you can run all tests with one click!

---

## 🎯 FULL TEST SEQUENCE

**Run these in order to fully test your system:**

1. **GET** `http://localhost:5000/health`
   → Verify server is running

2. **GET** `http://localhost:5000/stats`
   → Check starting stats

3. **POST** `http://localhost:5000/webhook/test` with USDC
   → Process first token

4. **POST** `http://localhost:5000/webhook/test` with Bonk
   → Process second token

5. **GET** `http://localhost:5000/stats`
   → Verify stats increased

6. **Check Dashboard** → See your new tokens!

---

## 🔍 WHAT TO LOOK FOR

### In Postman Response:

**Success looks like:**
```json
{
  "status": "success",
  "mint_address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
  "symbol": "USDC",
  "is_safe": true
}
```

**Already processed:**
```json
{
  "status": "processed",
  "message": "Event processed but no new mint found"
}
```
(This means token is already in your database - that's OK!)

### In Your Console:

You should see:
- `🔍 NEW MINT DETECTED`
- `📊 Collecting token data...`
- `✓ Data collected for [SYMBOL]`
- `🔒 Running safety filters...`
- `✓ PROCESSED: [SYMBOL]`

### In Dashboard:

- Token appears in "Top 20" section
- Shows market cap, liquidity, holders
- Green = Safe, Red = Risky

---

## 🚨 TROUBLESHOOTING

### "Connection refused"
**Fix:** Make sure `python main.py` is running

### "No response"
**Fix:** Check the URL is `http://localhost:5000` (not https)

### "Internal Server Error"
**Fix:** Check your console for error messages

### Token shows as "UNK"
**Reason:** Token metadata not available yet
**Fix:** Try a popular token (USDC, USDT, Bonk)

---

## 💡 PRO TIP: Create a Test Flow

**In Postman, create an automated test flow:**

1. Create Collection: "Daily Tests"
2. Add all 5 test tokens
3. Click "Run Collection"
4. Postman tests them all automatically!

Now you can test your entire system with one click! 🚀

---

## 🎯 WHAT'S NEXT?

**After testing with Postman, you have 2 options:**

### Option A: Keep Using Postman
- Good for manual testing
- Good for specific tokens you want to check
- You control exactly what gets added

### Option B: Use RPC Mode (Recommended)
- Stop current system (Ctrl+C)
- Run: `python main.py --rpc`
- Automatically finds new tokens every 10 seconds
- No manual work needed!

---

## 📝 QUICK REFERENCE

```
Health Check:     GET  http://localhost:5000/health
Statistics:       GET  http://localhost:5000/stats
Test Token:       POST http://localhost:5000/webhook/test
  Body: {"mint": "token_address_here"}
  Header: Content-Type: application/json
```

---

**Happy Testing! 🧪**
