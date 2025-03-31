#!/bin/bash
# Script voor het instellen van SSL/HTTPS met Let's Encrypt
# Gebruik dit script nadat je de setup-ubuntu.sh hebt uitgevoerd

# Kleuren voor terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log functie
log() {
    echo -e "${GREEN}[SSL SETUP]${NC} $1"
}

# Waarschuwing functie
warn() {
    echo -e "${YELLOW}[WAARSCHUWING]${NC} $1"
}

# Controleer of het script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    warn "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./setup-ssl.sh'"
    exit 1
fi

# Vraag om domeinnaam
read -p "Voer je domeinnaam in (bijv. factuur.jouwdomein.nl): " DOMAIN

if [ -z "$DOMAIN" ]; then
    warn "Geen domeinnaam opgegeven. SSL setup gestopt."
    exit 1
fi

log "SSL instellen voor domein: $DOMAIN"

# Installeer Certbot
log "Certbot installeren..."
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Configureer Nginx voor het domein
log "Nginx configureren voor $DOMAIN..."
cat > /etc/nginx/sites-available/facturatie << EOL
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $(pwd)/static;
    }

    client_max_body_size 10M;
}
EOL

# Activeer de configuratie
ln -sf /etc/nginx/sites-available/facturatie /etc/nginx/sites-enabled/

# Test Nginx configuratie
nginx -t
systemctl reload nginx

# Verkrijg SSL certificaat
log "SSL certificaat aanvragen via Let's Encrypt..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --redirect

# Test de Nginx configuratie opnieuw
nginx -t
systemctl reload nginx

log "SSL setup voltooid!"
log "Je applicatie is nu beschikbaar via https://$DOMAIN"
log ""
log "SSL certificaten worden automatisch vernieuwd via een Certbot cronjob."
log "Je kunt de vernieuwing testen met: sudo certbot renew --dry-run"