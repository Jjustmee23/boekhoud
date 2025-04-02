#!/bin/bash
# Volledig opschoonscript voor de server
# Dit script verwijdert Docker, alle installatiebestanden en andere componenten
# Na uitvoering blijft alleen de applicatiecode over

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log functie
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
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

# Header functie
header() {
    echo ""
    echo -e "${BLUE}===================================================================${NC}"
    echo -e "${BLUE}    $1${NC}"
    echo -e "${BLUE}===================================================================${NC}"
    echo ""
}

# Controleer of het script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./cleanup-server.sh'"
fi

# Waarschuwingsbericht en bevestiging
header "VOLLEDIGE SERVER OPSCHONING"
log "WAARSCHUWING: Dit script zal Docker volledig verwijderen, inclusief alle containers, images en volumes."
log "Eventuele database- en applicatiegegevens zullen permanent verloren gaan."
log "De applicatiecode blijft behouden, maar alle installatie- en configuratiebestanden worden verwijderd."
echo ""
read -p "Ben je ZEKER dat je wilt doorgaan met deze opschoning? (typ 'JA' om te bevestigen): " CONFIRM

if [ "$CONFIRM" != "JA" ]; then
    log "Opschoning geannuleerd."
    exit 0
fi

# Voer nog een bevestiging uit voor de zekerheid
echo ""
log "LAATSTE WAARSCHUWING: Deze actie kan niet ongedaan worden gemaakt. Alle Docker-containers en -volumes"
log "worden verwijderd, inclusief databasegegevens. Zorg voor backup indien nodig."
echo ""
read -p "Typ 'VERWIJDER ALLES' om definitief door te gaan: " FINAL_CONFIRM

if [ "$FINAL_CONFIRM" != "VERWIJDER ALLES" ]; then
    log "Opschoning geannuleerd."
    exit 0
fi

# Bepaal huidige directory
APP_DIR=$(pwd)
log "Werkdirectory: $APP_DIR"

# Stop en verwijder alle Docker containers
header "DOCKER OPSCHONEN"
log "Stoppen en verwijderen van alle Docker containers..."
if command -v docker &> /dev/null; then
    # Stop alle containers
    if docker ps -q | grep -q .; then
        docker stop $(docker ps -a -q)
        log "Alle Docker containers gestopt."
    else
        log "Geen actieve Docker containers gevonden."
    fi
    
    # Verwijder alle containers
    if docker ps -a -q | grep -q .; then
        docker rm -f $(docker ps -a -q)
        log "Alle Docker containers verwijderd."
    else
        log "Geen Docker containers om te verwijderen."
    fi
    
    # Verwijder alle volumes
    if docker volume ls -q | grep -q .; then
        docker volume rm $(docker volume ls -q)
        log "Alle Docker volumes verwijderd."
    else
        log "Geen Docker volumes om te verwijderen."
    fi
    
    # Verwijder alle images
    if docker images -q | grep -q .; then
        docker rmi -f $(docker images -q)
        log "Alle Docker images verwijderd."
    else
        log "Geen Docker images om te verwijderen."
    fi
    
    # Verwijder alle netwerken, behalve de standaard netwerken
    if docker network ls --filter "name=app" -q | grep -q .; then
        docker network rm $(docker network ls --filter "name=app" -q) 2>/dev/null || true
        log "Aangepaste Docker netwerken verwijderd."
    else
        log "Geen aangepaste Docker netwerken om te verwijderen."
    fi
else
    warn "Docker is niet geïnstalleerd. Niets om op te schonen."
fi

# Verwijder Docker volledig
header "DOCKER VERWIJDEREN"
log "Docker en gerelateerde componenten worden volledig verwijderd..."

if command -v docker &> /dev/null || command -v docker-compose &> /dev/null || [ -d "/var/lib/docker" ]; then
    # Stop Docker service
    systemctl stop docker docker.socket containerd || true
    
    # Verwijder Docker pakketten
    apt-get purge -y docker-ce docker-ce-cli containerd.io docker docker-engine docker.io 2>/dev/null || true
    apt-get purge -y runc docker-compose docker-compose-v2 2>/dev/null || true
    
    # Verwijder overige bestanden
    rm -rf /var/lib/docker /var/lib/containerd /etc/docker
    rm -f /usr/local/bin/docker-compose
    rm -rf /usr/local/lib/docker
    
    # Verwijder Docker repositories
    rm -f /etc/apt/sources.list.d/docker*.list
    
    # Verwijder Docker GPG sleutels
    rm -f /usr/share/keyrings/docker-archive-keyring.gpg
    
    # Update apt
    apt-get update
    
    # Autoremove om overgebleven pakketten op te schonen
    apt-get autoremove -y
    
    log "Docker en gerelateerde componenten zijn volledig verwijderd."
else
    log "Docker is niet geïnstalleerd. Niets om te verwijderen."
fi

# Verwijder installatiebestanden en scripts
header "INSTALLATIEBESTANDEN OPSCHONEN"
log "Installatiebestanden en scripts worden verwijderd..."

# Lijst van bestanden om te verwijderen
CLEANUP_FILES=(
    "installeer-boekhoud-app.sh"
    "setup-server.sh"
    "install-docker.sh"
    "setup-ssl.sh"
    "update-app.sh"
    "fix-workspaces.sh"
    "auto-fix-workspaces.sh"
    "beheer.sh"
    "troubleshoot-domain.sh"
    "docker-compose.yml"
    "Dockerfile"
    "docker-compose.yaml"
    "compose.yaml"
    "nginx"
    "backups"
    "fix_workspace_visibility.sql"
    "fix_results.log"
    "workspace_fix_result.log"
)

# Verwijder de bestanden en mappen
for file in "${CLEANUP_FILES[@]}"; do
    if [ -e "$APP_DIR/$file" ]; then
        rm -rf "$APP_DIR/$file"
        log "Verwijderd: $file"
    fi
done

# Verwijder alle .sh bestanden
find "$APP_DIR" -maxdepth 1 -name "*.sh" -type f -delete
log "Alle shell scripts verwijderd uit de hoofdmap."

# Verwijder Docker-gerelateerde bestanden
find "$APP_DIR" -maxdepth 1 -name "docker*" -type f -delete
log "Alle Docker-gerelateerde bestanden verwijderd."

# Verwijder .git mappen indien aanwezig
if [ -d "$APP_DIR/.git" ]; then
    log "Git repository wordt verwijderd..."
    rm -rf "$APP_DIR/.git"
    log "Git repository verwijderd."
fi

# Verwijder logs map
if [ -d "$APP_DIR/logs" ]; then
    log "Logs worden verwijderd..."
    rm -rf "$APP_DIR/logs"
    log "Logs verwijderd."
fi

# Bewaar alleen essentiële applicatiebestanden
header "APPLICATIEBESTANDEN BEHOUDEN"
log "Alleen essentiële applicatiebestanden worden behouden."

# Maak een nieuwe logs map aan
mkdir -p "$APP_DIR/logs"
log "Nieuwe logs map aangemaakt."

# Verwijder .env bestand
if [ -f "$APP_DIR/.env" ]; then
    log ".env configuratie wordt verwijderd..."
    mv "$APP_DIR/.env" "$APP_DIR/.env.backup"
    log ".env geback-upt naar .env.backup voor referentie."
fi

# Maak lege .env.example aan indien niet aanwezig
if [ ! -f "$APP_DIR/.env.example" ]; then
    log "Aanmaken van .env.example voor toekomstige configuratie..."
    cat > "$APP_DIR/.env.example" << 'EOL'
# Domein configuratie
DOMAIN=factuur.jouwdomein.nl
SSL_EMAIL=jouw@email.nl

# Database configuratie
DB_NAME=boekhouding
DB_USER=postgres
DB_PASSWORD=wachtwoord_veranderen!
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@postgres/${DB_NAME}

# Flask configuratie
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=verander_dit_wachtwoord_random_string

# Email configuratie (Microsoft Graph API)
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_TENANT_ID=
MS_GRAPH_SENDER_EMAIL=

# Mollie API configuratie
MOLLIE_API_KEY=
EOL
    log ".env.example aangemaakt."
fi

# Verwijder tijdelijke bestanden
log "Tijdelijke bestanden worden verwijderd..."
find "$APP_DIR" -name "*.tmp" -type f -delete
find "$APP_DIR" -name "*.bak" -type f -delete
find "$APP_DIR" -name "*~" -type f -delete
find "$APP_DIR" -name "*.swp" -type f -delete
log "Tijdelijke bestanden verwijderd."

# Verwijder dit script na uitvoering
header "OPSCHONING VOLTOOID"
log "De server is volledig opgeschoond. Docker en alle installatiebestanden zijn verwijderd."
log "Alleen de essentiële applicatiebestanden zijn behouden."
log ""
log "Volgende stappen:"
log "1. Je kunt een nieuwe, schone installatie uitvoeren op deze server."
log "2. Vergeet niet om nieuwe database-gegevens te configureren, aangezien alle data is verwijderd."
log ""
log "Dit opschoonscript zal zichzelf verwijderen na afsluiten."

# Maak een script dat zichzelf verwijdert
cat > /tmp/remove_cleanup.sh << 'EOL'
#!/bin/bash
rm -f "$0"
rm -f "cleanup-server.sh"
EOL

chmod +x /tmp/remove_cleanup.sh
log "Server opschonen voltooid."

# Voer het verwijderscript uit als laatste actie
at now + 1 minute -f /tmp/remove_cleanup.sh 2>/dev/null || {
    # Als 'at' niet beschikbaar is, verwijder niet automatisch
    log "Dit script (cleanup-server.sh) blijft behouden. Je kunt het handmatig verwijderen als je klaar bent."
}

exit 0