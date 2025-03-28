# Multi-stage build voor optimale image grootte
FROM python:3.11-slim AS builder

# Voorkom Python-bestanden die bytecode schrijven, zorg voor niet-gebufferde uitvoer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Instaleer build-afhankelijkheden
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Kopieer alleen requirements eerst om van caching te profiteren
COPY pyproject.toml /build/
COPY uv.lock /build/

# Installeer Python afhankelijkheden met een specifieke versie van pip
RUN pip install --upgrade pip==24.1.2 \
    && pip install -e .

# Tweede fase: runtime image
FROM python:3.11-slim AS runtime

# Configuratie variabelen
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000 \
    GUNICORN_CMD_ARGS="--timeout 120 --workers 2 --worker-class sync --reuse-port --access-logfile - --error-logfile -" \
    TZ=Europe/Amsterdam \
    PYTHONPATH=/app

WORKDIR /app

# Maak logs directory en zet permissies
RUN mkdir -p /app/logs && \
    chmod 777 /app/logs

# Installeer alleen runtime afhankelijkheden
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    curl \
    ca-certificates \
    tzdata \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Maak een niet-root gebruiker voor betere beveiliging
RUN groupadd -g 1000 appuser && \
    useradd -u 1000 -g appuser -s /bin/bash -m appuser

# Kopieer de geïnstalleerde Python-packages van de builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Maak benodigde directories
RUN mkdir -p /app/static/uploads /app/logs \
    && chown -R appuser:appuser /app \
    && chmod -R 755 /app

# Kopieer de applicatiecode
COPY --chown=appuser:appuser . /app/

# Verifieer dat de logmappen bestaan en toegankelijk zijn
RUN mkdir -p /app/logs \
    && touch /app/logs/app.log /app/logs/app.json.log /app/logs/error.log \
    && chown -R appuser:appuser /app/logs \
    && chmod -R 755 /app/logs

# Schakel over naar niet-root gebruiker
USER appuser

# Expose poort waarop de app draait
EXPOSE 5000

# Verbeterde gezondheidscontrole om container status te monitoren
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Commando om te starten
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]