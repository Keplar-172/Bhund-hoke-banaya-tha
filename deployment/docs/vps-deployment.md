# 🚀 Deploy to VPS (DigitalOcean, Linode, AWS EC2)

This guide covers deploying your IPL Fantasy League to a **Virtual Private Server** (VPS). This gives you **full control** but requires more setup.

**Best for:** Advanced users who want full control, custom configurations, or need to integrate with existing infrastructure.

---

## ✅ Prerequisites

- VPS with **Ubuntu 22.04 LTS** (or 20.04)
- Root/sudo access via SSH
- Domain name with DNS access (wizzlebin.com)
- Basic Linux command-line knowledge

**Recommended VPS Providers:**
- **DigitalOcean** ($6-12/month) - Easiest for beginners
- **Linode** ($5-10/month) - Great performance
- **AWS EC2** (variable) - Most flexible
- **Hetzner** ($4-8/month) - Best value

---

## 📋 Step-by-Step Deployment

### 1. Create and Setup VPS

#### Option A: DigitalOcean Droplet

1. Go to [digitalocean.com](https://www.digitalocean.com)
2. Create a new Droplet:
   - **Image:** Ubuntu 22.04 LTS
   - **Plan:** Basic ($6/month - 1GB RAM sufficient)
   - **Datacenter:** Closest to your users
   - **Authentication:** SSH key (recommended) or password
3. Note your droplet's IP address

#### Option B: Linode/AWS/Other

Similar process - create Ubuntu 22.04 instance, note IP address.

### 2. Initial Server Setup

SSH into your server:
```bash
ssh root@YOUR_SERVER_IP
```

Update system packages:
```bash
apt update && apt upgrade -y
```

Create a non-root user:
```bash
adduser appuser
usermod -aG sudo appuser
```

Setup firewall:
```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

Switch to new user:
```bash
su - appuser
```

---

### 3. Install Dependencies

#### Install Python 3.14 (or 3.11+)

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.14 python3.14-venv python3.14-dev python3-pip
```

#### Install System Tools

```bash
sudo apt install -y git nginx certbot python3-certbot-nginx curl htop
```

#### Install Docker (Optional - for containerized deployment)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

Logout and login again for Docker permissions.

---

### 4. Clone Your Application

```bash
cd /home/appuser
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git ipl-fantasy
cd ipl-fantasy
```

---

### 5. Setup Python Environment

Create virtual environment:
```bash
python3.14 -m venv venv
source venv/bin/activate
```

Install dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 6. Configure Environment Variables

Create production `.env` file:
```bash
nano .env
```

Add your configuration:
```env
# Required
RAPIDAPI_KEY=your_rapidapi_key_here
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Environment
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000

# Security
RATE_LIMIT=100
CORS_ORIGINS=https://fantasy.wizzlebin.com,https://wizzlebin.com
FORCE_HTTPS=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=/home/appuser/ipl-fantasy/logs/app.log
```

Save and exit (`Ctrl+X`, then `Y`, then `Enter`).

---

### 7. Setup Systemd Service

Create systemd service file:
```bash
sudo nano /etc/systemd/system/ipl-fantasy.service
```

Add this configuration:
```ini
[Unit]
Description=IPL Fantasy League 2026
After=network.target

[Service]
Type=notify
User=appuser
Group=appuser
WorkingDirectory=/home/appuser/ipl-fantasy
Environment="PATH=/home/appuser/ipl-fantasy/venv/bin"
EnvironmentFile=/home/appuser/ipl-fantasy/.env
ExecStart=/home/appuser/ipl-fantasy/venv/bin/gunicorn app:app \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile /home/appuser/ipl-fantasy/logs/access.log \
    --error-logfile /home/appuser/ipl-fantasy/logs/error.log \
    --log-level info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Save and exit.

Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ipl-fantasy
sudo systemctl start ipl-fantasy
sudo systemctl status ipl-fantasy
```

Check logs if needed:
```bash
sudo journalctl -u ipl-fantasy -f
```

---

### 8. Configure Nginx Reverse Proxy

Create Nginx configuration:
```bash
sudo nano /etc/nginx/sites-available/ipl-fantasy
```

Add this configuration:
```nginx
upstream ipl_fantasy {
    server 127.0.0.1:8000;
}

# HTTP - Redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name fantasy.wizzlebin.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name fantasy.wizzlebin.com;

    # SSL certificates (will be configured by certbot)
    ssl_certificate /etc/letsencrypt/live/fantasy.wizzlebin.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fantasy.wizzlebin.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Logs
    access_log /var/log/nginx/ipl-fantasy-access.log;
    error_log /var/log/nginx/ipl-fantasy-error.log;

    # Static files
    location /static/ {
        alias /home/appuser/ipl-fantasy/web/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy to application
    location / {
        proxy_pass http://ipl_fantasy;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        proxy_pass http://ipl_fantasy/health;
        access_log off;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/ipl-fantasy /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### 9. Configure DNS

Go to your domain registrar and add:

**A Record:**
```
Type: A
Name: fantasy
Value: YOUR_SERVER_IP
TTL: 3600
```

Wait 5-60 minutes for DNS propagation.

**Verify:**
```bash
dig fantasy.wizzlebin.com
# Should show your server IP
```

---

### 10. Setup SSL with Let's Encrypt

Obtain SSL certificate:
```bash
sudo certbot --nginx -d fantasy.wizzlebin.com
```

Follow prompts:
- Enter email address
- Agree to terms
- Choose option 2 (redirect HTTP to HTTPS)

Certbot will automatically:
- Generate SSL certificates
- Update Nginx configuration
- Setup auto-renewal

**Test auto-renewal:**
```bash
sudo certbot renew --dry-run
```

---

## 🔧 Maintenance & Operations

### View Application Logs

```bash
# Systemd service logs
sudo journalctl -u ipl-fantasy -f

# Application logs
tail -f /home/appuser/ipl-fantasy/logs/app.log

# Nginx logs
tail -f /var/log/nginx/ipl-fantasy-access.log
tail -f /var/log/nginx/ipl-fantasy-error.log
```

### Restart Application

```bash
sudo systemctl restart ipl-fantasy
```

### Update Application

```bash
cd /home/appuser/ipl-fantasy
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ipl-fantasy
```

### Check Service Status

```bash
sudo systemctl status ipl-fantasy
sudo systemctl status nginx
```

### Monitor Resources

```bash
htop
df -h  # Disk usage
free -h  # Memory usage
```

---

## 📊 Monitoring & Alerts

### Setup Log Rotation

Create logrotate config:
```bash
sudo nano /etc/logrotate.d/ipl-fantasy
```

Add:
```
/home/appuser/ipl-fantasy/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 appuser appuser
    sharedscripts
    postrotate
        systemctl reload ipl-fantasy > /dev/null 2>&1 || true
    endscript
}
```

### Setup Monitoring (Optional)

**Install Netdata** (real-time monitoring):
```bash
bash <(curl -Ss https://my-netdata.io/kickstart.sh)
```

Access at: `http://YOUR_SERVER_IP:19999`

---

## 🔒 Security Hardening

### 1. Setup Fail2Ban (Prevent Brute Force)

```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 2. Disable Root Login

```bash
sudo nano /etc/ssh/sshd_config
```

Change:
```
PermitRootLogin no
PasswordAuthentication no  # If using SSH keys
```

Restart SSH:
```bash
sudo systemctl restart ssh
```

### 3. Setup Unattended Upgrades

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Regular Backups

Create backup script:
```bash
nano /home/appuser/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/appuser/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR
cd /home/appuser/ipl-fantasy

# Backup data
tar -czf $BACKUP_DIR/data_$DATE.tar.gz data/

# Keep only last 7 backups
find $BACKUP_DIR -name "data_*.tar.gz" -mtime +7 -delete
```

Make executable:
```bash
chmod +x /home/appuser/backup.sh
```

Add to crontab (daily at 2 AM):
```bash
crontab -e
```

Add:
```
0 2 * * * /home/appuser/backup.sh
```

---

## 💰 Cost Breakdown

**DigitalOcean Example:**
- Droplet (1GB RAM): $6/month
- Backups: $1.20/month (optional)
- **Total: ~$7-8/month**

**Linode:**
- Nanode (1GB RAM): $5/month

**AWS EC2:**
- t2.micro: ~$8-10/month

---

## 🐛 Troubleshooting

### Application Won't Start

**Check service status:**
```bash
sudo systemctl status ipl-fantasy
sudo journalctl -u ipl-fantasy -n 50
```

**Common issues:**
- Missing environment variables in `.env`
- Python virtual environment not activated
- Port 8000 already in use
- Permission issues on log files

### Nginx Errors

**Test configuration:**
```bash
sudo nginx -t
```

**Check logs:**
```bash
sudo tail -f /var/log/nginx/error.log
```

### SSL Certificate Issues

**Renew manually:**
```bash
sudo certbot renew
sudo systemctl reload nginx
```

### High Memory Usage

**Check processes:**
```bash
htop
```

**Reduce workers** in systemd service:
```ini
--workers 2  # Instead of 4
```

---

## ✅ Post-Deployment Checklist

- [ ] VPS created and accessible via SSH
- [ ] Firewall configured (ports 80, 443, 22)
- [ ] Application cloned and dependencies installed
- [ ] Environment variables configured
- [ ] Systemd service running
- [ ] Nginx configured and running
- [ ] DNS A record pointing to server IP
- [ ] SSL certificate installed
- [ ] HTTPS redirect working
- [ ] Application accessible at fantasy.wizzlebin.com
- [ ] All pages load correctly
- [ ] Downloads work
- [ ] Monitoring setup
- [ ] Backups configured
- [ ] Default admin password changed

---

## 🔗 Useful Commands

```bash
# Service management
sudo systemctl start|stop|restart|status ipl-fantasy

# View logs
sudo journalctl -u ipl-fantasy -f
tail -f logs/app.log

# Nginx
sudo nginx -t && sudo systemctl reload nginx

# SSL renewal
sudo certbot renew
```

---

**🎉 Congratulations!** Your IPL Fantasy League is now live on your own VPS with full control!

Next: [Monitoring Guide](./monitoring.md) | [Backup Strategy](./backups.md)
