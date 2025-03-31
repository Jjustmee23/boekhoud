#!/bin/bash
# Installatie script voor Ubuntu 22.04 voor Facturatie & Boekhouding Systeem
# Dit script installeert alle benodigde software en configureert het systeem vanaf nul

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

# Controleer of script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd als root (gebruik sudo).${NC}"
    exit 1
fi

# Controleer of we Ubuntu 22.04 gebruiken
if ! grep -q "Ubuntu 22.04" /etc/os-release; then
    echo -e "${RED}Dit script is ontworpen voor Ubuntu 22.04.${NC}"
    echo -e "${RED}Huidige OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d '"' -f 2)${NC}"
    echo -e "${YELLOW}Wil je toch doorgaan?${NC}"
    read -p "Doorgaan? (j/n): " continue_anyway
    if [[ "$continue_anyway" != "j" && "$continue_anyway" != "J" ]]; then
        echo -e "${YELLOW}Installatie geannuleerd.${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Facturatie & Boekhouding Systeem - Ubuntu 22.04 Setup${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Functie om gebruiker om bevestiging te vragen
ask_yes_no() {
    read -p "$1 (j/n): " choice
    case "$choice" in 
        j|J|ja|Ja|JA ) return 0;;
        * ) return 1;;
    esac
}

# Vraag voor installatie locatie
read -p "Waar wil je de applicatie installeren? [/opt/facturatie]: " INSTALL_DIR
INSTALL_DIR=${INSTALL_DIR:-/opt/facturatie}

# Vraag voor domeinnaam
read -p "Voer de domeinnaam in voor deze server (laat leeg voor alleen IP): " DOMAIN_NAME

# Vraag voor GitHub repository (optioneel)
read -p "GitHub repository URL [laat leeg voor handmatige installatie]: " GITHUB_REPO

# Controleer internetverbinding
echo -e "${YELLOW}Internetverbinding controleren...${NC}"
if ! ping -c 1 google.com &> /dev/null; then
    echo -e "${RED}Geen internetverbinding. Controleer je netwerk.${NC}"
    exit 1
fi

# Update pakketlijsten
echo -e "${YELLOW}Pakketlijsten updaten...${NC}"
apt-get update || {
    echo -e "${RED}Kan pakketlijsten niet updaten.${NC}"
    exit 1
}

# Installeer essentiële pakketten
echo -e "${YELLOW}Essentiële pakketten installeren...${NC}"
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    wget \
    git \
    software-properties-common || {
    echo -e "${RED}Kan essentiële pakketten niet installeren.${NC}"
    exit 1
}

# Installeer Docker
echo -e "${YELLOW}Docker installeren...${NC}"
if ! command -v docker &> /dev/null; then
    # Verwijder eventuele oude versies
    apt-get remove -y docker docker-engine docker.io containerd runc || true
    
    # Docker GPG key toevoegen
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg || {
        echo -e "${RED}Kan Docker GPG key niet toevoegen.${NC}"
        exit 1
    }
    
    # Docker repository toevoegen
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null || {
        echo -e "${RED}Kan Docker repository niet toevoegen.${NC}"
        exit 1
    }
    
    # Update pakketlijsten en installeer Docker
    apt-get update || {
        echo -e "${RED}Kan pakketlijsten niet updaten.${NC}"
        exit 1
    }
    
    apt-get install -y docker-ce docker-ce-cli containerd.io || {
        echo -e "${RED}Kan Docker niet installeren.${NC}"
        exit 1
    }
    
    # Start Docker service
    systemctl enable --now docker || {
        echo -e "${RED}Kan Docker service niet starten.${NC}"
        exit 1
    }
    
    echo -e "${GREEN}Docker is succesvol geïnstalleerd.${NC}"
else
    echo -e "${YELLOW}Docker is al geïnstalleerd.${NC}"
fi

# Installeer Docker Compose
echo -e "${YELLOW}Docker Compose installeren...${NC}"
if ! command -v docker-compose &> /dev/null; then
    # Laatste versie van Docker Compose installeren
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose || {
        echo -e "${RED}Kan Docker Compose niet downloaden.${NC}"
        exit 1
    }
    
    chmod +x /usr/local/bin/docker-compose || {
        echo -e "${RED}Kan Docker Compose niet uitvoerbaar maken.${NC}"
        exit 1
    }
    
    # Maak symlink naar /usr/bin (voor sommige distributies)
    ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose || echo -e "${YELLOW}Kan geen symlink maken, maar Docker Compose is geïnstalleerd.${NC}"
    
    echo -e "${GREEN}Docker Compose is succesvol geïnstalleerd.${NC}"
else
    echo -e "${YELLOW}Docker Compose is al geïnstalleerd.${NC}"
fi

# Installeer Nginx
echo -e "${YELLOW}Nginx installeren...${NC}"
apt-get install -y nginx || {
    echo -e "${RED}Kan Nginx niet installeren.${NC}"
    exit 1
}

# Installeer Certbot voor SSL (optioneel, voor domeinnamen)
if [ -n "$DOMAIN_NAME" ]; then
    echo -e "${YELLOW}Certbot installeren voor SSL certificaten...${NC}"
    apt-get install -y certbot python3-certbot-nginx || {
        echo -e "${RED}Kan Certbot niet installeren.${NC}"
        exit 1
    }
fi

# Maak installatie directory
echo -e "${YELLOW}Installatie directory aanmaken: ${INSTALL_DIR}${NC}"
mkdir -p ${INSTALL_DIR} || {
    echo -e "${RED}Kan installatie directory niet aanmaken: ${INSTALL_DIR}${NC}"
    exit 1
}

# Installeer vanuit GitHub als een repository is opgegeven
if [ -n "$GITHUB_REPO" ]; then
    echo -e "${YELLOW}Code ophalen vanuit GitHub: ${GITHUB_REPO}${NC}"
    git clone "${GITHUB_REPO}" "${INSTALL_DIR}" || {
        echo -e "${RED}Kan repository niet clonen: ${GITHUB_REPO}${NC}"
        exit 1
    }
else
    echo -e "${YELLOW}Geen GitHub repository opgegeven, handmatige installatie vereist.${NC}"
    echo -e "${YELLOW}Kopieer alle bestanden naar: ${INSTALL_DIR}${NC}"
    
    # Wachten op bevestiging dat bestanden zijn gekopieerd
    if ! ask_yes_no "Heb je alle bestanden gekopieerd naar ${INSTALL_DIR}?"; then
        echo -e "${YELLOW}Kopieer alle bestanden naar ${INSTALL_DIR} en voer dit script opnieuw uit.${NC}"
        exit 1
    fi
fi

# Ga naar de installatie directory
cd "${INSTALL_DIR}" || {
    echo -e "${RED}Kan niet naar installatie directory navigeren: ${INSTALL_DIR}${NC}"
    exit 1
}

# Controleer of de benodigde bestanden aanwezig zijn
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}docker-compose.yml niet gevonden in ${INSTALL_DIR}${NC}"
    exit 1
fi

if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Dockerfile niet gevonden in ${INSTALL_DIR}${NC}"
    exit 1
fi

# Maak scripts uitvoerbaar
echo -e "${YELLOW}Scripts uitvoerbaar maken...${NC}"
find "${INSTALL_DIR}" -name "*.sh" -exec chmod +x {} \;

# Maak backup en uploads directory
echo -e "${YELLOW}Backup en uploads directory aanmaken...${NC}"
mkdir -p "${INSTALL_DIR}/backups" "${INSTALL_DIR}/static/uploads"

# Maak .env bestand aan op basis van .env.example
if [ -f ".env.example" ]; then
    echo -e "${YELLOW}Configuratie bestand aanmaken...${NC}"
    
    # Genereer willekeurige wachtwoorden
    DB_PASSWORD=$(tr -dc 'A-Za-z0-9!"#$%&()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 16)
    SESSION_SECRET=$(tr -dc 'A-Za-z0-9!"#$%&()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 32)
    
    # Maak een .env bestand op basis van .env.example
    cp ".env.example" ".env" || {
        echo -e "${RED}Kan .env bestand niet aanmaken.${NC}"
        exit 1
    }
    
    # Vervang database wachtwoord in .env
    sed -i "s/DB_PASSWORD=.*/DB_PASSWORD=${DB_PASSWORD}/" .env
    sed -i "s/SESSION_SECRET=.*/SESSION_SECRET=${SESSION_SECRET}/" .env
else
    echo -e "${YELLOW}Geen .env.example gevonden, handmatig configuratiebestand aanmaken...${NC}"
    
    # Genereer willekeurige wachtwoorden
    DB_PASSWORD=$(tr -dc 'A-Za-z0-9!"#$%&()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 16)
    SESSION_SECRET=$(tr -dc 'A-Za-z0-9!"#$%&()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 32)
    
    # Maak een nieuw .env bestand
    cat > .env << EOF
# Database instellingen
DB_USER=postgres
DB_PASSWORD=${DB_PASSWORD}
DB_NAME=facturatie
DB_HOST=db
DB_PORT=5432

# Applicatie instellingen
SESSION_SECRET=${SESSION_SECRET}
TZ=Europe/Amsterdam
EOF
fi

# Configureer en start Docker containers
echo -e "${YELLOW}Docker containers starten...${NC}"
docker-compose up -d || {
    echo -e "${RED}Kan Docker containers niet starten.${NC}"
    exit 1
}

# Configureer Nginx als reverse proxy
echo -e "${YELLOW}Nginx configureren als reverse proxy...${NC}"

# Controleer of nginx/conf.d bestaat
if [ ! -d "${INSTALL_DIR}/nginx/conf.d" ]; then
    mkdir -p "${INSTALL_DIR}/nginx/conf.d"
fi

# Maak Nginx configuratie bestand
if [ -n "$DOMAIN_NAME" ]; then
    # Configuratie met domeinnaam
    cat > /etc/nginx/sites-available/facturatie << EOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${INSTALL_DIR}/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    client_max_body_size 100M;
}
EOF
else
    # Configuratie zonder specifieke domeinnaam
    cat > /etc/nginx/sites-available/facturatie << EOF
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${INSTALL_DIR}/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    client_max_body_size 100M;
}
EOF
fi

# Activeer de Nginx configuratie
ln -sf /etc/nginx/sites-available/facturatie /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test de Nginx configuratie
nginx -t || {
    echo -e "${RED}Nginx configuratie bevat fouten. Zie foutmelding hierboven.${NC}"
    exit 1
}

# Herstart Nginx
systemctl reload nginx || {
    echo -e "${RED}Kan Nginx niet herstarten.${NC}"
    exit 1
}

# Configureer SSL als domeinnaam is opgegeven
if [ -n "$DOMAIN_NAME" ]; then
    echo -e "${YELLOW}SSL configureren met Certbot...${NC}"
    if ask_yes_no "Wil je een gratis SSL certificaat installeren voor ${DOMAIN_NAME}?"; then
        certbot --nginx -d "${DOMAIN_NAME}" --redirect --agree-tos --non-interactive || {
            echo -e "${RED}Kan SSL certificaat niet configureren.${NC}"
            echo -e "${YELLOW}Let op: De applicatie is nog steeds beschikbaar via HTTP.${NC}"
        }
    fi
fi

# Voeg actieve gebruiker toe aan docker groep
SUDO_USER="${SUDO_USER:-$USER}"
if [ "$SUDO_USER" != "root" ]; then
    echo -e "${YELLOW}Gebruiker ${SUDO_USER} toevoegen aan docker groep...${NC}"
    usermod -aG docker "$SUDO_USER" || {
        echo -e "${RED}Kan gebruiker niet toevoegen aan docker groep.${NC}"
    }
    echo -e "${YELLOW}Log uit en weer in om de wijzigingen toe te passen.${NC}"
fi

# Zet eigenaar van de installatie directory
if [ "$SUDO_USER" != "root" ]; then
    echo -e "${YELLOW}Eigenaar van installatie directory instellen...${NC}"
    chown -R ${SUDO_USER}:${SUDO_USER} ${INSTALL_DIR} || {
        echo -e "${RED}Kan eigenaar van installatie directory niet wijzigen.${NC}"
    }
fi

# Configureer firewall
echo -e "${YELLOW}Firewall configureren...${NC}"
if command -v ufw &> /dev/null; then
    ufw allow OpenSSH || true
    ufw allow 'Nginx Full' || true
    
    # Activeer firewall als deze nog niet actief is
    if ! ufw status | grep -q "Status: active"; then
        echo -e "${YELLOW}Firewall activeren...${NC}"
        if ask_yes_no "Wil je de firewall activeren?"; then
            ufw --force enable || {
                echo -e "${RED}Kan firewall niet activeren.${NC}"
            }
        fi
    fi
fi

# Controleer of alles draait
echo -e "${YELLOW}Controleren of alle services actief zijn...${NC}"
docker-compose ps || {
    echo -e "${RED}Kan status van Docker containers niet controleren.${NC}"
}

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Installatie voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Systeem is geïnstalleerd in: ${INSTALL_DIR}${NC}"
echo -e "${YELLOW}Database wachtwoord: ${DB_PASSWORD}${NC}"
echo

if [ -n "$DOMAIN_NAME" ]; then
    echo -e "${YELLOW}De applicatie is beschikbaar op:${NC}"
    echo -e "${YELLOW}https://${DOMAIN_NAME}${NC}"
else
    echo -e "${YELLOW}De applicatie is beschikbaar op:${NC}"
    echo -e "${YELLOW}http://$(hostname -I | awk '{print $1}')${NC}"
fi

echo
echo -e "${YELLOW}Beheer commando's:${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose down        # Stop containers${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose up -d       # Start containers${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose restart web # Herstart web container${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose logs -f     # Bekijk logs${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && ./backup-database.sh       # Maak database backup${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && ./deploy.sh                # Update applicatie${NC}"
echo
echo -e "${YELLOW}Vergeet niet om het wachtwoord veilig op te slaan:${NC}"
echo -e "${YELLOW}Database wachtwoord: ${DB_PASSWORD}${NC}"