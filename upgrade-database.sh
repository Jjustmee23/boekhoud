#!/bin/bash
# Database upgrade script voor het facturatie systeem
# Dit script voert database migraties uit op een veilige manier met backup

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

echo -e "${YELLOW}Database upgrade starten voor het facturatie systeem...${NC}"

# Controleer of we in de juiste directory zijn
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Voer dit script uit vanuit de project directory.${NC}"
    exit 1
fi

# Controleer of docker-compose geïnstalleerd is
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose is niet geïnstalleerd. Installeer eerst docker-compose.${NC}"
    exit 1
fi

# Waarschuwing
echo -e "${YELLOW}WAARSCHUWING: Dit script gaat database migraties uitvoeren. Zorg dat je een backup hebt.${NC}"
if ! ask_yes_no "Wil je doorgaan?"; then
    echo -e "${YELLOW}Database upgrade geannuleerd.${NC}"
    exit 0
fi

# Maak eerst een backup
echo -e "${YELLOW}Eerst maken we een backup van de huidige database...${NC}"
./backup-database.sh || {
    echo -e "${RED}Database backup mislukt. Upgrade wordt afgebroken voor veiligheid.${NC}"
    if ask_yes_no "Wil je toch doorgaan zonder backup (NIET AANBEVOLEN)?"; then
        echo -e "${YELLOW}Doorgaan zonder backup op eigen risico...${NC}"
    else
        echo -e "${YELLOW}Database upgrade geannuleerd.${NC}"
        exit 1
    fi
}

# Voer de migratie uit
echo -e "${YELLOW}Database migraties uitvoeren...${NC}"

# Optie 1: Voor Docker omgeving
if [ -z "$SKIP_DOCKER" ]; then
    docker-compose exec web python run_migrations.py || {
        echo -e "${RED}Migratie mislukt in Docker container.${NC}"
        echo -e "${YELLOW}Proberen met directe uitvoering...${NC}"
        SKIP_DOCKER=1
    }
fi

# Optie 2: Directe uitvoering (als Docker mislukt of overgeslagen wordt)
if [ -n "$SKIP_DOCKER" ]; then
    python run_migrations.py || {
        echo -e "${RED}Migratie mislukt. Zie error hierboven.${NC}"
        
        # Vraag om database herstel
        if ask_yes_no "Wil je de database herstellen van de backup?"; then
            echo -e "${YELLOW}Database herstellen van backup...${NC}"
            ./restore-database.sh
        else
            echo -e "${RED}Database is mogelijk in een inconsistente staat!${NC}"
        }
        
        exit 1
    }
fi

echo -e "${GREEN}Database migratie voltooid!${NC}"

# Notificatie over logbestanden
echo -e "${YELLOW}Controleer de logs voor eventuele waarschuwingen:${NC}"
if [ -z "$SKIP_DOCKER" ]; then
    docker-compose logs --tail=20 web
else
    echo -e "${YELLOW}Logs zijn niet beschikbaar bij directe uitvoering.${NC}"
fi

echo -e "${GREEN}Database upgrade voltooid!${NC}"