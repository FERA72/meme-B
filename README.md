# 🚀 MEME-BETA.5

Real-time Solana memecoin monitoring system with anti-rug filters and graduation tracking.

---

## 📋 PREREQUISITES

### Required Software
1. **Python 3.9+** (Download from python.org)
2. **PostgreSQL 14+** (Download from postgresql.org)
3. **Git** (Optional, for cloning)

---

## ⚡ QUICK START

### Step 1: Install PostgreSQL

#### Windows:
1. Download PostgreSQL installer from postgresql.org
2. Run installer (remember your password!)
3. Default port 5432 is fine
4. PostgreSQL should start automatically

#### To verify PostgreSQL is running:
```powershell
# In PowerShell
psql -U postgres -c "SELECT version();"
```

### Step 2: Create Database

```powershell
# Open PowerShell and run:
psql -U postgres

# Inside psql, create the database:
CREATE DATABASE memebeta;

# Exit psql:
\q
```

### Step 3: Install Python Dependencies

```powershell
# Navigate to project directory
cd C:\Users\k\projects\meme-beta.5

# Install all required packages
pip install -r requirements.txt
```

### Step 4: Configure Environment

1. **Copy the example config:**
```powershell
copy .env.example .env
```

2. **Edit `.env` file** (use notepad or any text editor):
```powershell
notepad .env
```

3. **Set these values:**

```env
# Replace with your actual PostgreSQL password
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD_HERE@localhost:5432/memebeta

# Get this FREE from helius.dev (create account and get API key)
HELIUS_API_KEY=YOUR_HELIUS_API_KEY_HERE

# Leave these as default (or change if needed)
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000

# Adjust filter thresholds if desired
MIN_LIQUIDITY_USD=20000
MAX_TOP_HOLDER_PCT=40
MIN_HOLDER_COUNT=10

# Adjust graduation criteria if desired
MIN_LIQUIDITY_GROWTH=2.0
MIN_MARKET_CAP=100000
MIN_HOLDER_GROWTH=1.5
MIN_VOLUME_24H=10000
GRADUATION_CHECK_INTERVAL=60
```

**IMPORTANT:** Replace `YOUR_PASSWORD_HERE` and `YOUR_HELIUS_API_KEY_HERE` with actual values!

### Step 5: Get Helius API Key (FREE)

1. Go to https://helius.dev
2. Sign up for FREE account
3. Create a new API key
4. Copy the key and paste it into your `.env` file

---

## 🎯 RUNNING THE SYSTEM

### Mode 1: Full System (Dashboard + Scanner + Watcher)

This runs everything together - webhook server, graduation watcher, and live dashboard:

```powershell
python main.py
```

**What you'll see:**
- Real-time dashboard showing top 20 tokens
- Recent mints section at the bottom
- Live updates every 2 seconds
- Press `Ctrl+C` to stop

### Mode 2: Dashboard Only (View Data)

Just view existing data without scanning for new tokens:

```powershell
python main.py --dashboard
```

**Use this when:**
- You want to view collected data
- Scanner is running on another machine
- You're testing the dashboard

### Mode 3: Scanner Only (No Dashboard)

Run webhook server and graduation watcher without the dashboard:

```powershell
python main.py --scanner
```

**Use this when:**
- Running on a server
- Viewing dashboard separately
- Want minimal resource usage

---

## 🌐 WEBHOOK SETUP

The system receives new token data via webhooks from Helius.

### For Local Development (ngrok):

1. **Install ngrok** from ngrok.com

2. **Run ngrok:**
```powershell
ngrok http 5000
```

3. **Copy the public URL** (e.g., https://abc123.ngrok.io)

4. **Configure Helius Webhook:**
   - Go to Helius dashboard
   - Create new webhook
   - Set URL to: `https://abc123.ngrok.io/webhook/mint`
   - Select "Token Creation" event type
   - Save

### For Production (Public Server):

Configure Helius to POST to:
```
http://YOUR_SERVER_IP:5000/webhook/mint
```

### Testing the Webhook:

Test manually with a known token:
```powershell
curl -X POST http://localhost:5000/webhook/test -H "Content-Type: application/json" -d "{\"mint\":\"REPLACE_WITH_REAL_MINT_ADDRESS\"}"
```

---

## 📊 HOW IT WORKS

### 1. **Scanner**
- Receives webhook events from Helius when new tokens are minted
- Collects complete token data (metadata, liquidity, holders, authorities)
- Uses DexScreener API for free DEX data

### 2. **Filters**
Checks each token for safety:
- ✓ Liquidity ≥ $20k (configurable)
- ✓ Mint authority revoked
- ✓ Freeze authority revoked
- ✓ No excessive holder concentration
- ✓ Minimum holder count
- ✓ LP lock status
- ✓ Trading active

**Tokens that fail = marked as RISKY**
**Tokens that pass = marked as SAFE**

### 3. **Graduation Watcher**
Monitors safe tokens for growth:
- Checks every 60 seconds (configurable)
- Looks for 2x liquidity growth
- Needs $100k market cap
- Requires 1.5x holder growth
- Needs $10k daily volume

**When all criteria met = marked as GRADUATED** 🎓

### 4. **Database**
PostgreSQL stores:
- All token data (safe and risky)
- Historical snapshots
- Filter logs
- Growth metrics

### 5. **Dashboard**
Real-time terminal UI showing:
- Top 20 tokens by market cap
- Recent mints (last 10 minutes)
- System statistics
- Updates every 2 seconds

---

## 🔧 CUSTOMIZATION

### Adjust Filter Thresholds

Edit `.env` file and change these values:

```env
MIN_LIQUIDITY_USD=20000      # Minimum liquidity in USD
MAX_TOP_HOLDER_PCT=40        # Max % one wallet can hold
MIN_HOLDER_COUNT=10          # Minimum number of holders
```

Restart the system after changes.

### Adjust Graduation Criteria

Edit `.env` file:

```env
MIN_LIQUIDITY_GROWTH=2.0     # Must be 2x initial liquidity
MIN_MARKET_CAP=100000        # Must reach $100k market cap
MIN_HOLDER_GROWTH=1.5        # Must be 1.5x initial holders
MIN_VOLUME_24H=10000         # Must have $10k daily volume
GRADUATION_CHECK_INTERVAL=60 # Check every 60 seconds
```

### Dashboard Refresh Rate

Edit `ui/dashboard.py`, line 32:

```python
self.refresh_rate = 2  # REPLACE ME - update every X seconds
```

---

## 📁 PROJECT STRUCTURE

```
meme-beta.5/
├── core/                      # Core functionality
│   ├── scanner.py            # Token detection and processing
│   ├── data_collector.py     # Fetches token data from APIs
│   ├── filters.py            # Anti-rug safety checks
│   └── graduation.py         # Monitors tokens for growth
├── db/                        # Database layer
│   ├── database.py           # Database operations
│   └── models.py             # Table definitions
├── ui/                        # User interface
│   └── dashboard.py          # Terminal dashboard
├── main.py                    # Main entry point
├── webhook_server.py          # Flask webhook receiver
├── requirements.txt           # Python dependencies
├── .env.example              # Example configuration
└── README.md                 # This file
```

---

## 🐛 TROUBLESHOOTING

### "Database connection failed"
- Check if PostgreSQL is running: `psql -U postgres -c "SELECT 1;"`
- Verify password in `.env` file
- Ensure database exists: `psql -U postgres -c "\l"`

### "HELIUS_API_KEY not configured"
- Get FREE key from helius.dev
- Add it to `.env` file
- Don't use the example key

### "No tokens appearing"
- Ensure webhook is configured in Helius dashboard
- Check if webhook server is running
- Test manually: `curl http://localhost:5000/health`
- Verify ngrok is running (for local development)

### "Module not found" errors
- Run: `pip install -r requirements.txt`
- Check Python version: `python --version` (need 3.9+)

### Dashboard not updating
- Check if database has data: Run dashboard mode `python main.py --dashboard`
- Verify PostgreSQL connection
- Look for errors in console output

---

## 📡 API ENDPOINTS

When running, these endpoints are available:

- **Health Check:** `http://localhost:5000/health`
  - Returns 200 if server is running

- **Main Webhook:** `http://localhost:5000/webhook/mint`
  - Receives POST requests from Helius

- **Test Webhook:** `http://localhost:5000/webhook/test`
  - Manually test with: `{"mint": "address_here"}`

- **Statistics:** `http://localhost:5000/stats`
  - Returns scanner statistics

---

## 🎓 TIPS

1. **Start with dashboard mode** to see if you have data:
   ```powershell
   python main.py --dashboard
   ```

2. **Use full mode** for everything at once:
   ```powershell
   python main.py
   ```

3. **Check logs** - all errors print to console

4. **Database persists** - data survives restarts

5. **Adjust thresholds** in `.env` based on your needs

6. **Monitor graduation** - graduated tokens are the winners!

---

## ⚙️ PERFORMANCE

- **Webhook response time:** < 500ms
- **Data collection:** ~2-3 seconds per token
- **Dashboard refresh:** Every 2 seconds (configurable)
- **Graduation checks:** Every 60 seconds (configurable)
- **Database:** Connection pooling for efficiency

---

## 🆘 SUPPORT

If you encounter issues:

1. Check console for error messages
2. Verify all configuration in `.env`
3. Ensure PostgreSQL is running
4. Check Helius dashboard for webhook status
5. Test endpoints manually with curl

---

## 📝 NOTES

- **DexScreener API** is FREE - no key needed
- **Helius FREE tier** has rate limits - upgrade if needed
- **PostgreSQL** stores everything - can grow large over time
- **Dashboard** works best in full-screen terminal
- **Press Ctrl+C** to stop any running mode

---

## 🚀 HAPPY HUNTING!

Monitor those memecoins and catch the next 100x before it moons! 🌙

---

Made with ❤️ for memecoin hunters
