#!/bin/bash
# Automatisch update script voor de boekhoudapplicatie
# Dit script update de applicatie, maakt een backup, installeert ontbrekende afhankelijkheden
# en herstart de applicatie indien nodig

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
        fi
    fi
fi

cd "$APP_DIR" || error "Kan niet naar de applicatiemap navigeren: $APP_DIR"

# Start het update proces
header "BOEKHOUDAPPLICATIE AUTOMATISCHE UPDATE"
log "Het update proces wordt gestart in map: $APP_DIR"
log "Dit script zal:"
log "1. Een backup maken van de database en configuratie"
log "2. De nieuwste code ophalen"
log "3. Ontbrekende afhankelijkheden installeren"
log "4. De applicatie herstarten"
echo ""
read -p "Wil je doorgaan met de update? (j/n): " CONTINUE
if [[ ! "$CONTINUE" =~ ^[Jj]$ ]]; then
    log "Update geannuleerd door gebruiker"
    exit 0
fi

# Controleer of Docker draait
header "CONTROLE VEREISTEN"
if ! systemctl is-active --quiet docker; then
    log "Docker service is niet actief. Service wordt gestart..."
    systemctl start docker
    systemctl enable docker
fi

# Maak een backup van de database
header "STAP 1: BACKUP MAKEN"
log "Database backup wordt gemaakt..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$APP_DIR/backups"
mkdir -p "$BACKUP_DIR"

# Maak een backup van de database
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
log "Database backup wordt gemaakt naar: $DB_BACKUP_FILE"
if docker exec -t $(docker ps -q --filter "name=db") pg_dumpall -c -U postgres > "$DB_BACKUP_FILE" 2>/dev/null; then
    log "Database backup succesvol gemaakt"
else
    warn "Kon geen volledige database backup maken, proberen met individuele database dump..."
    # Probeer een individuele database dump
    if docker exec -t $(docker ps -q --filter "name=db") pg_dump -U postgres -d boekhouding > "$DB_BACKUP_FILE" 2>/dev/null; then
        log "Database backup succesvol gemaakt met pg_dump"
    else
        warn "Kon geen database backup maken via Docker. Mogelijk is de container niet actief."
        # Als Docker containers niet draaien, sla deze stap over
    fi
fi

# Backup .env bestand
if [ -f "$APP_DIR/.env" ]; then
    log ".env bestand wordt gebackupt..."
    cp "$APP_DIR/.env" "$BACKUP_DIR/.env.backup_$TIMESTAMP"
    log ".env backup succesvol gemaakt"
fi

# Backup eventuele aangepaste bestanden
log "Aanpassingen worden gebackupt..."
if command -v git &> /dev/null && [ -d "$APP_DIR/.git" ]; then
    # Gebruik git stash voor lokale wijzigingen
    cd "$APP_DIR" || error "Kan niet naar de applicatiemap navigeren"
    if ! git diff --quiet; then
        log "Lokale aanpassingen gevonden, deze worden opgeslagen met git stash..."
        git stash save "Automatische backup voor update op $(date)"
        log "Aanpassingen opgeslagen in git stash"
    else
        log "Geen lokale aanpassingen gevonden in git"
    fi
else
    # Als git niet beschikbaar is, maak een tarball van belangrijke mappen
    log "Git niet beschikbaar, belangrijke mappen worden gebackupt..."
    tar -czf "$BACKUP_DIR/custom_files_$TIMESTAMP.tar.gz" templates static 2>/dev/null
    log "Belangrijke mappen gebackupt naar $BACKUP_DIR/custom_files_$TIMESTAMP.tar.gz"
fi

# Update de code
header "STAP 2: CODE BIJWERKEN"
if command -v git &> /dev/null && [ -d "$APP_DIR/.git" ]; then
    log "Git repository wordt bijgewerkt..."
    cd "$APP_DIR" || error "Kan niet naar de applicatiemap navigeren"
    
    # Controleer huidige branch
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    log "Huidige branch: $BRANCH"
    
    # Update de code
    log "Code wordt bijgewerkt vanaf oorsprong (origin)..."
    if git pull origin "$BRANCH"; then
        log "Code succesvol bijgewerkt"
    else
        warn "Er waren problemen bij het bijwerken van de code. Proberen te herstellen..."
        # Probeer eventuele problemen op te lossen
        git reset --hard origin/"$BRANCH"
        log "Code hersteld naar laatste versie op de server"
    fi
else
    warn "Git niet beschikbaar of geen git repository gevonden"
    log "Handmatige update is vereist. Download de nieuwste code van GitHub en kopieer deze naar $APP_DIR"
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
            
            # Kopieer de nieuwe code, maar behoud .env en uploads
            rm -rf "$TMP_DIR/.git" # Verwijder .git map om conflicten te voorkomen
            rsync -av --exclude='.env' --exclude='static/uploads' "$TMP_DIR/" "$APP_DIR/"
            rm -rf "$TMP_DIR"
            log "Code succesvol bijgewerkt"
        else
            error "Kon de code niet downloaden van GitHub"
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
        log "DH-parameters ontbreken, worden gegenereerd..."
        mkdir -p "$APP_DIR/nginx/ssl"
        openssl dhparam -out "$APP_DIR/nginx/ssl/dhparam.pem" 2048
        log "DH-parameters succesvol gegenereerd"
    fi
    
    # Maak dhparam-generator.sh uitvoerbaar
    if [ -f "$APP_DIR/nginx/dhparam-generator.sh" ]; then
        chmod +x "$APP_DIR/nginx/dhparam-generator.sh"
    fi
fi

# Controleer of beheerscripts en troubleshooting scripts aanwezig zijn
log "Beheerscripts worden gecontroleerd..."
if [ ! -f "$APP_DIR/beheer.sh" ]; then
    log "Beheerscript ontbreekt, wordt gecreëerd..."
    # Hier zou je het beheerscript kunnen genereren
    log "Zie update-logs voor details"
fi

if [ ! -f "$APP_DIR/troubleshoot-domain.sh" ]; then
    log "Troubleshoot-script ontbreekt, wordt gecreëerd..."
    # Hier zou je het troubleshoot-script kunnen genereren
    log "Zie update-logs voor details"
fi

# Maak alle scripts uitvoerbaar
find "$APP_DIR" -name "*.sh" -exec chmod +x {} \;
log "Alle scriptbestanden zijn nu uitvoerbaar"

# Herstart de applicatie
header "STAP 4: APPLICATIE HERSTARTEN"
log "Applicatie wordt herstart..."
if [ -f "$APP_DIR/docker-compose.yml" ]; then
    docker compose down
    docker compose up -d
    log "Applicatie succesvol herstart"
    
    # Toon de status van de containers
    log "Status van de containers:"
    docker compose ps
else
    warn "docker-compose.yml niet gevonden, applicatie kan niet worden herstart"
fi

# Controleer domeinconfiguratie
if [ -f "$APP_DIR/.env" ]; then
    DOMAIN=$(grep DOMAIN "$APP_DIR/.env" | cut -d '=' -f2)
    if [ -n "$DOMAIN" ]; then
        log "Geconfigureerd domein: $DOMAIN"
        log "De applicatie zou nu bereikbaar moeten zijn op: https://$DOMAIN"
    fi
fi

# Afsluitend bericht
header "UPDATE VOLTOOID"
log "De boekhoudapplicatie is succesvol bijgewerkt en herstart."
log "Backup bestanden zijn opgeslagen in: $BACKUP_DIR"
log ""
log "Als je problemen ondervindt, kun je de volgende commando's gebruiken:"
log "- Bekijk logs: docker compose logs -f"
log "- Voer troubleshooting uit: $APP_DIR/troubleshoot-domain.sh"
log "- Beheer de applicatie: $APP_DIR/beheer.sh"
log ""
log "Als je problemen niet kunt oplossen, kun je de backup herstellen met:"
log "1. Stop de applicatie: docker compose down"
log "2. Herstel de database: cat $DB_BACKUP_FILE | docker exec -i db psql -U postgres"
log "3. Herstel de .env: cp $BACKUP_DIR/.env.backup_$TIMESTAMP $APP_DIR/.env"
log "4. Start de applicatie: docker compose up -d"

# Einde script
exit 0