# 🚀 Deployment Documentation

Complete guides for deploying the IPL Fantasy League 2026 to production.

---

## 📚 Available Guides

### 🎯 Quick Start

**Choose your deployment platform:**

1. **[Railway.app](docs/railway-deployment.md)** ⭐ **Recommended for Beginners**
   - Easiest setup (5-10 minutes)
   - Automatic SSL certificates
   - Free tier available
   - Auto-deploy from GitHub
   - **Best for:** Quick deployment, prototypes, small-medium traffic

2. **[Render.com](docs/render-deployment.md)** ⭐ **Recommended for Production**
   - Straightforward deployment
   - Built-in persistent storage
   - Predictable pricing
   - Excellent documentation
   - **Best for:** Production apps, reliable hosting

3. **[VPS (DigitalOcean/Linode)](docs/vps-deployment.md)** ⭐ **For Advanced Users**
   - Full control over server
   - Most flexible configuration
   - Requires Linux knowledge
   - Manual SSL setup
   - **Best for:** Custom requirements, learning, full control

---

## 📖 Documentation Index

| Guide | Purpose | Time Required |
|-------|---------|---------------|
| [Railway Deployment](docs/railway-deployment.md) | Deploy to Railway PaaS | 10-15 min |
| [Render Deployment](docs/render-deployment.md) | Deploy to Render PaaS | 15-20 min |
| [VPS Deployment](docs/vps-deployment.md) | Deploy to your own server | 30-60 min |
| [Custom Domain Setup](docs/custom-domain.md) | Configure fantasy.wizzlebin.com | 15-60 min |
| [Production Checklist](docs/production-checklist.md) | Pre/post deployment verification | 30 min |

---

## 🎯 Recommended Deployment Path

### For Most Users (Easiest)

```
1. Choose Railway or Render
2. Follow deployment guide (10-15 min)
3. Setup custom domain (15-30 min)
4. Complete production checklist
5. Go live! 🎉
```

### For Advanced Users

```
1. Setup VPS (DigitalOcean recommended)
2. Follow VPS deployment guide (30-60 min)
3. Configure Nginx + SSL (included in guide)
4. Setup custom domain
5. Configure monitoring & backups
6. Go live! 🎉
```

---

## ✅ Prerequisites

Before deploying, ensure you have:

### Required
- [ ] GitHub account with repository
- [ ] RapidAPI key for Cricbuzz API
- [ ] Domain access (wizzlebin.com DNS management)
- [ ] Email address for SSL certificates

### For PaaS (Railway/Render)
- [ ] Platform account (free signup)
- [ ] Credit card for paid plans (optional for free tier)

### For VPS
- [ ] SSH key or password
- [ ] Basic Linux command-line knowledge
- [ ] 30-60 minutes for setup

---

## 🎯 Platform Comparison

| Feature | Railway | Render | VPS |
|---------|---------|--------|-----|
| **Difficulty** | ⭐ Easy | ⭐⭐ Easy | ⭐⭐⭐⭐ Advanced |
| **Setup Time** | 10 min | 15 min | 60 min |
| **Auto SSL** | ✅ Yes | ✅ Yes | ❌ Manual |
| **Persistent Storage** | ⚠️ Limited | ✅ Built-in | ✅ Full |
| **Control** | ⚠️ Limited | ⚠️ Limited | ✅ Full |
| **Starting Price** | Free tier | Free tier | $5/mo |
| **Production Ready** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Scaling** | Auto | Auto | Manual |
| **Monitoring** | Built-in | Built-in | DIY |

---

## 💰 Cost Comparison

### Railway
- **Free Tier:** $5 credit/month
- **Hobby:** $5/month + usage
- **Typical Cost:** $5-10/month

### Render
- **Free Tier:** Limited (spins down)
- **Starter:** $7/month
- **Typical Cost:** $7-15/month (with storage)

### VPS
- **DigitalOcean:** $6/month (1GB RAM)
- **Linode:** $5/month (1GB RAM)
- **Hetzner:** $4/month (2GB RAM)
- **Typical Cost:** $5-10/month

**Recommendation:** All options are affordable. Choose based on your technical comfort level.

---

## 🚀 Quick Deploy (Railway Example)

```bash
# 1. Prepare repository
git add .
git commit -m "Prepare for deployment"
git push origin main

# 2. Go to Railway
# - Visit railway.app
# - Click "New Project" → "Deploy from GitHub"
# - Select your repository

# 3. Add Environment Variables
RAPIDAPI_KEY=your_key_here
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
ENVIRONMENT=production

# 4. Deploy!
# Railway deploys automatically

# 5. Add Custom Domain
# - Settings → Domains → Add custom domain
# - Enter: fantasy.wizzlebin.com
# - Update DNS (CNAME record)
# - Done! 🎉
```

**Detailed instructions:** [Railway Deployment Guide](docs/railway-deployment.md)

---

## 🔧 Configuration Files

This deployment setup includes:

### Production Configuration
- **`config_prod.py`** - Production-specific settings
- **`.env.example`** - Environment variable template
- **`web/middleware.py`** - Security middleware (CORS, rate limiting, headers)
- **`web/logger.py`** - Structured logging system

### Docker Support
- **`Dockerfile`** - Production-ready container image
- **`docker-compose.yml`** - Multi-container orchestration
- **`.dockerignore`** - Exclude unnecessary files

### Server Configuration
- **`deployment/nginx.conf`** - Nginx reverse proxy config (VPS)
- **`deployment/systemd/ipl-fantasy.service`** - Systemd service (VPS)

---

## 📋 Environment Variables

Required for all deployments:

```env
# Required
RAPIDAPI_KEY=your_rapidapi_key
SECRET_KEY=generate_64_char_secret

# Environment
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

# Security
RATE_LIMIT=60
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com
FORCE_HTTPS=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 🔐 Security Considerations

### Before Deployment
- [ ] Change default admin password (`admin`/`admin123`)
- [ ] Set strong `SECRET_KEY` (64+ characters)
- [ ] Configure `CORS_ORIGINS` to specific domains
- [ ] Enable `FORCE_HTTPS=true` in production
- [ ] Review rate limiting settings

### After Deployment
- [ ] Monitor logs for suspicious activity
- [ ] Keep dependencies updated
- [ ] Regular security audits
- [ ] Backup data regularly

---

## 📊 Monitoring & Maintenance

### Health Check Endpoint
```bash
curl https://fantasy.wizzlebin.com/health
```

Returns:
```json
{
  "status": "healthy",
  "service": "ipl-fantasy-league",
  "version": "1.0.0",
  "environment": "production"
}
```

### Logging

**PaaS (Railway/Render):**
- View logs in platform dashboard
- Real-time streaming
- Search and filter

**VPS:**
```bash
# Application logs
tail -f /home/appuser/ipl-fantasy/logs/app.log

# Service logs
sudo journalctl -u ipl-fantasy -f

# Nginx logs
tail -f /var/log/nginx/ipl-fantasy-error.log
```

---

## 🐛 Troubleshooting

Common issues and solutions:

### Application Won't Start
1. Check environment variables (especially `SECRET_KEY`, `RAPIDAPI_KEY`)
2. Review logs for error messages
3. Verify dependencies installed correctly
4. Check health endpoint

### SSL Certificate Issues
1. Verify DNS propagation complete
2. Wait 5-10 minutes after domain setup
3. Check platform status page
4. For VPS: Re-run certbot

### Performance Issues
1. Check server resources (CPU, memory)
2. Review application logs for errors
3. Consider scaling up (more workers, bigger instance)
4. Enable caching if needed

**Full troubleshooting:** See individual deployment guides

---

## 📞 Support

### Platform Support
- **Railway:** Discord (https://discord.gg/railway) or Twitter (@Railway)
- **Render:** Email (support@render.com) or Community Forum
- **VPS:** Provider-specific support channels

### Application Issues
1. Check deployment guide troubleshooting section
2. Review application logs
3. Verify environment variables
4. Test health endpoint
5. Check [Production Checklist](docs/production-checklist.md)

---

## 🎓 Learning Resources

### Platform Documentation
- [Railway Docs](https://docs.railway.app)
- [Render Docs](https://render.com/docs)
- [DigitalOcean Tutorials](https://www.digitalocean.com/community/tutorials)

### General DevOps
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/docs/)

---

## 🚀 Next Steps

After successful deployment:

1. **[✓] Complete Checklist** - [Production Checklist](docs/production-checklist.md)
2. **[✓] Setup Monitoring** - Configure alerts and logging
3. **[✓] User Documentation** - Create user guide
4. **[✓] Announce Launch** - Social media, blog post
5. **[✓] Gather Feedback** - Monitor usage and improve

---

## 📝 Contributing

Found an issue in the deployment docs? Want to add a guide for another platform?

1. Fork the repository
2. Make your changes
3. Submit a pull request

---

## 📄 License

This deployment documentation is part of the IPL Fantasy League 2026 project.

---

**Ready to deploy?** Choose a guide above and get started! 🚀

**Questions?** Check the [Production Checklist](docs/production-checklist.md) or platform-specific troubleshooting sections.

**🎉 Good luck with your deployment!**
