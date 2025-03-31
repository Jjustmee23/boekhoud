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