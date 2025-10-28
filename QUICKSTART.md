# ⚡ QUICKSTART - MEME-BETA.5

**Get running in 5 minutes!**

---

## 1. Install PostgreSQL

Download and install from: https://www.postgresql.org/download/

Remember your password!

---

## 2. Create Database

```powershell
psql -U postgres
CREATE DATABASE memebeta;
\q
```

---

## 3. Install Python Packages

```powershell
cd C:\Users\k\projects\meme-beta.5
pip install -r requirements.txt
```

---

## 4. Configure

```powershell
# Copy example config
copy .env.example .env

# Edit .env file
notepad .env
```

**Change these 2 lines:**
```
DATABASE_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/memebeta
HELIUS_API_KEY=YOUR_HELIUS_KEY_FROM_HELIUS_DOT_DEV
```

Get FREE Helius key: https://helius.dev

---

## 5. Verify Setup

```powershell
python check_setup.py
```

If all checks pass → you're ready!

---

## 6. Run

```powershell
# Run everything (scanner + dashboard + watcher)
python main.py

# OR just view dashboard
python main.py --dashboard

# OR just scanner (no dashboard)
python main.py --scanner
```

---

## 7. Setup Webhook

### For Local Testing:

1. Install ngrok: https://ngrok.com/download
2. Run: `ngrok http 5000`
3. Copy the https URL (e.g., https://abc123.ngrok.io)
4. Go to https://helius.dev dashboard
5. Create webhook → Set URL: `https://abc123.ngrok.io/webhook/mint`
6. Select "Token Creation" event
7. Save

---

## ✅ DONE!

New memecoins will appear as they're minted!

Press **Ctrl+C** to stop.

---

## 🐛 Problems?

- **Database error?** → Check password in `.env`
- **Helius error?** → Get key from helius.dev
- **No packages?** → Run `pip install -r requirements.txt`
- **No tokens?** → Setup webhook (step 7)

Read full README.md for detailed help.
