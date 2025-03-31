#!/bin/bash
# Deployment script voor Facturatie & Boekhouding Systeem
# Dit script update de applicatie vanuit Git en herstart de containers

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
BACKUP_SCRIPT="${SCRIPT_DIR}/backup-database.sh"
BACKUP_BEFORE_DEPLOY=true
GIT_BRANCH="main"  # of master, afhankelijk van de repository

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Facturatie Systeem - Deployment${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of docker-compose beschikbaar is
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose is niet gevonden. Installeer docker-compose om verder te gaan.${NC}"
    exit 1
fi

# Controleer of docker-compose.yml bestaat
if [ ! -f "${SCRIPT_DIR}/docker-compose.yml" ]; then
    echo -e "${RED}docker-compose.yml niet gevonden. Voer dit script uit vanuit de project directory.${NC}"
    exit 1
fi

# Vraag gebruiker om bevestiging
if ! ask_yes_no "Wil je de applicatie updaten en opnieuw opstarten?"; then
    echo -e "${YELLOW}Deployment geannuleerd door gebruiker.${NC}"
    exit 0
fi

# Ga naar de project directory
cd "${SCRIPT_DIR}"

# Maak een database backup voor de update
if [ "$BACKUP_BEFORE_DEPLOY" = true ] && [ -f "$BACKUP_SCRIPT" ]; then
    echo -e "${YELLOW}Database backup maken voor deployment...${NC}"
    bash "$BACKUP_SCRIPT" || {
        echo -e "${RED}Kan geen database backup maken. Zie foutmelding hierboven.${NC}"
        if ! ask_yes_no "Wil je toch doorgaan zonder backup?"; then
            echo -e "${YELLOW}Deployment geannuleerd.${NC}"
            exit 1
        fi
    }
fi

# Update de code vanuit Git
if [ -d ".git" ]; then
    echo -e "${YELLOW}Code updaten vanuit Git repository...${NC}"
    
    # Controleer of er local changes zijn
    if ! git diff-index --quiet HEAD --; then
        echo -e "${RED}Er zijn lokale wijzigingen in de code.${NC}"
        if ! ask_yes_no "Wil je deze wijzigingen overschrijven?"; then
            echo -e "${YELLOW}Deployment geannuleerd.${NC}"
            exit 1
        fi
        # Reset lokale wijzigingen
        git reset --hard HEAD || {
            echo -e "${RED}Kan lokale wijzigingen niet resetten.${NC}"
            exit 1
        }
    fi
    
    # Update van remote en pull de laatste wijzigingen
    git fetch origin || {
        echo -e "${RED}Kan niet verbinden met git remote. Controleer je internetverbinding.${NC}"
        exit 1
    }
    
    git checkout "$GIT_BRANCH" || {
        echo -e "${RED}Kan niet overschakelen naar branch: ${GIT_BRANCH}${NC}"
        echo -e "${YELLOW}Beschikbare branches:${NC}"
        git branch -a
        exit 1
    }
    
    git pull origin "$GIT_BRANCH" || {
        echo -e "${RED}Kan wijzigingen niet ophalen van branch: ${GIT_BRANCH}${NC}"
        exit 1
    }
    
    echo -e "${GREEN}Code is bijgewerkt naar de laatste versie.${NC}"
else
    echo -e "${YELLOW}Geen Git repository gevonden. Code-update wordt overgeslagen.${NC}"
fi

# Containers stoppen en opnieuw starten
echo -e "${YELLOW}Docker containers opnieuw opbouwen en starten...${NC}"
docker-compose down || echo -e "${YELLOW}Er waren geen draaiende containers of ze konden niet gestopt worden.${NC}"
docker-compose build || {
    echo -e "${RED}Kan containers niet opbouwen. Zie foutmelding hierboven.${NC}"
    exit 1
}
docker-compose up -d || {
    echo -e "${RED}Kan containers niet starten. Zie foutmelding hierboven.${NC}"
    exit 1
}

echo -e "${GREEN}Containers succesvol opnieuw gestart!${NC}"

# Wacht tot de applicatie beschikbaar is
echo -e "${YELLOW}Wachten tot de applicatie beschikbaar is...${NC}"
sleep 5

# Toon logs van web container
echo -e "${YELLOW}Logs van de applicatie container:${NC}"
docker-compose logs --tail=20 web

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Deployment voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo
echo -e "${YELLOW}Gebruik de volgende commando's voor beheer:${NC}"
echo -e "${YELLOW}- docker-compose logs -f     # Bekijk logs${NC}"
echo -e "${YELLOW}- docker-compose restart web # Herstart web container${NC}"
echo -e "${YELLOW}- docker-compose down        # Stop containers${NC}"