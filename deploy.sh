#!/bin/bash
# Deploy script voor het bijwerken van de applicatie op een privéserver
# Gebruik: ./deploy.sh [server_adres] [server_gebruiker] [app_directory]

set -e  # Script stopt bij een fout

# Controleer argumenten
SERVER_ADDR=${1:-user@example.com}
SERVER_USER=${2:-$(whoami)}
APP_DIR=${3:-/opt/facturatie-app}

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

echo -e "${YELLOW}Deployment naar privéserver starten...${NC}"
echo -e "Server: ${SERVER_ADDR}"
echo -e "Gebruiker: ${SERVER_USER}"
echo -e "Applicatie directory: ${APP_DIR}"
echo ""

# Controleer of we de server kunnen bereiken
echo -e "${YELLOW}Controleren of de server bereikbaar is...${NC}"
ssh -q ${SERVER_ADDR} "echo -e '${GREEN}Verbinding met server succesvol${NC}'" || {
    echo -e "${RED}Kan geen verbinding maken met de server. Controleer het serveradres en SSH-toegang.${NC}"
    exit 1
}

# Bereid de code voor
echo -e "${YELLOW}Voorbereiden van de code voor deployment...${NC}"
TEMP_DIR=$(mktemp -d)
echo -e "Tijdelijke directory: ${TEMP_DIR}"

# Kopieer relevante bestanden naar een tijdelijke map
rsync -av --exclude='__pycache__' --exclude='*.pyc' --exclude='.git' \
      --exclude='venv' --exclude='node_modules' --exclude='logs/*' \
      --exclude='static/uploads/*' --exclude='db_backups/*' \
      --exclude='.env' \
      ./ ${TEMP_DIR}/

# Maak een backup van de database op de server
echo -e "${YELLOW}Database backup maken op de server...${NC}"
ssh ${SERVER_ADDR} "cd ${APP_DIR} && docker-compose exec -T db pg_dump -U \${POSTGRES_USER:-postgres} \${POSTGRES_DB:-facturatie} > /tmp/pre_deploy_backup_\$(date +%Y%m%d_%H%M%S).sql && echo -e '${GREEN}Database backup succesvol${NC}'"

# Kopieer de code naar de server
echo -e "${YELLOW}Code naar server kopiëren...${NC}"
ssh ${SERVER_ADDR} "mkdir -p ${APP_DIR}"
rsync -av --progress ${TEMP_DIR}/ ${SERVER_ADDR}:${APP_DIR}/

# Schoon tijdelijke directory op
rm -rf ${TEMP_DIR}

# Doe een graceful restart van de containers
echo -e "${YELLOW}Applicatie herstarten op de server...${NC}"
ssh ${SERVER_ADDR} "cd ${APP_DIR} && docker-compose build web && docker-compose up -d --no-deps web && echo -e '${GREEN}Applicatie succesvol herstart${NC}'"

# Toon logs voor mogelijke fouten
echo -e "${YELLOW}Controleren op fouten in de logs...${NC}"
ssh ${SERVER_ADDR} "cd ${APP_DIR} && docker-compose logs --tail=50 web"

echo -e "${GREEN}Deployment voltooid! De applicatie is bijgewerkt op de server.${NC}"
echo -e "${YELLOW}Controleer handmatig of alles correct werkt op https://uw-domein.nl${NC}"