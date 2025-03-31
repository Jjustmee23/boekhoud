#!/bin/bash
# Alles-in-één installatie script voor facturatie systeem op Ubuntu 22.04
# Dit script downloadt en voert alle benodigde installatiestappen uit

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Facturatie Systeem - Alles-in-één installatie${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of we root zijn
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd als root of met sudo.${NC}"
    exit 1
fi

# Update pakkettenlijst
echo -e "${YELLOW}Pakkettenlijst updaten...${NC}"
apt update || {
    echo -e "${RED}Kan pakkettenlijst niet updaten. Controleer je internetverbinding.${NC}"
    exit 1
}

# Upgrade pakketten
echo -e "${YELLOW}Pakketten upgraden...${NC}"
apt upgrade -y || {
    echo -e "${RED}Kan pakketten niet upgraden. Zie foutmelding hierboven.${NC}"
    exit 1
}

# Installeer benodigde pakketten
echo -e "${YELLOW}Benodigde pakketten installeren...${NC}"
apt install -y git docker.io docker-compose python3-pip curl postgresql-client ufw || {
    echo -e "${RED}Kan pakketten niet installeren. Zie foutmelding hierboven.${NC}"
    exit 1
}

# Start en enable Docker
echo -e "${YELLOW}Docker starten en enable...${NC}"
systemctl start docker
systemctl enable docker

# Stel Git repository URL in (deze URL moet worden aangepast aan jouw repository)
GIT_URL="https://github.com/jouw-gebruikersnaam/facturatie-systeem.git"
echo -e "${YELLOW}Git repository URL: ${GIT_URL}${NC}"
echo -e "${YELLOW}Je kunt deze URL wijzigen in dit script als het niet correct is.${NC}"

# Maak installatie map
INSTALL_DIR="/var/www/facturatie"
echo -e "${YELLOW}Installatie map aanmaken: ${INSTALL_DIR}${NC}"
mkdir -p "$INSTALL_DIR"

# Clone repository
echo -e "${YELLOW}Repository klonen naar ${INSTALL_DIR}...${NC}"
git clone "$GIT_URL" "$INSTALL_DIR" || {
    echo -e "${RED}Kan repository niet klonen. Controleer de URL en je internetverbinding.${NC}"
    exit 1
}

# Ga naar installatie map
cd "$INSTALL_DIR" || {
    echo -e "${RED}Kan niet naar installatie map gaan. Controleer permissies.${NC}"
    exit 1
}

# Maak scripts uitvoerbaar
echo -e "${YELLOW}Scripts uitvoerbaar maken...${NC}"
chmod +x *.sh || echo -e "${YELLOW}Geen uitvoerbare scripts gevonden of permissie geweigerd.${NC}"

# Maak .env bestand
if [ -f .env.example ]; then
    echo -e "${YELLOW}Configuratie bestand maken van voorbeeld...${NC}"
    cp .env.example .env || {
        echo -e "${RED}Kan .env bestand niet maken.${NC}"
        exit 1
    }
    
    echo -e "${YELLOW}Je moet het .env bestand bewerken voordat je de applicatie start:${NC}"
    echo -e "${YELLOW}${INSTALL_DIR}/.env${NC}"
else
    echo -e "${YELLOW}Geen .env.example gevonden. Je moet handmatig een .env bestand maken.${NC}"
fi

# Voeg huidige gebruiker toe aan docker groep
SUDO_USER="${SUDO_USER:-$USER}"
if [ "$SUDO_USER" != "root" ]; then
    echo -e "${YELLOW}Gebruiker ${SUDO_USER} toevoegen aan docker groep...${NC}"
    usermod -aG docker "$SUDO_USER"
    echo -e "${YELLOW}Let op: Log uit en log weer in om de wijzigingen toe te passen.${NC}"
fi

# Installatie voltooid
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Basis installatie voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Belangrijke volgende stappen:${NC}"
echo -e "${YELLOW}1. Log uit en log weer in (of herstart) om docker groep wijzigingen toe te passen${NC}"
echo -e "${YELLOW}2. Bewerk het .env bestand: nano ${INSTALL_DIR}/.env${NC}"
echo -e "${YELLOW}3. Start de applicatie: cd ${INSTALL_DIR} && docker-compose up -d${NC}"
echo
echo -e "${YELLOW}Gebruik de volgende commando's voor beheer:${NC}"
echo -e "${YELLOW}- docker-compose up -d       # Start de applicatie${NC}"
echo -e "${YELLOW}- docker-compose down        # Stop de applicatie${NC}"
echo -e "${YELLOW}- ./deploy.sh                # Update de applicatie${NC}"
echo -e "${YELLOW}- ./backup-database.sh       # Maak een database backup${NC}"
echo -e "${YELLOW}- ./schedule-backups.sh      # Stel automatische backups in${NC}"