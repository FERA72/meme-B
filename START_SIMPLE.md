# ⚡ SUPER SIMPLE START GUIDE
## For Python Beginners - Step by Step

---

## 🎯 WHAT WAS FIXED

**1 issue fixed in your code:**
- **File:** `core/data_collector.py` (line 103)
- **Problem:** Used wrong type hint syntax (wouldn't work on Python 3.9)
- **Fixed:** Changed to correct syntax
- ✅ **Your code is now ready to run!**

---

## 🚀 LET'S GET IT RUNNING (7 STEPS)

---

### STEP 1: Install PostgreSQL

**What is it?** A database to store all your token data.

**How to install:**
1. Go to: https://www.postgresql.org/download/windows/
2. Download the installer (Windows x86-64)
3. Run the installer
4. **IMPORTANT:** When it asks for a password, type something simple like: `postgres123`
5. **WRITE DOWN YOUR PASSWORD!** You'll need it in Step 4
6. Keep clicking Next (defaults are fine)
7. Finish installation

**How to check it worked:**
```powershell
# Open PowerShell (search "PowerShell" in Windows)
# Type this and press Enter:
psql -U postgres -c "SELECT 1;"

# If you see "1" - it worked! ✅
```

---

### STEP 2: Create Your Database

```powershell
# In PowerShell, type:
psql -U postgres

# You'll see: postgres=#
# Now type this and press Enter:
CREATE DATABASE memebeta;

# Then type:
\q

# Done! ✅
```

---

### STEP 3: Install Python Packages

```powershell
# Navigate to your project (copy and paste this):
cd C:\Users\k\projects\meme-beta.5

# Install everything (this takes ~2 minutes):
pip install -r requirements.txt

# You'll see packages installing... wait until it finishes
# When you see "Successfully installed..." - Done! ✅
```

---

### STEP 4: Configure Your .env File

**This is where you put YOUR settings.**

```powershell
# First, copy the example file:
copy .env.example .env

# Now open it in notepad:
notepad .env
```

**In notepad, find these 2 lines and change them:**

**Line 1 - Database Password:**
```env
# BEFORE (don't use this):
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/memebeta

# AFTER (use YOUR password from Step 1):
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/memebeta
#                                  ^^^^^^^^^^^
#                           REPLACE_ME with your actual password
```

**Line 2 - Helius API Key:**
```env
# BEFORE (don't use this):
HELIUS_API_KEY=your_helius_api_key_here

# AFTER (get free key from helius.dev):
HELIUS_API_KEY=abc123-your-actual-key-xyz789
#              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#              REPLACE_ME with your actual API key
```

**How to get Helius API key (it's FREE!):**
1. Go to: https://helius.dev
2. Click "Sign Up" (top right)
3. Create account (use your email)
4. After signing in, click "API Keys"
5. Click "Create New Key"
6. Copy the key
7. Paste it in your .env file (Line 2 above)

**Save the file!** (File → Save in notepad)

---

### STEP 5: Check Everything is OK

```powershell
# Run the setup checker:
python check_setup.py

# You should see:
# [1/6] Checking Python version... ✓
# [2/6] Checking .env file... ✓
# [3/6] Checking Python packages... ✓
# [4/6] Checking PostgreSQL... ✓
# [5/6] Checking Helius API... ✓
# [6/6] Checking database tables... ✓
#
# ✓ ALL CHECKS PASSED!

# If you see this - you're ready! ✅
```

**If something failed:**
- Read the error message
- Go back to that step
- Fix the issue
- Run `python check_setup.py` again

---

### STEP 6: RUN IT! 🚀

```powershell
# Run the full system:
python main.py

# You'll see:
# - System starting messages
# - Dashboard appears
# - Updates every 2 seconds
```

**What you'll see on the dashboard:**
- **Top section:** Statistics (total tokens, safe, graduated)
- **Middle section:** Top 20 tokens (ranked by market cap)
- **Bottom section:** Recent new tokens

**To stop:** Press `Ctrl+C` on your keyboard

---

### STEP 7: Get Live Data (Optional)

**Right now, the system only shows data you manually add.**

**To get REAL live data when new tokens mint:**

**Option A: Use RPC Mode (Easier for beginners)**
```powershell
# Stop the current system (Ctrl+C)
# Then run:
python main.py --rpc

# This will actively scan Solana every 10 seconds for new tokens
# You don't need webhooks or ngrok!
```

**Option B: Use Webhooks (More advanced)**
1. Download ngrok: https://ngrok.com/download
2. Extract the zip file
3. Run ngrok:
   ```powershell
   # Navigate to where you extracted ngrok
   cd C:\path\to\ngrok
   
   # Run it:
   ngrok http 5000
   ```
4. Copy the URL it shows (looks like: https://abc123.ngrok.io)
5. Go to helius.dev → Webhooks → Create Webhook
6. Set URL to: `https://abc123.ngrok.io/webhook/mint`
7. Select "Token Creation" event
8. Save

**I recommend Option A (RPC mode) if you're new to this!**

---

## 🎓 UNDERSTANDING THE DASHBOARD

### Colors Mean Things:

- 🟢 **Green text** = SAFE token (passed all safety checks)
- 🔴 **Red text** = RISKY token (failed safety checks)
- 🎓 **GRAD** = GRADUATED token (proven winner!)

### What to Look For:

**SAFE tokens have:**
- ✅ Good liquidity ($20k+)
- ✅ Mint authority revoked (good!)
- ✅ Freeze authority revoked (good!)
- ✅ Spread out holders (not concentrated)
- ✅ Active trading

**RISKY tokens have:**
- ⚠️ Low liquidity (< $20k)
- ⚠️ Can still mint tokens (bad!)
- ⚠️ Can freeze wallets (bad!)
- ⚠️ One person owns too much
- ⚠️ Very few holders

**GRADUATED tokens:**
- 🎓 Started safe
- 🎓 Liquidity grew 2x
- 🎓 Market cap hit $100k
- 🎓 Holders grew 1.5x
- 🎓 Good daily volume

**→ These are the winners! Watch these closely! 🌙**

---

## ⚙️ CHANGING SETTINGS

**All settings are in your .env file.**

```powershell
# Open it:
notepad .env
```

**Change these numbers to whatever you want:**

```env
# How much liquidity do you want tokens to have?
MIN_LIQUIDITY_USD=20000          # REPLACE_ME (default: $20k)

# How much can one person own?
MAX_TOP_HOLDER_PCT=40            # REPLACE_ME (default: 40%)

# How many holders minimum?
MIN_HOLDER_COUNT=10              # REPLACE_ME (default: 10)

# When should tokens "graduate"?
MIN_LIQUIDITY_GROWTH=2.0         # REPLACE_ME (default: 2x)
MIN_MARKET_CAP=100000            # REPLACE_ME (default: $100k)
MIN_HOLDER_GROWTH=1.5            # REPLACE_ME (default: 1.5x)
MIN_VOLUME_24H=10000             # REPLACE_ME (default: $10k)

# How often to check?
GRADUATION_CHECK_INTERVAL=60     # REPLACE_ME (default: every 60 seconds)
```

**After changing, save and restart:**
```powershell
# Stop: Ctrl+C
# Start: python main.py
```

---

## 🧪 TESTING MANUALLY

**Test with a real Solana token:**

```powershell
# Use Solana's wrapped SOL address as a test:
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"So11111111111111111111111111111111111111112\"}"

# You should see it process the token!
```

---

## 🐛 COMMON PROBLEMS & FIXES

### Problem: "Database connection failed"
**Fix:**
1. Check PostgreSQL is running
2. Check password in .env file
3. Make sure you created the database (Step 2)

### Problem: "HELIUS_API_KEY not configured"  
**Fix:**
1. Get free key from helius.dev
2. Paste it in .env file (replace the example)
3. Make sure no spaces or quotes around it

### Problem: "Module not found"
**Fix:**
```powershell
pip install -r requirements.txt
```

### Problem: "No tokens appearing"
**Fix:**
Use RPC mode to actively scan:
```powershell
python main.py --rpc
```

### Problem: Dashboard looks weird
**Fix:**
Make your PowerShell window fullscreen (F11)

---

## 📝 QUICK COMMANDS CHEAT SHEET

```powershell
# Check setup
python check_setup.py

# Run full system (dashboard + scanner)
python main.py

# Run RPC mode (actively scan for tokens)
python main.py --rpc

# Run dashboard only (view data)
python main.py --dashboard

# Run scanner only (no dashboard)
python main.py --scanner

# Stop any mode
Ctrl+C

# Open settings
notepad .env

# Check if server is running
curl http://localhost:5000/health
```

---

## 🎯 WHAT TO DO NOW

**Follow the 7 steps above in order:**
1. ✅ Install PostgreSQL
2. ✅ Create database
3. ✅ Install packages
4. ✅ Configure .env
5. ✅ Check setup
6. ✅ Run it!
7. ✅ Get live data (RPC mode recommended)

**Then:**
- Watch the dashboard
- Look for graduated tokens 🎓
- Adjust settings in .env
- Find the next 100x! 🚀

---

## 💬 UNDERSTANDING THE CODE (Simple Explanation)

**Since you're new to Python, here's what each file does:**

**Files you'll actually use:**
- `main.py` - Starts everything (RUN THIS!)
- `.env` - Your settings (EDIT THIS!)
- `check_setup.py` - Checks if setup is correct

**Files that do the work (you don't need to edit these):**
- `core/scanner.py` - Finds new tokens
- `core/data_collector.py` - Gets token info from internet [THIS WAS FIXED!]
- `core/filters.py` - Checks if tokens are safe
- `core/graduation.py` - Watches tokens for growth
- `db/database.py` - Saves everything to database
- `ui/dashboard.py` - Shows you the pretty display
- `webhook_server.py` - Receives alerts from Helius

**You only need to:**
1. Run: `python main.py`
2. Edit: `.env` file (to change settings)

**That's it!** The code does the rest! ✅

---

## 🎓 HELPFUL TO KNOW (But Not Required)

### What is Python?
- The programming language this is written in
- You already have it installed
- You don't need to learn it to use this system
- Just run the commands shown above

### What is PostgreSQL?
- A database (like Excel but much faster)
- Stores all your token data
- You installed it in Step 1

### What is Helius?
- A company that provides Solana blockchain data
- Free tier is enough for this system
- You got the API key in Step 4

### What is a webhook?
- How Helius tells your system "new token minted!"
- Optional - RPC mode works without webhooks

---

## ✅ YOU'RE DONE!

**Your system is fixed and ready!**

**Just follow the 7 steps and you'll be hunting memecoins in 15 minutes!**

Good luck and may your bags pump! 🚀🌙💰

---

*Made simple for beginners with ❤️*
