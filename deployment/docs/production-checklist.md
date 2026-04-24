# ✅ Production Deployment Checklist

Complete this checklist before deploying your IPL Fantasy League to production.

---

## 📋 Pre-Deployment

### Code Preparation

- [ ] All code committed to Git
- [ ] `.gitignore` excludes sensitive files (`.env`, `venv/`, etc.)
- [ ] No hardcoded secrets in code
- [ ] No `print()` statements (use logging instead)
- [ ] All features tested locally
- [ ] Requirements.txt up to date

### Environment Configuration

- [ ] `.env.example` file created with all required variables
- [ ] Production `.env` file ready (not committed to Git)
- [ ] `RAPIDAPI_KEY` obtained and set
- [ ] `SECRET_KEY` generated securely (64 characters minimum)
- [ ] `ENVIRONMENT=production` set
- [ ] `DEBUG=false` in production
- [ ] `RELOAD=false` in production

### Security

- [ ] Change default admin password (`admin`/`admin123`)
- [ ] Review and update `USERS_DB` in config.py
- [ ] `FORCE_HTTPS=true` for production domain
- [ ] `CORS_ORIGINS` set to specific domains (not `*`)
- [ ] Rate limiting configured appropriately
- [ ] Session cookies set to `secure` and `httponly`

---

## 🚀 Deployment

### Platform Setup (Choose One)

**Railway:**
- [ ] GitHub repository connected
- [ ] Environment variables configured
- [ ] Build command set: `pip install -r requirements.txt`
- [ ] Start command set: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 4 --worker-class uvicorn.workers.UvicornWorker`
- [ ] Health check endpoint configured: `/health`
- [ ] Deployment successful

**Render:**
- [ ] GitHub repository connected
- [ ] Environment variables configured
- [ ] Build command set
- [ ] Start command set
- [ ] Disk mounted for persistent data (1GB recommended)
- [ ] Health check path set: `/health`
- [ ] Deployment successful

**VPS (DigitalOcean/Linode):**
- [ ] Server created and accessible via SSH
- [ ] Firewall configured (ports 22, 80, 443)
- [ ] Dependencies installed (Python, Nginx, Certbot)
- [ ] Application code cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] Systemd service configured and running
- [ ] Nginx reverse proxy configured
- [ ] Nginx configuration tested: `sudo nginx -t`

---

## 🌐 Domain & SSL

### DNS Configuration

- [ ] Domain registrar account accessible
- [ ] DNS records updated:
  - CNAME or A record for `fantasy.wizzlebin.com`
  - Pointing to deployment platform or server IP
- [ ] DNS propagation complete (5-60 minutes)
- [ ] Verify with `dig fantasy.wizzlebin.com`

### SSL Certificate

**PaaS (Railway/Render):**
- [ ] Custom domain added in dashboard
- [ ] SSL automatically provisioned
- [ ] HTTPS accessible

**VPS:**
- [ ] Certbot installed
- [ ] SSL certificate obtained: `sudo certbot --nginx -d fantasy.wizzlebin.com`
- [ ] HTTP to HTTPS redirect configured
- [ ] Auto-renewal enabled: `sudo certbot renew --dry-run`
- [ ] Nginx reloaded: `sudo systemctl reload nginx`

---

## 🔍 Verification

### Application Access

- [ ] Homepage loads: `https://fantasy.wizzlebin.com`
- [ ] Login page accessible
- [ ] Can login with credentials
- [ ] Dashboard displays correctly
- [ ] All navigation links work

### Functionality Testing

- [ ] Leaderboard displays team scores
- [ ] Match history shows processed matches
- [ ] Master scoresheet loads
- [ ] Analytics dashboard renders charts
- [ ] Excel downloads work
- [ ] Dark mode toggle works
- [ ] Search functionality works
- [ ] Sortable tables work
- [ ] Expandable sections work

### Performance Testing

- [ ] Health check responds: `https://fantasy.wizzlebin.com/health`
- [ ] Page load time < 3 seconds
- [ ] Static files loading correctly (CSS, JS)
- [ ] No browser console errors
- [ ] No 404 errors in logs
- [ ] Charts render without delay

### Security Testing

- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] Security headers present (check browser dev tools)
- [ ] Session cookies have `Secure` and `HttpOnly` flags
- [ ] Rate limiting works (test by spamming requests)
- [ ] CORS policy enforced
- [ ] No sensitive data in client-side code

### Mobile Testing

- [ ] Responsive design works on mobile
- [ ] All buttons clickable
- [ ] Navigation menu works
- [ ] Forms submit correctly
- [ ] Charts visible and interactive

---

## 📊 Monitoring Setup

### Logging

- [ ] Application logs configured
- [ ] Log level set appropriately (INFO for production)
- [ ] Log file path accessible
- [ ] Log rotation configured (if VPS)
- [ ] Can access logs in platform dashboard or via SSH

### Health Monitoring

**PaaS:**
- [ ] Platform monitoring dashboard accessible
- [ ] Email/Slack alerts configured
- [ ] Uptime monitoring enabled

**VPS:**
- [ ] Netdata or similar tool installed (optional)
- [ ] Log monitoring setup
- [ ] Disk space monitoring
- [ ] CPU/Memory alerts configured

### Backup Strategy

**PaaS:**
- [ ] Data persistence enabled (Render Disk, Railway Volume)
- [ ] Automatic backups configured (if available)

**VPS:**
- [ ] Backup script created
- [ ] Cron job scheduled (daily recommended)
- [ ] Backup restoration tested
- [ ] Offsite backup location configured

---

## 🔒 Post-Deployment Security

### Immediate Actions

- [ ] Change default admin password
- [ ] Remove or disable test accounts
- [ ] Review user permissions
- [ ] Verify no debug endpoints exposed

### Ongoing Maintenance

- [ ] Setup dependency update alerts (GitHub Dependabot)
- [ ] Schedule regular security audits
- [ ] Monitor application logs daily
- [ ] Review failed login attempts
- [ ] Keep dependencies updated

---

## 📢 Integration with Main Website

### wizzlebin.com Integration

- [ ] Add navigation link on wizzlebin.com to fantasy subdomain
- [ ] Match branding/styling (colors, fonts, logo)
- [ ] Add announcement/blog post about fantasy league
- [ ] Update site footer with fantasy league link
- [ ] Test navigation flow from main site to fantasy subdomain

### Social Media

- [ ] Announce deployment on social channels
- [ ] Share fantasy.wizzlebin.com link
- [ ] Provide user instructions
- [ ] Highlight key features

---

## 📝 Documentation

### User Documentation

- [ ] User guide created (how to use the fantasy league)
- [ ] Login instructions shared with users
- [ ] Scoring rules documented
- [ ] FAQ section created

### Admin Documentation

- [ ] Deployment process documented
- [ ] Maintenance procedures documented
- [ ] Troubleshooting guide available
- [ ] Contact information for support

---

## 🚨 Rollback Plan

### Preparation

- [ ] Previous version tagged in Git
- [ ] Rollback procedure documented
- [ ] Database/data backup before deployment
- [ ] Quick access to platform dashboard

### Rollback Steps (if needed)

**PaaS:**
```bash
# Revert to previous deployment in dashboard
# Or redeploy previous Git commit
```

**VPS:**
```bash
# Checkout previous version
cd /home/appuser/ipl-fantasy
git checkout <previous-commit-hash>
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ipl-fantasy
```

---

## 📈 Performance Optimization

### Optional Enhancements

- [ ] Enable CDN for static files (Cloudflare)
- [ ] Setup Redis for caching (if high traffic)
- [ ] Configure database connection pooling
- [ ] Enable Gzip compression
- [ ] Optimize images and assets
- [ ] Implement lazy loading for charts

---

## 🎯 Success Metrics

### Track These Metrics

- [ ] Application uptime %
- [ ] Average response time
- [ ] Number of active users
- [ ] Page views per day
- [ ] Error rate
- [ ] Peak concurrent users
- [ ] Database/storage usage

---

## ✅ Final Sign-Off

**Before going live:**

- [ ] All above items checked
- [ ] Stakeholders notified
- [ ] Support team briefed
- [ ] Monitoring dashboard accessible
- [ ] Emergency contacts documented

**Deployment Date:** _______________

**Deployed By:** _______________

**Platform:** □ Railway  □ Render  □ VPS (__________)

**Domain:** fantasy.wizzlebin.com

**Approved By:** _______________

---

## 🔗 Quick Reference

**Application URLs:**
- Production: https://fantasy.wizzlebin.com
- Health Check: https://fantasy.wizzlebin.com/health
- API Docs: https://fantasy.wizzlebin.com/docs (dev only)

**Admin Access:**
- Username: admin
- Password: [CHANGED FROM DEFAULT]

**Platform Dashboard:**
- Railway: https://railway.app/dashboard
- Render: https://dashboard.render.com
- VPS: ssh appuser@YOUR_SERVER_IP

**Important Files:**
- Configuration: `config_prod.py`, `.env`
- Logs: `logs/app.log`
- Data: `data/` directory
- Backups: Platform-specific or `/home/appuser/backups/`

---

## 📞 Emergency Contacts

**Technical Issues:**
- Developer: _____________
- Platform Support: _____________

**Domain/DNS:**
- Domain Registrar: _____________
- DNS Support: _____________

**Application Issues:**
- Check logs first
- Review health endpoint
- Consult deployment guide
- Contact support if needed

---

**🎉 Congratulations on your production deployment!**

Remember to:
- Monitor logs regularly
- Keep dependencies updated
- Backup data frequently
- Review security settings periodically

**Need help?** Check deployment guides in `/deployment/docs/`
