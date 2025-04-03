#!/bin/bash
# update.sh - Script voor het updaten van de Flask applicatie
# Geschikt voor zowel Docker als directe installaties

set -e

# Project locatie
PROJECT_DIR="/opt/invoice-app"
cd "$PROJECT_DIR"

# Tijdstempel voor backups
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="$PROJECT_DIR/backups"
mkdir -p "$backup_dir"

echo "=== Flask Applicatie Update Script ==="
echo "Dit script werkt je applicatie bij naar de meest recente versie."

# Controleer of we Docker of directe installatie gebruiken
if command -v docker &> /dev/null && [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    # Docker installatie
    echo "=== Docker installatie gedetecteerd ==="
    
    echo ">> Database backup maken..."
    docker compose exec -T db pg_dump -U postgres -d invoicing > "$backup_dir/db_backup_$timestamp.sql"
    echo ">> Database backup gemaakt: $backup_dir/db_backup_$timestamp.sql"
    
    # Optioneel: Comprimeren van de backup
    gzip "$backup_dir/db_backup_$timestamp.sql"
    echo ">> Backup gecomprimeerd: $backup_dir/db_backup_$timestamp.sql.gz"
    
    echo ">> Git pull uitvoeren..."
    # Oplossen van mogelijk conflicterende bestanden
    git config --global user.email "server@example.com"
    git config --global user.name "Server Update"
    
    # Zoek naar ongetrackte bestanden die conflicteren met updates
    conflicting_files=$(git ls-files --others --exclude-standard | xargs -I{} git checkout --conflict=diff -- {} 2>&1 | grep "error: The following untracked working tree files would be overwritten by checkout" -A100 | grep -v "error:" | grep -v "Please" | tr -d '\t' | xargs)
    
    if [ ! -z "$conflicting_files" ]; then
        echo ">> Conflicterende bestanden gevonden. Backup maken en verwijderen..."
        mkdir -p "$PROJECT_DIR/backup_files_$timestamp"
        for file in $conflicting_files; do
            if [ -f "$file" ]; then
                echo "Backup maken van $file"
                cp "$file" "$PROJECT_DIR/backup_files_$timestamp/"
                rm "$file"
            fi
        done
    fi
    
    # Nu de git pull uitvoeren
    git pull || {
        echo ">> Git pull mislukt. Proberen met stash..."
        git stash
        git pull
        git stash pop || echo ">> Stash kon niet worden toegepast, maar update gaat door."
    }
    
    echo ">> Containers opnieuw bouwen en starten..."
    docker compose down
    docker compose up -d --build
    
    echo ">> Wachten tot de containers volledig zijn opgestart..."
    sleep 10
    
    echo ">> Update voltooid!"
    
else
    # Directe installatie
    echo "=== Directe installatie gedetecteerd ==="
    
    echo ">> Database backup maken..."
    if [ -f /etc/postgresql/*/main/pg_hba.conf ]; then
        sudo -u postgres pg_dump invoicing > "$backup_dir/db_backup_$timestamp.sql"
        echo ">> Database backup gemaakt: $backup_dir/db_backup_$timestamp.sql"
        
        # Optioneel: Comprimeren van de backup
        gzip "$backup_dir/db_backup_$timestamp.sql"
        echo ">> Backup gecomprimeerd: $backup_dir/db_backup_$timestamp.sql.gz"
    else
        echo ">> PostgreSQL niet gevonden. Database backup overgeslagen."
    fi
    
    echo ">> Git pull uitvoeren..."
    # Oplossen van mogelijk conflicterende bestanden
    git config --global user.email "server@example.com"
    git config --global user.name "Server Update"
    
    # Zoek naar ongetrackte bestanden die conflicteren met updates
    conflicting_files=$(git ls-files --others --exclude-standard | xargs -I{} git checkout --conflict=diff -- {} 2>&1 | grep "error: The following untracked working tree files would be overwritten by checkout" -A100 | grep -v "error:" | grep -v "Please" | tr -d '\t' | xargs)
    
    if [ ! -z "$conflicting_files" ]; then
        echo ">> Conflicterende bestanden gevonden. Backup maken en verwijderen..."
        mkdir -p "$PROJECT_DIR/backup_files_$timestamp"
        for file in $conflicting_files; do
            if [ -f "$file" ]; then
                echo "Backup maken van $file"
                cp "$file" "$PROJECT_DIR/backup_files_$timestamp/"
                rm "$file"
            fi
        done
    fi
    
    # Nu de git pull uitvoeren
    git pull || {
        echo ">> Git pull mislukt. Proberen met stash..."
        git stash
        git pull
        git stash pop || echo ">> Stash kon niet worden toegepast, maar update gaat door."
    }
    
    echo ">> Virtuele omgeving bijwerken..."
    VENV_DIR="/opt/invoice-app-venv"
    if [ -d "$VENV_DIR" ]; then
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip
        pip install -r requirements.txt
        
        echo ">> Applicatie herstarten..."
        sudo systemctl restart flask-app
        
        echo ">> Update voltooid!"
    else
        echo ">> Virtuele omgeving niet gevonden op $VENV_DIR."
        echo ">> Update deels voltooid, maar de applicatie is mogelijk niet bijgewerkt."
    fi
fi

# Opruimen van oude backups (> 30 dagen)
echo ">> Oude backups opruimen..."
find "$backup_dir" -name "db_backup_*.sql.gz" -mtime +30 -delete

echo "=== Update Proces Voltooid ==="
echo "Controleer of de applicatie correct werkt door in te loggen."