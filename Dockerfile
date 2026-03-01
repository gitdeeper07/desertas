# 🏜️ DESERTAS Dockerfile
# Desert Emission Sensing & Energetic Rock-Tectonic Analysis System

FROM python:3.10-slim AS builder

LABEL maintainer="gitdeeper@gmail.com"
LABEL version="1.0.0"
LABEL description="DESERTAS - Desert Gas Intelligence Framework"
LABEL doi="10.14293/DESERTAS.2026.001"
LABEL dashboard="https://desertas.netlify.app"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DESERTAS_HOME=/opt/desertas \
    DESERTAS_CONFIG=/etc/desertas/config.yaml \
    DESERTAS_DATA=/data \
    DESERTAS_LOGS=/var/log/desertas

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libhdf5-dev \
    libnetcdf-dev \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Create user and directories
RUN useradd -m -u 1000 -s /bin/bash desertas && \
    mkdir -p /opt/desertas && \
    mkdir -p /etc/desertas && \
    mkdir -p /data/field && \
    mkdir -p /data/backup && \
    mkdir -p /data/processed && \
    mkdir -p /var/log/desertas && \
    chown -R desertas:desertas /opt/desertas /etc/desertas /data /var/log/desertas

# Switch to user
USER desertas
WORKDIR /opt/desertas

# Copy requirements first for better caching
COPY --chown=desertas:desertas requirements.txt .
COPY --chown=desertas:desertas setup.py setup.cfg pyproject.toml ./
COPY --chown=desertas:desertas README.md ./

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt && \
    pip install --user --no-cache-dir gunicorn

# Copy application code
COPY --chown=desertas:desertas src/ ./src/
COPY --chown=desertas:desertas scripts/ ./scripts/
COPY --chown=desertas:desertas config/desertas.default.yaml /etc/desertas/config.yaml

# Install package
RUN pip install --user -e .

# Add .local to PATH
ENV PATH="/home/desertas/.local/bin:${PATH}"

# Create entrypoint script
RUN echo '#!/bin/bash\n\
if [ "$1" = "api" ]; then\n\
    exec gunicorn --bind 0.0.0.0:8000 desertas.api.app:app\n\
elif [ "$1" = "dashboard" ]; then\n\
    exec streamlit run desertas/dashboard/app.py --server.port 8501 --server.address 0.0.0.0\n\
elif [ "$1" = "worker" ]; then\n\
    exec celery -A desertas.tasks worker --loglevel=info\n\
elif [ "$1" = "all" ]; then\n\
    echo "Starting all services..."\n\
    gunicorn --bind 0.0.0.0:8000 desertas.api.app:app &\n\
    streamlit run desertas/dashboard/app.py --server.port 8501 --server.address 0.0.0.0\n\
else\n\
    exec desertas "$@"\n\
fi' > /home/desertas/entrypoint.sh && chmod +x /home/desertas/entrypoint.sh

# Expose ports
EXPOSE 8000 8501

# Set healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint
ENTRYPOINT ["/home/desertas/entrypoint.sh"]

# Default command
CMD ["all"]

# 🏜️ The desert breathes. DESERTAS decodes.
