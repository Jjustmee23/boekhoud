#!/bin/bash
# Installatie script voor facturatie systeem op Ubuntu 22.04
# Dit script installeert alle benodigde software en configureert de applicatie

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
echo -e "${YELLOW}Facturatie Systeem - Installatie voor Ubuntu 22.04${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of script als root wordt uitgevoerd
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd als root of met sudo.${NC}"
    exit 1
fi

# Vraag bevestiging voor installatie
if ! ask_yes_no "Dit script installeert alle software voor het facturatie systeem. Doorgaan?"; then
    echo -e "${YELLOW}Installatie geannuleerd.${NC}"
    exit 0
fi

# Update pakkettenlijst
echo -e "${YELLOW}Pakkettenlijst updaten...${NC}"
apt update || {
    echo -e "${RED}Kan pakkettenlijst niet updaten. Controleer je internetverbinding.${NC}"
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

# Vraag om installatie map
echo -e "${YELLOW}Kies een installatie map. Standaard is /var/www/facturatie.${NC}"
read -p "Installatie map [/var/www/facturatie]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-/var/www/facturatie}

# Maak installatie map
echo -e "${YELLOW}Installatie map aanmaken: ${INSTALL_DIR}${NC}"
mkdir -p "$INSTALL_DIR"

# Vraag om Git repository URL
echo -e "${YELLOW}Geef de URL van de Git repository.${NC}"
read -p "Git repository URL: " GIT_URL
if [ -z "$GIT_URL" ]; then
    echo -e "${RED}Geen Git repository URL opgegeven. Installatie wordt afgebroken.${NC}"
    exit 1
fi

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
    
    # Vraag gebruiker of ze het .env bestand willen bewerken
    if ask_yes_no "Wil je het .env bestand nu bewerken?"; then
        ${EDITOR:-nano} .env
    else
        echo -e "${YELLOW}Vergeet niet om het .env bestand later te configureren: ${INSTALL_DIR}/.env${NC}"
    fi
else
    echo -e "${YELLOW}Geen .env.example gevonden. Je moet handmatig een .env bestand maken.${NC}"
fi

# Vraag of gebruiker Docker containers wil starten
if ask_yes_no "Wil je de Docker containers nu starten?"; then
    echo -e "${YELLOW}Docker containers starten...${NC}"
    docker-compose up -d || {
        echo -e "${RED}Kan Docker containers niet starten. Zie foutmelding hierboven.${NC}"
        exit 1
    }
    echo -e "${GREEN}Docker containers succesvol gestart.${NC}"
else
    echo -e "${YELLOW}Docker containers niet gestart. Start later handmatig met: cd ${INSTALL_DIR} && docker-compose up -d${NC}"
fi

# Installatie voltooid
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Installatie voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Systeem is geïnstalleerd in: ${INSTALL_DIR}${NC}"
echo -e "${YELLOW}Je kunt nu de volgende commando's gebruiken:${NC}"
echo -e "${YELLOW}- docker-compose up -d       # Start de applicatie${NC}"
echo -e "${YELLOW}- docker-compose down        # Stop de applicatie${NC}"
echo -e "${YELLOW}- ./deploy.sh                # Update de applicatie${NC}"
echo -e "${YELLOW}- ./backup-database.sh       # Maak een database backup${NC}"
echo -e "${YELLOW}- docker-compose logs -f web # Bekijk de logs${NC}"
echo

# Voeg actieve gebruiker toe aan docker groep
SUDO_USER="${SUDO_USER:-$USER}"
if [ "$SUDO_USER" != "root" ]; then
    echo -e "${YELLOW}Gebruiker ${SUDO_USER} toevoegen aan docker groep...${NC}"
    usermod -aG docker "$SUDO_USER"
    echo -e "${YELLOW}Let op: Log uit en log weer in om de wijzigingen toe te passen.${NC}"
fi