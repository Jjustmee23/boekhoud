#!/bin/bash
# Database herstel script voor het facturatie systeem

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

echo -e "${YELLOW}Database Herstel Tool${NC}"

# Check of een backup bestand is opgegeven
if [ -z "$1" ]; then
    echo -e "${YELLOW}Geen backup bestand opgegeven. Beschikbare backups:${NC}"
    
    # Controleer of de backup map bestaat
    if [ ! -d "db_backups" ]; then
        echo -e "${RED}Geen db_backups map gevonden. Maak eerst een backup.${NC}"
        exit 1
    fi
    
    # Toon beschikbare backups
    echo -e "${YELLOW}Beschikbare backups:${NC}"
    ls -lt db_backups/*.sql.gz 2>/dev/null || echo -e "${RED}Geen backups gevonden in db_backups map.${NC}"
    
    # Vraag welke backup te herstellen
    echo
    read -p "Geef het pad naar het backup bestand: " BACKUP_FILE
    
    if [ -z "$BACKUP_FILE" ]; then
        echo -e "${RED}Geen backup bestand opgegeven. Herstel geannuleerd.${NC}"
        exit 1
    fi
else
    BACKUP_FILE="$1"
fi

# Controleer of het backup bestand bestaat
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Backup bestand niet gevonden: $BACKUP_FILE${NC}"
    exit 1
fi

# Waarschuwing over data verlies
echo -e "${RED}WAARSCHUWING: Dit zal de huidige database VOLLEDIG VERVANGEN met de backup.${NC}"
echo -e "${RED}Alle gegevens die niet in de backup zitten zullen verloren gaan!${NC}"

if ! ask_yes_no "Weet je zeker dat je door wilt gaan?"; then
    echo -e "${YELLOW}Database herstel geannuleerd.${NC}"
    exit 0
fi

# Bepaal of we Docker of directe connectie gebruiken
if [ -f "docker-compose.yml" ] && command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}Docker-compose gevonden, herstel via Docker...${NC}"
    USE_DOCKER=1
else
    echo -e "${YELLOW}Geen Docker-compose gevonden of niet beschikbaar, directe herstel...${NC}"
    USE_DOCKER=0
fi

# Database herstel functie voor Docker
docker_restore() {
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
    
    # Database herstellen
    echo -e "${YELLOW}Database herstellen...${NC}"
    docker-compose exec db sh -c "PGPASSWORD=\$POSTGRES_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $CONTAINER_BACKUP" || {
        echo -e "${RED}Database herstel mislukt. Zie foutmelding hierboven.${NC}"
        exit 1
    }
    
    # Opruimen
    docker-compose exec db sh -c "rm -f $CONTAINER_BACKUP"
}

# Database herstel functie voor directe verbinding
direct_restore() {
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
    
    # Herstel commando voorbereiden
    if [[ "$BACKUP_FILE" == *.gz ]]; then
        # Gecomprimeerde backup
        RESTORE_CMD="gunzip -c $BACKUP_FILE | PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME"
    else
        # Ongecomprimeerde backup
        RESTORE_CMD="PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f $BACKUP_FILE"
    fi
    
    # Database herstellen
    echo -e "${YELLOW}Database herstellen...${NC}"
    eval "$RESTORE_CMD" || {
        echo -e "${RED}Database herstel mislukt. Zie foutmelding hierboven.${NC}"
        exit 1
    }
}

# Voer het juiste herstel proces uit
if [ "$USE_DOCKER" -eq 1 ]; then
    docker_restore
else
    direct_restore
fi

echo -e "${GREEN}Database herstel voltooid!${NC}"

# Als er web containers zijn, herstart deze
if [ "$USE_DOCKER" -eq 1 ] && docker-compose ps | grep -q web; then
    echo -e "${YELLOW}Web container herstarten om wijzigingen toe te passen...${NC}"
    docker-compose restart web
fi

echo -e "${GREEN}Het systeem is nu hersteld naar de staat van de backup.${NC}"