#!/bin/bash
# Database restore script voor Facturatie & Boekhouding Systeem
# Herstelt een backup van de PostgreSQL database

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

# Functie om gebruiker om bevestiging te vragen
ask_yes_no() {
    read -p "$1 (j/n): " choice
    case "$choice" in 
        j|J|ja|Ja|JA ) return 0;;
        * ) return 1;;
    esac
}

# Instellingen
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"

# Controleer of .env bestand bestaat
if [ -f "${SCRIPT_DIR}/.env" ]; then
    source "${SCRIPT_DIR}/.env"
fi

# Default database gegevens als niet ingesteld in .env
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
DB_NAME=${DB_NAME:-facturatie}

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Facturatie Systeem - Database Herstel${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Function to check if we're in a Docker environment
in_docker() {
    [ -f /.dockerenv ] || grep -q '/docker/' /proc/1/cgroup
}

# Function to check if Docker is available
has_docker() {
    command -v docker-compose &> /dev/null
}

# Toon beschikbare backups
echo -e "${YELLOW}Beschikbare backups:${NC}"
if [ -d "$BACKUP_DIR" ]; then
    ls -lh ${BACKUP_DIR}/*.sql.gz 2>/dev/null || echo "Geen backups gevonden in ${BACKUP_DIR}"
else
    echo "Backup directory bestaat niet: ${BACKUP_DIR}"
    mkdir -p "${BACKUP_DIR}"
fi

# Vraag gebruiker welke backup te gebruiken
read -p "Geef het volledige pad van de backup die je wilt herstellen: " BACKUP_FILE

# Controleer of bestand bestaat
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Backup bestand niet gevonden: ${BACKUP_FILE}${NC}"
    exit 1
fi

# Bevestig de actie
echo -e "${RED}WAARSCHUWING: Dit zal de huidige database overschrijven!${NC}"
if ! ask_yes_no "Weet je zeker dat je door wilt gaan?"; then
    echo -e "${YELLOW}Herstel geannuleerd.${NC}"
    exit 0
fi

# Functies voor verschillende restore methoden
local_restore() {
    echo -e "${YELLOW}Directe restore gebruiken...${NC}"
    
    # Controleer of het een gecomprimeerd bestand is
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        echo -e "${YELLOW}Gecomprimeerd backup bestand gedetecteerd...${NC}"
        gunzip -c "$BACKUP_FILE" | PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME || {
            echo -e "${RED}Restore mislukt. Zie foutmelding hierboven.${NC}"
            exit 1
        }
    else
        echo -e "${YELLOW}Ongecomprimeerd backup bestand gedetecteerd...${NC}"
        PGPASSWORD="$DB_PASSWORD" psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$BACKUP_FILE" || {
            echo -e "${RED}Restore mislukt. Zie foutmelding hierboven.${NC}"
            exit 1
        }
    fi
}

docker_restore() {
    echo -e "${YELLOW}Restore via Docker container gebruiken...${NC}"
    
    # Controleer of database container draait
    if ! docker-compose ps | grep -q db; then
        echo -e "${YELLOW}Database container niet gevonden of niet actief.${NC}"
        echo -e "${YELLOW}Container starten...${NC}"
        docker-compose up -d db || {
            echo -e "${RED}Kan database container niet starten. Herstel mislukt.${NC}"
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
    
    # Kopieer backup bestand naar container
    echo -e "${YELLOW}Backup bestand naar container kopiëren...${NC}"
    # Eerst bestands extensie controleren
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        # Gecomprimeerde backup
        echo -e "${YELLOW}Gecomprimeerde backup gevonden...${NC}"
        cat "$BACKUP_FILE" | docker-compose exec -T db sh -c "gunzip > /tmp/backup.sql"
        CONTAINER_BACKUP="/tmp/backup.sql"
    else
        # Ongecomprimeerde backup
        echo -e "${YELLOW}Ongecomprimeerde backup gevonden...${NC}"
        cat "$BACKUP_FILE" | docker-compose exec -T db sh -c "cat > /tmp/backup.sql"
        CONTAINER_BACKUP="/tmp/backup.sql"
    fi
    
    # Restore in container
    echo -e "${YELLOW}Database herstellen in container...${NC}"
    docker-compose exec db psql -U $DB_USER -d $DB_NAME -f $CONTAINER_BACKUP || {
        echo -e "${RED}Kan database niet herstellen. Zie foutmelding hierboven.${NC}"
        exit 1
    }
    
    # Verwijder tijdelijk bestand
    docker-compose exec db rm -f $CONTAINER_BACKUP
}

# Bepaal welke restore methode te gebruiken
if in_docker; then
    echo -e "${YELLOW}In Docker container gedetecteerd, directe restore gebruiken...${NC}"
    local_restore
elif has_docker; then
    echo -e "${YELLOW}Docker gedetecteerd, restore via Docker gebruiken...${NC}"
    cd "${SCRIPT_DIR}"  # Zorg ervoor dat we in de juiste directory staan voor docker-compose
    docker_restore
else
    echo -e "${YELLOW}Geen Docker gedetecteerd, directe restore gebruiken...${NC}"
    local_restore
fi

# Herstel voltooid
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Database herstel voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}De database is hersteld vanuit: ${BACKUP_FILE}${NC}"
echo
echo -e "${YELLOW}Als je de webapplicatie gebruikt, herstart deze dan met:${NC}"
echo -e "${YELLOW}docker-compose restart web${NC}"