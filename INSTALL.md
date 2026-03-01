# 🍄 FUNGI-MYCEL INSTALLATION GUIDE

This guide covers installation of the FUNGI-MYCEL framework for mycelial network intelligence assessment.

---

## Table of Contents
- [System Requirements](#system-requirements)
- [Quick Installation](#quick-installation)
- [Detailed Installation](#detailed-installation)
  - [1. Python Environment](#1-python-environment)
  - [2. Install FUNGI-MYCEL](#2-install-fungi-mycel)
  - [3. Database Setup](#3-database-setup)
  - [4. Configuration](#4-configuration)
  - [5. Verify Installation](#5-verify-installation)
- [Platform-Specific Instructions](#platform-specific-instructions)
  - [Linux / Ubuntu](#linux--ubuntu)
  - [macOS](#macos)
  - [Windows](#windows)
  - [Termux (Android)](#termux-android)
- [Docker Installation](#docker-installation)
- [Development Installation](#development-installation)
- [Troubleshooting](#troubleshooting)

---

## System Requirements

### Minimum Requirements
- **Python**: 3.8 or higher
- **RAM**: 8 GB (16 GB recommended for large datasets)
- **Storage**: 10 GB free space
- **OS**: Linux, macOS, Windows, or Termux (Android)

### Optional Requirements
- **GPU**: CUDA-capable (for ML acceleration)
- **Database**: PostgreSQL 13+ (for production)
- **Microelectrode hardware**: For ρ_e field recordings

---

## Quick Installation

```bash
# Install from PyPI
pip install fungi-mycel

# Verify installation
fungi-mycel --version
fungi-mycel doctor  # Check system compatibility
```

---

Detailed Installation

1. Python Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

2. Install FUNGI-MYCEL

```bash
# Basic installation
pip install fungi-mycel

# With all optional dependencies
pip install "fungi-mycel[all]"

# Or specific extras
pip install "fungi-mycel[ml]"      # For machine learning features
pip install "fungi-mycel[viz]"      # For visualization
pip install "fungi-mycel[web]"      # For web dashboard
pip install "fungi-mycel[field]"    # For field data processing
pip install "fungi-mycel[dev]"      # For development
```

3. Database Setup (Optional)

For production deployments storing MNU data:

```bash
# Install PostgreSQL (Ubuntu)
sudo apt install postgresql postgresql-contrib

# Create database
sudo -u postgres createdb fungi_mycel
sudo -u postgres createuser --interactive
# Create fungi_mycel user with password

# Initialize schema
psql -U fungi_mycel -d fungi_mycel -f schema.sql
```

4. Configuration

```bash
# Create configuration directory
mkdir -p ~/.fungi_mycel
mkdir -p ~/.fungi_mycel/data
mkdir -p ~/.fungi_mycel/logs
mkdir -p ~/.fungi_mycel/recordings

# Copy default configuration
cp config/fungi_mycel.default.yaml ~/.fungi_mycel/config.yaml

# Edit configuration
nano ~/.fungi_mycel/config.yaml
# Set database credentials, API keys, electrode calibration data

# Set environment variable
export FUNGI_MYCEL_CONFIG=~/.fungi_mycel/config.yaml
# Add to .bashrc or .zshrc for persistence
```

5. Verify Installation

```bash
# Run diagnostics
fungi-mycel doctor

# Expected output:
# ✓ Python 3.8+ detected
# ✓ Dependencies installed
# ✓ Configuration file found
# ✓ MNIS module loaded
# ✓ Database connection successful (if configured)

# Run tests
pytest --pyargs fungi_mycel -v

# Test with sample data
fungi-mycel demo --site bialowieza

# Check parameter correlations
fungi-mycel check-correlation --rho-e --k-topo
```

---

Platform-Specific Instructions

Linux / Ubuntu

```bash
# Install system dependencies
sudo apt update
sudo apt install -y \
    python3.10 python3.10-dev python3.10-venv \
    build-essential libssl-dev libffi-dev \
    libgdal-dev gdal-bin \
    libhdf5-dev libnetcdf-dev \
    postgresql postgresql-contrib \
    ffmpeg  # For video processing of hyphal growth

# Install FUNGI-MYCEL
pip install fungi-mycel[all]
```

macOS

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and dependencies
brew install python@3.10
brew install hdf5 netcdf
brew install postgresql@14

# Install FUNGI-MYCEL
pip install fungi-mycel[all]
```

Windows

Using WSL2 (Recommended)

```bash
# In PowerShell as Administrator
wsl --install -d Ubuntu

# Then follow Linux instructions inside WSL
```

Native Windows

```bash
# Download Python 3.10 from python.org
# Open PowerShell as Administrator

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install FUNGI-MYCEL
pip install fungi-mycel[all]
```

Termux (Android)

For field data collection on mobile devices:

```bash
# Update packages
pkg update && pkg upgrade

# Install Python and dependencies
pkg install python python-pip
pkg install libxml2 libxslt
pkg install ffmpeg

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install FUNGI-MYCEL (core only, no ML)
pip install fungi-mycel

# Note: ML features are limited on mobile devices
# Use for field data collection and basic analysis only
```

---

Docker Installation

Using pre-built image

```bash
# Pull image
docker pull gitlab.com/fungi-mycel/fungi-mycel:latest

# Run container
docker run -it \
  --name fungi-mycel \
  -v ~/.fungi_mycel:/root/.fungi_mycel \
  -v ~/field_data:/data/field \
  -e FUNGI_MYCEL_CONFIG=/root/.fungi_mycel/config.yaml \
  -p 8501:8501 \
  gitlab.com/fungi-mycel/fungi-mycel:latest
```

Docker Compose (full stack)

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    image: gitlab.com/fungi-mycel/fungi-mycel:latest
    command: fungi-mycel serve --api
    ports:
      - "8000:8000"
    volumes:
      - ./config:/root/.fungi_mycel
      - ./data:/data
    environment:
      - FUNGI_MYCEL_CONFIG=/root/.fungi_mycel/config.yaml
    depends_on:
      - postgres
      - redis

  dashboard:
    image: gitlab.com/fungi-mycel/fungi-mycel:latest
    command: fungi-mycel serve --dashboard
    ports:
      - "8501:8501"
    volumes:
      - ./config:/root/.fungi_mycel
    environment:
      - FUNGI_MYCEL_CONFIG=/root/.fungi_mycel/config.yaml
      - API_URL=http://api:8000
    depends_on:
      - api

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: fungi_mycel
      POSTGRES_USER: fungi_user
      POSTGRES_PASSWORD: secure_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - api
      - dashboard

volumes:
  postgres_data:
  redis_data:
```

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

---

Development Installation

For contributors and developers:

```bash
# Clone repository
git clone https://gitlab.com/gitdeeper07/fungi-mycel.git
cd fungi-mycel

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode with all extras
pip install -e ".[all,dev]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest tests/ -v --cov=fungi_mycel

# Run hypothesis tests (H1-H8)
pytest tests/hypothesis/ -v
```

---

Configuration Reference

Main Configuration File

```yaml
# ~/.fungi_mycel/config.yaml

# FUNGI-MYCEL Configuration
version: 1.0

# Project settings
project:
  name: "FUNGI-MYCEL"
  sites: 39
  mnus: 2648
  version: 1.0.0

# Database
database:
  url: postgresql://fungi_user:password@localhost:5432/fungi_mycel
  pool_size: 10
  timeout: 30

# MNIS Parameters
parameters:
  eta_NW:
    enabled: true
    calibration_file: calibrations/eta_NW_2026.json
  rho_e:
    enabled: true
    sampling_rate: 1000
    threshold_sigma: 3.0
    electrode_count: 16
  k_topo:
    enabled: true
    box_sizes: [1, 2, 4, 8, 16, 32, 64, 128, 256, 512]
    unit: "μm"

# AI Ensemble
ai:
  model: ensemble
  cnn_layers: 3
  xgboost_rounds: 100
  lstm_units: 64
  batch_size: 32
  epochs: 50

# Dashboard
dashboard:
  host: 0.0.0.0
  port: 8501
  theme: dark
  refresh_rate: 30  # seconds

# Field data
field:
  data_dir: /data/field
  backup_dir: /data/backup
  auto_upload: true
  compression: gzip

# Logging
logging:
  level: INFO
  file: logs/fungi_mycel.log
  max_size: 100MB
  backup_count: 5
```

---

Troubleshooting

Common Issues

Package not found

```bash
# Ensure pip is up to date
pip install --upgrade pip

# Try installing with --no-cache-dir
pip install --no-cache-dir fungi-mycel

# Check Python version
python --version  # Must be >=3.8
```

Import errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Ensure virtual environment is activated
which python

# Reinstall package
pip uninstall fungi-mycel -y
pip install fungi-mycel
```

Memory issues

```bash
# Reduce batch size
export FUNGI_MYCEL_BATCH_SIZE=100

# Use chunked processing
fungi-mycel analyze --chunk-size 1000

# For large datasets, use:
fungi-mycel analyze --memory-efficient
```

Electrode connection issues

```bash
# Check electrode drivers
fungi-mycel doctor --hardware

# Test electrode array
python scripts/test_electrodes.py --port /dev/ttyUSB0

# Calibrate electrodes
fungi-mycel calibrate --electrodes --output calibration.json
```

Database connection

```bash
# Test connection
fungi-mycel db test

# Initialize database
fungi-mycel db init --force

# Backup database
fungi-mycel db backup --output backup.sql
```

---

Getting Help

· Documentation: https://fungi-mycel.readthedocs.io
· Dashboard: https://fungi-mycel.netlify.app
· Issues: https://gitlab.com/gitdeeper07/fungi-mycel/-/issues
· Discussions: https://gitlab.com/gitdeeper07/fungi-mycel/-/discussions
· Email: support@fungi-mycel.org
· Principal Investigator: gitdeeper@gmail.com

---

Verification Script

```python
# verify.py
import fungi_mycel
print(f"FUNGI-MYCEL version: {fungi_mycel.__version__}")
print(f"MNIS accuracy: {fungi_mycel.MNIS_ACCURACY}%")
print(f"Parameters: {fungi_mycel.PARAMETERS}")
print("Installation successful! 🍄")
```

---

Live Dashboard: https://fungi-mycel.netlify.app
Documentation: https://fungi-mycel.readthedocs.io
DOI: 10.14293/FUNGI-MYCEL.2026.001

🍄 The forest speaks. FUNGI-MYCEL translates.
