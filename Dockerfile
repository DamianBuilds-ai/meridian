FROM python:3.12-slim

WORKDIR /app

# System deps: gcc for psycopg2, libpq-dev for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Python deps (installed as root, before user switch)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for runtime
RUN groupadd -r meridian && useradd -r -g meridian -d /app -s /sbin/nologin meridian

# App code
COPY src/ /app/

# Static files (hub dashboard)
COPY static/ /app/static/

# Export directory (mount a host volume here if your bots produce file exports)
RUN mkdir -p /app/exports && chown -R meridian:meridian /app/exports

# Data directory for SQLite session stores
RUN mkdir -p /app/data && chown -R meridian:meridian /app/data

RUN chown -R meridian:meridian /app

USER meridian

# Run
CMD ["python", "-m", "main"]
