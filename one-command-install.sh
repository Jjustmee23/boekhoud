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
apt install -y git docker.io docker-compose python3-pip curl postgresql-client ufw nginx certbot python3-certbot-nginx || {
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

# Automatisch configuratie bestand maken
if [ -f auto-config.sh ]; then
    echo -e "${YELLOW}Automatische configuratie starten...${NC}"
    chmod +x auto-config.sh
    ./auto-config.sh --force || {
        echo -e "${RED}Automatische configuratie mislukt.${NC}"
        
        # Fallback naar .env.example als dat bestaat
        if [ -f .env.example ]; then
            echo -e "${YELLOW}Fallback: .env bestand maken van voorbeeld...${NC}"
            cp .env.example .env || {
                echo -e "${RED}Kan .env bestand niet maken.${NC}"
                exit 1
            }
        else
            echo -e "${RED}Geen configuratie mogelijk. Installatie wordt afgebroken.${NC}"
            exit 1
        fi
    }
elif [ -f .env.example ]; then
    echo -e "${YELLOW}Configuratie bestand maken van voorbeeld...${NC}"
    cp .env.example .env || {
        echo -e "${RED}Kan .env bestand niet maken.${NC}"
        exit 1
    }
    
    # Genereer een random Flask geheim
    FLASK_SECRET=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 64)
    if grep -q "FLASK_SECRET_KEY" .env; then
        sed -i "s/FLASK_SECRET_KEY=.*/FLASK_SECRET_KEY=${FLASK_SECRET}/" .env
    else
        echo "FLASK_SECRET_KEY=${FLASK_SECRET}" >> .env
    fi
    
    echo -e "${YELLOW}Je moet het .env bestand mogelijk nog verder aanpassen:${NC}"
    echo -e "${YELLOW}${INSTALL_DIR}/.env${NC}"
else
    echo -e "${RED}Geen .env.example of auto-config.sh gevonden. Je moet handmatig een .env bestand maken.${NC}"
    exit 1
fi

# Voeg huidige gebruiker toe aan docker groep
SUDO_USER="${SUDO_USER:-$USER}"
if [ "$SUDO_USER" != "root" ]; then
    echo -e "${YELLOW}Gebruiker ${SUDO_USER} toevoegen aan docker groep...${NC}"
    usermod -aG docker "$SUDO_USER"
    echo -e "${YELLOW}Let op: Log uit en log weer in om de wijzigingen toe te passen.${NC}"
fi

# Pas maximale upload grootte aan in PHP configuratie als het bestaat
if [ -f "/etc/php/*/fpm/php.ini" ]; then
    echo -e "${YELLOW}PHP configuratie aanpassen voor grote bestandsuploads...${NC}"
    for phpini in /etc/php/*/fpm/php.ini; do
        sed -i 's/upload_max_filesize = [0-9MG]*/upload_max_filesize = 1024M/' "$phpini"
        sed -i 's/post_max_size = [0-9MG]*/post_max_size = 1024M/' "$phpini"
        sed -i 's/memory_limit = [0-9MG]*/memory_limit = 1024M/' "$phpini"
        sed -i 's/max_execution_time = [0-9]*/max_execution_time = 600/' "$phpini"
        sed -i 's/max_input_time = [0-9]*/max_input_time = 600/' "$phpini"
    done
    
    # Herstart PHP-FPM als het draait
    if systemctl is-active --quiet php*-fpm; then
        echo -e "${YELLOW}PHP-FPM herstarten...${NC}"
        systemctl restart php*-fpm
    fi
    
    echo -e "${GREEN}PHP configuratie aangepast voor bestanden tot 1GB.${NC}"
fi

# Start NGINX voor domein configuratie
if ! systemctl is-active --quiet nginx; then
    echo -e "${YELLOW}NGINX starten...${NC}"
    systemctl start nginx
    systemctl enable nginx
fi

# Haal domein uit .env bestand als het bestaat
DOMAIN=""
if [ -f .env ] && grep -q "DOMAIN_NAME" .env; then
    DOMAIN=$(grep "DOMAIN_NAME" .env | cut -d'=' -f2)
fi

# Als domein niet gevonden is in .env, vraag het
if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "localhost" ]; then
    echo -e "${YELLOW}Domein configuratie voor facturatie systeem:${NC}"
    read -p "Voer je hoofddomein in (bijv. mijnbedrijf.nl) of druk Enter om over te slaan: " DOMAIN
fi

# Als domein is opgegeven, configureer NGINX
if [ -n "$DOMAIN" ]; then
    echo -e "${YELLOW}NGINX configureren voor domein ${DOMAIN}...${NC}"
    
    # Controleer of nginx-setup.sh bestaat en voer uit
    if [ -f "${INSTALL_DIR}/nginx-setup.sh" ]; then
        echo -e "${YELLOW}NGINX setup script uitvoeren...${NC}"
        "${INSTALL_DIR}/nginx-setup.sh"
    else
        # Eenvoudige NGINX configuratie zonder script
        echo -e "${YELLOW}NGINX setup script niet gevonden, eenvoudige configuratie maken...${NC}"
        
        # Maak een basis NGINX configuratie bestand
        cat > "/etc/nginx/sites-available/${DOMAIN}" << EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    
    # Logging
    access_log /var/log/nginx/${DOMAIN}_access.log;
    error_log /var/log/nginx/${DOMAIN}_error.log;
    
    # Max upload filesize verhoogd naar 1GB
    client_max_body_size 1024M;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Lange connecties toestaan voor grote uploads
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
        send_timeout 600;
    }
}
EOF
        
        # Activeer de site
        ln -sf "/etc/nginx/sites-available/${DOMAIN}" /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
        
        # Herlaad NGINX
        systemctl reload nginx
        
        # Vraag om SSL certificaat
        if command -v certbot &> /dev/null; then
            if ask_yes_no "Wil je een SSL certificaat aanvragen voor ${DOMAIN}?"; then
                echo -e "${YELLOW}SSL certificaat aanvragen via Let's Encrypt...${NC}"
                
                # Vraag om e-mailadres
                read -p "E-mailadres voor certificaat notificaties: " EMAIL
                
                # Voer certbot uit
                certbot --nginx -d "${DOMAIN}" -d "www.${DOMAIN}" --agree-tos -m "${EMAIL}" --redirect || {
                    echo -e "${RED}SSL certificaat aanvragen mislukt. Zie foutmelding hierboven.${NC}"
                    echo -e "${YELLOW}Je kunt dit later handmatig proberen met:${NC}"
                    echo -e "${YELLOW}sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}${NC}"
                }
            fi
        else
            echo -e "${YELLOW}Certbot niet geïnstalleerd. SSL configuratie overgeslagen.${NC}"
        fi
    fi
    
    echo -e "${GREEN}NGINX configuratie voltooid voor ${DOMAIN}!${NC}"
else
    echo -e "${YELLOW}Domein configuratie overgeslagen.${NC}"
    echo -e "${YELLOW}Je kunt dit later handmatig configureren met:${NC}"
    echo -e "${YELLOW}sudo ${INSTALL_DIR}/nginx-setup.sh${NC}"
fi

# Installatie voltooid
echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Basis installatie voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Belangrijke volgende stappen:${NC}"
echo -e "${YELLOW}1. Log uit en log weer in (of herstart) om docker groep wijzigingen toe te passen${NC}"
echo -e "${YELLOW}2. Start de applicatie: cd ${INSTALL_DIR} && docker-compose up -d${NC}"
if [ -n "$DOMAIN" ]; then
    echo -e "${YELLOW}4. Je site is bereikbaar op: https://${DOMAIN}${NC}"
else
    echo -e "${YELLOW}4. Configureer een domein met: sudo ${INSTALL_DIR}/nginx-setup.sh${NC}"
fi
echo
echo -e "${YELLOW}Gebruik de volgende commando's voor beheer:${NC}"
echo -e "${YELLOW}- docker-compose up -d       # Start de applicatie${NC}"
echo -e "${YELLOW}- docker-compose down        # Stop de applicatie${NC}"
echo -e "${YELLOW}- ./deploy.sh                # Update de applicatie${NC}"
echo -e "${YELLOW}- ./backup-database.sh       # Maak een database backup${NC}"
echo -e "${YELLOW}- ./schedule-backups.sh      # Stel automatische backups in${NC}"