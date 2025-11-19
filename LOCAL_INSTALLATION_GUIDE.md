# Complete Local Installation Guide for TALE-Webtool
## From Setup to Domain Access via Cloudflare

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Initial Installation](#initial-installation)
3. [Security Configuration (Change Passwords)](#security-configuration)
4. [Testing Local Installation](#testing-local-installation)
5. [Getting a Domain on Cloudflare](#getting-a-domain-on-cloudflare)
6. [Setting Up Cloudflare Tunnel (Recommended)](#setting-up-cloudflare-tunnel)
7. [Alternative: Cloudflare as DNS + Local Reverse Proxy](#alternative-cloudflare-dns-with-nginx)
8. [Final Testing and Verification](#final-testing-and-verification)
9. [Maintenance and Troubleshooting](#maintenance-and-troubleshooting)

---

## Prerequisites

### Hardware Requirements 
- **RAM:** Recommended 8GB+
- **Storage:** At least 100GB free space
- **CPU:** Any. Faster CPU will provide faster results

### Software Requirements
- **Operating System:** Linux 
- **Docker:** Version 20.10+
- **Docker Compose:** Version 2.0+
- **Internet Connection:** For website hosting

### Install Docker and Docker Compose

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (to run docker without sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Log out and log back in for group changes to take effect
# Then verify installation
docker --version
docker compose version
```

---

## Initial Installation

### Step 1: Navigate to Project Directory

```bash
cd /home/user/TALE-Webtool
```

### Step 2: Check Current Files

```bash
ls -la
# You should see: docker-compose.yml, Dockerfile, app/, templates/, static/, etc.
```

### Step 3: Create Environment File

```bash
# Create .env file for configuration
cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql+asyncpg://tale_user:CHANGEME_DB_PASSWORD@postgres:5432/tale_db
POSTGRES_USER=tale_user
POSTGRES_PASSWORD=CHANGEME_DB_PASSWORD
POSTGRES_DB=tale_db

# Security
SECRET_KEY=CHANGEME_SECRET_KEY

# Application Settings
DEBUG=False
SESSION_RETENTION_DAYS=7

# Server Configuration
HOST=0.0.0.0
PORT=8000
EOF

echo ".env file created. You MUST change the passwords before starting!"
```

---

## Security Configuration

### Step 1: Generate Secure Secret Key

```bash
# Generate a secure random secret key
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

**Copy the output** (it will look like: `SECRET_KEY=xK7jP9mN...`)

### Step 2: Generate Secure Database Password

```bash
# Generate a secure database password
python3 -c "import secrets; print('DB_PASSWORD=' + secrets.token_urlsafe(24))"
```

**Copy the output** (it will look like: `DB_PASSWORD=aB3xY9...`)

### Step 3: Update .env File with Secure Values

```bash
# Edit .env file
nano .env
```

**Replace the following:**
1. Replace `CHANGEME_SECRET_KEY` with your generated secret key
2. Replace both instances of `CHANGEME_DB_PASSWORD` with your generated database password

**Example of what your .env should look like:**
```bash
DATABASE_URL=postgresql+asyncpg://tale_user:xK7jP9mN2qL5wR8tY@postgres:5432/tale_db
POSTGRES_USER=tale_user
POSTGRES_PASSWORD=xK7jP9mN2qL5wR8tY
POSTGRES_DB=tale_db

SECRET_KEY=aB3xY9zC6vN1mK4pQ7sT2wE5rU8iO0uY

DEBUG=False
SESSION_RETENTION_DAYS=7

HOST=0.0.0.0
PORT=8000
```

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 4: Update docker-compose.yml

```bash
# Edit docker-compose.yml to use environment variables
nano docker-compose.yml
```

**Find the postgres service section and update it:**

```yaml
  postgres:
    image: postgres:15-alpine
    container_name: tale_postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
```

**Find the app service section and update the DATABASE_URL:**

```yaml
  app:
    build: .
    container_name: tale_app
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: ${DATABASE_URL}
      SECRET_KEY: ${SECRET_KEY}
      DEBUG: ${DEBUG}
      SESSION_RETENTION_DAYS: ${SESSION_RETENTION_DAYS}
```

**Save and exit:** Press `Ctrl+X`, then `Y`, then `Enter`

### Step 5: Set Proper Permissions

```bash
# Restrict .env file permissions (important for security)
chmod 600 .env

# Verify permissions
ls -l .env
# Should show: -rw------- (only owner can read/write)
```

---

## Testing Local Installation

### Step 1: Start the Services

```bash
# Build and start containers
docker compose up -d --build

# This will:
# 1. Build the application Docker image
# 2. Start PostgreSQL database
# 3. Wait for database to be healthy
# 4. Start the FastAPI application
# 5. Run database migrations
```

### Step 2: Check Service Status

```bash
# Check if containers are running
docker compose ps

# You should see both containers with "Up" status:
# tale_postgres - Up (healthy)
# tale_app - Up (healthy)
```

### Step 3: View Logs

```bash
# View application logs
docker compose logs -f app

# In another terminal, check postgres logs
docker compose logs -f postgres

# Press Ctrl+C to stop viewing logs
```

### Step 4: Test Local Access

```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Expected response:
# {"status":"healthy","database":"connected"}

# Test web interface
curl -I http://localhost:8000/
# Should return: HTTP/1.1 200 OK
```

### Step 5: Access from Browser on Your Network

1. **Find your minicomputer's local IP address:**
   ```bash
   hostname -I | awk '{print $1}'
   # Example output: 192.168.1.100
   ```

2. **Open browser on any device on your network:**
   - Navigate to: `http://192.168.1.100:8000`
   - You should see the TALE Pair Finder interface

3. **Test the application:**
   - Try a simple search with sample DNA sequence
   - Verify results are displayed

**If you can access it locally, your installation is successful!** ✓

---

## Getting a Domain on Cloudflare

### Option 1: Register a New Domain Through Cloudflare

#### Step 1: Create Cloudflare Account
1. Go to [https://dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up)
2. Enter your email and create a password
3. Verify your email address

#### Step 2: Register a Domain
1. Log in to Cloudflare Dashboard
2. Click **"Domain Registration"** in the left sidebar
3. Click **"Register Domains"**
4. Search for available domains 
5. Add domain to cart and purchase 

---

## Setting Up Cloudflare Tunnel (Recommended)

Cloudflare Tunnel provides secure access without opening ports on your router or requiring a public IP address. This is the best option for quick setup.


### Step 1: Install Cloudflare Tunnel (cloudflared)

```bash
# Download and install cloudflared for Linux
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb

# For x86_64 (Intel/AMD) systems, use:
# wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb

# Install the package
sudo dpkg -i cloudflared-linux-arm64.deb

# Verify installation
cloudflared --version
```

### Step 2: Authenticate with Cloudflare

```bash
# This will open a browser for authentication
cloudflared tunnel login
```

**What happens:**
1. A browser window opens to Cloudflare
2. Select your domain from the list
3. Authorize cloudflared
4. Certificate is saved to `~/.cloudflared/cert.pem`

### Step 3: Create a Tunnel

```bash
# Create a tunnel named "tale-tool"
cloudflared tunnel create tale-tool

# Output will show:
# Tunnel credentials written to /home/user/.cloudflared/<TUNNEL-ID>.json
# Created tunnel tale-tool with id <TUNNEL-ID>

# Copy the TUNNEL-ID from the output - you'll need it!
```

### Step 4: Create Tunnel Configuration File

```bash
# Create config directory if it doesn't exist
mkdir -p ~/.cloudflared

# Create configuration file
nano ~/.cloudflared/config.yml
```

**Paste the following** (replace `<TUNNEL-ID>` and `mytaletools.com` with your values):

```yaml
tunnel: <TUNNEL-ID>
credentials-file: /home/user/.cloudflared/<TUNNEL-ID>.json

ingress:
  # Route your domain to the TALE application
  - hostname: mytaletools.com
    service: http://localhost:8000

  # Optional: Add www subdomain
  - hostname: www.mytaletools.com
    service: http://localhost:8000

  # Catch-all rule (required as last entry)
  - service: http_status:404
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

### Step 5: Route DNS to Your Tunnel

```bash
# Route your domain to the tunnel
cloudflared tunnel route dns tale-tool mytaletools.com

# Add www subdomain (optional)
cloudflared tunnel route dns tale-tool www.mytaletools.com
```

**Output:**
```
Added CNAME mytaletools.com which will route to this tunnel
```

### Step 6: Start the Tunnel

```bash
# Test the tunnel first
cloudflared tunnel run tale-tool

# You should see:
# INF Connection <ID> registered
# INF Connection <ID> registered
# INF Connection <ID> registered
# INF Connection <ID> registered
# (4 connections = healthy tunnel)

# Press Ctrl+C to stop
```

### Step 7: Install Tunnel as System Service

```bash
# Install as a system service
sudo cloudflared service install

# Start the service
sudo systemctl start cloudflared

# Enable autostart on boot
sudo systemctl enable cloudflared

# Check status
sudo systemctl status cloudflared
```

### Step 8: Verify Tunnel in Cloudflare Dashboard

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Select your domain
3. Click **"Zero Trust"** in the left sidebar
4. Click **"Networks"** → **"Tunnels"**
5. You should see your tunnel **"tale-tool"** with status **"Healthy"**

### Step 9: Test Your Domain

```bash
# From any computer (not just your local network):
curl -I https://mytaletools.com

# Expected response:
# HTTP/2 200
# ...
```

**Open your browser and navigate to:**
- `https://mytaletools.com`

**You should see your TALE Pair Finder application!** ✓

**Cloudflare automatically provides:**
- HTTPS/SSL certificate (automatic)
- HTTP to HTTPS redirect

---

## Alternative: Cloudflare DNS with Nginx

If you prefer to expose your minicomputer directly to the internet (requires public IP and port forwarding):

### Prerequisites
- Static public IP address or Dynamic DNS
- Ability to forward ports 80 and 443 on your router
- Nginx installed on your minicomputer

### Step 1: Install Nginx

```bash
sudo apt update
sudo apt install nginx -y
```

### Step 2: Configure Nginx as Reverse Proxy

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/tale-tool
```

**Paste the following** (replace `mytaletools.com`):

```nginx
server {
    listen 80;
    server_name mytaletools.com www.mytaletools.com;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to FastAPI application
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;

        # Preserve headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed in future)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /api/health {
        proxy_pass http://localhost:8000/api/health;
        access_log off;
    }
}
```

**Save and exit:** `Ctrl+X`, `Y`, `Enter`

### Step 3: Enable Nginx Configuration

```bash
# Create symbolic link to enable site
sudo ln -s /etc/nginx/sites-available/tale-tool /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Step 4: Configure Cloudflare DNS

1. Go to Cloudflare Dashboard
2. Select your domain
3. Click **"DNS"** → **"Records"**
4. Click **"Add record"**
5. Configure:
   - **Type:** A
   - **Name:** @ (for root domain) or www
   - **IPv4 address:** Your public IP address
   - **Proxy status:** Toggle **ON** (orange cloud)
   - **TTL:** Auto
6. Click **"Save"**

**Find your public IP:**
```bash
curl ifconfig.me
```

### Step 5: Configure Port Forwarding on Router

1. Log into your router (typically `192.168.1.1` or `192.168.0.1`)
2. Find **Port Forwarding** or **NAT** settings
3. Add two rules:
   - **Rule 1:** External Port 80 → Internal IP (minicomputer) Port 80
   - **Rule 2:** External Port 443 → Internal IP (minicomputer) Port 443

### Step 6: Set Up HTTPS with Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d mytaletools.com -d www.mytaletools.com

# Follow prompts:
# - Enter email address
# - Agree to terms
# - Choose whether to redirect HTTP to HTTPS (recommended: yes)

# Test automatic renewal
sudo certbot renew --dry-run
```

### Step 7: Configure Cloudflare SSL/TLS Settings

1. In Cloudflare Dashboard, go to **SSL/TLS** → **Overview**
2. Set SSL/TLS encryption mode to **"Full (strict)"**
3. Go to **SSL/TLS** → **Edge Certificates**
4. Enable:
   - ✓ Always Use HTTPS
   - ✓ Automatic HTTPS Rewrites
   - ✓ Minimum TLS Version: 1.2

---

## Final Testing and Verification

### Test 1: DNS Resolution

```bash
# Check DNS resolution
nslookup mytaletools.com

# Should show Cloudflare IPs (if proxied)
```

### Test 2: HTTPS Certificate

```bash
# Check SSL certificate
curl -vI https://mytaletools.com 2>&1 | grep -i "SSL"

# Should show successful SSL handshake
```

### Test 3: Application Functionality

1. **Homepage:** Visit `https://mytaletools.com`
2. **API Health:** Visit `https://mytaletools.com/api/health`
3. **Run Test Search:**
   - Enter sample DNA sequence
   - Verify search completes
   - Check results display
   - Test CSV export

### Test 4: Performance

```bash
# Test response time
time curl -I https://mytaletools.com

# Should be under 2 seconds
```

### Test 5: From Different Networks

- Test from mobile phone (using cellular data, not WiFi)
- Test from a friend's computer
- Test from a VPN location

---

## Maintenance and Troubleshooting

**Check application status:**
```bash
docker compose ps
```

**View recent logs:**
```bash
docker compose logs --tail=100 app
```

**Restart services:**
```bash
docker compose restart
```

### Database Backup

```bash
# Create backup directory
mkdir -p ~/backups

# Backup database
docker exec tale_postgres pg_dump -U tale_user tale_db > ~/backups/tale_backup_$(date +%Y%m%d_%H%M%S).sql

# Automate backups with cron
crontab -e

# Add line for daily backup at 2 AM:
0 2 * * * docker exec tale_postgres pg_dump -U tale_user tale_db > ~/backups/tale_backup_$(date +\%Y\%m\%d).sql
```

### Update Application

```bash
cd /home/user/TALE-Webtool

# Pull latest code (if using git)
git pull

# Rebuild and restart
docker compose down
docker compose up -d --build
```

### Monitor Cloudflare Tunnel

```bash
# Check tunnel status
sudo systemctl status cloudflared

# View tunnel logs
sudo journalctl -u cloudflared -f

# Restart tunnel
sudo systemctl restart cloudflared
```

### Common Issues

#### Issue: Application won't start
```bash
# Check logs
docker compose logs app

# Common causes:
# - Database not ready
# - Port 8000 already in use
# - Invalid .env configuration

# Solution: Check database, change port, verify .env
```

#### Issue: Domain not accessible
```bash
# Check tunnel status (if using Cloudflare Tunnel)
sudo systemctl status cloudflared

# Check Nginx (if using reverse proxy)
sudo systemctl status nginx
sudo nginx -t

# Check DNS propagation
nslookup mytaletools.com
```

#### Issue: Database connection errors
```bash
# Check PostgreSQL container
docker compose logs postgres

# Verify credentials in .env match docker-compose.yml
cat .env | grep PASSWORD
```

#### Issue: Slow performance
```bash
# Check system resources
htop
# or
top

# Check Docker resource usage
docker stats

# Increase session retention if database is too large
nano .env
# Change: SESSION_RETENTION_DAYS=3
docker compose restart
```

### Security Best Practices

1. **Regularly update system:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Monitor access logs:**
   ```bash
   docker compose logs app | grep "POST /api/search"
   ```

3. **Review Cloudflare Security settings:**
   - Enable Bot Fight Mode
   - Configure Security Level
   - Set up Rate Limiting if needed

4. **Backup .env file securely:**
   ```bash
   cp .env .env.backup
   chmod 600 .env.backup
   # Store backup offline
   ```

5. **Monitor disk space:**
   ```bash
   df -h
   ```

---

## Summary

You now have:
- ✓ TALE-Webtool installed on your minicomputer
- ✓ Secure passwords configured
- ✓ Domain registered on Cloudflare
- ✓ HTTPS enabled with automatic certificate
- ✓ Application accessible from anywhere
- ✓ DDoS protection and CDN
- ✓ Automated backups configured

**Your application is now accessible at:** `https://mytaletools.com`

---

## Quick Reference Commands

```bash
# Start application
docker compose up -d

# Stop application
docker compose down

# View logs
docker compose logs -f app

# Restart application
docker compose restart

# Update application
git pull && docker compose up -d --build

# Backup database
docker exec tale_postgres pg_dump -U tale_user tale_db > backup.sql

# Check tunnel status (if using Cloudflare Tunnel)
sudo systemctl status cloudflared

# Restart tunnel
sudo systemctl restart cloudflared
```

---

## Need Help?

- **Application logs:** `docker compose logs -f app`
- **Database logs:** `docker compose logs -f postgres`
- **Tunnel logs:** `sudo journalctl -u cloudflared -f`
- **Nginx logs:** `sudo tail -f /var/log/nginx/error.log`
- **Cloudflare Dashboard:** [https://dash.cloudflare.com](https://dash.cloudflare.com)

---

**Version:** 1.0.1
**Last Updated:** 2025-11-19
**Application Version:** beta 0.2.0


