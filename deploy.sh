#!/bin/bash
# Deployment script voor het facturatie systeem
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

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Facturatie Systeem - Deployment${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of docker-compose beschikbaar is
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose is niet gevonden. Installeer docker-compose om verder te gaan.${NC}"
    exit 1
fi

# Controleer of docker-compose.yml bestaat
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}docker-compose.yml niet gevonden. Voer dit script uit vanuit de project directory.${NC}"
    exit 1
fi

# Controleer Git status
if [ -d ".git" ]; then
    echo -e "${YELLOW}Git repository detecteren...${NC}"
    
    # Controleer of er lokale wijzigingen zijn
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}Let op: Er zijn niet gecommitte wijzigingen in de repository.${NC}"
        if ! ask_yes_no "Wil je doorgaan? Lokale wijzigingen kunnen verloren gaan."; then
            echo -e "${YELLOW}Deployment geannuleerd.${NC}"
            exit 0
        fi
    fi
    
    # Fetch remote changes
    echo -e "${YELLOW}Ophalen van wijzigingen vanaf remote...${NC}"
    git fetch origin || {
        echo -e "${RED}Kan wijzigingen niet ophalen van remote. Controleer je internetverbinding.${NC}"
        exit 1
    }
    
    # Controleer of we updates hebben
    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse @{u})
    
    if [ "$LOCAL" = "$REMOTE" ]; then
        echo -e "${GREEN}Je bent al up-to-date met de laatste versie.${NC}"
        if ! ask_yes_no "Wil je toch doorgaan met de herstart?"; then
            echo -e "${YELLOW}Deployment geannuleerd.${NC}"
            exit 0
        fi
    else
        echo -e "${YELLOW}Er zijn updates beschikbaar. Wijzigingen ophalen...${NC}"
        
        # Maak eerst een database backup
        if [ -f "backup-database.sh" ]; then
            echo -e "${YELLOW}Database backup maken voor de update...${NC}"
            ./backup-database.sh || {
                echo -e "${RED}Database backup mislukt. Deployment wordt afgebroken.${NC}"
                if ask_yes_no "Wil je toch doorgaan zonder backup?"; then
                    echo -e "${YELLOW}Doorgaan zonder backup op eigen risico...${NC}"
                else
                    echo -e "${YELLOW}Deployment geannuleerd.${NC}"
                    exit 1
                fi
            }
        else
            echo -e "${YELLOW}Waarschuwing: backup-database.sh niet gevonden. Geen backup gemaakt.${NC}"
            if ! ask_yes_no "Wil je doorgaan zonder backup?"; then
                echo -e "${YELLOW}Deployment geannuleerd.${NC}"
                exit 0
            fi
        fi
        
        # Pull changes
        echo -e "${YELLOW}Wijzigingen ophalen...${NC}"
        git pull || {
            echo -e "${RED}Kan wijzigingen niet ophalen. Los eventuele merge conflicten op.${NC}"
            exit 1
        }
    fi
else
    echo -e "${YELLOW}Geen Git repository gevonden. Alleen containers herstarten.${NC}"
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