#!/bin/bash
# Script voor het opzetten van SSL certificaten voor lokale ontwikkeling
# Dit script is alleen nodig voor lokale ontwikkeling, niet voor productie

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

# Zorg ervoor dat nginx/ssl directory bestaat
mkdir -p nginx/ssl
cd nginx/ssl

# Creëer een lokale CA (Certificate Authority)
log "Genereren van lokale Certificate Authority..."
openssl genrsa -out localCA.key 2048
openssl req -x509 -new -nodes -key localCA.key -sha256 -days 365 -out localCA.pem \
    -subj "/C=NL/ST=NoordHolland/L=Amsterdam/O=YourCompany/CN=Local Development CA"

# Creëer certificaat aanvraag en sleutel voor je lokale domein
log "Genereren van certificaat voor lokale ontwikkeling..."
openssl genrsa -out cert.key 2048

# Vraag gebruiker om domeinnaam
read -p "Voer de lokale domeinnaam in (bijv. localhost of factuur.local): " DOMAIN
if [ -z "$DOMAIN" ]; then
    warn "Geen domeinnaam opgegeven. 'localhost' wordt gebruikt."
    DOMAIN="localhost"
fi

# Maak een CSR config bestand
cat > cert.conf << EOL
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = NL
ST = NoordHolland
L = Amsterdam
O = YourCompany
OU = Development
CN = ${DOMAIN}

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = ${DOMAIN}
DNS.2 = www.${DOMAIN}
DNS.3 = localhost
IP.1 = 127.0.0.1
EOL

# Genereer CSR
openssl req -new -key cert.key -out cert.csr -config cert.conf

# Onderteken het certificaat met je lokale CA
openssl x509 -req -in cert.csr -CA localCA.pem -CAkey localCA.key -CAcreateserial \
    -out cert.crt -days 365 -sha256 -extensions v3_req -extfile cert.conf

# Check resultaat
if [ -f cert.crt ] && [ -f cert.key ]; then
    log "SSL certificaten zijn succesvol gegenereerd."
    log "Je moet het localCA.pem bestand nog toevoegen aan de vertrouwde root certificaten van je browser/systeem."
    
    # Toon volgende stappen
    log "Volgende stappen:"
    log "1. Voeg nginx/ssl/localCA.pem toe aan je vertrouwde certificaten"
    log "2. Voeg '127.0.0.1 ${DOMAIN}' toe aan je hosts bestand"
    log "3. Update docker-compose.yml om deze certificaten te gebruiken"
    
    # Genereer nginx config snippet
    cat > ../ssl.conf << EOL
ssl_certificate /etc/nginx/ssl/cert.crt;
ssl_certificate_key /etc/nginx/ssl/cert.key;
ssl_protocols TLSv1.2 TLSv1.3;
ssl_prefer_server_ciphers on;
ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256';
ssl_session_timeout 1d;
ssl_session_cache shared:SSL:10m;
ssl_session_tickets off;
ssl_stapling on;
ssl_stapling_verify on;
EOL
    
    log "Nginx SSL configuratie is gegenereerd in nginx/ssl.conf"
else
    error "Er is een fout opgetreden bij het genereren van de certificaten"
fi