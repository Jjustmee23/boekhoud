FROM python:3.11-slim

WORKDIR /app

# Installeer benodigde systeempakketten, inclusief PostgreSQL-client en afhankelijkheden voor WeasyPrint
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Kopieer de requirements naar de container
COPY pyproject.toml .
COPY uv.lock .

# Installeer de afhankelijkheden
RUN pip install --no-cache-dir uv && \
    uv pip install --system -r uv.lock

# Kopieer de rest van de applicatie
COPY . .

# Maak directory voor uploads als deze nog niet bestaat
RUN mkdir -p static/uploads

# Exposeer poort 5000 voor de Flask-applicatie
EXPOSE 5000

# Start de applicatie met Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--workers", "2", "main:app"]