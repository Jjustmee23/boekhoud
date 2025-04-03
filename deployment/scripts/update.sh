#!/bin/bash
# Update script voor de Flask facturatie-applicatie
# Uitvoeren vanaf de applicatiemap

set -e  # Stop bij fouten

APP_DIR="/opt/invoice-app"
BACKUP_DIR="${APP_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Controleer of we in de applicatiemap zijn
if [ ! -d "${APP_DIR}" ]; then
    echo "Fout: Applicatiemap ${APP_DIR} niet gevonden."
    echo "Zorg ervoor dat je dit script uitvoert op de server waar de applicatie draait."
    exit 1
fi

# Controleer of Git geïnstalleerd is
if ! [ -x "$(command -v git)" ]; then
    echo "Fout: Git is niet geïnstalleerd. Voer eerst setup_flask_app.sh uit."
    exit 1
fi

# Controleer of we in een git repository zijn
cd "${APP_DIR}"
if [ ! -d ".git" ]; then
    echo "Fout: ${APP_DIR} is geen Git repository."
    exit 1
fi

# Haal huidige branch op
current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "detached")
echo "Huidige branch: ${current_branch}"

# Maak een backup van de database voor de zekerheid
echo "=== Database backup maken voor update ==="
echo "Tijdstempel: ${TIMESTAMP}"

mkdir -p "${BACKUP_DIR}"

# Database backup
echo ">> Database backup maken..."
if [ -f "${APP_DIR}/docker-compose.yml" ]; then
    # Docker installatie
    docker compose exec -T db pg_dump -U postgres invoicing > "${BACKUP_DIR}/pre_update_db_backup_${TIMESTAMP}.sql"
else
    # Directe installatie
    echo "Geen docker-compose.yml gevonden, directe PostgreSQL-backup uitvoeren..."
    sudo -u postgres pg_dump invoicing > "${BACKUP_DIR}/pre_update_db_backup_${TIMESTAMP}.sql"
fi

# Haal de laatste wijzigingen op van de remote repository
echo ">> Git pull uitvoeren om laatste wijzigingen op te halen..."
git pull

# Controleer of requirements.txt is gewijzigd
if [ -f "requirements.txt" ] && [ -f "requirements.txt.old" ]; then
    if ! cmp --silent "requirements.txt" "requirements.txt.old"; then
        echo ">> Requirements zijn gewijzigd. Docker image wordt opnieuw gebouwd..."
        # Bewaar de huidige requirements voor toekomstige vergelijking
        cp requirements.txt requirements.txt.old
        
        if [ -f "${APP_DIR}/docker-compose.yml" ]; then
            # Docker installatie
            docker compose build web
        else
            # Directe installatie
            pip install -r requirements.txt
        fi
    else
        echo ">> Geen wijzigingen in requirements.txt gedetecteerd."
    fi
else
    echo ">> Eerste keer dat we requirements controleren of requirements.txt.old bestaat niet."
    # Bewaar de huidige requirements voor toekomstige vergelijking
    cp requirements.txt requirements.txt.old
fi

# Herstart de applicatie
echo ">> Applicatie herstarten..."
if [ -f "${APP_DIR}/docker-compose.yml" ]; then
    # Docker installatie
    docker compose down
    docker compose up -d
else
    # Directe installatie
    if [ -f "/etc/systemd/system/flask-app.service" ]; then
        sudo systemctl restart flask-app
    else
        echo "Waarschuwing: Kon de service niet herstarten, geen systemd service gevonden."
    fi
fi

echo "=== Update voltooid ==="
echo "De applicatie is bijgewerkt naar de laatste versie en herstart."
echo "Database backup voor deze update: ${BACKUP_DIR}/pre_update_db_backup_${TIMESTAMP}.sql"
echo ""
echo "Controleer de applicatie om te verifiëren dat alles correct werkt."