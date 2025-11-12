# TALE Pair Finder - Deployment Guide

## Quick Start (Docker - Recommended)

### Prerequisites
- Docker and Docker Compose installed on your Debian server
- At least 2GB RAM available
- Port 8000 available

### Installation Steps

1. **Clone or copy the repository to your Debian server**
   ```bash
   cd /path/to/TALE-TALEN-tool
   ```

2. **Configure environment variables (optional)**
   ```bash
   # Edit .env file if needed
   nano .env
   ```

3. **Build and start the services**
   ```bash
   docker-compose up -d --build
   ```

4. **Check if services are running**
   ```bash
   docker-compose ps
   docker-compose logs -f
   ```

5. **Access the application**
   - Open browser: `http://your-server-ip:8000`
   - Health check: `http://your-server-ip:8000/api/health`

### Management Commands

**Start services:**
```bash
docker-compose up -d
```

**Stop services:**
```bash
docker-compose down
```

**View logs:**
```bash
docker-compose logs -f app
docker-compose logs -f postgres
```

**Restart services:**
```bash
docker-compose restart
```

**Update code and restart:**
```bash
git pull  # if using git
docker-compose down
docker-compose up -d --build
```

**Clean database and start fresh:**
```bash
docker-compose down -v  # WARNING: Deletes all data
docker-compose up -d --build
```

---

## Manual Installation (Without Docker)

### Prerequisites
- Python 3.10 or higher
- PostgreSQL 15 or higher
- pip

### Steps

1. **Install PostgreSQL**
   ```bash
   sudo apt update
   sudo apt install postgresql postgresql-contrib
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   ```

2. **Create database and user**
   ```bash
   sudo -u postgres psql
   ```

   In PostgreSQL shell:
   ```sql
   CREATE DATABASE tale_db;
   CREATE USER tale_user WITH PASSWORD 'tale_password';
   GRANT ALL PRIVILEGES ON DATABASE tale_db TO tale_user;
   \q
   ```

3. **Install Python dependencies**
   ```bash
   cd /path/to/TALE-TALEN-tool
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env
   # Update DATABASE_URL to: postgresql+asyncpg://tale_user:tale_password@localhost:5432/tale_db
   ```

5. **Run the application**
   ```bash
   # Development
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

   # Production with Gunicorn (install first: pip install gunicorn)
   gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

6. **Setup as systemd service (optional)**

   Create `/etc/systemd/system/tale-finder.service`:
   ```ini
   [Unit]
   Description=TALE Pair Finder
   After=network.target postgresql.service

   [Service]
   Type=notify
   User=your-user
   WorkingDirectory=/path/to/TALE-TALEN-tool
   Environment="PATH=/path/to/TALE-TALEN-tool/venv/bin"
   ExecStart=/path/to/TALE-TALEN-tool/venv/bin/gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable tale-finder
   sudo systemctl start tale-finder
   sudo systemctl status tale-finder
   ```

---

## Configuration

### Environment Variables

Edit `.env` file:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://tale_user:tale_password@postgres:5432/tale_db

# Security
SECRET_KEY=your-secure-random-key-here

# Application
DEBUG=False
SESSION_RETENTION_DAYS=7

# Server
HOST=0.0.0.0
PORT=8000
```

### Generate Secure Secret Key

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Monitoring and Maintenance

### Check Application Health
```bash
curl http://localhost:8000/api/health
```

### Database Backup
```bash
# With Docker
docker exec tale_postgres pg_dump -U tale_user tale_db > backup_$(date +%Y%m%d).sql

# Without Docker
pg_dump -U tale_user tale_db > backup_$(date +%Y%m%d).sql
```

### Database Restore
```bash
# With Docker
docker exec -i tale_postgres psql -U tale_user tale_db < backup_20241103.sql

# Without Docker
psql -U tale_user tale_db < backup_20241103.sql
```

### View Database Size
```bash
# With Docker
docker exec tale_postgres psql -U tale_user tale_db -c "SELECT pg_size_pretty(pg_database_size('tale_db'));"

# Without Docker
psql -U tale_user tale_db -c "SELECT pg_size_pretty(pg_database_size('tale_db'));"
```

### Manual Session Cleanup
```bash
# Connect to database and run cleanup
docker exec -it tale_postgres psql -U tale_user tale_db

# Then in PostgreSQL:
DELETE FROM tale_pairs WHERE session_id IN (
    SELECT session_id FROM search_sessions WHERE created_at < NOW() - INTERVAL '7 days'
);
DELETE FROM search_sessions WHERE created_at < NOW() - INTERVAL '7 days';
```

---

## Troubleshooting

### Application won't start
1. Check logs: `docker-compose logs app`
2. Verify PostgreSQL is running: `docker-compose ps`
3. Check environment variables in `.env`

### Database connection errors
1. Check PostgreSQL logs: `docker-compose logs postgres`
2. Verify credentials in `.env`
3. Test connection: `docker exec tale_postgres pg_isready -U tale_user`

### Port already in use
Change port in `docker-compose.yml`:
```yaml
ports:
  - "8001:8000"  # Change 8000 to your desired port
```

### Performance issues
1. Check system resources: `docker stats`
2. Increase worker count (manual installation)
3. Add more RAM if needed
4. Check database size and clean old sessions

### Cannot access from other machines
1. Check firewall: `sudo ufw allow 8000`
2. Verify application is binding to 0.0.0.0, not 127.0.0.1

---

## Upgrading

### Docker Installation
```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose up -d --build
```

### Manual Installation
```bash
# Pull latest code
git pull

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# Restart service
sudo systemctl restart tale-finder
```

---

## Performance Tuning

### For Large Sequences

1. **Increase workers** (manual installation)
   ```bash
   gunicorn app.main:app --workers 8 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

2. **PostgreSQL tuning** (edit postgresql.conf)
   ```
   shared_buffers = 256MB
   effective_cache_size = 1GB
   work_mem = 16MB
   ```

3. **Docker resource limits** (docker-compose.yml)
   ```yaml
   app:
     deploy:
       resources:
         limits:
           cpus: '2'
           memory: 2G
   ```

---

## Security Recommendations

1. **Change default passwords**
   - Update PostgreSQL password in `.env` and `docker-compose.yml`
   - Generate new SECRET_KEY

2. **Use reverse proxy** (Nginx example)
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Enable HTTPS** with Let's Encrypt
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

4. **Firewall configuration**
   ```bash
   sudo ufw allow 22     # SSH
   sudo ufw allow 80     # HTTP
   sudo ufw allow 443    # HTTPS
   sudo ufw enable
   ```

---

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Review this documentation
3. Check application status: `/api/health`

---

## Version Information

- **Application Version:** 2.0.0
- **Python:** 3.10+
- **PostgreSQL:** 15+
- **FastAPI:** 0.109.0+

---

## Technology Stack

- **Backend:** FastAPI 0.109+ (Python 3.10+)
- **Database:** PostgreSQL 15+ with AsyncIO
- **Frontend:** Vanilla JavaScript, DataTables, CSS3
- **Deployment:** Docker & Docker Compose

---

## API Endpoints

- `POST /api/search` - Initiate TALE pair search
- `GET /api/status/{session_id}` - Check search status
- `GET /api/results/{session_id}` - Get paginated results
- `GET /api/export/{session_id}` - Export results (CSV/TSV)
- `GET /api/health` - Health check

Interactive API documentation: `http://localhost:8000/docs`
