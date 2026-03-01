# 🏜️ DESERTAS DEPLOYMENT GUIDE

This guide covers deployment options for the DESERTAS framework, including the live dashboard, API services, documentation, and data repositories.

---

## Quick Deployments

### Netlify (Dashboard)

The DESERTAS interactive dashboard is pre-configured for Netlify deployment.

#### Automatic Deployment

1. Connect your Git repository to Netlify
2. Use these settings:
   - Build command: `cd dashboard && npm run build` (if using Node) or leave empty
   - Publish directory: `dashboard/dist` or `dashboard`
   - Environment variables: none required

3. Or use the `netlify.toml` configuration:
```toml
[build]
  publish = "dashboard"

[build.environment]
  PYTHON_VERSION = "3.11"

[[redirects]]
  from = "/api/*"
  to = "https://desertas.netlify.app/api/:splat"
  status = 200
  force = true

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
```

Manual Deployment

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
netlify deploy --prod --dir=dashboard
```

Live dashboard: https://desertas.netlify.app
API endpoint: https://desertas.netlify.app/api

---

ReadTheDocs (Documentation)

Deploy technical documentation to ReadTheDocs.

Configuration

1. Connect your Git repository to readthedocs.org
2. Use the .readthedocs.yaml configuration in this repository
3. Build documentation automatically on push

Documentation: https://desertas.readthedocs.io

---

PyPI (Python Package)

Deploy the core DESERTAS package to PyPI.

Preparation

```bash
# Install build tools
pip install build twine

# Update version in setup.py/pyproject.toml
# Version: 1.0.0

# Create distribution files
python -m build
```

Upload to PyPI

```bash
# Upload to production PyPI
twine upload dist/*

# Install
pip install desertas
```

PyPI package: https://pypi.org/project/desertas

---

Docker Deployment

Build Image

```dockerfile
# Dockerfile
FROM python:3.10-slim

LABEL maintainer="gitdeeper@gmail.com"
LABEL version="1.0.0"
LABEL description="DESERTAS - Desert Gas Intelligence Framework"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DESERTAS_HOME=/opt/desertas \
    DESERTAS_CONFIG=/etc/desertas/config.yaml

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash desertas && \
    mkdir -p /opt/desertas && \
    mkdir -p /etc/desertas && \
    mkdir -p /data/field && \
    mkdir -p /data/backup && \
    chown -R desertas:desertas /opt/desertas /etc/desertas /data

USER desertas
WORKDIR /opt/desertas

COPY --chown=desertas:desertas requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

COPY --chown=desertas:desertas . .

RUN pip install --user -e .

EXPOSE 8000 8501

CMD ["desertas", "serve", "--all"]
```

Build and Run

```bash
# Build image
docker build -t desertas:1.0.0 .

# Run container
docker run -d \
  --name desertas-prod \
  -p 8000:8000 \
  -p 8501:8501 \
  -v /host/data:/data \
  -v /host/config:/etc/desertas \
  -e DESERTAS_CONFIG=/etc/desertas/config.yaml \
  --restart unless-stopped \
  desertas:1.0.0
```

---

Docker Compose (Full Stack)

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: desertas-postgres
    environment:
      POSTGRES_DB: desertas
      POSTGRES_USER: desertas_user
      POSTGRES_PASSWORD: ${DB_PASSWORD:-change_me}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    networks:
      - desertas-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U desertas_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build: .
    container_name: desertas-api
    command: desertas serve --api --host 0.0.0.0 --port 8000
    environment:
      DESERTAS_CONFIG: /etc/desertas/config.yaml
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: desertas
      DB_USER: desertas_user
      DB_PASSWORD: ${DB_PASSWORD}
      API_URL: https://desertas.netlify.app/api
    volumes:
      - ./config:/etc/desertas
      - ./data:/data
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - desertas-network
    restart: unless-stopped

  dashboard:
    build: .
    container_name: desertas-dashboard
    command: desertas serve --dashboard --host 0.0.0.0 --port 8501
    environment:
      DESERTAS_CONFIG: /etc/desertas/config.yaml
      API_URL: http://api:8000
      PUBLIC_API_URL: https://desertas.netlify.app/api
    volumes:
      - ./config:/etc/desertas
    ports:
      - "8501:8501"
    depends_on:
      - api
    networks:
      - desertas-network
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: desertas-nginx
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
      - ./www:/var/www/html
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
      - dashboard
    networks:
      - desertas-network
    restart: unless-stopped

networks:
  desertas-network:
    driver: bridge

volumes:
  postgres_data:
```

Deploy with Docker Compose

```bash
# Set environment variables
export DB_PASSWORD=$(openssl rand -base64 32)

# Create directories
mkdir -p config data backups ssl www

# Copy configuration
cp config/desertas.prod.yaml config/config.yaml

# Start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

Configuration

Production Configuration

```yaml
# config/desertas.prod.yaml
# DESERTAS Production Configuration

version: 1.0
environment: production

server:
  host: 0.0.0.0
  port: 8000
  workers: 4
  timeout: 120

database:
  host: postgres
  port: 5432
  name: desertas
  user: desertas_user
  password: ${DB_PASSWORD}
  pool_size: 20

monitoring:
  metrics_enabled: true
  metrics_port: 9090

security:
  jwt_secret: ${JWT_SECRET}
  jwt_expiry_hours: 24
  rate_limit: 100/minute
  cors_origins:
    - https://desertas.netlify.app
    - https://desertas.readthedocs.io

api:
  public_url: https://desertas.netlify.app/api
  docs_url: https://desertas.readthedocs.io/api

field_data:
  upload_dir: /data/uploads
  max_file_size: 1GB
  allowed_formats:
    - .csv
    - .npy
    - .json
```

---

Monitoring

Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'desertas'
    static_configs:
      - targets: ['api:8000', 'dashboard:8501']
    metrics_path: /metrics
    scrape_interval: 15s
```

Grafana Dashboard

Import the DESERTAS dashboard template to visualize:

· DRGIS scores across stations
· Rn_pulse activity in real-time
· Parameter correlations
· Early warning alerts
· System health metrics

---

Backup & Recovery

Automated Backup Script

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"

# Database backup
pg_dump -h postgres -U desertas_user desertas | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Field data backup
tar -czf $BACKUP_DIR/field_data_$DATE.tar.gz /data/field

# Configuration backup
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /etc/desertas

# Clean old backups (keep 30 days)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup completed: $DATE"
```

---

Quick Reference

```bash
# Netlify Dashboard
https://desertas.netlify.app
https://desertas.netlify.app/api

# PyPI Package
pip install desertas

# Docker
docker pull gitlab.com/gitdeeper4/desertas:latest

# Documentation
https://desertas.readthedocs.io

# Source Code
https://gitlab.com/gitdeeper4/desertas
https://github.com/gitdeeper4/desertas
```

---

Support

For deployment assistance:

· Dashboard: https://desertas.netlify.app
· Documentation: https://desertas.readthedocs.io
· Issues: https://gitlab.com/gitdeeper4/desertas/-/issues
· Email: deploy@desertas.org
· Principal Investigator: gitdeeper@gmail.com

---

🏜️ The desert breathes. DESERTAS decodes.

DOI: 10.14293/DESERTAS.2026.001
