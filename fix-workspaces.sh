#!/bin/bash
# Script om werkruimteproblemen in het beheerdersdashboard op te lossen

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
    error "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./fix-workspaces.sh'"
    exit 1
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
            exit 1
        fi
    fi
fi

cd "$APP_DIR" || { error "Kan niet naar de applicatiemap navigeren: $APP_DIR"; exit 1; }

# Start het diagnoseproces
header "WERKRUIMTEN DIAGNOSE"
log "Diagnose wordt gestart voor werkruimten in beheerdersdashboard."
log "Applicatiemap: $APP_DIR"

# Controleer of Docker draait
log "Controleren of Docker service actief is..."
if ! systemctl is-active --quiet docker; then
    warn "Docker service is niet actief. Service wordt gestart..."
    systemctl start docker
    systemctl enable docker
fi

# Controleer of de containers draaien
log "Controleren of alle containers draaien..."
if ! docker compose ps | grep -q "Up"; then
    warn "Niet alle containers lijken te draaien. Containers worden herstart..."
    docker compose down
    docker compose up -d
    sleep 5
fi

# Controleer de database verbinding
log "Controleren of database bereikbaar is..."
if ! docker exec -t $(docker ps -q --filter "name=db") pg_isready -U postgres -d boekhouding 2>/dev/null; then
    warn "Database lijkt niet bereikbaar te zijn. Mogelijke databaseproblemen."
    docker compose restart db
    sleep 5
fi

# Dump werkruimten uit de database
log "Werkruimten ophalen uit database..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
WORKSPACE_DUMP_FILE="$APP_DIR/workspaces_dump_$TIMESTAMP.sql"

docker exec -t $(docker ps -q --filter "name=db") psql -U postgres -d boekhouding -c "SELECT * FROM workspaces;" > "$WORKSPACE_DUMP_FILE" 2>/dev/null

if [ $? -eq 0 ]; then
    WORKSPACE_COUNT=$(grep -v "^(" "$WORKSPACE_DUMP_FILE" | grep -v "^-" | grep -v "row" | grep -v "^$" | wc -l)
    WORKSPACE_COUNT=$((WORKSPACE_COUNT-2)) # Correctie voor kolomnamen en header
    
    if [ $WORKSPACE_COUNT -gt 0 ]; then
        log "Aantal werkruimten in database: $WORKSPACE_COUNT"
    else
        warn "Geen werkruimten gevonden in database. Mogelijk database-probleem."
    fi
else
    warn "Kon geen werkruimtengegevens ophalen. Mogelijke databaseproblemen."
fi

# Controleer de gebruikersrechten
log "Controleren van admin gebruikersrechten..."
docker exec -t $(docker ps -q --filter "name=db") psql -U postgres -d boekhouding -c "SELECT u.id, u.email, u.is_admin FROM users u WHERE u.is_admin = TRUE;" > "$APP_DIR/admin_users_$TIMESTAMP.sql" 2>/dev/null

if [ $? -eq 0 ]; then
    ADMIN_COUNT=$(grep -v "^(" "$APP_DIR/admin_users_$TIMESTAMP.sql" | grep -v "^-" | grep -v "row" | grep -v "^$" | wc -l)
    ADMIN_COUNT=$((ADMIN_COUNT-2)) # Correctie voor kolomnamen en header
    
    if [ $ADMIN_COUNT -gt 0 ]; then
        log "Aantal admin gebruikers: $ADMIN_COUNT"
    else
        warn "Geen admin gebruikers gevonden. Dit kan een probleem zijn."
    fi
else
    warn "Kon geen gebruikersgegevens ophalen. Mogelijke databaseproblemen."
fi

# Controleer admin-werkruimte relaties
log "Controleren van admin-werkruimte relaties..."
docker exec -t $(docker ps -q --filter "name=db") psql -U postgres -d boekhouding -c "SELECT wu.user_id, wu.workspace_id, wu.role FROM workspace_users wu JOIN users u ON wu.user_id = u.id WHERE u.is_admin = TRUE;" > "$APP_DIR/admin_workspace_rel_$TIMESTAMP.sql" 2>/dev/null

if [ $? -eq 0 ]; then
    ADMIN_WS_COUNT=$(grep -v "^(" "$APP_DIR/admin_workspace_rel_$TIMESTAMP.sql" | grep -v "^-" | grep -v "row" | grep -v "^$" | wc -l)
    ADMIN_WS_COUNT=$((ADMIN_WS_COUNT-2)) # Correctie voor kolomnamen en header
    
    if [ $ADMIN_WS_COUNT -gt 0 ]; then
        log "Aantal werkruimte-toewijzingen voor admins: $ADMIN_WS_COUNT"
    else
        warn "Geen admin-werkruimte relaties gevonden. Dit is waarschijnlijk het probleem."
        log "Mogelijke oplossing: Voeg werkruimte-toegang toe voor admin gebruikers"
    fi
else
    warn "Kon geen admin-werkruimte relaties ophalen. Mogelijke databaseproblemen."
fi

# Controleer applicatielogbestanden
log "Controleren van applicatielogbestanden..."
if [ -d "$APP_DIR/logs" ]; then
    RECENT_ERRORS=$(grep -i "error" "$APP_DIR/logs/app.log" | tail -20)
    if [ -n "$RECENT_ERRORS" ]; then
        warn "Recente fouten gevonden in logbestanden:"
        echo "$RECENT_ERRORS"
    else
        log "Geen recente fouten gevonden in logbestanden."
    fi
else
    warn "Logs map niet gevonden. Kan logbestanden niet controleren."
fi

# Controleer container logs
log "Controleren van container logs..."
APP_CONTAINER_LOGS=$(docker logs $(docker ps -q --filter "name=app") --tail 50 2>&1 | grep -i "error\|exception\|fail")
if [ -n "$APP_CONTAINER_LOGS" ]; then
    warn "Fouten gevonden in container logs:"
    echo "$APP_CONTAINER_LOGS"
else
    log "Geen significante fouten gevonden in container logs."
fi

# Korte debug-instructies
log "Voorstel voor een oplossing..."
cat << 'EOF' > "$APP_DIR/fix_workspace_visibility.sql"
-- Voer dit script uit in de database om de zichtbaarheid van werkruimten voor admins te herstellen

-- 1. Controleer bestaande werkruimten
SELECT id, name FROM workspaces;

-- 2. Controleer admin gebruikers
SELECT id, email FROM users WHERE is_admin = TRUE;

-- 3. Controleer werkruimte toewijzingen
SELECT * FROM workspace_users;

-- 4. Voeg ontbrekende werkruimte toewijzingen toe voor admins (pas de IDs aan)
-- Vervang user_id en workspace_id met de juiste waarden uit eerdere queries
INSERT INTO workspace_users (user_id, workspace_id, role, created_at, updated_at)
SELECT u.id, w.id, 'admin', NOW(), NOW()
FROM users u, workspaces w
WHERE u.is_admin = TRUE
AND NOT EXISTS (
    SELECT 1 FROM workspace_users wu 
    WHERE wu.user_id = u.id AND wu.workspace_id = w.id
);

-- 5. Controleer of de toewijzingen zijn toegevoegd
SELECT wu.user_id, u.email, wu.workspace_id, w.name, wu.role 
FROM workspace_users wu
JOIN users u ON wu.user_id = u.id
JOIN workspaces w ON wu.workspace_id = w.id
WHERE u.is_admin = TRUE;
EOF

log "Diagnosescript heeft mogelijke problemen geïdentificeerd."
log ""
log "Gevonden bestanden:"
log "- Werkruimten dump: $WORKSPACE_DUMP_FILE"
log "- Admin gebruikers: $APP_DIR/admin_users_$TIMESTAMP.sql"
log "- Admin-werkruimte relaties: $APP_DIR/admin_workspace_rel_$TIMESTAMP.sql"
log "- SQL-oplossingsscript: $APP_DIR/fix_workspace_visibility.sql"
log ""
log "Om de werkruimten in het beheerdersdashboard zichtbaar te maken:"
log "1. Bekijk de gemaakte bestanden om de IDs van werkruimten en admins te identificeren"
log "2. Voer het volgende uit om het probleem op te lossen:"
log ""
log "   docker exec -it \$(docker ps -q --filter \"name=db\") psql -U postgres -d boekhouding -f /app/fix_workspace_visibility.sql"
log ""
log "   (Zorg ervoor dat het SQL-bestand eerst naar de container wordt gekopieerd met:"
log "    docker cp $APP_DIR/fix_workspace_visibility.sql \$(docker ps -q --filter \"name=db\"):/app/)"
log ""
log "3. Herstart de applicatie met: docker compose restart app"
log ""
log "Als je het probleem automatisch wilt proberen op te lossen, voer dan uit:"
log ""
log "   sudo $APP_DIR/auto-fix-workspaces.sh"
log ""

# Maak een automatisch fix script
cat << 'EOF' > "$APP_DIR/auto-fix-workspaces.sh"
#!/bin/bash
# Script om automatisch werkruimterelaties te herstellen

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
    exit 1
}

log "Automatische fix voor werkruimteproblemen wordt uitgevoerd..."

# Kopieer het SQL bestand naar de container
DB_CONTAINER=$(docker ps -q --filter "name=db")
if [ -z "$DB_CONTAINER" ]; then
    error "Database container niet gevonden. Is de applicatie actief?"
fi

log "SQL-bestand wordt gekopieerd naar database container..."
docker cp fix_workspace_visibility.sql $DB_CONTAINER:/app/ || error "Kan SQL-bestand niet kopiëren"

# Voer het SQL-script uit
log "SQL-script wordt uitgevoerd om werkruimten te herstellen..."
docker exec -i $DB_CONTAINER psql -U postgres -d boekhouding -f /app/fix_workspace_visibility.sql > workspace_fix_result.log 2>&1

# Toon het resultaat
log "Resultaat van de reparatie:"
cat workspace_fix_result.log

# Restart de applicatie
log "Applicatie wordt herstart om wijzigingen toe te passen..."
docker compose restart app

log "Reparatie voltooid. Vernieuw nu je browserpagina en controleer of werkruimten zichtbaar zijn."
log "Als het probleem aanhoudt, kijk dan in workspace_fix_result.log voor meer details."

# Einde script
exit 0
EOF

chmod +x "$APP_DIR/auto-fix-workspaces.sh"

# Einde script
log "Diagnose voltooid. Zie bovenstaande instructies voor herstel."
exit 0