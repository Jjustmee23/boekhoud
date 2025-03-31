#!/bin/bash
# Test deployment script voor het lokaal testen van wijzigingen
# zonder de productiedatabase te beïnvloeden

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

echo -e "${YELLOW}Test deployment starten...${NC}"

# Controleer of docker en docker-compose geïnstalleerd zijn
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}docker-compose kon niet gevonden worden. Installeer docker-compose eerst.${NC}"
    exit 1
fi

# Maak een backup van de bestaande database (indien nodig)
if [ "$1" = "--backup" ] || [ "$1" = "-b" ]; then
    echo -e "${YELLOW}Database backup maken...${NC}"
    ./backup-database.sh || {
        echo -e "${RED}Database backup mislukt.${NC}"
        exit 1
    }
fi

# Build en start de applicatie (zonder database te verwijderen)
echo -e "${YELLOW}Applicatie bouwen en starten...${NC}"
docker-compose build web || {
    echo -e "${RED}Docker build mislukt.${NC}"
    exit 1
}

docker-compose up -d --no-deps web || {
    echo -e "${RED}Docker compose up mislukt.${NC}"
    exit 1
}

# Wacht even totdat de applicatie is opgestart
echo -e "${YELLOW}Even wachten totdat de applicatie is opgestart...${NC}"
sleep 3

# Toon de logs
echo -e "${YELLOW}Logs van de applicatie:${NC}"
docker-compose logs --tail=30 web

echo -e "${GREEN}Test deployment voltooid! De applicatie is bijgewerkt en draait nu op http://localhost:${PORT:-5000}${NC}"
echo -e "${YELLOW}Controleer of alle functionaliteit correct werkt voordat je naar productie deployt.${NC}"