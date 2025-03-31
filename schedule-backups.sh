#!/bin/bash
# Script om automatische database backups in te stellen
# Voegt een cron job toe voor dagelijkse backups

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

echo -e "${YELLOW}Automatische database backups instellen...${NC}"

# Controleer of we in de juiste directory zijn
if [ ! -f "backup-database.sh" ]; then
    echo -e "${RED}backup-database.sh niet gevonden. Voer dit script uit vanuit de project directory.${NC}"
    exit 1
fi

# Zorg ervoor dat het backup script uitvoerbaar is
chmod +x backup-database.sh

# Haal het volledige pad op voor de backup script
BACKUP_SCRIPT=$(realpath backup-database.sh)
PROJECT_DIR=$(dirname "$BACKUP_SCRIPT")

# Controleer of crontab commando beschikbaar is
if ! command -v crontab &> /dev/null; then
    echo -e "${RED}crontab commando niet gevonden. Installeer cron.${NC}"
    echo -e "${YELLOW}sudo apt install -y cron${NC}"
    exit 1
fi

# Vraag om backup frequentie
echo -e "${YELLOW}Hoe vaak wil je een backup maken?${NC}"
echo "1) Dagelijks (3:00 AM)"
echo "2) Wekelijks (zondag 3:00 AM)"
echo "3) Maandelijks (1e van de maand 3:00 AM)"
echo "4) Aangepaste cronexpressie"

read -p "Keuze [1-4]: " backup_choice

case $backup_choice in
    1)
        # Dagelijks om 3:00
        CRON_EXPR="0 3 * * *"
        SCHEDULE_DESC="dagelijks om 3:00 AM"
        ;;
    2)
        # Wekelijks op zondag om 3:00
        CRON_EXPR="0 3 * * 0"
        SCHEDULE_DESC="wekelijks op zondag 3:00 AM"
        ;;
    3)
        # Maandelijks op de 1e om 3:00
        CRON_EXPR="0 3 1 * *"
        SCHEDULE_DESC="maandelijks op de 1e van de maand 3:00 AM"
        ;;
    4)
        # Aangepaste cron expressie
        echo -e "${YELLOW}Voer een aangepaste cron expressie in (bijv. '0 3 * * *' voor dagelijks om 3:00 AM):${NC}"
        read -p "Cron expressie: " CRON_EXPR
        SCHEDULE_DESC="volgens aangepaste planning '$CRON_EXPR'"
        ;;
    *)
        echo -e "${RED}Ongeldige keuze. Standaard instelling: dagelijks om 3:00 AM.${NC}"
        CRON_EXPR="0 3 * * *"
        SCHEDULE_DESC="dagelijks om 3:00 AM"
        ;;
esac

# Vraag om automatische opschoning
echo -e "${YELLOW}Automatisch oude backups verwijderen?${NC}"
echo "1) Nee, bewaar alle backups"
echo "2) Verwijder backups ouder dan 7 dagen"
echo "3) Verwijder backups ouder dan 30 dagen"
echo "4) Verwijder backups ouder dan 90 dagen"
echo "5) Aangepast aantal dagen"

read -p "Keuze [1-5]: " cleanup_choice

CLEANUP_CMD=""
case $cleanup_choice in
    1)
        # Geen opschoning
        CLEANUP_DESC="Geen automatische opschoning"
        ;;
    2)
        # 7 dagen
        CLEANUP_CMD="find $PROJECT_DIR/db_backups -name \"*.sql.gz\" -type f -mtime +7 -delete"
        CLEANUP_DESC="Backups ouder dan 7 dagen worden automatisch verwijderd"
        ;;
    3)
        # 30 dagen
        CLEANUP_CMD="find $PROJECT_DIR/db_backups -name \"*.sql.gz\" -type f -mtime +30 -delete"
        CLEANUP_DESC="Backups ouder dan 30 dagen worden automatisch verwijderd"
        ;;
    4)
        # 90 dagen
        CLEANUP_CMD="find $PROJECT_DIR/db_backups -name \"*.sql.gz\" -type f -mtime +90 -delete"
        CLEANUP_DESC="Backups ouder dan 90 dagen worden automatisch verwijderd"
        ;;
    5)
        # Aangepast
        echo -e "${YELLOW}Voer het aantal dagen in waarna backups verwijderd mogen worden:${NC}"
        read -p "Dagen: " custom_days
        if [[ "$custom_days" =~ ^[0-9]+$ ]]; then
            CLEANUP_CMD="find $PROJECT_DIR/db_backups -name \"*.sql.gz\" -type f -mtime +$custom_days -delete"
            CLEANUP_DESC="Backups ouder dan $custom_days dagen worden automatisch verwijderd"
        else
            echo -e "${RED}Ongeldig aantal dagen. Geen automatische opschoning ingesteld.${NC}"
            CLEANUP_DESC="Geen automatische opschoning"
        fi
        ;;
    *)
        echo -e "${RED}Ongeldige keuze. Geen automatische opschoning ingesteld.${NC}"
        CLEANUP_DESC="Geen automatische opschoning"
        ;;
esac

# Maak de cron job
CRON_JOB="$CRON_EXPR cd $PROJECT_DIR && ./backup-database.sh"

# Voeg opschoning toe indien gekozen
if [ -n "$CLEANUP_CMD" ]; then
    CRON_JOB="$CRON_JOB && $CLEANUP_CMD"
fi

# Voeg de cron job toe
(crontab -l 2>/dev/null || echo "") | grep -v "backup-database.sh" | { cat; echo "$CRON_JOB"; } | crontab -

echo -e "${GREEN}Automatische backups zijn ingesteld!${NC}"
echo -e "${YELLOW}Schema: $SCHEDULE_DESC${NC}"
echo -e "${YELLOW}$CLEANUP_DESC${NC}"
echo
echo -e "${YELLOW}Je kunt de ingestelde cron jobs bekijken met:${NC}"
echo -e "${YELLOW}crontab -l${NC}"