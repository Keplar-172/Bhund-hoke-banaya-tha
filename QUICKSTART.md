# 🚀 Quick Start Guide - Web Interface

## 🎯 Start in 3 Steps

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Start the Server
```bash
python main.py runserver
```

### Step 3: Login
Open browser: **http://localhost:8000**

**Login:**
- Username: `admin`
- Password: `admin123`

---

## 📊 What You Get

### Web Dashboard
✅ **Leaderboard** - Real-time standings  
✅ **Match History** - All processed matches  
✅ **Master Scoresheet** - Cumulative stats  
✅ **Match Details** - Player breakdowns  

### Downloads (Excel)
📥 Master Scoresheet  
📥 Team Points per match  
📥 Cricket Scorecards  
📥 Analytics Dashboard  

---

## 🔒 Security Setup (Before Going Public)

### 1. Change Admin Password
```bash
python generate_password_hash.py
```
Then update `config.py` with the new hash

### 2. Set Environment Variables
```bash
cp .env.example .env
# Edit .env with your keys
```

### 3. Production Deploy
See `WEB_README.md` for full deployment guide

---

## 💡 Pro Tips

**CLI Still Works** - All `python main.py` commands work as before  
**Auto-Backup** - Data is in `data/` directory  
**Multi-User** - Add users in `config.py` USERS_DB  

---

## 🆘 Troubleshooting

**Can't start server?**
```bash
# Check if port 8000 is already in use
lsof -ti:8000 | xargs kill -9
```

**Import errors?**
```bash
pip install -r requirements.txt --upgrade
```

**Can't login?**
- Username: `admin` (lowercase)
- Password: `admin123` (no spaces)

---

📖 **Full Documentation:** See `WEB_README.md`
