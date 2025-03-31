#!/bin/bash
# Script voor het instellen van automatische backups via cron

# Bepaal absolute pad naar de hoofdmap van het project
PROJECT_DIR=$(pwd)
BACKUP_SCRIPT="$PROJECT_DIR/backup-database.sh"

# Controleer of het backup script bestaat
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "Backup script niet gevonden: $BACKUP_SCRIPT"
    exit 1
fi

# Controleer of het backup script uitvoerbaar is
if [ ! -x "$BACKUP_SCRIPT" ]; then
    echo "Backup script is niet uitvoerbaar. Rechten worden aangepast..."
    chmod +x "$BACKUP_SCRIPT"
fi

# Stel dagelijkse backup in om 2:00 uur 's nachts
CRON_JOB="0 2 * * * cd $PROJECT_DIR && ./backup-database.sh > /dev/null 2>&1"

# Voeg toe aan crontab als het er nog niet in staat
(crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" ; echo "$CRON_JOB") | crontab -

# Controleer of de crontab is bijgewerkt
if [ $? -eq 0 ]; then
    echo "Automatische dagelijkse backups zijn ingesteld voor 2:00 uur 's nachts."
    echo "Je kunt dit controleren met het commando: crontab -l"
else
    echo "Fout bij het instellen van automatische backups."
    exit 1
fi