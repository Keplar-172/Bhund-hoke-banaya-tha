# 🌐 Custom Domain Setup Guide

This guide covers setting up `fantasy.wizzlebin.com` as a custom subdomain for your IPL Fantasy League application, regardless of your deployment platform.

---

## 📋 Overview

**What you'll do:**
1. Point DNS subdomain to your application
2. Configure SSL certificate
3. Update application CORS settings
4. Verify everything works

**Time Required:** 15-60 minutes (mostly waiting for DNS propagation)

---

## 🎯 Step 1: Get Your Application URL

First, identify where your app is hosted:

### Railway
After deployment, Railway provides:
```
https://ipl-fantasy-production-xxxx.up.railway.app
```

### Render
After deployment, Render provides:
```
https://ipl-fantasy-league.onrender.com
```

### VPS (DigitalOcean/Linode/etc.)
Your server's IP address:
```
123.456.789.012
```

**Note this down** - you'll need it for DNS configuration.

---

## 🔧 Step 2: Configure DNS Records

### Access Your DNS Management

Go to where you manage wizzlebin.com DNS. This could be:
- **Domain Registrar** (GoDaddy, Namecheap, Google Domains, etc.)
- **DNS Provider** (Cloudflare, Route53, etc.)
- **Hosting Provider** (if hosting wizzlebin.com there)

### Add DNS Record

Navigate to DNS settings for `wizzlebin.com`.

#### Option A: CNAME Record (Recommended for PaaS)

**Use if deploying to Railway or Render:**

```
Type: CNAME
Name: fantasy
Value: ipl-fantasy-production-xxxx.up.railway.app  (Railway)
   OR: ipl-fantasy-league.onrender.com  (Render)
TTL: 3600 (or Auto)
```

**Example Screenshot:**
```
┌──────┬─────────┬──────────────────────────────────────────┬──────┐
│ Type │  Name   │               Value                      │ TTL  │
├──────┼─────────┼──────────────────────────────────────────┼──────┤
│CNAME │ fantasy │ ipl-fantasy-production-xxxx.railway.app  │ 3600 │
└──────┴─────────┴──────────────────────────────────────────┴──────┘
```

#### Option B: A Record (Required for VPS)

**Use if deploying to your own server:**

```
Type: A
Name: fantasy
Value: 123.456.789.012  (your server IP)
TTL: 3600 (or Auto)
```

**Example Screenshot:**
```
┌──────┬─────────┬─────────────────┬──────┐
│ Type │  Name   │      Value      │ TTL  │
├──────┼─────────┼─────────────────┼──────┤
│  A   │ fantasy │ 123.456.789.012 │ 3600 │
└──────┴─────────┴─────────────────┴──────┘
```

### Common DNS Providers

#### GoDaddy
1. Login → My Products → DNS
2. Click "Add" under Records
3. Select Type, enter Name and Value
4. Save

#### Cloudflare
1. Login → Select wizzlebin.com
2. Click "DNS" tab
3. Click "Add record"
4. Fill in details, ensure proxy status (cloud icon) is OFF for initial setup
5. Save

#### Namecheap
1. Login → Domain List → Manage
2. Advanced DNS tab
3. Add New Record
4. Fill in details → Save

#### Google Domains
1. Login → My domains → wizzlebin.com
2. DNS tab → Custom records
3. Create new record
4. Save

---

## ⏱️ Step 3: Wait for DNS Propagation

DNS changes take time to propagate globally:
- **Minimum:** 5-15 minutes
- **Typical:** 30-60 minutes
- **Maximum:** 24-48 hours (rare)

### Check DNS Propagation

**Option A: Using command line**
```bash
# Check A record
dig fantasy.wizzlebin.com

# Check CNAME record
dig fantasy.wizzlebin.com CNAME

# Alternative
nslookup fantasy.wizzlebin.com
```

**Expected output:**
```
;; ANSWER SECTION:
fantasy.wizzlebin.com. 3600 IN CNAME ipl-fantasy-production.railway.app.
```
or
```
;; ANSWER SECTION:
fantasy.wizzlebin.com. 3600 IN A 123.456.789.012
```

**Option B: Online tools**
- https://www.whatsmydns.net/
- https://dnschecker.org/
- Enter `fantasy.wizzlebin.com` and check multiple locations

---

## 🔐 Step 4: Configure SSL Certificate

### Railway (Automatic)

1. Go to your Railway project dashboard
2. Click on your service
3. Navigate to **Settings** → **Domains**
4. Click "**Custom Domain**"
5. Enter: `fantasy.wizzlebin.com`
6. Click "**Add Domain**"
7. Railway automatically provisions SSL (1-5 minutes)
8. Done! HTTPS will work automatically.

### Render (Automatic)

1. Go to your Render dashboard
2. Select your web service
3. Click **Settings** tab
4. Scroll to "**Custom Domains**"
5. Click "**Add Custom Domain**"
6. Enter: `fantasy.wizzlebin.com`
7. Click "**Save**"
8. Render automatically provisions Let's Encrypt SSL (1-5 minutes)
9. Done! HTTPS will work automatically.

### VPS (Manual with Certbot)

SSH into your server:
```bash
ssh appuser@YOUR_SERVER_IP
```

Obtain SSL certificate:
```bash
sudo certbot --nginx -d fantasy.wizzlebin.com
```

Follow the prompts:
1. Enter your email address
2. Agree to Terms of Service (Y)
3. Share email with EFF (optional)
4. Choose option 2: Redirect HTTP to HTTPS

Certbot will:
- Generate SSL certificates
- Update Nginx configuration
- Enable HTTPS
- Setup HTTP → HTTPS redirect

**Test auto-renewal:**
```bash
sudo certbot renew --dry-run
```

**Done!** Your site is now secured with HTTPS.

---

## 🔧 Step 5: Update Application Configuration

### Update Environment Variables

Update your `.env` or platform environment variables:

```env
# Update CORS to allow your domain
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com,https://www.wizzlebin.com

# Enable HTTPS redirect
FORCE_HTTPS=true
```

### Apply Changes

**Railway:**
- Update in Settings → Environment Variables
- Deployment happens automatically

**Render:**
- Update in Settings → Environment
- Click "Save Changes"
- Redeploy if needed

**VPS:**
```bash
cd /home/appuser/ipl-fantasy
nano .env  # Update variables
sudo systemctl restart ipl-fantasy
```

---

## ✅ Step 6: Verify Everything Works

### 1. Test HTTPS Access

Open in browser:
```
https://fantasy.wizzlebin.com
```

**Should see:**
- 🔒 Secure padlock icon in address bar
- Login page loads
- No security warnings

### 2. Test HTTP Redirect

Open in browser:
```
http://fantasy.wizzlebin.com
```

**Should:**
- Automatically redirect to HTTPS version
- Show secure padlock

### 3. Test All Features

- [ ] Login works
- [ ] Dashboard loads
- [ ] Navigation works
- [ ] Static files load (CSS, JS)
- [ ] Charts render
- [ ] Downloads work
- [ ] Dark mode toggle works

### 4. Check SSL Certificate

**Browser method:**
1. Click padlock icon in address bar
2. View certificate details
3. Verify:
   - Issued to: fantasy.wizzlebin.com
   - Valid dates
   - Trusted certificate authority

**Command line:**
```bash
curl -I https://fantasy.wizzlebin.com
# Should show HTTP/2 200 and no SSL errors
```

**Online tool:**
- https://www.ssllabs.com/ssltest/
- Test `fantasy.wizzlebin.com`
- Should get **A or A+** rating

---

## 🔗 Step 7: Integrate with Main Website

### Add Navigation Link on wizzlebin.com

Edit your main website's navigation to include the fantasy league:

**Example HTML:**
```html
<nav>
  <a href="https://wizzlebin.com">Home</a>
  <a href="https://wizzlebin.com/about">About</a>
  <a href="https://fantasy.wizzlebin.com">Fantasy League 🏏</a>
  <a href="https://wizzlebin.com/contact">Contact</a>
</nav>
```

**Example for WordPress:**
1. Dashboard → Appearance → Menus
2. Add Custom Link:
   - URL: `https://fantasy.wizzlebin.com`
   - Link Text: `Fantasy League 🏏`
3. Save Menu

### Match Branding (Optional)

To make the fantasy league match wizzlebin.com style:

1. Get main site colors/fonts
2. Update `web/static/style.css` variables:
```css
:root {
  --primary-color: #YOUR_BRAND_COLOR;
  --font-family: 'Your Brand Font', sans-serif;
}
```
3. Redeploy

---

## 🐛 Troubleshooting

### DNS Not Resolving

**Symptom:** `fantasy.wizzlebin.com` doesn't resolve or shows old IP

**Solutions:**
1. Wait longer (DNS can take up to 24-48 hours)
2. Clear your DNS cache:
   ```bash
   # Mac
   sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
   
   # Windows
   ipconfig /flushdns
   
   # Linux
   sudo systemd-resolve --flush-caches
   ```
3. Try accessing from different device/network
4. Verify DNS record is correct in registrar

### SSL Certificate Not Working

**Symptom:** Browser shows "Not Secure" or certificate error

**Solutions:**

**For PaaS (Railway/Render):**
1. Ensure DNS propagation is complete
2. Remove and re-add custom domain
3. Wait a few more minutes
4. Check platform status page

**For VPS:**
1. Verify Nginx configuration:
   ```bash
   sudo nginx -t
   ```
2. Check certificate files exist:
   ```bash
   sudo ls -la /etc/letsencrypt/live/fantasy.wizzlebin.com/
   ```
3. Re-run certbot:
   ```bash
   sudo certbot --nginx -d fantasy.wizzlebin.com --force-renewal
   ```

### Application Not Loading

**Symptom:** 502 Bad Gateway or 500 errors

**Solutions:**
1. Check application is running:
   ```bash
   # VPS
   sudo systemctl status ipl-fantasy
   
   # PaaS
   Check platform logs
   ```
2. Verify environment variables are set
3. Check application logs for errors
4. Ensure PORT is correct

### CORS Errors

**Symptom:** Console shows "blocked by CORS policy"

**Solution:**
Update `CORS_ORIGINS` environment variable:
```env
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com
```

Restart application.

---

## 📊 Verification Checklist

- [ ] DNS record added correctly (CNAME or A)
- [ ] DNS propagation complete (`dig` command shows correct value)
- [ ] Application accessible at `https://fantasy.wizzlebin.com`
- [ ] HTTPS working (secure padlock visible)
- [ ] HTTP → HTTPS redirect working
- [ ] SSL certificate valid (no browser warnings)
- [ ] All application features working
- [ ] CORS configured correctly
- [ ] Navigation link added on main site (wizzlebin.com)
- [ ] Branding matches (if desired)

---

## 📱 Mobile Testing

Test on mobile devices:
1. Open `https://fantasy.wizzlebin.com` on phone
2. Verify responsive design
3. Test all key features
4. Check navigation from main site

---

## 🎉 Success!

Your fantasy league is now accessible at:
```
https://fantasy.wizzlebin.com
```

**Share with users and enjoy!** 🏏

---

## 🔗 Additional Resources

- **DNS Propagation Checker:** https://www.whatsmydns.net/
- **SSL Test:** https://www.ssllabs.com/ssltest/
- **Certbot Documentation:** https://certbot.eff.org/
- **Railway Custom Domains:** https://docs.railway.app/deploy/exposing-your-app#custom-domains
- **Render Custom Domains:** https://render.com/docs/custom-domains

---

**Need help?** Refer back to your platform-specific deployment guide:
- [Railway Deployment](./railway-deployment.md)
- [Render Deployment](./render-deployment.md)
- [VPS Deployment](./vps-deployment.md)
