#!/bin/bash
# Database upgrade script
# Dit script voert database migraties uit om de tabellen bij te werken

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

# Bepaal script locatie
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo -e "${RED}Kan niet naar script directory navigeren${NC}"; exit 1; }

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Database Upgrade Script${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of de database container draait
if ! docker-compose ps | grep -q "db.*Up"; then
    echo -e "${YELLOW}Database container is niet actief. Starten...${NC}"
    docker-compose up -d db
    
    # Wacht tot de database volledig is opgestart
    echo -e "${YELLOW}Wachten tot database is opgestart...${NC}"
    sleep 5
fi

# Maak backup voordat we wijzigingen maken
echo -e "${YELLOW}Database backup maken voor de upgrade...${NC}"
if [ -f "${SCRIPT_DIR}/backup-database.sh" ]; then
    ./backup-database.sh pre-upgrade
else
    echo -e "${YELLOW}Backup script niet gevonden, backup wordt overgeslagen.${NC}"
    echo -e "${YELLOW}Het is aanbevolen om een backup te maken voor grote wijzigingen.${NC}"
fi

# Voer migratie uit in web container als deze draait
if docker-compose ps | grep -q "web.*Up"; then
    echo -e "${YELLOW}Web container is actief, migratie wordt uitgevoerd in de container...${NC}"
    docker-compose exec web python run_migrations.py || {
        echo -e "${RED}Fout bij het uitvoeren van migratie script in container.${NC}"
        exit 1
    }
else
    # Als web container niet draait, start tijdelijke container
    echo -e "${YELLOW}Web container is niet actief, een tijdelijke container wordt gestart...${NC}"
    docker-compose run --rm web python run_migrations.py || {
        echo -e "${RED}Fout bij het uitvoeren van migratie script.${NC}"
        exit 1
    }
fi

echo -e "${GREEN}Database upgrade succesvol afgerond!${NC}"

# Herstart web service om wijzigingen door te voeren
if docker-compose ps | grep -q "web.*Up"; then
    echo -e "${YELLOW}Web service wordt opnieuw gestart...${NC}"
    docker-compose restart web
    echo -e "${GREEN}Web service herstart.${NC}"
fi

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Database upgrade voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"