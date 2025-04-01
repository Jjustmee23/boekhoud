#!/bin/bash
# Script voor het opzetten van de facturatie applicatie op een schone Ubuntu 22.04 server
# Dit script installeert Docker, klont de repository en voert de installatie uit

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log functie
log() {
    echo -e "${GREEN}[SETUP]${NC} $1"
}

# Waarschuwing functie
warn() {
    echo -e "${YELLOW}[WAARSCHUWING]${NC} $1"
}

# Error functie
error() {
    echo -e "${RED}[FOUT]${NC} $1"
    exit 1
}

# Controleer of het script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./setup-ubuntu.sh'"
fi

# Update systeem
log "Pakketlijsten bijwerken..."
apt-get update && apt-get upgrade -y || error "Kan pakketlijsten niet bijwerken"

# Installeer benodigde pakketten
log "Benodigde pakketten installeren..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    || error "Kan benodigde pakketten niet installeren"

# Installeer Docker
log "Docker installeren..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io || error "Kan Docker niet installeren"
    log "Docker is geïnstalleerd"
else
    log "Docker is al geïnstalleerd"
fi

# Installeer Docker Compose
log "Docker Compose installeren..."
if ! command -v docker-compose &> /dev/null; then
    apt-get install -y docker-compose-plugin || error "Kan Docker Compose niet installeren"
    log "Docker Compose is geïnstalleerd"
else
    log "Docker Compose is al geïnstalleerd"
fi

# Vraag de gebruiker om de git repository URL
read -p "Voer de git repository URL in (laat leeg voor handmatige setup): " GIT_REPO
if [ -z "$GIT_REPO" ]; then
    log "Geen git repository opgegeven. Je kunt handmatig bestanden uploaden naar de server."
    read -p "In welke map wil je de applicatie installeren? [/opt/facturatie]: " APP_DIR
    APP_DIR=${APP_DIR:-/opt/facturatie}
    mkdir -p "$APP_DIR"
    log "Directory aangemaakt: $APP_DIR"
    log "Upload de applicatiebestanden naar deze map en voer daar ./install-docker.sh uit"
else
    # Vraag om de doelmap
    read -p "In welke map wil je de applicatie installeren? [/opt/facturatie]: " APP_DIR
    APP_DIR=${APP_DIR:-/opt/facturatie}
    
    # Clone de repository
    log "Git repository klonen naar $APP_DIR..."
    git clone "$GIT_REPO" "$APP_DIR" || error "Kan git repository niet klonen. Als je de standaard repository wilt gebruiken, voer dan in: git clone https://github.com/Jjustmee23/boekhoud.git $APP_DIR"
    
    # Ga naar de map en maak install-docker.sh uitvoerbaar
    cd "$APP_DIR" || error "Kan niet naar $APP_DIR navigeren"
    chmod +x install-docker.sh
    
    # Vraag of de gebruiker direct wil doorgaan met de installatie
    read -p "Wil je direct doorgaan met de installatie? (j/n) [j]: " CONTINUE
    CONTINUE=${CONTINUE:-j}
    if [[ $CONTINUE == "j" || $CONTINUE == "J" ]]; then
        log "Installatie starten..."
        ./install-docker.sh || error "Installatie is mislukt"
    else
        log "Installatie gepauzeerd. Voer later '$APP_DIR/install-docker.sh' uit om verder te gaan."
    fi
fi

log "Setup script voltooid."
log "Controleer dat je domein correct is geconfigureerd in DNS en dat poorten 80 en 443 zijn opengesteld in de firewall."
log "Voor meer informatie, zie README.md en GEBRUIKSHANDLEIDING.md in de applicatiemap."