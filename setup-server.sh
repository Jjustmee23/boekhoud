#!/bin/bash
# Volledig automatisch installatiesysteem voor Boekhoudapplicatie
# Dit script zet automatisch alle benodigde componenten op voor een productie-omgeving

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
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

# Controleer of script wordt uitgevoerd als root
if [ "$EUID" -ne 0 ]; then
    error "Dit script moet als root worden uitgevoerd. Probeer 'sudo $0'"
fi

# Welkomstbericht
clear
log "==================================================================="
log "    AUTOMATISCHE INSTALLATIE VAN BOEKHOUDAPPLICATIE"
log "==================================================================="
log ""

# Vraag om installatie-opties
read -p "Voer het domein in (bijv. boekhoud.midaweb.be): " DOMAIN
read -p "Voer je e-mailadres in (voor SSL certificaten): " EMAIL
read -p "Wil je een strong wachtwoord genereren voor de database? (j/n): " GEN_PASSWORD

# Genereer wachtwoord indien gevraagd
if [[ "$GEN_PASSWORD" =~ ^[Jj]$ ]]; then
    DB_PASSWORD=$(openssl rand -base64 16)
    log "Database wachtwoord gegenereerd"
else
    read -s -p "Voer een wachtwoord in voor de database: " DB_PASSWORD
    echo ""
fi

# Maak .env bestand
log "Aanmaken van .env bestand met configuratie-instellingen"
cat > .env << EOF
# Basis configuratie
DOMAIN=${DOMAIN}
LETSENCRYPT_EMAIL=${EMAIL}

# Database configuratie
POSTGRES_USER=postgres
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=boekhouding
DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/boekhouding

# Applicatie instellingen
FLASK_SECRET_KEY=$(openssl rand -hex 32)
SESSION_SECRET=$(openssl rand -hex 32)
ADMIN_EMAIL=${EMAIL}
ADMIN_PASSWORD=$(openssl rand -base64 12)
ENABLE_REGISTRATION=True
DOCKER_MODE=True

# Timezone instellingen
TZ=Europe/Amsterdam
EOF

log ".env bestand aangemaakt met basis configuratie"
log ""
log "Admin wachtwoord: $(grep ADMIN_PASSWORD .env | cut -d '=' -f2)"
log "Bewaar dit wachtwoord op een veilige plaats!"
log ""

# Update systeem en installeer benodigde pakketten
log "Updaten van systeem en installeren van benodigde pakketten"
apt-get update
apt-get upgrade -y
apt-get install -y curl git ufw

# Installeer Docker en Docker Compose
log "Installeren van Docker en Docker Compose via install-docker.sh"
chmod +x install-docker.sh
./install-docker.sh

# Configureer firewall
log "Configureren van firewall"
ufw allow ssh
ufw allow http
ufw allow https
yes | ufw enable

# Maak directory structuur aan
log "Aanmaken van directory structuur"
mkdir -p nginx/ssl
chmod +x nginx/dhparam-generator.sh
./nginx/dhparam-generator.sh

# Start de applicatie
log "Starten van de applicatie containers"
docker compose up -d

# Controleer of containers draaien
log "Controleren of alle containers actief zijn"
docker compose ps
sleep 5

# Laatste stappen en instructies
log "==================================================================="
log "INSTALLATIE VOLTOOID!"
log "==================================================================="
log ""
log "Je applicatie wordt nu opgestart op ${DOMAIN}."
log "Het kan enkele minuten duren voordat het SSL certificaat is uitgegeven."
log ""
log "Admin account gegevens:"
log "- E-mail: ${EMAIL}"
log "- Wachtwoord: $(grep ADMIN_PASSWORD .env | cut -d '=' -f2)"
log ""
log "Database gegevens:"
log "- Gebruikersnaam: postgres"
log "- Wachtwoord: ${DB_PASSWORD}"
log ""
log "Om te controleren of alles correct werkt, ga naar: https://${DOMAIN}"
log ""
log "Troubleshooting:"
log "- Gebruik './troubleshoot-domain.sh' als de website niet bereikbaar is"
log "- Bekijk logs met 'docker compose logs -f'"
log "- Herstart alle services met 'docker compose restart'"

# Einde script
exit 0