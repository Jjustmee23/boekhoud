#!/bin/bash
# Script voor het installeren van Docker en het opzetten van de factuurapplicatie
# op een Ubuntu 22.04 server

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
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./install-docker.sh'"
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

# Maak .env bestand op basis van .env.example als het nog niet bestaat
if [ ! -f .env ]; then
    log "Configuratiebestand .env aanmaken..."
    
    # Vraag om domeinnaam
    read -p "Voer je domeinnaam in (bijv. factuur.jouwdomein.nl): " DOMAIN
    if [ -z "$DOMAIN" ]; then
        warn "Geen domeinnaam opgegeven. Standaard domeinnaam wordt gebruikt."
        DOMAIN="factuur.jouwdomein.nl"
    fi
    
    # Vraag om e-mailadres voor SSL certificaten
    read -p "Voer je e-mailadres in voor SSL certificaten: " SSL_EMAIL
    if [ -z "$SSL_EMAIL" ]; then
        warn "Geen e-mailadres opgegeven. Standaard e-mailadres wordt gebruikt."
        SSL_EMAIL="admin@$DOMAIN"
    fi
    
    # Genereer database wachtwoord
    DB_PASSWORD=$(openssl rand -base64 12)
    
    # Genereer sessie geheim
    SESSION_SECRET=$(openssl rand -base64 24)
    
    # Maak .env bestand
    cat > .env << EOL
# Domein configuratie
DOMAIN=$DOMAIN
SSL_EMAIL=$SSL_EMAIL

# Database configuratie
DB_NAME=facturatie
DB_USER=facturatie_user
DB_PASSWORD=$DB_PASSWORD
DATABASE_URL=postgresql://\${DB_USER}:\${DB_PASSWORD}@postgres/\${DB_NAME}

# Flask configuratie
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=$SESSION_SECRET

# Email configuratie (Microsoft Graph API)
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_TENANT_ID=
MS_GRAPH_SENDER_EMAIL=

# Mollie API configuratie
MOLLIE_API_KEY=
EOL

    log ".env bestand aangemaakt"
    log "Database wachtwoord: $DB_PASSWORD (bewaar dit op een veilige plaats)"
    log "Je moet nog je Microsoft Graph API en Mollie API instellingen invullen in het .env bestand"
else
    log ".env bestand bestaat al, geen nieuw bestand aangemaakt"
fi

# Maak mappen aan als ze nog niet bestaan
log "Benodigde mappen aanmaken..."
mkdir -p logs
mkdir -p static/uploads
mkdir -p nginx/ssl

# Genereer dhparam.pem bestand
if [ ! -f nginx/ssl/dhparam.pem ]; then
    log "DH parameters genereren voor verhoogde veiligheid..."
    log "Dit kan enkele minuten duren..."
    openssl dhparam -out nginx/ssl/dhparam.pem 2048 || warn "Kon geen dhparam.pem genereren"
    
    if [ -f nginx/ssl/dhparam.pem ]; then
        log "DH parameters succesvol gegenereerd"
    fi
else
    log "DH parameters bestaan al"
fi

# Start de containers
log "Docker containers starten..."
docker compose up -d || error "Kan Docker containers niet starten"

log "Installatie voltooid!"
log "Je applicatie is nu beschikbaar via https://$DOMAIN (wanneer je domein is geconfigureerd)"
log ""
log "Gebruik de volgende commando's om je applicatie te beheren:"
log "  Start:   docker compose up -d"
log "  Stop:    docker compose down"
log "  Logs:    docker compose logs -f"
log "  Status:  docker compose ps"
log ""
log "Vergeet niet de benodigde API sleutels in te vullen in het .env bestand!"
log "Zodra je de sleutels hebt ingevuld, herstart de applicatie met: docker compose restart"