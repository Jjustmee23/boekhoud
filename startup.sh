#!/bin/bash
set -e

# Wacht tot de database beschikbaar is
echo "Wachten tot de database beschikbaar is..."
python -c "
import time
import sys
import os
import psycopg2

db_url = os.environ.get('DATABASE_URL')
max_retries = 30
retry_interval = 2

for i in range(max_retries):
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print('Database is beschikbaar!')
        sys.exit(0)
    except psycopg2.OperationalError:
        print(f'Wachten op database... ({i+1}/{max_retries})')
        time.sleep(retry_interval)

print('Kon geen verbinding maken met de database!')
sys.exit(1)
"

# Voer migratie scripts uit
echo "Migratiescripts uitvoeren..."
python migrate_oauth.py

# Start de applicatie
echo "Applicatie starten..."
exec gunicorn --bind 0.0.0.0:5000 --timeout 120 --workers 2 --reuse-port main:app