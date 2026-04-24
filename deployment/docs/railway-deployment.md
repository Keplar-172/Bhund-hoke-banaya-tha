# 🚀 Deploy to Railway.app

**Railway** is a modern Platform-as-a-Service (PaaS) that makes deployment incredibly easy. It's perfect for getting your IPL Fantasy League application online quickly.

## ✅ Prerequisites

- GitHub account
- Railway account (sign up at [railway.app](https://railway.app))
- Your code pushed to a GitHub repository

---

## 📋 Deployment Steps

### 1. Prepare Your Repository

Make sure your code is pushed to GitHub:

```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### 2. Create Railway Project

1. Go to [railway.app](https://railway.app) and login
2. Click "**New Project**"
3. Select "**Deploy from GitHub repo**"
4. Choose your repository: `Python app fantasy score calculator_1`
5. Railway will automatically detect it's a Python app

### 3. Configure Environment Variables

Click on your service → **Variables** tab → Add these:

```env
# Required
RAPIDAPI_KEY=your_rapidapi_key_here
SECRET_KEY=your_generated_secret_key_here

# Environment
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

# Security
RATE_LIMIT=60
CORS_ORIGINS=*
FORCE_HTTPS=false

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Configure Build & Start Command

Railway should auto-detect settings, but verify:

**Build Command** (if needed):
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

### 5. Deploy!

Railway will automatically deploy your application. Watch the logs in the deployment tab.

### 6. Get Your URL

Once deployed, Railway provides a URL like:
```
https://ipl-fantasy-production-xxxx.up.railway.app
```

Test it: Open the URL and login with `admin`/`admin123`

---

## 🌐 Custom Domain Setup (fantasy.wizzlebin.com)

### Step 1: Add Custom Domain in Railway

1. Go to your Railway project
2. Click **Settings** → **Domains**
3. Click "**Custom Domain**"
4. Enter: `fantasy.wizzlebin.com`
5. Railway will show you DNS records to add

### Step 2: Update DNS Records

Go to your domain registrar (where you manage wizzlebin.com DNS):

**Add CNAME Record:**
```
Type: CNAME
Name: fantasy
Value: [provided by Railway, e.g., ipl-fantasy.up.railway.app]
TTL: 3600
```

**Or A Record (if CNAME not supported):**
```
Type: A
Name: fantasy
Value: [IP provided by Railway]
TTL: 3600
```

### Step 3: Wait for DNS Propagation

DNS changes can take 5-60 minutes. Check status:
```bash
dig fantasy.wizzlebin.com
```

### Step 4: Update CORS Settings

Once domain is active, update environment variables:
```env
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com
FORCE_HTTPS=true
```

---

## 🔧 Railway Configuration Options

### Scaling

Railway auto-scales based on traffic. Adjust resources:

1. Go to **Settings** → **Resources**
2. Set memory/CPU limits

### Persistent Storage

Railway provides ephemeral storage by default. For persistent data:

1. Add **Volume** in Railway dashboard
2. Mount at `/app/data`

### Monitoring

Railway provides built-in monitoring:
- **Metrics**: CPU, memory, network usage
- **Logs**: Real-time application logs
- **Deployments**: Version history

---

## 💰 Pricing

- **Free Tier**: $5 credit/month (great for testing)
- **Developer Plan**: $5/month + usage
- **Team Plan**: $20/month + usage

Typical cost for this app: **$5-10/month**

---

## 🐛 Troubleshooting

### Build Fails

**Error:** `Python version mismatch`
- Add `runtime.txt` with: `python-3.14.3`

**Error:** `Module not found`
- Verify all dependencies in `requirements.txt`

### Application Won't Start

**Check logs:**
```
Railway Dashboard → Logs tab
```

**Common issues:**
- Missing environment variables (especially SECRET_KEY)
- PORT variable not set (Railway auto-sets this)
- Health check failing (check /health endpoint)

### Database Connection Issues

**Currently using JSON files** - works fine for Railway ephemeral storage.

For production with high traffic:
- Consider Railway Postgres addon
- Or external MongoDB Atlas

---

## ✅ Post-Deployment Checklist

- [ ] Application accessible at Railway URL
- [ ] Login works (admin/admin123)
- [ ] All pages load correctly
- [ ] Dark mode toggle works
- [ ] Download Excel files work
- [ ] Analytics charts render
- [ ] Custom domain configured (fantasy.wizzlebin.com)
- [ ] HTTPS enabled
- [ ] Change default admin password!

---

## 🔗 Useful Links

- Railway Dashboard: https://railway.app/dashboard
- Railway Docs: https://docs.railway.app
- Deployment Logs: Check Railway project logs tab
- Health Check: https://your-app.up.railway.app/health

---

## 📞 Support

**Railway Support:**
- Discord: https://discord.gg/railway
- Twitter: @Railway

**Application Issues:**
- Check logs in Railway dashboard
- Review environment variables
- Verify SECRET_KEY and RAPIDAPI_KEY are set

---

**🎉 Congratulations!** Your IPL Fantasy League is now live on Railway!

Next: [Setup Custom Domain](./custom-domain.md) | [VPS Deployment](./vps-deployment.md)
