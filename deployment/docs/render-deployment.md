# 🚀 Deploy to Render.com

**Render** is a powerful PaaS with excellent GitHub integration and automatic SSL certificates. Great for production deployments with straightforward pricing.

## ✅ Prerequisites

- GitHub account
- Render account (sign up at [render.com](https://render.com))
- Your code pushed to a GitHub repository

---

## 📋 Deployment Steps

### 1. Prepare Your Repository

Ensure your code is on GitHub:

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 2. Create Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. Click "**New +**" → "**Web Service**"
3. Connect your GitHub account (if not already connected)
4. Select your repository: `Python app fantasy score calculator_1`
5. Click "**Connect**"

### 3. Configure Service Settings

Fill in the deployment form:

**Basic Settings:**
```
Name: ipl-fantasy-league
Region: Oregon (US West) [or closest to your users]
Branch: main
Runtime: Python 3
```

**Build Settings:**
```
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker --log-level info
```

**Plan:**
```
Instance Type: Starter ($7/month) or Free (limited)
```

### 4. Set Environment Variables

Scroll to **Environment Variables** section:

Click "**Add Environment Variable**" for each:

```env
# Required
RAPIDAPI_KEY=your_rapidapi_key_here
SECRET_KEY=your_generated_secret_key_here

# Environment
ENVIRONMENT=production
HOST=0.0.0.0
PORT=10000

# Security
RATE_LIMIT=60
CORS_ORIGINS=*
FORCE_HTTPS=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Note:** Render uses PORT=10000 by default, but sets it automatically.

### 5. Add Optional Files

#### render.yaml (Optional - Infrastructure as Code)

Create `render.yaml` in your repository root for easier configuration:

```yaml
services:
  - type: web
    name: ipl-fantasy-league
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: RAPIDAPI_KEY
        sync: false
      - key: SECRET_KEY
        generateValue: true
      - key: LOG_LEVEL
        value: INFO
      - key: RATE_LIMIT
        value: 60
      - key: FORCE_HTTPS
        value: true
    healthCheckPath: /health
```

### 6. Deploy!

1. Click "**Create Web Service**"
2. Render will:
   - Clone your repository
   - Install dependencies
   - Start your application
3. Watch logs in real-time during deployment

### 7. Access Your Application

Render provides a URL like:
```
https://ipl-fantasy-league.onrender.com
```

Test: Open URL and login with `admin`/`admin123`

---

## 🌐 Custom Domain Setup (fantasy.wizzlebin.com)

### Step 1: Add Custom Domain in Render

1. Go to your service dashboard
2. Click "**Settings**" tab
3. Scroll to "**Custom Domains**"
4. Click "**Add Custom Domain**"
5. Enter: `fantasy.wizzlebin.com`
6. Click "**Save**"

### Step 2: Configure DNS

Render will show you DNS records to add. Go to your domain registrar:

**Option A: CNAME Record (Recommended)**
```
Type: CNAME
Name: fantasy
Value: ipl-fantasy-league.onrender.com
TTL: 3600
```

**Option B: A Records (if CNAME not supported at apex)**
```
Type: A
Name: fantasy
Value: [IP addresses provided by Render]
TTL: 3600
```

### Step 3: Verify Domain

1. Wait 5-60 minutes for DNS propagation
2. Check status in Render dashboard
3. Render automatically provisions SSL certificate (Let's Encrypt)

**Verify DNS:**
```bash
dig fantasy.wizzlebin.com
# or
nslookup fantasy.wizzlebin.com
```

### Step 4: Update CORS Settings

Once domain is active, update environment variables:

```env
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com,https://www.wizzlebin.com
FORCE_HTTPS=true
```

---

## 💾 Persistent Storage with Render Disks

Render's default filesystem is **ephemeral** (resets on deploy). For persistent data:

### Create a Disk

1. Go to your service → **Settings**
2. Scroll to "**Disks**"
3. Click "**Add Disk**"
4. Configure:
   ```
   Name: ipl-data
   Mount Path: /app/data
   Size: 1 GB (adjust as needed)
   ```
5. Click "**Save**"

### Update Your Code (Already Done)

Your app already uses `data/` directory, so it will automatically persist!

---

## 📊 Monitoring & Logs

### View Logs

1. Dashboard → Your Service → **Logs** tab
2. Real-time streaming logs
3. Search and filter available

### Metrics

1. Dashboard → Your Service → **Metrics** tab
2. View:
   - CPU usage
   - Memory usage
   - Network traffic
   - Request rate

### Health Checks

Render automatically checks `/health` endpoint every 30 seconds.

Configure in **Settings** → **Health Check Path**: `/health`

---

## 🔧 Advanced Configuration

### Auto-Deploy from GitHub

**Enable in Settings:**
```
Settings → Build & Deploy → Auto-Deploy: Yes
```

Now every push to `main` branch triggers deployment!

### Preview Environments

Render can create preview environments for pull requests:

1. Settings → **Preview Environments**
2. Enable "**Create preview environments for pull requests**"

### Background Workers (Optional)

For long-running tasks, add a background worker:

1. Dashboard → New → **Background Worker**
2. Use same repo
3. Start command: `python worker.py`

---

## 💰 Pricing

**Free Tier:**
- Limited to 750 hours/month
- Spins down after 15 minutes of inactivity
- **Good for testing only**

**Starter ($7/month):**
- Always on
- No spin down
- 512 MB RAM, 0.5 CPU
- **Recommended for this app**

**Standard ($25/month):**
- 2 GB RAM, 1 CPU
- Better performance for high traffic

**Disk Storage:**
- $0.25/GB/month

**Typical total cost:** $7-10/month

---

## 🐛 Troubleshooting

### Build Fails

**Python version mismatch:**
Add `runtime.txt`:
```
python-3.14.3
```

**Missing dependencies:**
Verify `requirements.txt` includes all packages.

### Service Won't Start

**Check logs:**
```
Dashboard → Logs tab
```

**Common issues:**
1. Missing `RAPIDAPI_KEY` or `SECRET_KEY`
2. Wrong start command (must use gunicorn)
3. PORT binding issues (use `0.0.0.0:$PORT`)

### Health Check Failing

**Verify endpoint:**
```bash
curl https://your-app.onrender.com/health
```

Should return:
```json
{"status": "healthy", "service": "ipl-fantasy-league"}
```

### Slow First Request

**Symptom:** App sleeps after inactivity (Free tier only)

**Solution:** Upgrade to Starter plan ($7/month) for always-on service.

---

## 🔒 Security Best Practices

### 1. Change Default Password

After deployment, immediately change admin password:
```python
# In web/auth.py or use admin panel
```

### 2. Secure Environment Variables

- Never commit `.env` to GitHub
- Use Render's encrypted environment variables
- Rotate SECRET_KEY periodically

### 3. Enable HTTPS Only

```env
FORCE_HTTPS=true
```

### 4. Configure Proper CORS

```env
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com
```

---

## ✅ Post-Deployment Checklist

- [ ] Application accessible at Render URL
- [ ] Login works
- [ ] All pages load correctly
- [ ] Static files serving (CSS, JS)
- [ ] Dark mode toggle works
- [ ] Downloads work
- [ ] Analytics charts render
- [ ] Custom domain configured
- [ ] SSL certificate active (HTTPS)
- [ ] Disk mounted for persistent data
- [ ] Health check passing
- [ ] Logs showing no errors
- [ ] Changed default admin password

---

## 🔗 Useful Links

- Render Dashboard: https://dashboard.render.com
- Render Docs: https://render.com/docs
- Status Page: https://status.render.com
- Community Forum: https://community.render.com

---

## 📞 Support

**Render Support:**
- Email: support@render.com
- Community: https://community.render.com
- Twitter: @render

**Application Issues:**
- Check Render logs
- Review environment variables
- Test /health endpoint

---

## 🎯 Render vs Railway

**Render Pros:**
✅ More predictable pricing
✅ Built-in persistent disk storage
✅ Excellent documentation
✅ Preview environments for PRs

**Railway Pros:**
✅ Simpler interface
✅ Better free tier
✅ Faster deployments
✅ Usage-based pricing

**Recommendation:** Both are excellent! Render for production, Railway for quick prototypes.

---

**🎉 Congratulations!** Your IPL Fantasy League is now live on Render!

Next: [Custom Domain Setup](./custom-domain.md) | [VPS Deployment](./vps-deployment.md)
