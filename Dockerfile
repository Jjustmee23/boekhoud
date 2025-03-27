FROM python:3.11-slim

WORKDIR /app

# Installeer systeemafhankelijkheden voor weasyprint
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Kopieer alleen requirements eerst om van caching te profiteren
COPY pyproject.toml /app/
COPY uv.lock /app/

# Installeer Python afhankelijkheden
RUN pip install --no-cache-dir --upgrade pip \
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

# Start de applicatie
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "--workers", "2", "--reuse-port", "main:app"]