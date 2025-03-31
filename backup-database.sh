#!/bin/bash
# Database backup script voor Boekhoud Systeem
# Maakt een backup van de PostgreSQL database

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

# Instellingen
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${SCRIPT_DIR}/backups"
DATE_FORMAT=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="${BACKUP_DIR}/boekhoud_backup_${DATE_FORMAT}.sql.gz"
KEEP_DAYS=30  # Hoeveel dagen backups bewaren

# Controleer of .env bestand bestaat
if [ -f "${SCRIPT_DIR}/.env" ]; then
    source "${SCRIPT_DIR}/.env"
fi

# Default database gegevens als niet ingesteld in .env
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
DB_NAME=${DB_NAME:-boekhoud}

# Maak backup directory als deze niet bestaat
mkdir -p "${BACKUP_DIR}"

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Boekhoud Systeem - Database Backup${NC}"
echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Backup aanmaken in: ${BACKUP_FILE}${NC}"

# Function to check if we're in a Docker environment
in_docker() {
    [ -f /.dockerenv ] || grep -q '/docker/' /proc/1/cgroup
}

# Function to check if Docker is available
has_docker() {
    command -v docker-compose &> /dev/null
}

# Functies voor verschillende backup methoden
local_backup() {
    # Directe backup met pg_dump
    PGPASSWORD="${DB_PASSWORD}" pg_dump -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER} \
        -d ${DB_NAME} -F p | gzip > "${BACKUP_FILE}" || {
        echo -e "${RED}Backup mislukt. Zie foutmelding hierboven.${NC}"
        exit 1
    }
}

docker_backup() {
    # Backup via Docker container
    echo -e "${YELLOW}Backup uitvoeren via Docker container...${NC}"
    
    # Controleer of database container draait
    if ! docker-compose ps | grep -q db; then
        echo -e "${YELLOW}Database container niet gevonden of niet actief.${NC}"
        echo -e "${YELLOW}Container starten...${NC}"
        docker-compose up -d db || {
            echo -e "${RED}Kan database container niet starten. Backup mislukt.${NC}"
            exit 1
        }
        # Wacht tot database klaar is voor connecties
        sleep 5
    fi
    
    # Haal database verbindingsgegevens op uit Docker
    DB_HOST=$(docker-compose exec db printenv POSTGRES_HOST 2>/dev/null || echo "db")
    DB_PORT=$(docker-compose exec db printenv POSTGRES_PORT 2>/dev/null || echo "5432")
    DB_USER=$(docker-compose exec db printenv POSTGRES_USER 2>/dev/null || echo "postgres")
    DB_NAME=$(docker-compose exec db printenv POSTGRES_DB 2>/dev/null || echo "boekhoud")
    
    # Maak backup met pg_dump in de database container
    docker-compose exec db pg_dump -U ${DB_USER} ${DB_NAME} | gzip > "${BACKUP_FILE}" || {
        echo -e "${RED}Backup via Docker container mislukt. Zie foutmelding hierboven.${NC}"
        exit 1
    }
}

# Bepaal welke backup methode te gebruiken
if in_docker; then
    echo -e "${YELLOW}In Docker container gedetecteerd, directe backup gebruiken...${NC}"
    local_backup
elif has_docker; then
    echo -e "${YELLOW}Docker gedetecteerd, backup via Docker gebruiken...${NC}"
    cd "${SCRIPT_DIR}"  # Zorg ervoor dat we in de juiste directory staan voor docker-compose
    docker_backup
else
    echo -e "${YELLOW}Geen Docker gedetecteerd, directe backup gebruiken...${NC}"
    local_backup
fi

# Verwijder oude backups
echo -e "${YELLOW}Oude backups verwijderen (ouder dan ${KEEP_DAYS} dagen)...${NC}"
find "${BACKUP_DIR}" -type f -name "boekhoud_backup_*.sql.gz" -mtime +${KEEP_DAYS} -delete

# Backup voltooid
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Backup voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Backup bestand: ${BACKUP_FILE}${NC}"

# Toon backup statistieken
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
BACKUP_COUNT=$(find "${BACKUP_DIR}" -type f -name "boekhoud_backup_*.sql.gz" | wc -l)
TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)

echo -e "${YELLOW}Backup grootte: ${BACKUP_SIZE}${NC}"
echo -e "${YELLOW}Totaal aantal backups: ${BACKUP_COUNT}${NC}"
echo -e "${YELLOW}Totaal gebruikt: ${TOTAL_SIZE}${NC}"