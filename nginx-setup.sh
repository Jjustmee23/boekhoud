#!/bin/bash
# NGINX setup script voor het facturatie systeem
# Dit script installeert en configureert NGINX als reverse proxy met SSL

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
echo -e "${YELLOW}NGINX Setup voor Facturatie Systeem${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of script als root wordt uitgevoerd
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd als root of met sudo.${NC}"
    exit 1
fi

# Controleer of NGINX al is geïnstalleerd
if command -v nginx &> /dev/null; then
    echo -e "${YELLOW}NGINX is al geïnstalleerd.${NC}"
else
    # Installeer NGINX
    echo -e "${YELLOW}NGINX installeren...${NC}"
    apt update
    apt install -y nginx || {
        echo -e "${RED}Kan NGINX niet installeren. Zie foutmelding hierboven.${NC}"
        exit 1
    }
fi

# Start NGINX en enable bij boot
echo -e "${YELLOW}NGINX starten en inschakelen bij opstarten...${NC}"
systemctl start nginx
systemctl enable nginx

# Controleer NGINX status
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}NGINX draait nu!${NC}"
else
    echo -e "${RED}NGINX kon niet worden gestart. Controleer de logs met: journalctl -u nginx${NC}"
    exit 1
fi

# Vraag domein informatie
echo -e "${YELLOW}Domein configuratie:${NC}"
read -p "Voer je hoofddomein in (bijv. mijnbedrijf.nl): " DOMAIN

# Valideer domein
if [[ ! "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$ ]]; then
    echo -e "${RED}Ongeldig domein formaat. Gebruik een geldig domein zonder http:// of www.${NC}"
    exit 1
fi

# Vraag of een subdomein moet worden gebruikt
if ask_yes_no "Wil je een subdomein gebruiken in plaats van het hoofddomein?"; then
    read -p "Voer het subdomein in (bijv. facturatie): " SUBDOMAIN
    if [[ -z "$SUBDOMAIN" ]]; then
        echo -e "${RED}Geen subdomein opgegeven. Hoofddomein wordt gebruikt.${NC}"
        FULL_DOMAIN="$DOMAIN"
    else
        FULL_DOMAIN="${SUBDOMAIN}.${DOMAIN}"
        echo -e "${YELLOW}Volledig domein: ${FULL_DOMAIN}${NC}"
    fi
else
    FULL_DOMAIN="$DOMAIN"
fi

# Vraag om de locatie van de applicatie
read -p "Geef het pad naar de applicatie map [/var/www/facturatie]: " APP_PATH
APP_PATH=${APP_PATH:-/var/www/facturatie}

# Controleer of de map bestaat
if [ ! -d "$APP_PATH" ]; then
    echo -e "${RED}Applicatie map bestaat niet: $APP_PATH${NC}"
    if ask_yes_no "Wil je deze map aanmaken?"; then
        mkdir -p "$APP_PATH"
    else
        echo -e "${RED}Kan NGINX niet configureren zonder geldige applicatie map.${NC}"
        exit 1
    fi
fi

# Vraag om SSL configuratie
USE_SSL=0
if ask_yes_no "Wil je SSL (HTTPS) configureren met Let's Encrypt?"; then
    USE_SSL=1
    
    # Controleer of certbot is geïnstalleerd
    if ! command -v certbot &> /dev/null; then
        echo -e "${YELLOW}Certbot installeren...${NC}"
        apt update
        apt install -y certbot python3-certbot-nginx || {
            echo -e "${RED}Kan Certbot niet installeren. Zie foutmelding hierboven.${NC}"
            exit 1
        }
    fi
    
    # Vraag om e-mailadres voor certificaat waarschuwingen
    read -p "E-mailadres voor SSL certificaat notificaties: " EMAIL
    
    # Valideer e-mailadres
    if [[ ! "$EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        echo -e "${RED}Ongeldig e-mailadres formaat.${NC}"
        exit 1
    fi
fi

# Maak NGINX configuratie voor de site
NGINX_CONF="/etc/nginx/sites-available/${FULL_DOMAIN}"

echo -e "${YELLOW}NGINX configuratie maken...${NC}"

# Basis configuratie voor NGINX
cat > "$NGINX_CONF" << EOF
server {
    listen 80;
    server_name ${FULL_DOMAIN};

    # Logging
    access_log /var/log/nginx/${FULL_DOMAIN}_access.log;
    error_log /var/log/nginx/${FULL_DOMAIN}_error.log;

    # Max upload filesize verhoogd naar 1GB
    client_max_body_size 1024M;
    
    # Proxy headers
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;

    # Lange connecties toestaan voor grote uploads
    proxy_connect_timeout 600;
    proxy_send_timeout 600;
    proxy_read_timeout 600;
    send_timeout 600;

    location / {
        proxy_pass http://localhost:5000;
    }
}
EOF

# Activeer de site
echo -e "${YELLOW}NGINX site activeren...${NC}"
ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test NGINX configuratie
echo -e "${YELLOW}NGINX configuratie testen...${NC}"
nginx -t || {
    echo -e "${RED}NGINX configuratie test mislukt. Zie foutmelding hierboven.${NC}"
    exit 1
}

# Herlaad NGINX om de nieuwe configuratie te activeren
echo -e "${YELLOW}NGINX herladen...${NC}"
systemctl reload nginx

# Vraag om firewall configuratie
if command -v ufw &> /dev/null; then
    echo -e "${YELLOW}Firewall configureren...${NC}"
    
    # Controleer of HTTP en HTTPS al zijn toegestaan
    if ! ufw status | grep -q "80/tcp.*ALLOW"; then
        ufw allow 80/tcp
        echo -e "${GREEN}HTTP (poort 80) geopend in firewall.${NC}"
    fi
    
    if ! ufw status | grep -q "443/tcp.*ALLOW"; then
        ufw allow 443/tcp
        echo -e "${GREEN}HTTPS (poort 443) geopend in firewall.${NC}"
    fi
    
    # Controleer of UFW is ingeschakeld
    if ! ufw status | grep -q "Status: active"; then
        echo -e "${YELLOW}Firewall (UFW) is niet actief.${NC}"
        if ask_yes_no "Wil je de firewall inschakelen?"; then
            # Zorg ervoor dat SSH toegang behouden blijft
            ufw allow ssh
            echo -e "${GREEN}SSH toegang gegarandeerd in firewall.${NC}"
            
            # Enable firewall
            echo "y" | ufw enable
            echo -e "${GREEN}Firewall (UFW) ingeschakeld.${NC}"
        fi
    fi
fi

# Configureer SSL met Let's Encrypt als gevraagd
if [ "$USE_SSL" -eq 1 ]; then
    echo -e "${YELLOW}SSL certificaat aanvragen via Let's Encrypt...${NC}"
    
    # Controleer of het domein juist is geconfigureerd met DNS
    echo -e "${YELLOW}Controleer of je domein ${FULL_DOMAIN} juist is geconfigureerd met DNS${NC}"
    echo -e "${YELLOW}en wijst naar het IP-adres van deze server voordat je doorgaat.${NC}"
    if ! ask_yes_no "Is je domein correct geconfigureerd en bereikbaar?"; then
        echo -e "${RED}SSL certificaat wordt niet aangevraagd. Configureer eerst je DNS.${NC}"
        echo -e "${YELLOW}Je kunt dit later handmatig doen met:${NC}"
        echo -e "${YELLOW}sudo certbot --nginx -d ${FULL_DOMAIN} -m ${EMAIL} --agree-tos --redirect${NC}"
    else
        # Vraag certificaat aan met certbot
        certbot --nginx -d "$FULL_DOMAIN" -m "$EMAIL" --agree-tos --redirect || {
            echo -e "${RED}Kan SSL certificaat niet aanvragen. Zie foutmelding hierboven.${NC}"
            echo -e "${YELLOW}Je kunt dit later handmatig proberen met:${NC}"
            echo -e "${YELLOW}sudo certbot --nginx -d ${FULL_DOMAIN} -m ${EMAIL} --agree-tos --redirect${NC}"
        }
        
        # Controleer of de aanvraag is gelukt
        if [ -d "/etc/letsencrypt/live/${FULL_DOMAIN}" ]; then
            echo -e "${GREEN}SSL certificaat succesvol aangevraagd en geconfigureerd!${NC}"
            echo -e "${YELLOW}Certificaat vernieuwing wordt automatisch beheerd door een systemd timer.${NC}"
            
            # Toon certificaat verlooptijd
            EXPIRY=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/${FULL_DOMAIN}/cert.pem" | cut -d= -f2)
            echo -e "${YELLOW}Certificaat is geldig tot: ${EXPIRY}${NC}"
            
            # Controleer of certbot timer actief is
            if systemctl is-active --quiet certbot.timer; then
                echo -e "${GREEN}Automatische certificaat vernieuwing is actief.${NC}"
            else
                echo -e "${YELLOW}Certbot timer activeren voor automatische vernieuwing...${NC}"
                systemctl enable certbot.timer
                systemctl start certbot.timer
            fi
            
            echo -e "${YELLOW}Je kunt de vernieuwing testen met:${NC}"
            echo -e "${YELLOW}sudo certbot renew --dry-run${NC}"
        fi
    fi
fi

# Maak script voor automatische certificaat controle
CERT_CHECK_SCRIPT="$APP_PATH/check-ssl-cert.sh"
echo -e "${YELLOW}Script maken voor certificaat monitoring...${NC}"

cat > "$CERT_CHECK_SCRIPT" << 'EOF'
#!/bin/bash
# Script voor het controleren van SSL certificaat verloopdatum

DOMAIN=$1
DAYS_WARNING=30
EMAIL=$2

if [ -z "$DOMAIN" ]; then
    echo "Gebruik: $0 domein.nl [email@voorbeeld.nl]"
    exit 1
fi

if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    echo "Geen SSL certificaat gevonden voor $DOMAIN"
    exit 1
fi

# Bereken dagen tot verlopen
EXPIRY=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$DOMAIN/cert.pem" | cut -d= -f2)
EXPIRY_DATE=$(date -d "$EXPIRY" +%s)
CURRENT_DATE=$(date +%s)
DAYS_LEFT=$(( ($EXPIRY_DATE - $CURRENT_DATE) / 86400 ))

echo "SSL certificaat voor $DOMAIN verloopt over $DAYS_LEFT dagen op $EXPIRY"

# Als certificaat bijna verloopt, probeer te vernieuwen
if [ $DAYS_LEFT -lt $DAYS_WARNING ]; then
    echo "Waarschuwing: certificaat verloopt binnen $DAYS_WARNING dagen"
    
    # Probeer certificaat te vernieuwen
    certbot renew --quiet
    
    # Controleer of vernieuwing succesvol was
    NEW_EXPIRY=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/$DOMAIN/cert.pem" | cut -d= -f2)
    NEW_EXPIRY_DATE=$(date -d "$NEW_EXPIRY" +%s)
    NEW_DAYS_LEFT=$(( ($NEW_EXPIRY_DATE - $CURRENT_DATE) / 86400 ))
    
    # Stuur e-mail notificatie als opgegeven
    if [ -n "$EMAIL" ] && [ $NEW_DAYS_LEFT -le $DAYS_LEFT ]; then
        echo "Certificaat vernieuwing mislukt, e-mail notificatie sturen naar $EMAIL"
        echo "WAARSCHUWING: SSL certificaat voor $DOMAIN verloopt over $DAYS_LEFT dagen en automatische vernieuwing lijkt niet te werken." | mail -s "SSL Certificaat Waarschuwing: $DOMAIN" "$EMAIL"
    fi
fi
EOF

chmod +x "$CERT_CHECK_SCRIPT"

# Voeg script toe aan crontab voor wekelijkse controle
if [ "$USE_SSL" -eq 1 ]; then
    echo -e "${YELLOW}Wekelijkse certificaat controle instellen...${NC}"
    
    # Verwijder eventuele bestaande crontab regels voor dit script
    crontab -l 2>/dev/null | grep -v "$CERT_CHECK_SCRIPT" | crontab -
    
    # Voeg nieuwe crontab regel toe
    (crontab -l 2>/dev/null; echo "0 0 * * 0 $CERT_CHECK_SCRIPT $FULL_DOMAIN $EMAIL > /var/log/ssl-check.log 2>&1") | crontab -
    
    echo -e "${GREEN}Wekelijkse certificaat controle ingesteld (elke zondag om middernacht).${NC}"
fi

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}NGINX setup voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo
echo -e "${YELLOW}Je website is nu bereikbaar op: ${NC}"
if [ "$USE_SSL" -eq 1 ]; then
    echo -e "${GREEN}https://${FULL_DOMAIN}${NC}"
else
    echo -e "${GREEN}http://${FULL_DOMAIN}${NC}"
fi
echo
echo -e "${YELLOW}Belangrijke commando's:${NC}"
echo -e "${YELLOW}- sudo systemctl status nginx        # Controleer NGINX status${NC}"
echo -e "${YELLOW}- sudo systemctl restart nginx       # Herstart NGINX${NC}"
echo -e "${YELLOW}- sudo certbot renew --dry-run       # Test certificaat vernieuwing${NC}"
echo
echo -e "${YELLOW}Logbestanden:${NC}"
echo -e "${YELLOW}- /var/log/nginx/${FULL_DOMAIN}_access.log  # Toegangslogboek${NC}"
echo -e "${YELLOW}- /var/log/nginx/${FULL_DOMAIN}_error.log   # Foutenlogboek${NC}"