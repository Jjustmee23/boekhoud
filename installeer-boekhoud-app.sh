#!/bin/bash
# Automatische installatie script voor Boekhoud Applicatie
# Installatie op Ubuntu 22.04 of hoger met Docker, Nginx proxy en SSL

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
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./installeer-boekhoud-app.sh'"
fi

# Welkomstbericht
header "BOEKHOUD APPLICATIE INSTALLER"
log "Welkom bij het automatische installatiescript voor de Boekhoud Applicatie."
log "Dit script zal:"
log "1. De benodigde software installeren (Docker, Git, etc.)"
log "2. De applicatie configureren"
log "3. Een beveiligde database opzetten"
log "4. Een SSL/TLS-certificaat aanvragen via Let's Encrypt"
log "5. De applicatie opstarten"
echo ""
log "De applicatie maakt gebruik van de volgende technologieën:"
log "- Docker en Docker Compose voor containerisatie"
log "- Nginx als reverse proxy met automatische SSL-certificaten"
log "- PostgreSQL als database"
log "- Python Flask als applicatieframework"
echo ""

# Vraag om bevestiging
read -p "Wil je doorgaan met de installatie? (j/n): " CONTINUE
if [[ ! "$CONTINUE" =~ ^[Jj]$ ]]; then
    log "Installatie geannuleerd."
    exit 0
fi

# Bepaal installatiemap
header "INSTALLATIE LOCATIE"
DEFAULT_INSTALL_DIR="/opt/boekhoudapp"
read -p "Geef de installatiemap op [$DEFAULT_INSTALL_DIR]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-$DEFAULT_INSTALL_DIR}

# Controleer en maak de installatiemap
if [ -d "$INSTALL_DIR" ]; then
    warn "De map $INSTALL_DIR bestaat al."
    read -p "Wil je doorgaan en de map overschrijven? (j/n): " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Jj]$ ]]; then
        log "Installatie geannuleerd."
        exit 0
    fi
else
    log "Aanmaken van installatiemap $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
fi

# Navigeer naar installatiemap
cd "$INSTALL_DIR" || error "Kan niet naar installatiemap navigeren: $INSTALL_DIR"
log "Werken in: $INSTALL_DIR"

# Controleer systeemvereisten
header "SYSTEEMVEREISTEN CONTROLEREN"
log "Controleren van OS versie..."
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" == "ubuntu" ]]; then
        if [[ "$VERSION_ID" == "22.04" || "$VERSION_ID" > "22.04" ]]; then
            log "Ubuntu $VERSION_ID gedetecteerd. Ondersteunde versie."
        else
            warn "Ubuntu $VERSION_ID gedetecteerd. Aanbevolen is 22.04 of hoger."
            read -p "Wil je toch doorgaan? (j/n): " CONTINUE_ANYWAY
            if [[ ! "$CONTINUE_ANYWAY" =~ ^[Jj]$ ]]; then
                log "Installatie geannuleerd."
                exit 0
            fi
        fi
    else
        warn "Het besturingssysteem ($ID) is niet Ubuntu. Deze installer is geoptimaliseerd voor Ubuntu."
        read -p "Wil je toch doorgaan? (j/n): " CONTINUE_ANYWAY
        if [[ ! "$CONTINUE_ANYWAY" =~ ^[Jj]$ ]]; then
            log "Installatie geannuleerd."
            exit 0
        fi
    fi
else
    warn "Kan het besturingssysteem niet detecteren. Ga door op eigen risico."
    read -p "Wil je toch doorgaan? (j/n): " CONTINUE_ANYWAY
    if [[ ! "$CONTINUE_ANYWAY" =~ ^[Jj]$ ]]; then
        log "Installatie geannuleerd."
        exit 0
    fi
fi

# Server setup script aanmaken en uitvoeren
header "SERVER VOORBEREIDEN"
log "Server setup script wordt aangemaakt..."

cat > "$INSTALL_DIR/setup-server.sh" << 'EOL'
#!/bin/bash
# Server setup script voor Boekhoud Applicatie

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

log "Server setup wordt gestart..."

# Update systeem
log "Systeem wordt bijgewerkt..."
apt-get update
apt-get upgrade -y

# Installeer essentiële pakketten
log "Installeren van essentiële pakketten..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    nano \
    ufw \
    unzip \
    htop

# Installeer Docker
log "Docker wordt geïnstalleerd..."
if command -v docker &> /dev/null; then
    log "Docker is al geïnstalleerd."
else
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    systemctl enable docker
    systemctl start docker
    log "Docker is geïnstalleerd en gestart."
fi

# Installeer Docker Compose
log "Docker Compose wordt geïnstalleerd..."
if command -v docker-compose &> /dev/null; then
    log "Docker Compose is al geïnstalleerd."
else
    mkdir -p /usr/local/lib/docker/cli-plugins
    curl -SL https://github.com/docker/compose/releases/download/v2.23.3/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
    log "Docker Compose is geïnstalleerd."
fi

# Configureer firewall
log "Firewall wordt geconfigureerd..."
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
if ! ufw status | grep -q "Status: active"; then
    log "Firewall wordt geactiveerd..."
    echo "y" | ufw enable
    log "Firewall is geactiveerd."
else
    log "Firewall is al geactiveerd."
fi

# Toon firewall status
ufw status

log "Server setup is voltooid."
EOL

chmod +x "$INSTALL_DIR/setup-server.sh"
log "Server setup script wordt uitgevoerd..."
"$INSTALL_DIR/setup-server.sh" || error "Server setup mislukt."

# Docker installatie script aanmaken en uitvoeren
header "DOCKER INSTALLEREN"
log "Docker installatie script wordt aangemaakt..."

cat > "$INSTALL_DIR/install-docker.sh" << 'EOL'
#!/bin/bash
# Docker installatiescript voor Boekhoud Applicatie

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

log "Docker installatie wordt gestart..."

# Controleer of Docker al is geïnstalleerd
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    log "Docker en Docker Compose zijn al geïnstalleerd."
    docker --version
    docker-compose --version
    
    # Controleer of Docker daemon draait
    if systemctl is-active --quiet docker; then
        log "Docker daemon is actief."
    else
        log "Docker daemon wordt gestart..."
        systemctl start docker
        systemctl enable docker
    fi
    
    exit 0
fi

# Verwijder oude Docker versies indien aanwezig
log "Verwijderen van oudere Docker versies..."
apt-get remove -y docker docker-engine docker.io containerd runc || true

# Update pakketindex
log "Bijwerken van pakketindex..."
apt-get update

# Installeer benodigde pakketten voor HTTPS repos
log "Installeren van benodigde pakketten..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Voeg Docker GPG sleutel toe
log "Toevoegen Docker GPG sleutel..."
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Configureer Docker repository
log "Configureren Docker repository..."
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update pakketindex
log "Bijwerken van pakketindex met nieuwe repository..."
apt-get update

# Installeer Docker
log "Installeren van Docker Engine..."
apt-get install -y docker-ce docker-ce-cli containerd.io

# Zorg ervoor dat Docker wordt gestart bij het booten
log "Configureren Docker om te starten bij het opstarten..."
systemctl enable docker
systemctl start docker

# Test Docker
log "Testen van Docker installatie..."
if docker run --rm hello-world; then
    log "Docker werkt correct!"
else
    error "Docker installatie test mislukt. Zie bovenstaande foutmeldingen."
fi

# Installeer Docker Compose
log "Installeren van Docker Compose..."
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.23.3/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose

# Test Docker Compose
log "Testen van Docker Compose installatie..."
if docker-compose version; then
    log "Docker Compose werkt correct!"
else
    error "Docker Compose installatie mislukt. Zie bovenstaande foutmeldingen."
fi

log "Docker en Docker Compose zijn succesvol geïnstalleerd!"
EOL

chmod +x "$INSTALL_DIR/install-docker.sh"
log "Docker installatie script wordt uitgevoerd..."
"$INSTALL_DIR/install-docker.sh" || error "Docker installatie mislukt."

# Clone de applicatie code
header "APPLICATIE CODE OPHALEN"
log "Applicatiecode wordt opgehaald van GitHub..."

if command -v git &> /dev/null; then
    if [ -d "$INSTALL_DIR/.git" ]; then
        log "Git repository is al aanwezig. Update wordt uitgevoerd..."
        git pull origin main || warn "Kon de code niet updaten, ga door met bestaande code."
    else
        log "Klonen van GitHub repository..."
        # Verwijder alle bestanden behalve de scripts die we net hebben gemaakt
        find "$INSTALL_DIR" -maxdepth 1 -not -path "$INSTALL_DIR" -not -path "$INSTALL_DIR/setup-server.sh" -not -path "$INSTALL_DIR/install-docker.sh" -not -path "$INSTALL_DIR/installeer-boekhoud-app.sh" -exec rm -rf {} \; 2>/dev/null || true
        
        git clone https://github.com/Jjustmee23/boekhoud.git "$INSTALL_DIR/temp" || error "Kon de repository niet klonen."
        
        # Verplaats alle bestanden uit de temp map naar de hoofdmap
        mv "$INSTALL_DIR/temp"/* "$INSTALL_DIR/" 2>/dev/null || true
        mv "$INSTALL_DIR/temp"/.[!.]* "$INSTALL_DIR/" 2>/dev/null || true
        rm -rf "$INSTALL_DIR/temp"
        
        log "Repository succesvol gekloond."
    fi
else
    error "Git is niet geïnstalleerd. Installeer Git en probeer opnieuw."
fi

# Controleer of de benodigde bestanden aanwezig zijn
if [ ! -f "$INSTALL_DIR/docker-compose.yml" ] || [ ! -f "$INSTALL_DIR/Dockerfile" ]; then
    error "Kritieke bestanden ontbreken. Controleer de repository en probeer opnieuw."
fi

# Maak nginx directory structuur
log "Aanmaken van nginx directory structuur..."
mkdir -p "$INSTALL_DIR/nginx/ssl"

# Genereer DH Parameters voor extra security
log "Genereren van DH parameters voor SSL/TLS..."
if [ ! -f "$INSTALL_DIR/nginx/ssl/dhparam.pem" ]; then
    log "Dit kan enkele minuten duren..."
    openssl dhparam -out "$INSTALL_DIR/nginx/ssl/dhparam.pem" 2048 || warn "Kon geen DH parameters genereren. SSL/TLS beveiliging kan minder sterk zijn."
else
    log "DH parameters bestaan al, wordt overgeslagen."
fi

# Maak script voor automatische DH parameter generatie
cat > "$INSTALL_DIR/nginx/dhparam-generator.sh" << 'EOL'
#!/bin/bash
# Script voor het genereren van DH parameters voor SSL/TLS

# Kleuren voor output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${GREEN}[INFO]${NC} Genereren van DH parameters voor SSL/TLS beveiliging..."
echo -e "${GREEN}[INFO]${NC} Dit kan enkele minuten duren..."

mkdir -p /etc/nginx/ssl
openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048

echo -e "${GREEN}[INFO]${NC} DH parameters succesvol gegenereerd."
EOL

chmod +x "$INSTALL_DIR/nginx/dhparam-generator.sh"

# Aanmaken van nginx custom configuratie
cat > "$INSTALL_DIR/nginx/custom.conf" << 'EOL'
# Custom Nginx configuratie voor Boekhoud Applicatie

# Meer geheugen toewijzen voor grote uploads
client_max_body_size 50M;

# HTTP/2 instellingen
http2_push_preload on;

# Beveiliging headers
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

# Compressie instellingen
gzip on;
gzip_vary on;
gzip_proxied any;
gzip_comp_level 6;
gzip_types text/plain text/css text/xml application/json application/javascript application/xml+rss application/atom+xml image/svg+xml;
EOL

# Configuratie van de applicatie
header "APPLICATIE CONFIGUREREN"
log "Applicatieconfiguratie wordt aangemaakt..."

# Aanmaken van .env bestand
if [ -f "$INSTALL_DIR/.env" ]; then
    log ".env bestand bestaat al."
    read -p "Wil je het bestaande .env bestand overschrijven? (j/n): " OVERWRITE_ENV
    if [[ ! "$OVERWRITE_ENV" =~ ^[Jj]$ ]]; then
        log ".env blijft ongewijzigd."
    else
        mv "$INSTALL_DIR/.env" "$INSTALL_DIR/.env.backup.$(date +%Y%m%d%H%M%S)"
        log "Bestaande .env bestand is geback-upt."
    fi
fi

if [ ! -f "$INSTALL_DIR/.env" ] || [[ "$OVERWRITE_ENV" =~ ^[Jj]$ ]]; then
    log "Nieuw .env bestand wordt aangemaakt..."
    
    # Vraag domein informatie
    echo ""
    read -p "Voer het domein in voor de applicatie (bijv. factuur.jouwdomein.nl): " APP_DOMAIN
    read -p "Voer een e-mailadres in voor SSL certificaten: " SSL_EMAIL
    
    # Genereer wachtwoorden
    DB_PASSWORD=$(openssl rand -base64 16 | tr -dc 'a-zA-Z0-9' | head -c 16)
    SESSION_SECRET=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
    
    # Aanmaken .env bestand
    cat > "$INSTALL_DIR/.env" << EOL
# Domein configuratie
DOMAIN=${APP_DOMAIN}
SSL_EMAIL=${SSL_EMAIL}

# Database configuratie
DB_NAME=boekhouding
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@postgres/${DB_NAME}

# Flask configuratie
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=${SESSION_SECRET}

# Email configuratie (Microsoft Graph API)
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_TENANT_ID=
MS_GRAPH_SENDER_EMAIL=

# Mollie API configuratie
MOLLIE_API_KEY=
EOL

    log ".env bestand is aangemaakt met configuratie-instellingen."
    log "Database wachtwoord en sessie secret zijn automatisch gegenereerd."
    log "Je kunt de Microsoft Graph API en Mollie API-instellingen later configureren in het beheerdersdashboard."
fi

# Aanmaken van SSL-setup script
cat > "$INSTALL_DIR/setup-ssl.sh" << 'EOL'
#!/bin/bash
# SSL setup script voor Boekhoud Applicatie

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

log "SSL setup wordt gestart..."

# Controleer of .env bestand bestaat
if [ ! -f ".env" ]; then
    error ".env bestand niet gevonden. Zorg ervoor dat je in de juiste map bent."
fi

# Lees domein en e-mail uit .env
DOMAIN=$(grep DOMAIN .env | cut -d '=' -f2)
SSL_EMAIL=$(grep SSL_EMAIL .env | cut -d '=' -f2)

if [ -z "$DOMAIN" ] || [ -z "$SSL_EMAIL" ]; then
    error "Domein of SSL e-mail niet gevonden in .env bestand."
fi

log "Domein: $DOMAIN"
log "SSL E-mail: $SSL_EMAIL"

# Controleer of nginx directory bestaat
if [ ! -d "nginx" ]; then
    log "Nginx directory wordt aangemaakt..."
    mkdir -p nginx/ssl
fi

# Genereer DH parameters
if [ ! -f "nginx/ssl/dhparam.pem" ]; then
    log "Genereren van DH parameters voor SSL/TLS... (dit kan enkele minuten duren)"
    openssl dhparam -out nginx/ssl/dhparam.pem 2048 || warn "Kon geen DH parameters genereren."
else
    log "DH parameters bestaan al."
fi

log "SSL setup is voltooid. Certificaten worden automatisch aangevraagd bij eerste start."
EOL

chmod +x "$INSTALL_DIR/setup-ssl.sh"
log "SSL setup script is aangemaakt."

# Aanmaken van troubleshoot script
cat > "$INSTALL_DIR/troubleshoot-domain.sh" << 'EOL'
#!/bin/bash
# Domeintroubleshooting script voor Boekhoud Applicatie

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
}

# Header functie
header() {
    echo ""
    echo -e "${BLUE}===================================================================${NC}"
    echo -e "${BLUE}    $1${NC}"
    echo -e "${BLUE}===================================================================${NC}"
    echo ""
}

header "DOMEIN TROUBLESHOOTING"
log "Dit script controleert de domein- en SSL-configuratie."

# Controleer of .env bestand bestaat
if [ ! -f ".env" ]; then
    error ".env bestand niet gevonden. Zorg ervoor dat je in de juiste map bent."
    exit 1
fi

# Lees domein en e-mail uit .env
DOMAIN=$(grep DOMAIN .env | cut -d '=' -f2)
SSL_EMAIL=$(grep SSL_EMAIL .env | cut -d '=' -f2)

if [ -z "$DOMAIN" ] || [ -z "$SSL_EMAIL" ]; then
    error "Domein of SSL e-mail niet gevonden in .env bestand."
    exit 1
fi

log "Domein: $DOMAIN"
log "SSL E-mail: $SSL_EMAIL"

# Controleer of Docker draait
header "DOCKER STATUS"
if ! systemctl is-active --quiet docker; then
    error "Docker service is niet actief. Start met: systemctl start docker"
    exit 1
else
    log "Docker service is actief."
fi

# Controleer of containers draaien
header "CONTAINER STATUS"
log "Docker containers status:"
docker compose ps

# Controleer domein DNS
header "DNS CHECKS"
log "DNS records voor $DOMAIN:"
dig +short $DOMAIN A
dig +short $DOMAIN AAAA

log "IP van deze server:"
curl -s ifconfig.me
echo ""

# Controleer poorten
header "POORT CHECKS"
log "Controleren of poorten 80 en 443 open zijn:"
nc -zv localhost 80 || warn "Poort 80 lijkt niet open te zijn."
nc -zv localhost 443 || warn "Poort 443 lijkt niet open te zijn."

# Controleer SSL certificaten
header "SSL CERTIFICAAT STATUS"
log "SSL certificaten in container:"
docker exec -it nginx-proxy find /etc/nginx/certs -name "$DOMAIN*" || warn "Geen certificaten gevonden voor $DOMAIN"

# Bekijk logs van acme-companion
header "ACME COMPANION LOGS"
log "Laatste 20 log regels van acme-companion:"
docker logs acme-companion --tail 20

# Bekijk logs van nginx-proxy
header "NGINX PROXY LOGS"
log "Laatste 20 log regels van nginx-proxy:"
docker logs nginx-proxy --tail 20

# Bekijk logs van de app
header "APP LOGS"
log "Laatste 20 log regels van de app:"
docker compose logs app --tail 20

header "SUGGESTIES"
log "Als je problemen ervaart met het domein of SSL certificaten:"
log "1. Controleer of het DNS A-record verwijst naar het IP-adres van deze server"
log "2. Zorg ervoor dat poorten 80 en 443 open zijn in je firewall"
log "3. Controleer of het domein correct is ingesteld in het .env bestand"
log "4. Als SSL certificaten niet worden aangemaakt, herstart de containers:"
log "   docker compose down && docker compose up -d"
log "5. Controleer of het domein bereikbaar is op: http://$DOMAIN"
log "   Let's Encrypt moet toegang hebben tot http://$DOMAIN/.well-known/acme-challenge/"
log ""
log "Voor verdere hulp, bekijk de logs en raadpleeg de documentatie."
EOL

chmod +x "$INSTALL_DIR/troubleshoot-domain.sh"
log "Domeintroubleshooting script is aangemaakt."

# Aanmaken van beheer script
cat > "$INSTALL_DIR/beheer.sh" << 'EOL'
#!/bin/bash
# Beheerschript voor Boekhoud Applicatie

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
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./beheer.sh'"
    exit 1
fi

# Hoofdmenu functie
hoofdmenu() {
    clear
    header "BOEKHOUD APPLICATIE BEHEER"
    echo "1) Status weergeven"
    echo "2) Start applicatie"
    echo "3) Stop applicatie"
    echo "4) Herstart applicatie"
    echo "5) Toon logs"
    echo "6) Database backup maken"
    echo "7) Update applicatie"
    echo "8) Troubleshoot domein en SSL"
    echo "9) Fix werkruimten in beheerdersdashboard"
    echo "10) Reset admin wachtwoord"
    echo "0) Afsluiten"
    echo ""
    read -p "Maak een keuze: " KEUZE
    
    case $KEUZE in
        1) status ;;
        2) start ;;
        3) stop ;;
        4) herstart ;;
        5) logs ;;
        6) backup ;;
        7) update ;;
        8) troubleshoot ;;
        9) fix_workspaces ;;
        10) reset_admin ;;
        0) exit 0 ;;
        *) log "Ongeldige keuze."; sleep 2; hoofdmenu ;;
    esac
}

# Status functie
status() {
    header "APPLICATIE STATUS"
    log "Docker containers status:"
    docker compose ps
    
    log "Systeem informatie:"
    df -h | grep -v tmp | grep -v udev
    echo ""
    free -h
    echo ""
    
    log "Netwerkpoorten in gebruik:"
    ss -tulpn | grep -E ':(80|443)'
    
    read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
    hoofdmenu
}

# Start functie
start() {
    header "APPLICATIE STARTEN"
    log "Applicatie wordt gestart..."
    docker compose up -d
    log "Applicatie is gestart."
    sleep 2
    hoofdmenu
}

# Stop functie
stop() {
    header "APPLICATIE STOPPEN"
    log "Applicatie wordt gestopt..."
    docker compose down
    log "Applicatie is gestopt."
    sleep 2
    hoofdmenu
}

# Herstart functie
herstart() {
    header "APPLICATIE HERSTARTEN"
    log "Applicatie wordt herstart..."
    docker compose restart
    log "Applicatie is herstart."
    sleep 2
    hoofdmenu
}

# Logs functie
logs() {
    header "APPLICATIE LOGS"
    echo "1) Toon applicatie logs"
    echo "2) Toon nginx-proxy logs"
    echo "3) Toon acme-companion logs"
    echo "4) Toon database logs"
    echo "0) Terug naar hoofdmenu"
    echo ""
    read -p "Maak een keuze: " LOG_KEUZE
    
    case $LOG_KEUZE in
        1) 
            log "Applicatie logs worden weergegeven (Ctrl+C om te stoppen):"
            docker compose logs -f app
            logs
            ;;
        2) 
            log "Nginx-proxy logs worden weergegeven (Ctrl+C om te stoppen):"
            docker logs -f nginx-proxy
            logs
            ;;
        3) 
            log "Acme-companion logs worden weergegeven (Ctrl+C om te stoppen):"
            docker logs -f acme-companion
            logs
            ;;
        4) 
            log "Database logs worden weergegeven (Ctrl+C om te stoppen):"
            docker compose logs -f postgres
            logs
            ;;
        0) hoofdmenu ;;
        *) log "Ongeldige keuze."; sleep 2; logs ;;
    esac
}

# Backup functie
backup() {
    header "DATABASE BACKUP"
    BACKUP_DIR="backups"
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    
    mkdir -p "$BACKUP_DIR"
    
    log "Database backup wordt gemaakt..."
    docker exec -t $(docker ps -q --filter "name=postgres") pg_dumpall -c -U postgres > "$BACKUP_DIR/database_backup_$TIMESTAMP.sql"
    
    if [ $? -eq 0 ]; then
        log "Backup succesvol aangemaakt: $BACKUP_DIR/database_backup_$TIMESTAMP.sql"
    else
        error "Backup maken mislukt. Controleer de foutmeldingen."
    fi
    
    read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
    hoofdmenu
}

# Update functie
update() {
    header "APPLICATIE UPDATE"
    log "Let op: Dit zal de applicatie bijwerken naar de laatste versie."
    read -p "Wil je doorgaan met de update? (j/n): " UPDATE_CONFIRM
    
    if [[ "$UPDATE_CONFIRM" =~ ^[Jj]$ ]]; then
        if [ -f "./update-app.sh" ]; then
            log "Update script wordt uitgevoerd..."
            ./update-app.sh
        else
            error "Update script niet gevonden. Zorg ervoor dat update-app.sh aanwezig is."
        fi
    else
        log "Update geannuleerd."
    fi
    
    read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
    hoofdmenu
}

# Troubleshoot functie
troubleshoot() {
    header "DOMEIN TROUBLESHOOTING"
    if [ -f "./troubleshoot-domain.sh" ]; then
        log "Troubleshoot script wordt uitgevoerd..."
        ./troubleshoot-domain.sh
    else
        error "Troubleshoot script niet gevonden. Zorg ervoor dat troubleshoot-domain.sh aanwezig is."
    fi
    
    read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
    hoofdmenu
}

# Fix werkruimten functie
fix_workspaces() {
    header "WERKRUIMTEN FIXEN IN BEHEERDERSDASHBOARD"
    log "SQL-fix wordt aangemaakt voor het werkruimteprobleem..."
    
    # Maak een tijdelijk SQL-bestand
    cat > fix_workspaces.sql << 'EOF'
-- SQL fix voor het werkruimteprobleem
-- Dit voegt ontbrekende relaties toe tussen admins en werkruimten

-- Debug info
SELECT 'Controleren van werkruimten:' as info;
SELECT id, name FROM workspaces;

SELECT 'Controleren van admin gebruikers:' as info;
SELECT id, email FROM users WHERE is_admin = TRUE;

SELECT 'Controleren van werkruimte toewijzingen:' as info;
SELECT * FROM workspace_users;

-- Fix: Voeg alle admins toe aan alle werkruimten als ze nog niet zijn toegewezen
SELECT 'Toevoegen van ontbrekende admin-werkruimte relaties:' as info;

INSERT INTO workspace_users (user_id, workspace_id, role, created_at, updated_at)
SELECT u.id, w.id, 'admin', NOW(), NOW()
FROM users u, workspaces w
WHERE u.is_admin = TRUE
AND NOT EXISTS (
    SELECT 1 FROM workspace_users wu 
    WHERE wu.user_id = u.id AND wu.workspace_id = w.id
);

-- Verifieer de resultaten
SELECT 'Verifieer de resultaten:' as info;
SELECT wu.user_id, u.email, wu.workspace_id, w.name, wu.role 
FROM workspace_users wu
JOIN users u ON wu.user_id = u.id
JOIN workspaces w ON wu.workspace_id = w.id
WHERE u.is_admin = TRUE;
EOF

    # Kopieer het SQL-bestand naar de database container
    log "SQL-bestand wordt gekopieerd naar database container..."
    DB_CONTAINER=$(docker ps -q --filter "name=postgres")
    if [ -z "$DB_CONTAINER" ]; then
        error "Database container niet gevonden. Is de applicatie actief?"
        read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
        hoofdmenu
        return
    fi

    docker cp fix_workspaces.sql $DB_CONTAINER:/tmp/

    # Voer het SQL-bestand uit
    log "SQL-fix wordt uitgevoerd..."
    docker exec -i $DB_CONTAINER psql -U postgres -d boekhouding -f /tmp/fix_workspaces.sql > fix_results.log

    # Toon resultaten
    log "Fix uitgevoerd! Resultaten:"
    cat fix_results.log

    # Herstart de applicatie
    log "Applicatie wordt herstart om wijzigingen door te voeren..."
    docker compose restart app

    log "Fix voltooid. Vernieuw nu je beheerdersdashboard om te zien of de werkruimten zichtbaar zijn."
    log "Als het probleem blijft bestaan, bekijk fix_results.log voor meer details."
    
    read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
    hoofdmenu
}

# Reset admin wachtwoord functie
reset_admin() {
    header "ADMIN WACHTWOORD RESETTEN"
    log "Dit zal het wachtwoord van een admin gebruiker resetten."
    read -p "Voer het e-mailadres van de admin in: " ADMIN_EMAIL
    
    if [ -z "$ADMIN_EMAIL" ]; then
        error "Geen e-mailadres opgegeven."
        read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
        hoofdmenu
        return
    fi
    
    # Genereer een nieuw wachtwoord
    NEW_PASSWORD=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 12)
    
    # Maak een tijdelijk SQL-bestand
    cat > reset_password.sql << EOF
-- Controleer of de gebruiker bestaat
SELECT id, email, is_admin FROM users WHERE email = '$ADMIN_EMAIL';

-- Reset het wachtwoord (werkzeug.security generate_password_hash gebruikt)
UPDATE users SET 
  password_hash = crypt('$NEW_PASSWORD', gen_salt('bf'))
WHERE email = '$ADMIN_EMAIL'
RETURNING id, email;
EOF

    # Kopieer het SQL-bestand naar de database container
    log "Wachtwoord wordt gereset..."
    DB_CONTAINER=$(docker ps -q --filter "name=postgres")
    if [ -z "$DB_CONTAINER" ]; then
        error "Database container niet gevonden. Is de applicatie actief?"
        read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
        hoofdmenu
        return
    fi

    docker cp reset_password.sql $DB_CONTAINER:/tmp/

    # Voer het SQL-bestand uit
    RESULT=$(docker exec -i $DB_CONTAINER psql -U postgres -d boekhouding -f /tmp/reset_password.sql)
    
    # Controleer of de reset succesvol was
    if echo "$RESULT" | grep -q "0 rows"; then
        error "Gebruiker met e-mail $ADMIN_EMAIL niet gevonden."
    else
        log "Wachtwoord voor $ADMIN_EMAIL is gereset naar: $NEW_PASSWORD"
        log "Gebruik dit wachtwoord om in te loggen en verander het daarna onmiddellijk."
    fi
    
    # Verwijder het tijdelijke SQL-bestand
    rm -f reset_password.sql
    
    read -p "Druk op Enter om terug te gaan naar het hoofdmenu..." DUMMY
    hoofdmenu
}

# Start het hoofdmenu
hoofdmenu
EOL

chmod +x "$INSTALL_DIR/beheer.sh"
log "Beheerschript is aangemaakt."

# Script voor het updaten van de app
cat > "$INSTALL_DIR/update-app.sh" << 'EOL'
#!/bin/bash
# Automatisch update script voor Boekhoud Applicatie
# Dit script werkt de applicatie bij, maakt backups en herstart alles

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
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./update-app.sh'"
fi

# Bepaal applicatiemap
APP_DIR=$(pwd)
if [ ! -f "$APP_DIR/docker-compose.yml" ] && [ ! -f "$APP_DIR/compose.yaml" ]; then
    # Probeer standaard locaties
    if [ -d "/opt/boekhoudapp" ]; then
        APP_DIR="/opt/boekhoudapp"
    elif [ -d "/opt/facturatie" ]; then
        APP_DIR="/opt/facturatie"
    else
        read -p "Voer het volledige pad in naar de applicatiemap: " APP_DIR
        if [ ! -d "$APP_DIR" ]; then
            error "De opgegeven map bestaat niet: $APP_DIR"
        fi
    fi
fi

cd "$APP_DIR" || error "Kan niet naar de applicatiemap navigeren: $APP_DIR"

# Start het updateproces
header "APPLICATIE AUTOMATISCHE UPDATE"
log "Update proces wordt gestart in map: $APP_DIR"
log "Dit script zal:"
log "1. Een backup maken van de database en configuratie"
log "2. De nieuwste code ophalen"
log "3. Ontbrekende afhankelijkheden controleren en installeren"
log "4. De applicatie herstarten"
echo ""
read -p "Wil je doorgaan met de update? (j/n): " CONTINUE
if [[ ! "$CONTINUE" =~ ^[Jj]$ ]]; then
    log "Update geannuleerd door gebruiker"
    exit 0
fi

# Controleer of Docker draait
header "VEREISTEN CONTROLEREN"
if ! systemctl is-active --quiet docker; then
    log "Docker service is niet actief. Service wordt gestart..."
    systemctl start docker
    systemctl enable docker
fi

# Maak database backup
header "STAP 1: BACKUP MAKEN"
log "Database backup wordt gemaakt..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$APP_DIR/backups"
mkdir -p "$BACKUP_DIR"

# Backup database
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
log "Database backup wordt gemaakt naar: $DB_BACKUP_FILE"
if docker exec -t $(docker ps -q --filter "name=postgres") pg_dumpall -c -U postgres > "$DB_BACKUP_FILE" 2>/dev/null; then
    log "Database backup succesvol gemaakt"
else
    warn "Kon geen volledige database backup maken, probeer met individuele database dump..."
    # Probeer individuele database dump
    if docker exec -t $(docker ps -q --filter "name=postgres") pg_dump -U postgres -d boekhouding > "$DB_BACKUP_FILE" 2>/dev/null; then
        log "Database backup succesvol gemaakt met pg_dump"
    else
        warn "Kon geen database backup maken via Docker. Container is mogelijk niet actief."
        # Als Docker containers niet draaien, sla deze stap over
    fi
fi

# Backup .env bestand
if [ -f "$APP_DIR/.env" ]; then
    log "Backup maken van .env bestand..."
    cp "$APP_DIR/.env" "$BACKUP_DIR/.env.backup_$TIMESTAMP"
    log ".env backup succesvol gemaakt"
fi

# Backup custom bestanden
log "Backup maken van custom bestanden..."
if command -v git &> /dev/null && [ -d "$APP_DIR/.git" ]; then
    # Gebruik git stash voor lokale wijzigingen
    cd "$APP_DIR" || error "Kan niet naar applicatiemap navigeren"
    if ! git diff --quiet; then
        log "Lokale wijzigingen gevonden, worden opgeslagen met git stash..."
        git stash save "Automatische backup voor update op $(date)"
        log "Wijzigingen opgeslagen in git stash"
    else
        log "Geen lokale wijzigingen gevonden in git"
    fi
else
    # Als git niet beschikbaar is, maak tarball van belangrijke mappen
    log "Git niet beschikbaar, backup maken van belangrijke mappen..."
    tar -czf "$BACKUP_DIR/custom_files_$TIMESTAMP.tar.gz" templates static 2>/dev/null
    log "Belangrijke mappen geback-upt naar $BACKUP_DIR/custom_files_$TIMESTAMP.tar.gz"
fi

# Update de code
header "STAP 2: CODE UPDATEN"
if command -v git &> /dev/null && [ -d "$APP_DIR/.git" ]; then
    log "Git repository wordt bijgewerkt..."
    cd "$APP_DIR" || error "Kan niet naar applicatiemap navigeren"
    
    # Controleer huidige branch
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log "Huidige branch: $BRANCH"
    
    # Update code
    log "Code wordt bijgewerkt vanaf origin..."
    if git pull origin "$BRANCH"; then
        log "Code succesvol bijgewerkt"
    else
        warn "Er waren problemen bij het updaten van de code. Probeer te herstellen..."
        # Probeer eventuele problemen op te lossen
        git reset --hard origin/"$BRANCH"
        log "Code hersteld naar laatste versie op server"
    fi
else
    warn "Git niet beschikbaar of git repository niet gevonden"
    log "Handmatige update vereist. Download de nieuwste code van GitHub en kopieer naar $APP_DIR"
    read -p "Wil je de applicatie downloaden van GitHub? (j/n): " DOWNLOAD_GITHUB
    if [[ "$DOWNLOAD_GITHUB" =~ ^[Jj]$ ]]; then
        log "Code wordt gedownload van GitHub..."
        TMP_DIR=$(mktemp -d)
        if git clone https://github.com/Jjustmee23/boekhoud.git "$TMP_DIR"; then
            log "Code succesvol gedownload"
            
            # Bewaar .env en andere belangrijke bestanden
            if [ -f "$APP_DIR/.env" ]; then
                cp "$APP_DIR/.env" "$TMP_DIR/"
            fi
            
            # Bewaar uploads map indien aanwezig
            if [ -d "$APP_DIR/static/uploads" ]; then
                mkdir -p "$TMP_DIR/static"
                cp -r "$APP_DIR/static/uploads" "$TMP_DIR/static/"
            fi
            
            # Kopieer de nieuwe code maar behoud .env en uploads
            rm -rf "$TMP_DIR/.git" # Verwijder .git map om conflicten te voorkomen
            rsync -av --exclude='.env' --exclude='static/uploads' "$TMP_DIR/" "$APP_DIR/"
            rm -rf "$TMP_DIR"
            log "Code succesvol bijgewerkt"
        else
            error "Kon code niet downloaden van GitHub"
        fi
    else
        log "Code update overgeslagen"
    fi
fi

# Controleer en installeer ontbrekende afhankelijkheden
header "STAP 3: AFHANKELIJKHEDEN CONTROLEREN"
log "Docker images worden bijgewerkt..."
if [ -f "$APP_DIR/docker-compose.yml" ]; then
    docker compose pull
    log "Docker images succesvol bijgewerkt"
else
    warn "docker-compose.yml niet gevonden, images kunnen niet worden bijgewerkt"
fi

# Controleer of nginx configuratie is bijgewerkt
if [ -d "$APP_DIR/nginx" ]; then
    log "Nginx configuratie wordt gecontroleerd..."
    
    # Controleer of dhparam.pem bestaat
    if [ ! -f "$APP_DIR/nginx/ssl/dhparam.pem" ]; then
        log "DH parameters ontbreken, worden gegenereerd..."
        mkdir -p "$APP_DIR/nginx/ssl"
        openssl dhparam -out "$APP_DIR/nginx/ssl/dhparam.pem" 2048
        log "DH parameters succesvol gegenereerd"
    fi
    
    # Maak dhparam-generator.sh uitvoerbaar
    if [ -f "$APP_DIR/nginx/dhparam-generator.sh" ]; then
        chmod +x "$APP_DIR/nginx/dhparam-generator.sh"
    fi
fi

# Controleer of beheer- en troubleshoot-scripts bestaan
log "Beheerscripts worden gecontroleerd..."
if [ ! -f "$APP_DIR/beheer.sh" ]; then
    log "Beheerschript ontbreekt, wordt gemaakt in een toekomstige update"
    log "Zie update logs voor details"
fi

if [ ! -f "$APP_DIR/troubleshoot-domain.sh" ]; then
    log "Troubleshoot script ontbreekt, wordt gemaakt in een toekomstige update"
    log "Zie update logs voor details"
fi

# Maak alle scripts uitvoerbaar
find "$APP_DIR" -name "*.sh" -exec chmod +x {} \;
log "Alle script bestanden zijn nu uitvoerbaar"

# Herstart de applicatie
header "STAP 4: APPLICATIE HERSTARTEN"
log "Applicatie wordt herstart..."
if [ -f "$APP_DIR/docker-compose.yml" ]; then
    docker compose down
    docker compose up -d
    log "Applicatie succesvol herstart"
    
    # Toon container status
    log "Container status:"
    docker compose ps
else
    warn "docker-compose.yml niet gevonden, applicatie kan niet worden herstart"
fi

# Controleer domein configuratie
if [ -f "$APP_DIR/.env" ]; then
    DOMAIN=$(grep DOMAIN "$APP_DIR/.env" | cut -d '=' -f2)
    if [ -n "$DOMAIN" ]; then
        log "Geconfigureerde domein: $DOMAIN"
        log "De applicatie zou nu bereikbaar moeten zijn op: https://$DOMAIN"
    fi
fi

# Fix werkruimte zichtbaarheid in beheerdersdashboard
header "WERKRUIMTE ZICHTBAARHEID FIXEN"
log "Werkruimten zichtbaarheid in beheerdersdashboard wordt gerepareerd..."

# Maak een tijdelijk SQL-bestand
cat > fix_workspaces.sql << 'EOF'
-- SQL fix voor het werkruimteprobleem
-- Dit voegt ontbrekende relaties toe tussen admins en werkruimten

-- Debug info
SELECT 'Controleren van werkruimten:' as info;
SELECT id, name FROM workspaces;

SELECT 'Controleren van admin gebruikers:' as info;
SELECT id, email FROM users WHERE is_admin = TRUE;

SELECT 'Controleren van werkruimte toewijzingen:' as info;
SELECT * FROM workspace_users;

-- Fix: Voeg alle admins toe aan alle werkruimten als ze nog niet zijn toegewezen
SELECT 'Toevoegen van ontbrekende admin-werkruimte relaties:' as info;

INSERT INTO workspace_users (user_id, workspace_id, role, created_at, updated_at)
SELECT u.id, w.id, 'admin', NOW(), NOW()
FROM users u, workspaces w
WHERE u.is_admin = TRUE
AND NOT EXISTS (
    SELECT 1 FROM workspace_users wu 
    WHERE wu.user_id = u.id AND wu.workspace_id = w.id
);

-- Verifieer de resultaten
SELECT 'Verifieer de resultaten:' as info;
SELECT wu.user_id, u.email, wu.workspace_id, w.name, wu.role 
FROM workspace_users wu
JOIN users u ON wu.user_id = u.id
JOIN workspaces w ON wu.workspace_id = w.id
WHERE u.is_admin = TRUE;
EOF

# Kopieer het SQL-bestand naar de database container
DB_CONTAINER=$(docker ps -q --filter "name=postgres")
if [ -n "$DB_CONTAINER" ]; then
    log "SQL-fix wordt toegepast..."
    docker cp fix_workspaces.sql $DB_CONTAINER:/tmp/
    docker exec -i $DB_CONTAINER psql -U postgres -d boekhouding -f /tmp/fix_workspaces.sql > fix_results.log 2>&1
    log "Werkruimte fix complete."
else
    warn "Database container niet actief, werkruimte fix overgeslagen"
fi

# Slotbericht
header "UPDATE VOLTOOID"
log "De applicatie is succesvol bijgewerkt en herstart."
log "Backup bestanden zijn opgeslagen in: $BACKUP_DIR"
log ""
log "Als je problemen ondervindt, kun je de volgende commando's gebruiken:"
log "- Logs bekijken: docker compose logs -f"
log "- Troubleshooting uitvoeren: $APP_DIR/troubleshoot-domain.sh"
log "- Applicatie beheren: $APP_DIR/beheer.sh"
log ""
log "Als je problemen niet kunt oplossen, kun je de backup herstellen met:"
log "1. Stop de applicatie: docker compose down"
log "2. Herstel de database: cat $DB_BACKUP_FILE | docker exec -i postgres psql -U postgres"
log "3. Herstel .env: cp $BACKUP_DIR/.env.backup_$TIMESTAMP $APP_DIR/.env"
log "4. Start de applicatie: docker compose up -d"

# Einde script
exit 0
EOL

chmod +x "$INSTALL_DIR/update-app.sh"
log "Update script is aangemaakt."

# Fix voor werkruimten in het beheerdersdashboard
cat > "$INSTALL_DIR/fix-workspaces.sh" << 'EOL'
#!/bin/bash
# Script om werkruimteproblemen in het beheerdersdashboard op te lossen

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
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./fix-workspaces.sh'"
    exit 1
fi

# Bepaal het pad waar de applicatie is geïnstalleerd
APP_DIR=$(pwd)
if [ ! -f "$APP_DIR/docker-compose.yml" ] && [ ! -f "$APP_DIR/compose.yaml" ]; then
    # Probeer standaard locaties
    if [ -d "/opt/boekhoudapp" ]; then
        APP_DIR="/opt/boekhoudapp"
    elif [ -d "/opt/facturatie" ]; then
        APP_DIR="/opt/facturatie"
    else
        read -p "Voer het volledige pad in naar de applicatiemap: " APP_DIR
        if [ ! -d "$APP_DIR" ]; then
            error "De opgegeven map bestaat niet: $APP_DIR"
            exit 1
        fi
    fi
fi

cd "$APP_DIR" || { error "Kan niet naar de applicatiemap navigeren: $APP_DIR"; exit 1; }

# Start het diagnoseproces
header "WERKRUIMTEN DIAGNOSE"
log "Diagnose wordt gestart voor werkruimten in beheerdersdashboard."
log "Applicatiemap: $APP_DIR"

# Controleer of Docker draait
log "Controleren of Docker service actief is..."
if ! systemctl is-active --quiet docker; then
    warn "Docker service is niet actief. Service wordt gestart..."
    systemctl start docker
    systemctl enable docker
fi

# Controleer of de containers draaien
log "Controleren of alle containers draaien..."
if ! docker compose ps | grep -q "Up"; then
    warn "Niet alle containers lijken te draaien. Containers worden herstart..."
    docker compose down
    docker compose up -d
    sleep 5
fi

# Controleer de database verbinding
log "Controleren of database bereikbaar is..."
if ! docker exec -t $(docker ps -q --filter "name=postgres") pg_isready -U postgres -d boekhouding 2>/dev/null; then
    warn "Database lijkt niet bereikbaar te zijn. Mogelijke databaseproblemen."
    docker compose restart postgres
    sleep 5
fi

# Dump werkruimten uit de database
log "Werkruimten ophalen uit database..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
WORKSPACE_DUMP_FILE="$APP_DIR/workspaces_dump_$TIMESTAMP.sql"

docker exec -t $(docker ps -q --filter "name=postgres") psql -U postgres -d boekhouding -c "SELECT * FROM workspaces;" > "$WORKSPACE_DUMP_FILE" 2>/dev/null

if [ $? -eq 0 ]; then
    WORKSPACE_COUNT=$(grep -v "^(" "$WORKSPACE_DUMP_FILE" | grep -v "^-" | grep -v "row" | grep -v "^$" | wc -l)
    WORKSPACE_COUNT=$((WORKSPACE_COUNT-2)) # Correctie voor kolomnamen en header
    
    if [ $WORKSPACE_COUNT -gt 0 ]; then
        log "Aantal werkruimten in database: $WORKSPACE_COUNT"
    else
        warn "Geen werkruimten gevonden in database. Mogelijk database-probleem."
    fi
else
    warn "Kon geen werkruimtengegevens ophalen. Mogelijke databaseproblemen."
fi

# Controleer de gebruikersrechten
log "Controleren van admin gebruikersrechten..."
docker exec -t $(docker ps -q --filter "name=postgres") psql -U postgres -d boekhouding -c "SELECT u.id, u.email, u.is_admin FROM users u WHERE u.is_admin = TRUE;" > "$APP_DIR/admin_users_$TIMESTAMP.sql" 2>/dev/null

if [ $? -eq 0 ]; then
    ADMIN_COUNT=$(grep -v "^(" "$APP_DIR/admin_users_$TIMESTAMP.sql" | grep -v "^-" | grep -v "row" | grep -v "^$" | wc -l)
    ADMIN_COUNT=$((ADMIN_COUNT-2)) # Correctie voor kolomnamen en header
    
    if [ $ADMIN_COUNT -gt 0 ]; then
        log "Aantal admin gebruikers: $ADMIN_COUNT"
    else
        warn "Geen admin gebruikers gevonden. Dit kan een probleem zijn."
    fi
else
    warn "Kon geen gebruikersgegevens ophalen. Mogelijke databaseproblemen."
fi

# Controleer admin-werkruimte relaties
log "Controleren van admin-werkruimte relaties..."
docker exec -t $(docker ps -q --filter "name=postgres") psql -U postgres -d boekhouding -c "SELECT wu.user_id, wu.workspace_id, wu.role FROM workspace_users wu JOIN users u ON wu.user_id = u.id WHERE u.is_admin = TRUE;" > "$APP_DIR/admin_workspace_rel_$TIMESTAMP.sql" 2>/dev/null

if [ $? -eq 0 ]; then
    ADMIN_WS_COUNT=$(grep -v "^(" "$APP_DIR/admin_workspace_rel_$TIMESTAMP.sql" | grep -v "^-" | grep -v "row" | grep -v "^$" | wc -l)
    ADMIN_WS_COUNT=$((ADMIN_WS_COUNT-2)) # Correctie voor kolomnamen en header
    
    if [ $ADMIN_WS_COUNT -gt 0 ]; then
        log "Aantal werkruimte-toewijzingen voor admins: $ADMIN_WS_COUNT"
    else
        warn "Geen admin-werkruimte relaties gevonden. Dit is waarschijnlijk het probleem."
        log "Mogelijke oplossing: Voeg werkruimte-toegang toe voor admin gebruikers"
    fi
else
    warn "Kon geen admin-werkruimte relaties ophalen. Mogelijke databaseproblemen."
fi

# Controleer applicatielogbestanden
log "Controleren van applicatielogbestanden..."
if [ -d "$APP_DIR/logs" ]; then
    RECENT_ERRORS=$(grep -i "error" "$APP_DIR/logs/app.log" | tail -20)
    if [ -n "$RECENT_ERRORS" ]; then
        warn "Recente fouten gevonden in logbestanden:"
        echo "$RECENT_ERRORS"
    else
        log "Geen recente fouten gevonden in logbestanden."
    fi
else
    warn "Logs map niet gevonden. Kan logbestanden niet controleren."
fi

# Controleer container logs
log "Controleren van container logs..."
APP_CONTAINER_LOGS=$(docker logs $(docker ps -q --filter "name=app") --tail 50 2>&1 | grep -i "error\|exception\|fail")
if [ -n "$APP_CONTAINER_LOGS" ]; then
    warn "Fouten gevonden in container logs:"
    echo "$APP_CONTAINER_LOGS"
else
    log "Geen significante fouten gevonden in container logs."
fi

# Korte debug-instructies
log "Voorstel voor een oplossing..."
cat << 'EOF' > "$APP_DIR/fix_workspace_visibility.sql"
-- Voer dit script uit in de database om de zichtbaarheid van werkruimten voor admins te herstellen

-- 1. Controleer bestaande werkruimten
SELECT id, name FROM workspaces;

-- 2. Controleer admin gebruikers
SELECT id, email FROM users WHERE is_admin = TRUE;

-- 3. Controleer werkruimte toewijzingen
SELECT * FROM workspace_users;

-- 4. Voeg ontbrekende werkruimte toewijzingen toe voor admins (pas de IDs aan)
-- Vervang user_id en workspace_id met de juiste waarden uit eerdere queries
INSERT INTO workspace_users (user_id, workspace_id, role, created_at, updated_at)
SELECT u.id, w.id, 'admin', NOW(), NOW()
FROM users u, workspaces w
WHERE u.is_admin = TRUE
AND NOT EXISTS (
    SELECT 1 FROM workspace_users wu 
    WHERE wu.user_id = u.id AND wu.workspace_id = w.id
);

-- 5. Controleer of de toewijzingen zijn toegevoegd
SELECT wu.user_id, u.email, wu.workspace_id, w.name, wu.role 
FROM workspace_users wu
JOIN users u ON wu.user_id = u.id
JOIN workspaces w ON wu.workspace_id = w.id
WHERE u.is_admin = TRUE;
EOF

log "Diagnosescript heeft mogelijke problemen geïdentificeerd."
log ""
log "Gevonden bestanden:"
log "- Werkruimten dump: $WORKSPACE_DUMP_FILE"
log "- Admin gebruikers: $APP_DIR/admin_users_$TIMESTAMP.sql"
log "- Admin-werkruimte relaties: $APP_DIR/admin_workspace_rel_$TIMESTAMP.sql"
log "- SQL-oplossingsscript: $APP_DIR/fix_workspace_visibility.sql"
log ""
log "Om de werkruimten in het beheerdersdashboard zichtbaar te maken:"
log "1. Bekijk de gemaakte bestanden om de IDs van werkruimten en admins te identificeren"
log "2. Voer het volgende uit om het probleem op te lossen:"
log ""
log "   docker exec -it \$(docker ps -q --filter \"name=postgres\") psql -U postgres -d boekhouding -f /app/fix_workspace_visibility.sql"
log ""
log "   (Zorg ervoor dat het SQL-bestand eerst naar de container wordt gekopieerd met:"
log "    docker cp $APP_DIR/fix_workspace_visibility.sql \$(docker ps -q --filter \"name=postgres\"):/app/)"
log ""
log "3. Herstart de applicatie met: docker compose restart app"
log ""
log "Als je het probleem automatisch wilt proberen op te lossen, voer dan uit:"
log ""
log "   sudo $APP_DIR/auto-fix-workspaces.sh"
log ""

# Maak een automatisch fix script
cat << 'EOF' > "$APP_DIR/auto-fix-workspaces.sh"
#!/bin/bash
# Script om automatisch werkruimterelaties te herstellen

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

log "Automatische fix voor werkruimteproblemen wordt uitgevoerd..."

# Kopieer het SQL bestand naar de container
DB_CONTAINER=$(docker ps -q --filter "name=postgres")
if [ -z "$DB_CONTAINER" ]; then
    error "Database container niet gevonden. Is de applicatie actief?"
fi

log "SQL-bestand wordt gekopieerd naar database container..."
docker cp fix_workspace_visibility.sql $DB_CONTAINER:/app/ || error "Kan SQL-bestand niet kopiëren"

# Voer het SQL-script uit
log "SQL-script wordt uitgevoerd om werkruimten te herstellen..."
docker exec -i $DB_CONTAINER psql -U postgres -d boekhouding -f /app/fix_workspace_visibility.sql > workspace_fix_result.log 2>&1

# Toon het resultaat
log "Resultaat van de reparatie:"
cat workspace_fix_result.log

# Restart de applicatie
log "Applicatie wordt herstart om wijzigingen toe te passen..."
docker compose restart app

log "Reparatie voltooid. Vernieuw nu je browserpagina en controleer of werkruimten zichtbaar zijn."
log "Als het probleem aanhoudt, kijk dan in workspace_fix_result.log voor meer details."

# Einde script
exit 0
EOF

chmod +x "$APP_DIR/auto-fix-workspaces.sh"

# Einde script
log "Diagnose voltooid. Zie bovenstaande instructies voor herstel."
exit 0
EOL

chmod +x "$INSTALL_DIR/fix-workspaces.sh"
log "Werkruimte fix script is aangemaakt."

# Start de app
header "APPLICATIE STARTEN"
log "De applicatie wordt nu gestart met Docker Compose..."

# Controleer of Docker en Docker Compose geïnstalleerd zijn
if ! command -v docker &> /dev/null || ! docker compose &> /dev/null; then
    error "Docker of Docker Compose is niet correct geïnstalleerd. Controleer de installatielogboeken."
fi

# Start de applicatie met docker-compose
cd "$INSTALL_DIR" || error "Kan niet naar de installatiemap navigeren: $INSTALL_DIR"
docker compose up -d || error "Kon de applicatie niet starten. Controleer de logs voor meer details."

# Controleer of de containers draaien
if docker compose ps | grep -q "Up"; then
    log "Applicatie succesvol gestart!"
else
    warn "Niet alle containers lijken te draaien. Controleer 'docker compose ps' voor details."
fi

# Toon de URL van de applicatie
if [ -f ".env" ]; then
    DOMAIN=$(grep DOMAIN .env | cut -d '=' -f2)
    if [ -n "$DOMAIN" ]; then
        log "De applicatie is nu beschikbaar op: https://$DOMAIN"
        log "Let op: Het kan enkele minuten duren voordat SSL-certificaten zijn aangevraagd en geconfigureerd."
    else
        log "Geen domein gevonden in .env bestand."
    fi
fi

# Instructies voor na de installatie
header "INSTALLATIE VOLTOOID"
log "De Boekhoud Applicatie is succesvol geïnstalleerd en gestart."
log ""
log "Volgende stappen:"
log "1. Controleer of de applicatie bereikbaar is op je domein: https://$DOMAIN"
log "2. Als de applicatie niet bereikbaar is, voer dan het troubleshoot script uit:"
log "   sudo $INSTALL_DIR/troubleshoot-domain.sh"
log ""
log "Beheer je applicatie met het beheerschript:"
log "   sudo $INSTALL_DIR/beheer.sh"
log ""
log "Bedankt voor het gebruiken van het automatische installatiescript!"
log "Voor ondersteuning, raadpleeg de documentatie of neem contact op met de ontwikkelaars."

# Einde script
exit 0