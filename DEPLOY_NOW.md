# 🚀 Railway Deployment Instructions for Your IPL Fantasy League

## ✅ Step 1: Create GitHub Repository (DO THIS NOW)

1. **Go to:** https://github.com/new

2. **Fill in:**
   - Repository name: `ipl-fantasy-league-2026`
   - Description: `IPL Fantasy League 2026 - Fantasy cricket scoring system`
   - Visibility: **Public** (or Private if you prefer)
   - ❌ DON'T check "Initialize with README" (we already have files)

3. **Click:** "Create repository"

---

## ✅ Step 2: Push Your Code to GitHub

After creating the repository, GitHub will show you commands. 

**Copy those exact commands** (they'll have your username), but they should look like:

```bash
git remote add origin https://github.com/YOUR_USERNAME/ipl-fantasy-league-2026.git
git branch -M main
git push -u origin main
```

**Run those commands in your terminal** (the one with this project open).

---

## ✅ Step 3: Deploy on Railway (10 minutes)

### 3A. Sign Up/Login to Railway

1. **Go to:** https://railway.app
2. **Click:** "Login" → Sign in with GitHub
3. **Authorize Railway** to access your GitHub repositories

### 3B. Create New Project

1. **Click:** "New Project"
2. **Select:** "Deploy from GitHub repo"
3. **Choose:** Your repository (`ipl-fantasy-league-2026`)
4. **Railway automatically:**
   - Detects it's a Python app
   - Reads `requirements.txt`
   - Starts building!

### 3C. Add Environment Variables

While it's building, click on your service → **"Variables"** tab:

**Click "Add Variable"** for each of these:

```
RAPIDAPI_KEY = your_rapidapi_key_here
SECRET_KEY = 2d1ff3b72729041dae923feaa6e7b8f69b45486faf9101f8a01802213965c514
ENVIRONMENT = production
RATE_LIMIT = 60
CORS_ORIGINS = https://fantasy.wizzlebin.com,https://wizzlebin.com,https://www.wizzlebin.com
FORCE_HTTPS = true
LOG_LEVEL = INFO
HOST = 0.0.0.0
PORT = 8000
```

**Important:** Replace `your_rapidapi_key_here` with your actual RapidAPI key!

### 3D. Wait for Deployment

Railway will:
- ✅ Install dependencies
- ✅ Build your app
- ✅ Start the server
- ✅ Give you a URL like: `https://ipl-fantasy-production-xxxx.up.railway.app`

**Test it immediately!** Open that URL and login with:
- Username: `admin`
- Password: `admin123`

---

## ✅ Step 4: Add Custom Domain (10-30 minutes)

### 4A. In Railway Dashboard

1. **Click:** Your service → "Settings" → "Domains"
2. **Click:** "Custom Domain"
3. **Enter:** `fantasy.wizzlebin.com`
4. **Note the CNAME value** Railway shows you (looks like: `ipl-fantasy-production-xxxx.up.railway.app`)

### 4B. Update DNS for wizzlebin.com

**Where to do this:** Go to where you manage DNS for wizzlebin.com

This could be:
- Your WordPress hosting provider (Bluehost, SiteGround, WP Engine, etc.)
- Domain registrar (GoDaddy, Namecheap, Google Domains)
- Cloudflare (if using)

**Add this DNS record:**

```
Type: CNAME
Name: fantasy
Value: ipl-fantasy-production-xxxx.up.railway.app
TTL: 3600 (or Auto)
```

**Save the record.**

### 4C. Wait for DNS Propagation (15-60 minutes)

DNS changes take time. Check status:

```bash
dig fantasy.wizzlebin.com
```

When it shows the Railway URL, it's ready!

### 4D. SSL Certificate (Automatic)

Railway will **automatically** provision an SSL certificate (takes 1-5 minutes after DNS propagates).

Your site will be accessible at: **https://fantasy.wizzlebin.com**

---

## ✅ Step 5: WordPress Integration (5 minutes)

### Add Navigation Link

1. **WordPress Dashboard** → **Appearance** → **Menus**
2. **Click:** "Custom Links" (expand if needed)
3. **Add:**
   - URL: `https://fantasy.wizzlebin.com`
   - Link Text: `Fantasy League 🏏`
4. **Click:** "Add to Menu"
5. **Drag** to desired position
6. **Click:** "Save Menu"

**Done!** The link now appears in your WordPress navigation.

---

## ✅ Step 6: Post-Deployment Tasks

### Change Admin Password (IMPORTANT!)

After deployment, login and change the default password from `admin123` to something secure.

### Test Everything

- [ ] Login works
- [ ] Dashboard loads
- [ ] All pages accessible (History, Master, Analytics)
- [ ] Downloads work
- [ ] Dark mode toggles
- [ ] Charts render
- [ ] Mobile responsive

### Announce to Users

- Post on social media
- Write WordPress blog post
- Email your fantasy league participants

---

## 🎯 Quick Reference

**Your URLs:**
- **Railway URL:** `https://ipl-fantasy-production-xxxx.up.railway.app`
- **Custom Domain:** `https://fantasy.wizzlebin.com`
- **WordPress:** `https://wizzlebin.com`

**Railway Dashboard:** https://railway.app/dashboard

**Health Check:** `https://fantasy.wizzlebin.com/health`

**Default Login:**
- Username: `admin`
- Password: `admin123` (CHANGE THIS!)

---

## 🐛 Troubleshooting

### Build Failed on Railway
- Check "Deployments" tab for error logs
- Verify `requirements.txt` is committed
- Ensure all environment variables are set

### Can't Access Custom Domain
- Verify DNS record is correct (CNAME pointing to Railway URL)
- Wait longer (DNS can take 60 minutes)
- Check `dig fantasy.wizzlebin.com` output

### SSL Not Working
- Wait 5-10 minutes after DNS propagates
- Railway auto-provisions SSL
- Check Railway dashboard for SSL status

### WordPress Link Not Showing
- Verify menu is assigned to a theme location
- Clear WordPress cache
- Try a different browser/incognito

---

## 📞 Need Help?

**Railway Support:**
- Discord: https://discord.gg/railway
- Twitter: @Railway

**Check deployment guide:** `deployment/docs/railway-deployment.md`

---

**🎉 You're ready to deploy! Start with Step 1 above.**
