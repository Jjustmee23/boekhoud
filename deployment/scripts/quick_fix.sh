#!/bin/bash
# quick_fix.sh - Snel script om git conflicten op te lossen zonder database te raken
# Gebruik: sudo bash quick_fix.sh

set -e

# Ga naar /opt/invoice-app
cd /opt/invoice-app

echo "=== Quick Fix voor requirements.txt conflict ==="
echo "Dit script bewaart een kopie van bestaande requirements.txt en voert dan git pull uit."

# Maak een backup van requirements.txt als deze bestaat
if [ -f requirements.txt ]; then
    echo ">> Backup maken van requirements.txt..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    cp requirements.txt requirements.txt.backup.$timestamp
    echo ">> Backup gemaakt: requirements.txt.backup.$timestamp"
    
    # Verwijder het conflicterende bestand
    echo ">> Verwijderen van requirements.txt voor git pull..."
    rm requirements.txt
fi

# Stel git user in
git config --global user.email "server@example.com"
git config --global user.name "Server Update"

# Voer git pull uit
echo ">> Git pull uitvoeren..."
git pull

echo ">> Git pull voltooid!"

# Kopieer de update en backup scripts
echo ">> Kopiëren van nieuwe scripts..."
cp -f deployment/scripts/update.sh .
cp -f deployment/scripts/backup.sh .
cp -f deployment/scripts/fix_conflicts.sh .

# Maak ze uitvoerbaar
chmod +x update.sh backup.sh fix_conflicts.sh

echo "=== Quick Fix Voltooid ==="
echo "Je kunt nu de volgende commando's gebruiken:"
echo "- Voor toekomstige updates: ./update.sh"
echo "- Voor backups: ./backup.sh"
echo "- Voor het oplossen van conflicten: ./fix_conflicts.sh"
echo
echo "Als je een Docker-installatie hebt, voer dan uit: docker compose restart web"
echo "Als je een directe installatie hebt, voer dan uit: sudo systemctl restart flask-app"