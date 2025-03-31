#!/bin/bash
set -e

echo "Docker entrypoint script gestart"

# Als dit de web service is, wacht dan tot de database beschikbaar is en voer migraties uit
if [ "$1" = "web" ] || [ "$1" = "gunicorn" ]; then
    echo "Web service gedetecteerd, wachten op database..."
    
    # Eerste korte wachttijd om te zorgen dat de database container is opgestart
    sleep 5
    
    # Controleer of database beschikbaar is
    MAX_TRIES=30
    CURRENT_TRY=1
    
    echo "Database beschikbaarheid controleren..."
    until python -c "import sys, os, psycopg2; sys.exit(0 if psycopg2.connect(os.environ.get('DATABASE_URL')) else 1)" 2>/dev/null; do
        echo "Wachten op database... poging ${CURRENT_TRY}/${MAX_TRIES}"
        CURRENT_TRY=$((CURRENT_TRY + 1))
        
        if [ ${CURRENT_TRY} -gt ${MAX_TRIES} ]; then
            echo "Database niet beschikbaar na ${MAX_TRIES} pogingen, opgegeven"
            exit 1
        fi
        
        sleep 2
    done
    
    echo "Database is nu beschikbaar!"
    
    # Voer database migraties uit
    echo "Database migraties uitvoeren..."
    python run_migrations.py || {
        echo "Database migratie mislukt"
        exit 1
    }
    
    echo "Database migraties succesvol, applicatie wordt gestart..."
fi

# Voer het gegeven commando uit
exec "$@"