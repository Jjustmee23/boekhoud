#!/bin/bash
# Installatie script voor Boekhoud Systeem
# Installeert alle benodigde software en configureert het systeem

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

# Controleer of script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd als root (gebruik sudo).${NC}"
    exit 1
fi

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Boekhoud Systeem - Installatie${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Instellingsvariabelen
INSTALL_DIR="/opt/boekhoud"
GITHUB_REPO="https://github.com/Jjustmee23/boekhoud.git"
DB_PASSWORD=$(tr -dc 'A-Za-z0-9!"#$%&()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 16)
SESSION_SECRET=$(tr -dc 'A-Za-z0-9!"#$%&()*+,-./:;<=>?@[\]^_`{|}~' </dev/urandom | head -c 32)
ENV_FILE="${INSTALL_DIR}/.env"

# Vraag de gebruiker voor de installatie directory
read -p "Installatie directory [$INSTALL_DIR]: " custom_dir
INSTALL_DIR=${custom_dir:-$INSTALL_DIR}

# Vraag de gebruiker voor de Github repository URL
read -p "GitHub repository URL [$GITHUB_REPO]: " custom_repo
GITHUB_REPO=${custom_repo:-$GITHUB_REPO}

echo -e "${YELLOW}De volgende software zal worden geïnstalleerd:${NC}"
echo "- Docker"
echo "- Docker Compose"
echo "- Git"
echo "- Nginx"
echo "- Andere benodigde pakketten"
echo

# Vraag gebruiker om bevestiging
if ! ask_yes_no "Wil je doorgaan met de installatie?"; then
    echo -e "${YELLOW}Installatie geannuleerd door gebruiker.${NC}"
    exit 0
fi

# Update pakketlijsten
echo -e "${YELLOW}Pakketlijsten updaten...${NC}"
apt-get update || {
    echo -e "${RED}Kan pakketlijsten niet updaten. Controleer je internetverbinding.${NC}"
    exit 1
}

# Installeer benodigde pakketten
echo -e "${YELLOW}Benodigde pakketten installeren...${NC}"
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    nginx \
    python3-certbot-nginx \
    software-properties-common || {
    echo -e "${RED}Kan benodigde pakketten niet installeren.${NC}"
    exit 1
}

# Docker installeren
echo -e "${YELLOW}Docker installeren...${NC}"
if ! command -v docker &> /dev/null; then
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
else
    echo -e "${YELLOW}Docker is al geïnstalleerd.${NC}"
fi

# Docker Compose installeren
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
else
    echo -e "${YELLOW}Docker Compose is al geïnstalleerd.${NC}"
fi

# Maak installatie directory
echo -e "${YELLOW}Installatie directory aanmaken...${NC}"
mkdir -p ${INSTALL_DIR} || {
    echo -e "${RED}Kan installatie directory niet aanmaken: ${INSTALL_DIR}${NC}"
    exit 1
}

# Clone repository
echo -e "${YELLOW}Project code ophalen via Git...${NC}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo -e "${YELLOW}Git repository bestaat al. Updates ophalen...${NC}"
    cd ${INSTALL_DIR}
    git pull || {
        echo -e "${RED}Kan git repository niet updaten.${NC}"
        exit 1
    }
else
    git clone ${GITHUB_REPO} ${INSTALL_DIR} || {
        echo -e "${RED}Kan git repository niet clonen: ${GITHUB_REPO}${NC}"
        exit 1
    }
    cd ${INSTALL_DIR}
fi

# Maak scripts uitvoerbaar
echo -e "${YELLOW}Scripts uitvoerbaar maken...${NC}"
chmod +x *.sh || echo -e "${YELLOW}Geen uitvoerbare scripts gevonden of permissie geweigerd.${NC}"

# Maak .env bestand
if [ -f ${INSTALL_DIR}/.env.example ]; then
    echo -e "${YELLOW}Configuratie bestand maken van voorbeeld...${NC}"
    cp ${INSTALL_DIR}/.env.example ${ENV_FILE} || {
        echo -e "${RED}Kan .env bestand niet maken.${NC}"
        exit 1
    }
    
    # Update gegevens in .env bestand
    sed -i "s|DB_PASSWORD=.*|DB_PASSWORD=${DB_PASSWORD}|g" ${ENV_FILE}
    sed -i "s|SESSION_SECRET=.*|SESSION_SECRET=${SESSION_SECRET}|g" ${ENV_FILE}
    
    # Update docker-compose.yml met database wachtwoord
    if [ -f "${INSTALL_DIR}/docker-compose.yml" ]; then
        echo -e "${YELLOW}docker-compose.yml gevonden, database wachtwoord bijwerken...${NC}"
        
        # Maak backup van docker-compose.yml
        cp "${INSTALL_DIR}/docker-compose.yml" "${INSTALL_DIR}/docker-compose.yml.bak"
        
        # Update database wachtwoord in docker-compose.yml als nodig
        if grep -q "POSTGRES_PASSWORD" "${INSTALL_DIR}/docker-compose.yml"; then
            sed -i "s|POSTGRES_PASSWORD:.*|POSTGRES_PASSWORD: \"${DB_PASSWORD}\"|g" "${INSTALL_DIR}/docker-compose.yml"
        fi
    fi
    
    # Vraag gebruiker of ze het .env bestand willen bewerken
    if ask_yes_no "Wil je het .env bestand nu bewerken?"; then
        ${EDITOR:-nano} ${ENV_FILE}
    else
        echo -e "${YELLOW}Vergeet niet om het .env bestand later te configureren: ${ENV_FILE}${NC}"
    fi
else
    echo -e "${YELLOW}Geen .env.example gevonden. Je moet handmatig een .env bestand maken.${NC}"
    touch ${ENV_FILE}
    echo "DB_PASSWORD=${DB_PASSWORD}" >> ${ENV_FILE}
    echo "SESSION_SECRET=${SESSION_SECRET}" >> ${ENV_FILE}
    echo "DB_USER=postgres" >> ${ENV_FILE}
    echo "DB_NAME=boekhoud" >> ${ENV_FILE}
    echo "DB_HOST=db" >> ${ENV_FILE}
    echo "DB_PORT=5432" >> ${ENV_FILE}
fi

# Nginx configureren
echo -e "${YELLOW}Nginx configureren...${NC}"
mkdir -p ${INSTALL_DIR}/nginx/conf.d ${INSTALL_DIR}/nginx/ssl || {
    echo -e "${RED}Kan Nginx configuratie mappen niet aanmaken.${NC}"
    exit 1
}

# Nginx configuratiebestand aanmaken als het nog niet bestaat
if [ ! -f "${INSTALL_DIR}/nginx/conf.d/default.conf" ]; then
    # Vraag voor domeinnaam
    read -p "Voer de domeinnaam in voor deze server (of laat leeg voor alleen IP): " DOMAIN_NAME
    
    if [ -n "$DOMAIN_NAME" ]; then
        # Configuratie met domeinnaam
        cat > ${INSTALL_DIR}/nginx/conf.d/default.conf << EOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    location / {
        proxy_pass http://web:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
}
EOF
        
        # Vraag of gebruiker SSL wil instellen
        if ask_yes_no "Wil je SSL (HTTPS) instellen met Let's Encrypt?"; then
            # Stel Certbot in voor Let's Encrypt certificaat
            certbot --nginx -d ${DOMAIN_NAME} --redirect --agree-tos --no-eff-email --email admin@${DOMAIN_NAME} || {
                echo -e "${YELLOW}Kon geen SSL certificaat genereren, je kunt dit later handmatig doen.${NC}"
            }
        fi
    else
        # Configuratie zonder specifieke domeinnaam
        cat > ${INSTALL_DIR}/nginx/conf.d/default.conf << EOF
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://web:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }
}
EOF
    fi
fi

# Voeg actieve gebruiker toe aan docker groep
SUDO_USER="${SUDO_USER:-$USER}"
if [ "$SUDO_USER" != "root" ]; then
    echo -e "${YELLOW}Gebruiker ${SUDO_USER} toevoegen aan docker groep...${NC}"
    usermod -aG docker "$SUDO_USER"
    echo -e "${YELLOW}Let op: Log uit en log weer in om de wijzigingen toe te passen.${NC}"
fi

# Zet eigenaar van de installatie directory
echo -e "${YELLOW}Eigenaar van installatie directory instellen...${NC}"
if [ "$SUDO_USER" != "root" ]; then
    chown -R ${SUDO_USER}:${SUDO_USER} ${INSTALL_DIR}
fi

# Vraag of gebruiker Docker containers wil starten
if ask_yes_no "Wil je de Docker containers nu starten?"; then
    echo -e "${YELLOW}Docker containers starten...${NC}"
    cd ${INSTALL_DIR}
    docker-compose up -d || {
        echo -e "${RED}Kan Docker containers niet starten. Zie foutmelding hierboven.${NC}"
        exit 1
    }
    echo -e "${GREEN}Docker containers succesvol gestart.${NC}"
else
    echo -e "${YELLOW}Docker containers niet gestart. Start later handmatig met: cd ${INSTALL_DIR} && docker-compose up -d${NC}"
fi

# Cron job instellen voor database backups (optioneel)
if ask_yes_no "Wil je automatische dagelijkse database backups instellen?"; then
    BACKUP_SCRIPT="${INSTALL_DIR}/backup-database.sh"
    CRON_ENTRY="0 3 * * * ${BACKUP_SCRIPT} > /var/log/backup-boekhoud.log 2>&1"
    
    # Voeg cron job toe voor root gebruiker
    (crontab -l 2>/dev/null || echo "") | grep -v "${BACKUP_SCRIPT}" | { cat; echo "${CRON_ENTRY}"; } | crontab -
    
    echo -e "${YELLOW}Dagelijkse backup ingesteld om 03:00 uur.${NC}"
fi

# Installatie voltooid
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Installatie voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Systeem is geïnstalleerd in: ${INSTALL_DIR}${NC}"
echo -e "${YELLOW}Database wachtwoord: ${DB_PASSWORD}${NC}"
echo -e "${YELLOW}Je kunt nu de volgende commando's gebruiken:${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose up -d       # Start de applicatie${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose down        # Stop de applicatie${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && ./deploy.sh                # Update de applicatie${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && ./backup-database.sh       # Maak een database backup${NC}"
echo -e "${YELLOW}- cd ${INSTALL_DIR} && docker-compose logs -f web # Bekijk de logs${NC}"
echo
echo -e "${YELLOW}Onthoud om de .env file te controleren en aan te passen voor productie gebruik.${NC}"
echo
echo -e "${YELLOW}Als je SSL hebt ingesteld, is de applicatie beschikbaar op:${NC}"
echo -e "${YELLOW}https://${DOMAIN_NAME:-<jouw-domein-naam>}${NC}"
echo
echo -e "${YELLOW}Anders is de applicatie beschikbaar op:${NC}"
echo -e "${YELLOW}http://${DOMAIN_NAME:-<jouw-server-ip>}${NC}"