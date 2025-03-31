#!/bin/bash
# Script voor het maken van een backup van de PostgreSQL database

# Configuratie
BACKUP_DIR="./db_backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILENAME="facturatie_backup_$DATE.sql"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_FILENAME"
COMPRESS=true  # true om het bestand te comprimeren, false om het in plaintext te houden

# Controleer of docker-compose beschikbaar is
if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose kon niet gevonden worden. Installeer docker-compose of gebruik de volledige pad."
    exit 1
fi

# Controleer of de backup directory bestaat, zo niet maak deze aan
if [ ! -d "$BACKUP_DIR" ]; then
    echo "Backup directory bestaat niet. Aanmaken: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Haal database variabelen uit .env bestand of gebruik standaardwaarden
if [ -f ./.env ]; then
    source ./.env
fi

DB_USER=${POSTGRES_USER:-postgres}
DB_PASSWORD=${POSTGRES_PASSWORD:-postgres}
DB_NAME=${POSTGRES_DB:-facturatie}

echo "Start backup van database $DB_NAME naar $BACKUP_PATH"

# Maak een backup van de database met docker-compose
docker-compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_PATH"

# Controleer of de backup is gemaakt
if [ $? -eq 0 ]; then
    echo "Database backup is succesvol aangemaakt"

    # Comprimeer het bestand als dat is ingesteld
    if [ "$COMPRESS" = true ]; then
        echo "Comprimeren van de backup..."
        gzip "$BACKUP_PATH"
        BACKUP_PATH="$BACKUP_PATH.gz"
        echo "Gecomprimeerde backup opgeslagen als: $BACKUP_PATH"
    fi

    # Toon de bestandsgrootte
    FILESIZE=$(du -h "$BACKUP_PATH" | cut -f1)
    echo "Bestandsgrootte: $FILESIZE"
    echo "Backup voltooid!"
else
    echo "Fout bij het maken van de database backup!"
    exit 1
fi