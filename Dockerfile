FROM python:3.11-slim

WORKDIR /app

# Installeer systeemafhankelijkheden voor weasyprint en hulpmiddelen
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Kopieer alleen requirements eerst om van caching te profiteren
COPY pyproject.toml /app/
COPY uv.lock /app/

# Installeer Python afhankelijkheden met een specifieke versie van pip
RUN pip install --no-cache-dir --upgrade pip==24.1.2 \
    && pip install --no-cache-dir -e .

# Kopieer de rest van de applicatie
COPY . /app/

# Maak map voor geüploade bestanden
RUN mkdir -p /app/static/uploads \
    && chmod 777 /app/static/uploads

# Configuratie variabelen 
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5000

# Expose poort waarop de app draait
EXPOSE 5000

# Gezondheidscontrole om container status te monitoren
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Start de applicatie met verbeterde instellingen
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "2", "--worker-class", "sync", "--reuse-port", "--access-logfile", "-", "--error-logfile", "-", "main:app"]