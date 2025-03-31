FROM python:3.11-slim

# Installeer benodigde systeempakketten
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    gcc \
    musl-dev \
    postgresql-client \
    libpq-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    mime-support \
    libxml2-dev \
    libxslt-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Maak werkdirectory
WORKDIR /app

# Kopieer requirements eerst (voor betere caching)
COPY requirements_for_docker.txt ./requirements.txt

# Installeer Python-afhankelijkheden
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer de rest van de applicatie
COPY . .

# Maak logs en uploads map
RUN mkdir -p logs static/uploads && \
    chmod 755 logs static/uploads

# Poort voor de webapplicatie
EXPOSE 5000

# Stel de entrypoint in
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "main:app"]