#!/bin/bash
# Database backup script voor het facturatie systeem

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

echo -e "${YELLOW}Database backup starten...${NC}"

# Maak backup map als deze niet bestaat
if [ ! -d "db_backups" ]; then
    mkdir db_backups
    echo -e "${YELLOW}Backup map 'db_backups' aangemaakt.${NC}"
fi

# Bepaal bestandsnaam met timestamp
BACKUP_TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="db_backups/backup-${BACKUP_TIMESTAMP}.sql.gz"

# Bepaal of we Docker of directe connectie gebruiken
if [ -f "docker-compose.yml" ] && command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Docker-compose gevonden, backup via Docker...${NC}"
    USE_DOCKER=1
else
    echo -e "${YELLOW}Geen Docker-compose gevonden of niet beschikbaar, directe backup...${NC}"
    USE_DOCKER=0
fi

# Database backup functie voor Docker
docker_backup() {
    # Controleer of database container draait
    if ! docker-compose ps | grep -q db; then
        echo -e "${YELLOW}Database container niet gevonden of niet actief.${NC}"
        echo -e "${YELLOW}Container starten...${NC}"
        docker-compose up -d db || {
            echo -e "${RED}Kan database container niet starten. Backup mislukt.${NC}"
            exit 1
        }
        # Wacht tot database klaar is voor connecties
        echo -e "${YELLOW}Wachten tot database gereed is...${NC}"
        sleep 5
    fi
    
    # Haal database verbindingsgegevens op
    DB_HOST=$(docker-compose exec db printenv POSTGRES_HOST 2>/dev/null || echo "db")
    DB_PORT=$(docker-compose exec db printenv POSTGRES_PORT 2>/dev/null || echo "5432")
    DB_USER=$(docker-compose exec db printenv POSTGRES_USER 2>/dev/null || echo "postgres")
    DB_NAME=$(docker-compose exec db printenv POSTGRES_DB 2>/dev/null || echo "facturatie")
    
    # Maak backup
    echo -e "${YELLOW}Database backup maken via Docker...${NC}"
    docker-compose exec db sh -c "PGPASSWORD=\$POSTGRES_PASSWORD pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME | gzip" > "$BACKUP_FILE" || {
        echo -e "${RED}Database backup mislukt. Zie foutmelding hierboven.${NC}"
        rm -f "$BACKUP_FILE"  # Verwijder gedeeltelijke backup
        exit 1
    }
}

# Database backup functie voor directe verbinding
direct_backup() {
    # Haal database verbindingsgegevens op uit .env bestand als het bestaat
    if [ -f ".env" ]; then
        source .env
    fi
    
    # Als DATABASE_URL bestaat, gebruik die
    if [ -n "$DATABASE_URL" ]; then
        # Extract connectie info from DATABASE_URL
        DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
        DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([^\/]*\)\/.*/\1/p')
        DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\(.*\)$/\1/p')
    else
        # Vraag handmatig
        read -p "Database host [localhost]: " DB_HOST
        DB_HOST=${DB_HOST:-localhost}
        
        read -p "Database poort [5432]: " DB_PORT
        DB_PORT=${DB_PORT:-5432}
        
        read -p "Database gebruiker [postgres]: " DB_USER
        DB_USER=${DB_USER:-postgres}
        
        read -p "Database naam [facturatie]: " DB_NAME
        DB_NAME=${DB_NAME:-facturatie}
        
        read -s -p "Database wachtwoord: " DB_PASSWORD
        echo
    fi
    
    # Maak backup
    echo -e "${YELLOW}Database backup maken...${NC}"
    PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME | gzip > "$BACKUP_FILE" || {
        echo -e "${RED}Database backup mislukt. Zie foutmelding hierboven.${NC}"
        rm -f "$BACKUP_FILE"  # Verwijder gedeeltelijke backup
        exit 1
    }
}

# Voer het juiste backup proces uit
if [ "$USE_DOCKER" -eq 1 ]; then
    docker_backup
else
    direct_backup
fi

# Controleer of backup bestand is aangemaakt en niet leeg is
if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
    FILESIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}Database backup voltooid!${NC}"
    echo -e "${GREEN}Backup opgeslagen als: ${BACKUP_FILE} (${FILESIZE})${NC}"
    
    # Maak een symbolische link naar de laatste backup
    ln -sf "$BACKUP_FILE" "db_backups/latest_backup.sql.gz"
    echo -e "${YELLOW}Symbolische link gemaakt: db_backups/latest_backup.sql.gz -> ${BACKUP_FILE}${NC}"
else
    echo -e "${RED}Backup bestand ontbreekt of is leeg. Er is iets misgegaan.${NC}"
    exit 1
fi

# Toon totaal aantal backups en totale grootte
TOTAL_BACKUPS=$(ls db_backups/*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh db_backups | cut -f1)

echo -e "${YELLOW}Totaal aantal backups: ${TOTAL_BACKUPS}${NC}"
echo -e "${YELLOW}Totale grootte van backups: ${TOTAL_SIZE}${NC}"
echo
echo -e "${YELLOW}Gebruik ./restore-database.sh ${BACKUP_FILE} om deze backup te herstellen.${NC}"