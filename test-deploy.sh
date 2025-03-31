#!/bin/bash
# Test deployment script voor het facturatie systeem
# Dit script test de deployment procedure in een tijdelijke container

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
echo -e "${YELLOW}Facturatie Systeem - Test Deployment${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of docker-compose beschikbaar is
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose is niet gevonden. Installeer docker-compose om verder te gaan.${NC}"
    exit 1
fi

# Controleer of we in een Git repository zijn
if [ ! -d ".git" ]; then
    echo -e "${RED}Geen Git repository gevonden. Deze test is bedoeld voor gebruik in een Git repository.${NC}"
    if ! ask_yes_no "Wil je toch doorgaan?"; then
        echo -e "${YELLOW}Test deployment geannuleerd.${NC}"
        exit 0
    fi
fi

# Controleer of docker-compose.yml bestaat
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}docker-compose.yml niet gevonden. Voer dit script uit vanuit de project directory.${NC}"
    exit 1
fi

# Waarschuwing voor gebruiker
echo -e "${YELLOW}Dit script maakt een tijdelijke kopie van je project en test de deployment procedure.${NC}"
echo -e "${YELLOW}Dit heeft geen invloed op je bestaande installatie.${NC}"
if ! ask_yes_no "Wil je doorgaan?"; then
    echo -e "${YELLOW}Test deployment geannuleerd.${NC}"
    exit 0
fi

# Maak een tijdelijke directory
TEMP_DIR=$(mktemp -d)
echo -e "${YELLOW}Tijdelijke map aangemaakt: ${TEMP_DIR}${NC}"

# Functie om op te ruimen bij exit
cleanup() {
    echo -e "${YELLOW}Opruimen van tijdelijke bestanden...${NC}"
    rm -rf "$TEMP_DIR"
    echo -e "${YELLOW}Tijdelijke bestanden verwijderd.${NC}"
}

# Registreer cleanup functie om uitgevoerd te worden bij exit
trap cleanup EXIT

# Kopieer project naar tijdelijke directory
echo -e "${YELLOW}Project kopiëren naar tijdelijke map...${NC}"
git archive --format=tar HEAD | (cd "$TEMP_DIR" && tar xf -)

# Ga naar tijdelijke directory
cd "$TEMP_DIR"

# Voer docker-compose build uit
echo -e "${YELLOW}Docker containers bouwen...${NC}"
docker-compose build || {
    echo -e "${RED}Docker build mislukt! Dit zou problemen kunnen veroorzaken bij deployment.${NC}"
    exit 1
}

# Start containers
echo -e "${YELLOW}Docker containers starten...${NC}"
docker-compose up -d || {
    echo -e "${RED}Docker start mislukt! Dit zou problemen kunnen veroorzaken bij deployment.${NC}"
    exit 1
}

# Wacht even zodat containers kunnen opstarten
echo -e "${YELLOW}Wachten tot containers gereed zijn...${NC}"
sleep 10

# Controleer status van containers
echo -e "${YELLOW}Container status controleren...${NC}"
if docker-compose ps | grep -q "Exit"; then
    echo -e "${RED}Eén of meer containers zijn gestopt! Bekijk de logs hieronder.${NC}"
    docker-compose logs
    echo -e "${RED}Test deployment MISLUKT! Los deze problemen op voor deployment.${NC}"
    exit 1
else
    echo -e "${GREEN}Alle containers draaien!${NC}"
fi

# Controleer of web container reageert
echo -e "${YELLOW}Web service testen...${NC}"
if docker-compose exec web curl -s --head http://localhost:5000 | grep -q "200 OK"; then
    echo -e "${GREEN}Web service reageert met HTTP 200 OK!${NC}"
else
    echo -e "${RED}Web service reageert niet correct. Bekijk de logs hieronder.${NC}"
    docker-compose logs web
    echo -e "${RED}Test deployment MISLUKT! Los deze problemen op voor deployment.${NC}"
    exit 1
fi

# Stop containers
echo -e "${YELLOW}Test containers stoppen...${NC}"
docker-compose down

# Test geslaagd
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Test deployment GESLAAGD!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo
echo -e "${GREEN}Het deployment proces werkt correct. Je kunt nu veilig deployen.${NC}"
echo -e "${YELLOW}Gebruik ./deploy.sh om de echte deployment uit te voeren.${NC}"