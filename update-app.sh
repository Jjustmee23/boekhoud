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