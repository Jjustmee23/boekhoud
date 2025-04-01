#!/bin/bash
# Alles-in-één installatiescript voor de Boekhoudapplicatie
# Voer dit uit op een verse Ubuntu 22.04 server om alles automatisch te installeren

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
clear
header "AUTOMATISCHE INSTALLATIE VAN BOEKHOUDAPPLICATIE"
log "Dit script zal automatisch alle benodigde componenten installeren en configureren"
log "voor een volledige productie-omgeving van de boekhoudapplicatie."
echo ""
log "Het installatieproces bevat de volgende stappen:"
log "1. Systeem update en installatie van benodigde pakketten"
log "2. Installatie van Docker en Docker Compose"
log "3. Configuratie van de firewall"
log "4. Download en installatie van de boekhoudapplicatie"
log "5. Configuratie van de domeingegevens en SSL-certificaten"
log "6. Starten van de applicatie"
echo ""
read -p "Wil je doorgaan met de installatie? (j/n): " CONTINUE
if [[ ! "$CONTINUE" =~ ^[Jj]$ ]]; then
    log "Installatie geannuleerd door gebruiker"
    exit 0
fi

# Vraag om installatie-opties
header "CONFIGURATIE INSTELLINGEN"
read -p "Voer het domein in (bijv. boekhoud.midaweb.be): " DOMAIN
while [[ -z "$DOMAIN" ]]; do
    warn "Een domeinnaam is vereist"
    read -p "Voer het domein in (bijv. boekhoud.midaweb.be): " DOMAIN
done

read -p "Voer je e-mailadres in (voor SSL certificaten en admin account): " EMAIL
while [[ -z "$EMAIL" ]]; do
    warn "Een e-mailadres is vereist"
    read -p "Voer je e-mailadres in (voor SSL certificaten en admin account): " EMAIL
done

read -p "Wil je een sterk wachtwoord genereren voor de database? (j/n) [j]: " GEN_PASSWORD
GEN_PASSWORD=${GEN_PASSWORD:-j}

if [[ "$GEN_PASSWORD" =~ ^[Jj]$ ]]; then
    DB_PASSWORD=$(openssl rand -base64 16)
    log "Database wachtwoord gegenereerd"
else
    read -s -p "Voer een wachtwoord in voor de database: " DB_PASSWORD
    echo ""
    while [[ -z "$DB_PASSWORD" ]]; do
        warn "Een database wachtwoord is vereist"
        read -s -p "Voer een wachtwoord in voor de database: " DB_PASSWORD
        echo ""
    done
fi

read -p "In welke map wil je de applicatie installeren? [/opt/boekhoudapp]: " APP_DIR
APP_DIR=${APP_DIR:-/opt/boekhoudapp}

# Update systeem
header "STAP 1: SYSTEEM UPDATE EN INSTALLATIE VAN PAKKETTEN"
log "Pakketlijsten bijwerken..."
apt-get update && apt-get upgrade -y || error "Kan pakketlijsten niet bijwerken"

log "Benodigde pakketten installeren..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    openssl \
    || error "Kan benodigde pakketten niet installeren"

# Installeer Docker
header "STAP 2: DOCKER INSTALLATIE"
log "Docker installeren..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io || error "Kan Docker niet installeren"
    
    # Start en enable Docker service
    systemctl start docker
    systemctl enable docker
    
    log "Docker is geïnstalleerd"
else
    log "Docker is al geïnstalleerd"
fi

# Installeer Docker Compose
log "Docker Compose installeren..."
if ! command -v docker compose &> /dev/null; then
    apt-get install -y docker-compose-plugin || error "Kan Docker Compose niet installeren"
    log "Docker Compose is geïnstalleerd"
else
    log "Docker Compose is al geïnstalleerd"
fi

# Configureer firewall
header "STAP 3: FIREWALL CONFIGURATIE"
log "Firewall configureren..."
ufw allow ssh
ufw allow http
ufw allow https
ufw allow 5432/tcp comment 'PostgreSQL (optioneel)'
yes | ufw enable
log "Firewall geconfigureerd"

# Maak directories
header "STAP 4: APPLICATIE INSTALLATIE"
log "Applicatiemap aanmaken: $APP_DIR"
mkdir -p "$APP_DIR"
cd "$APP_DIR" || error "Kan niet naar $APP_DIR navigeren"

log "Applicatiebestanden downloaden..."
git clone https://github.com/Jjustmee23/boekhoud.git . || warn "Kon repository niet klonen - aangenomen dat bestanden al aanwezig zijn"

# Maak benodigde mappen aan
log "Benodigde mappen aanmaken..."
mkdir -p logs
mkdir -p static/uploads
mkdir -p nginx/ssl

# Genereer dhparam.pem bestand
log "DH parameters genereren voor verhoogde veiligheid..."
if [ ! -f nginx/ssl/dhparam.pem ]; then
    log "Dit kan enkele minuten duren..."
    openssl dhparam -out nginx/ssl/dhparam.pem 2048 || warn "Kon geen dhparam.pem genereren"
    
    if [ -f nginx/ssl/dhparam.pem ]; then
        log "DH parameters succesvol gegenereerd"
    fi
else
    log "DH parameters bestaan al"
fi

# Maak .env bestand
header "STAP 5: CONFIGURATIE"
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

# Email configuratie (Microsoft Graph API) - optioneel
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_TENANT_ID=
MS_GRAPH_SENDER_EMAIL=

# Mollie API configuratie - optioneel
MOLLIE_API_KEY=
EOF

log ".env bestand aangemaakt met basis configuratie"
log ""
log "Admin wachtwoord: $(grep ADMIN_PASSWORD .env | cut -d '=' -f2)"
log "Bewaar dit wachtwoord op een veilige plaats!"
log ""

# Maak troubleshooting script
log "Aanmaken van hulpscripts voor beheer en troubleshooting..."
cat > troubleshoot-domain.sh << 'EOF'
#!/bin/bash
# Script om domein problemen te diagnosticeren

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
}

# Controleer huidige gebruiker
log "Controle uitvoeren als gebruiker: $(whoami)"

# Controleer of Docker draait
log "Controleren of Docker service actief is..."
if systemctl is-active --quiet docker; then
    log "Docker service is actief"
else
    error "Docker service is niet actief. Start deze met: sudo systemctl start docker"
fi

# Controleer containers status
log "Controleren van Docker container status..."
docker ps
docker compose ps

# Controleer of .env bestand bestaat en domein is ingesteld
log "Controleren van domein configuratie in .env bestand..."
if [ -f .env ]; then
    DOMAIN=$(grep DOMAIN .env | cut -d '=' -f2)
    log "Geconfigureerd domein: $DOMAIN"
else
    error ".env bestand bestaat niet. Maak deze aan met het juiste domein."
fi

# Controleer of het domein bereikbaar is
log "Controleren of het domein verwijst naar deze server..."
SERVER_IP=$(curl -s https://ipinfo.io/ip)
log "Server IP: $SERVER_IP"

log "Controleren van DNS-records voor $DOMAIN..."
HOST_IP=$(host $DOMAIN | grep "has address" | awk '{print $4}')

if [ -z "$HOST_IP" ]; then
    error "Geen A-record gevonden voor $DOMAIN. Controleer je DNS-instellingen."
else
    log "Domein $DOMAIN verwijst naar IP: $HOST_IP"
    
    if [ "$HOST_IP" = "$SERVER_IP" ]; then
        log "DNS is correct geconfigureerd."
    else
        warn "Let op: Domein verwijst naar $HOST_IP, maar de server heeft IP $SERVER_IP"
    fi
fi

# Controleer of poorten 80 en 443 open staan
log "Controleren of poorten 80 en 443 open staan..."
if command -v netstat > /dev/null; then
    netstat -tuln | grep -E ':(80|443)'
elif command -v ss > /dev/null; then
    ss -tuln | grep -E ':(80|443)'
else
    warn "Kan poorten niet controleren, netstat en ss zijn niet beschikbaar."
fi

# Controleer nginx logs
log "Laatste regels uit nginx container logs:"
docker logs nginx-proxy --tail 20

# Controleer acme logs
log "Laatste regels uit acme-companion logs:"
docker logs acme-companion --tail 20

# Controleer app logs
log "Laatste regels uit app container logs:"
docker logs $(docker ps -q --filter "name=app") --tail 20 2>/dev/null || warn "App container niet gevonden."

log "Diagnostiek voltooid."
log ""
log "Als je domein niet bereikbaar is, controleer het volgende:"
log "1. Zorg dat DNS correct is ingesteld (A-record naar het server IP)"
log "2. Zorg dat poorten 80 en 443 open staan in je firewall"
log "3. Controleer of de juiste DOMAIN waarde staat in het .env bestand"
log "4. Herstart de containers met: docker compose restart"
log "5. Controleer alle logs met: docker compose logs"
EOF

chmod +x troubleshoot-domain.sh

# Maak beheerscript
cat > beheer.sh << 'EOF'
#!/bin/bash
# Beheerscript voor boekhoudapplicatie

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Log functie
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

# Menu weergeven
show_menu() {
    clear
    echo "==============================================="
    echo "    BOEKHOUDAPPLICATIE BEHEER MENU"
    echo "==============================================="
    echo "1. Start alle containers"
    echo "2. Stop alle containers"
    echo "3. Herstart alle containers"
    echo "4. Bekijk container status"
    echo "5. Bekijk logs"
    echo "6. Troubleshooting uitvoeren"
    echo "7. Database backup maken"
    echo "8. Database backup herstellen"
    echo "9. Systeem updaten"
    echo "0. Afsluiten"
    echo "==============================================="
    read -p "Maak een keuze [0-9]: " choice
}

# Database backup maken
backup_db() {
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    BACKUP_FILE="db_backup_${TIMESTAMP}.sql"
    log "Database backup maken naar ${BACKUP_FILE}..."
    docker exec -t $(docker ps -q --filter "name=db") pg_dumpall -c -U postgres > "${BACKUP_FILE}"
    if [ $? -eq 0 ]; then
        log "Database backup succesvol gemaakt: ${BACKUP_FILE}"
    else
        log "Fout bij maken van database backup"
    fi
    read -p "Druk op Enter om door te gaan..."
}

# Database backup herstellen
restore_db() {
    log "Beschikbare database backups:"
    ls -1 db_backup_*.sql 2>/dev/null
    echo ""
    read -p "Voer de naam van het backup bestand in: " BACKUP_FILE
    
    if [ -f "$BACKUP_FILE" ]; then
        log "Let op: Dit zal de huidige database overschrijven!"
        read -p "Weet je zeker dat je door wilt gaan? (j/n): " CONFIRM
        if [[ "$CONFIRM" =~ ^[Jj]$ ]]; then
            log "Database backup herstellen vanuit ${BACKUP_FILE}..."
            cat "${BACKUP_FILE}" | docker exec -i $(docker ps -q --filter "name=db") psql -U postgres
            if [ $? -eq 0 ]; then
                log "Database backup succesvol hersteld"
            else
                log "Fout bij herstellen van database backup"
            fi
        else
            log "Herstellen geannuleerd"
        fi
    else
        log "Backup bestand ${BACKUP_FILE} niet gevonden"
    fi
    read -p "Druk op Enter om door te gaan..."
}

# Systeem updaten
update_system() {
    log "Systeem updaten..."
    apt-get update && apt-get upgrade -y
    log "Docker images updaten..."
    docker compose pull
    log "Applicatie herstarten met nieuwe images..."
    docker compose up -d
    log "Systeemupdate voltooid"
    read -p "Druk op Enter om door te gaan..."
}

# Hoofdlus
while true; do
    show_menu
    case $choice in
        1)
            log "Containers starten..."
            docker compose up -d
            read -p "Druk op Enter om door te gaan..."
            ;;
        2)
            log "Containers stoppen..."
            docker compose down
            read -p "Druk op Enter om door te gaan..."
            ;;
        3)
            log "Containers herstarten..."
            docker compose restart
            read -p "Druk op Enter om door te gaan..."
            ;;
        4)
            log "Container status:"
            docker compose ps
            read -p "Druk op Enter om door te gaan..."
            ;;
        5)
            log "Logs bekijken (Ctrl+C om te stoppen):"
            docker compose logs -f
            ;;
        6)
            log "Troubleshooting uitvoeren..."
            ./troubleshoot-domain.sh
            read -p "Druk op Enter om door te gaan..."
            ;;
        7)
            backup_db
            ;;
        8)
            restore_db
            ;;
        9)
            update_system
            ;;
        0)
            log "Beheerscript afsluiten..."
            exit 0
            ;;
        *)
            log "Ongeldige keuze, probeer opnieuw"
            read -p "Druk op Enter om door te gaan..."
            ;;
    esac
done
EOF

chmod +x beheer.sh

# Start de applicatie
header "STAP 6: APPLICATIE STARTEN"
log "Docker containers starten..."
docker compose up -d

# Controleer of containers draaien
log "Status van containers controleren..."
docker compose ps
sleep 5

# Laatste stappen en instructies
header "INSTALLATIE VOLTOOID!"
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
log "Om de applicatie te beheren, gebruik het beheerscript:"
log "  sudo ${APP_DIR}/beheer.sh"
log ""
log "Troubleshooting:"
log "- Als de website niet bereikbaar is, gebruik: ${APP_DIR}/troubleshoot-domain.sh"
log "- Zorg ervoor dat je domein ${DOMAIN} correct is geconfigureerd in DNS"
log "- Controleer of poorten 80 en 443 open staan in je firewall"
log ""
log "Voor technische ondersteuning, raadpleeg de documentatie of neem contact op met de ontwikkelaar."

# Einde script
exit 0