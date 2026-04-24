# IPL Fantasy Premier League 2026 - Web Interface

## Quick Start

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows

# Install/upgrade dependencies
pip install -r requirements.txt
```

### 2. Set Environment Variables (Optional)

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:
- `RAPIDAPI_KEY` - Your Cricbuzz API key (required for fetching new matches)
- `SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_hex(32))"`

### 3. Start Web Server

```bash
python main.py runserver
```

The web interface will be available at: **http://localhost:8000**

**Default Login:**
- Username: `admin`
- Password: `admin123`

⚠️ **IMPORTANT:** Change the admin password before deploying to production!

## Features

### Dashboard Pages

- **Leaderboard** - Current cumulative standings
- **Match History** - All processed matches with quick access to details
- **Master Scoresheet** - Comprehensive view across all matches
- **Match Detail** - Player-by-player breakdown for each match

### Download Exports

All existing Excel exports are available as authenticated downloads:

- Master Scoresheet (cumulative)
- Team Points (per match)
- Cricket Scorecards (per match)
- Team Rosters
- Analytics Dashboard

### Security

- Session-based authentication
- Password hashing with bcrypt
- Secure cookie settings for production
- Role-based access (admin/user)

## User Management

### Add New Users

1. Generate password hash:

```bash
python generate_password_hash.py
```

2. Add the generated entry to `config.py` in the `USERS_DB` dictionary

### Change Admin Password

1. Generate new hash with `generate_password_hash.py`
2. Replace the hash in `config.py` for the `admin` user

## CLI Commands (Still Available)

All existing CLI commands continue to work:

```bash
python main.py                    # Show leaderboard
python main.py matches            # List recent matches
python main.py score <match_id>   # Calculate scores
python main.py history            # Match history
python main.py master             # Master scoresheet
# ... and all other commands
```

## Production Deployment

### 1. Security Checklist

- [ ] Set strong `SECRET_KEY` in environment
- [ ] Change admin password
- [ ] Set `ENVIRONMENT=production`
- [ ] Use proper process manager (systemd, PM2, etc.)
- [ ] Configure reverse proxy (Nginx/Caddy) with TLS
- [ ] Set up firewall rules
- [ ] Regular backups of `data/` directory

### 2. Systemd Service (Linux)

Create `/etc/systemd/system/ipl-fantasy.service`:

```ini
[Unit]
Description=IPL Fantasy League Web Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/app
Environment="SECRET_KEY=your_secret_key"
Environment="RAPIDAPI_KEY=your_api_key"
Environment="ENVIRONMENT=production"
ExecStart=/path/to/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable ipl-fantasy
sudo systemctl start ipl-fantasy
```

### 3. Nginx Reverse Proxy

Example `/etc/nginx/sites-available/ipl-fantasy`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /path/to/app/web/static;
        expires 30d;
    }
}
```

### 4. Docker Deployment (Optional)

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t ipl-fantasy .
docker run -d -p 8000:8000 \
  -e SECRET_KEY="your_secret" \
  -e RAPIDAPI_KEY="your_key" \
  -v $(pwd)/data:/app/data \
  ipl-fantasy
```

## Troubleshooting

### Import Errors

If you see import errors, ensure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Can't Access Web Interface

1. Check the server is running: `python main.py runserver`
2. Verify firewall allows port 8000
3. Check logs for errors

### Authentication Issues

1. Verify `SECRET_KEY` is set and consistent
2. Clear browser cookies
3. Check `USERS_DB` in `config.py`

### Export Downloads Fail

1. Ensure `Match data/` directory exists and is writable
2. Check logs for openpyxl errors
3. Verify match data exists in `data/scorecards/`

## Architecture

```
app.py                      # FastAPI application entry point
main.py                     # CLI commands (includes runserver)
config.py                   # Configuration and security settings
web/
  ├── auth.py              # Authentication logic
  ├── services.py          # Data transformation layer
  ├── routers/
  │   ├── auth.py          # Login/logout routes
  │   ├── dashboard.py     # Dashboard pages
  │   └── downloads.py     # Export download endpoints
  ├── templates/           # Jinja2 HTML templates
  └── static/
      └── style.css        # CSS styles
```

## Support

For issues or questions:
1. Check existing CLI functionality still works
2. Review logs when running `python main.py runserver`
3. Verify environment variables are set correctly
