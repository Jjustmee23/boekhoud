#!/bin/bash
# fix_conflicts.sh - Los conflicten op bij git pull in bestaande installatie
# Gebruik: sudo ./fix_conflicts.sh
set -e

# Project locatie
PROJECT_DIR="/opt/invoice-app"
cd "$PROJECT_DIR"

# Tijdstempel voor backups
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="$PROJECT_DIR/backups"
mkdir -p "$backup_dir"

echo "=== Conflicterende Bestanden Oplossen ==="
echo "Dit script lost conflicten op met niet-getrackte bestanden bij updates."

# Database backup maken
echo ">> Eerst een database backup maken voor veiligheid..."
if command -v docker &> /dev/null && [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    # Docker installatie
    docker compose exec -T db pg_dump -U postgres -d invoicing > "$backup_dir/db_backup_$timestamp.sql"
else
    # Directe installatie
    if [ -f /etc/postgresql/*/main/pg_hba.conf ]; then
        sudo -u postgres pg_dump invoicing > "$backup_dir/db_backup_$timestamp.sql"
    fi
fi

# Comprimeer de backup
if [ -f "$backup_dir/db_backup_$timestamp.sql" ]; then
    gzip "$backup_dir/db_backup_$timestamp.sql"
    echo ">> Database backup gemaakt: $backup_dir/db_backup_$timestamp.sql.gz"
fi

# Git configureren
git config --global user.email "server@example.com"
git config --global user.name "Server Update"

# Zoek naar niet-getrackte bestanden die zouden conflicteren
echo ">> Zoeken naar niet-getrackte bestanden die kunnen conflicteren..."
untracked_files=$(git ls-files --others --exclude-standard)

if [ -z "$untracked_files" ]; then
    echo ">> Geen niet-getrackte bestanden gevonden."
else
    echo ">> Niet-getrackte bestanden gevonden:"
    echo "$untracked_files"
    
    # Maak een map voor backup bestanden
    echo ">> Backup maken van niet-getrackte bestanden..."
    mkdir -p "$PROJECT_DIR/backup_files_$timestamp"
    
    # Voor elk niet-getrackt bestand
    echo "$untracked_files" | while read -r file; do
        if [ -f "$file" ]; then
            echo "Backup maken van $file"
            cp "$file" "$PROJECT_DIR/backup_files_$timestamp/"
            echo "Verwijderen van $file"
            rm "$file"
        fi
    done
    
    echo ">> Alle conflicterende bestanden zijn opgeslagen in: $PROJECT_DIR/backup_files_$timestamp/"
fi

# Probeer git pull
echo ">> Git pull uitvoeren..."
if git pull; then
    echo ">> Git pull succesvol uitgevoerd!"
else
    # Als git pull faalt, probeer met stash
    echo ">> Git pull mislukt. Proberen met stash..."
    git stash
    if git pull; then
        echo ">> Git pull met stash succesvol!"
        # Probeer stash toe te passen (kan falen, maar dat is OK)
        git stash pop || echo ">> Stash kon niet worden toegepast, handmatige controle nodig."
    else
        echo ">> Git pull blijft falen. Probeer eventueel: git fetch origin && git reset --hard origin/main"
        exit 1
    fi
fi

# Update toepassen
echo ">> Update toepassen..."
if command -v docker &> /dev/null && [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    # Docker installatie
    echo ">> Docker containers opnieuw bouwen en starten..."
    docker compose down
    docker compose up -d --build
else
    # Directe installatie
    echo ">> Python packages bijwerken..."
    VENV_DIR="/opt/invoice-app-venv"
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r requirements.txt
        
        echo ">> Applicatie service opnieuw starten..."
        sudo systemctl restart flask-app
    fi
fi

echo "=== Conflict Oplossing Voltooid ==="
echo "Controleer of de applicatie correct werkt door in te loggen."