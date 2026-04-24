#!/bin/bash
# Deployment script for IPL Fantasy League

set -e

echo "=================================================="
echo "  IPL Fantasy League - Deployment Script"
echo "=================================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root (sudo)"
    exit 1
fi

# Variables
APP_DIR="/opt/ipl-fantasy"
SERVICE_NAME="ipl-fantasy"
NGINX_SITE="ipl-fantasy"
APP_USER="www-data"

echo ""
echo "1. Installing system dependencies..."
apt-get update
apt-get install -y python3-pip python3-venv nginx certbot python3-certbot-nginx

echo ""
echo "2. Creating application directory..."
mkdir -p $APP_DIR
chown $APP_USER:$APP_USER $APP_DIR

echo ""
echo "3. Setting up Python virtual environment..."
cd $APP_DIR
sudo -u $APP_USER python3 -m venv venv
sudo -u $APP_USER venv/bin/pip install --upgrade pip

echo ""
echo "4. Installing Python packages..."
sudo -u $APP_USER venv/bin/pip install -r requirements.txt

echo ""
echo "5. Setting up systemd service..."
cp deployment/ipl-fantasy.service /etc/systemd/system/$SERVICE_NAME.service
# Prompt for configuration
echo ""
echo "Edit /etc/systemd/system/$SERVICE_NAME.service to set:"
echo "  - WorkingDirectory=$APP_DIR"
echo "  - SECRET_KEY (generate with: python -c 'import secrets; print(secrets.token_hex(32))')"
echo "  - RAPIDAPI_KEY"
read -p "Press Enter after editing the service file..."

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo ""
echo "6. Setting up Nginx..."
cp deployment/nginx.conf /etc/nginx/sites-available/$NGINX_SITE
# Update paths in nginx config
sed -i "s|/path/to/app|$APP_DIR|g" /etc/nginx/sites-available/$NGINX_SITE
echo ""
echo "Edit /etc/nginx/sites-available/$NGINX_SITE to set your domain name"
read -p "Press Enter after editing the Nginx config..."

ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx

echo ""
echo "7. Setting up SSL certificate with Let's Encrypt..."
echo "Your domain must be pointing to this server's IP"
read -p "Enter your domain name: " DOMAIN
certbot --nginx -d $DOMAIN

echo ""
echo "=================================================="
echo "  Deployment Complete!"
echo "=================================================="
echo ""
echo "Service status: systemctl status $SERVICE_NAME"
echo "View logs:      journalctl -u $SERVICE_NAME -f"
echo "Nginx config:   /etc/nginx/sites-available/$NGINX_SITE"
echo ""
echo "Access your app at: https://$DOMAIN"
echo ""
echo "IMPORTANT NEXT STEPS:"
echo "1. Change the admin password (see WEB_README.md)"
echo "2. Set up regular backups of $APP_DIR/data/"
echo "3. Configure firewall (ufw allow 80,443/tcp)"
echo ""
