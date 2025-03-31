#!/bin/bash
# Script voor het instellen van geautomatiseerde database backups
# Dit script configureert cron jobs voor periodieke backups

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

# Functie om gebruiker om bevestiging te vragen
ask_yes_no() {
    read -p "$1 (j/n): " choice
    case "$choice" in 
        j|J|ja|Ja|JA ) return 0;;
        * ) return 1;;
    esac
}

# Instellingen
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup-database.sh"
LOGFILE="/var/log/boekhoud-backup.log"

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Boekhoud Systeem - Backup Planning${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of het backup script bestaat
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo -e "${RED}Backup script niet gevonden: ${BACKUP_SCRIPT}${NC}"
    exit 1
fi

# Controleer of script met root privileges wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd met root privileges (gebruik sudo).${NC}"
    exit 1
fi

# Maak backup script uitvoerbaar
chmod +x "$BACKUP_SCRIPT"

# Backup frequenties
echo -e "${YELLOW}Hoe vaak wil je database backups maken?${NC}"
echo "1) Dagelijks"
echo "2) Wekelijks"
echo "3) Maandelijks"
echo "4) Aangepast schema"
echo "5) Verwijder alle geplande backups"

read -p "Kies een optie (1-5): " freq_option

case $freq_option in
    1)
        echo -e "${YELLOW}Op welk tijdstip wil je de dagelijkse backup (24-uursnotatie, bijv. 03:00)?${NC}"
        read -p "Tijd (UU:MM): " backup_time
        
        # Valideer tijd format
        if ! [[ $backup_time =~ ^([0-1][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
            echo -e "${RED}Ongeldig tijdformaat. Gebruik UU:MM (bijv. 03:00).${NC}"
            exit 1
        fi
        
        hour=${backup_time%%:*}
        minute=${backup_time##*:}
        
        # Maak cron regel
        CRON_ENTRY="$minute $hour * * * ${BACKUP_SCRIPT} >> ${LOGFILE} 2>&1"
        SCHEDULE_DESC="dagelijks om $backup_time"
        ;;
    2)
        echo -e "${YELLOW}Op welke dag van de week wil je de backup (1=maandag, 7=zondag)?${NC}"
        read -p "Dag (1-7): " day_of_week
        
        if ! [[ $day_of_week =~ ^[1-7]$ ]]; then
            echo -e "${RED}Ongeldige dag. Kies een getal tussen 1 en 7.${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}Op welk tijdstip wil je de wekelijkse backup (24-uursnotatie, bijv. 03:00)?${NC}"
        read -p "Tijd (UU:MM): " backup_time
        
        # Valideer tijd format
        if ! [[ $backup_time =~ ^([0-1][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
            echo -e "${RED}Ongeldig tijdformaat. Gebruik UU:MM (bijv. 03:00).${NC}"
            exit 1
        fi
        
        hour=${backup_time%%:*}
        minute=${backup_time##*:}
        
        # Converteer dag van de week (1-7 naar 1-7, waarbij 1=maandag in cron)
        day_name=("maandag" "dinsdag" "woensdag" "donderdag" "vrijdag" "zaterdag" "zondag")
        
        # Maak cron regel
        CRON_ENTRY="$minute $hour * * $day_of_week ${BACKUP_SCRIPT} >> ${LOGFILE} 2>&1"
        SCHEDULE_DESC="wekelijks op ${day_name[$((day_of_week-1))]} om $backup_time"
        ;;
    3)
        echo -e "${YELLOW}Op welke dag van de maand wil je de backup (1-28)?${NC}"
        read -p "Dag (1-28): " day_of_month
        
        if ! [[ $day_of_month =~ ^([1-9]|1[0-9]|2[0-8])$ ]]; then
            echo -e "${RED}Ongeldige dag. Kies een getal tussen 1 en 28.${NC}"
            exit 1
        fi
        
        echo -e "${YELLOW}Op welk tijdstip wil je de maandelijkse backup (24-uursnotatie, bijv. 03:00)?${NC}"
        read -p "Tijd (UU:MM): " backup_time
        
        # Valideer tijd format
        if ! [[ $backup_time =~ ^([0-1][0-9]|2[0-3]):[0-5][0-9]$ ]]; then
            echo -e "${RED}Ongeldig tijdformaat. Gebruik UU:MM (bijv. 03:00).${NC}"
            exit 1
        fi
        
        hour=${backup_time%%:*}
        minute=${backup_time##*:}
        
        # Maak cron regel
        CRON_ENTRY="$minute $hour $day_of_month * * ${BACKUP_SCRIPT} >> ${LOGFILE} 2>&1"
        SCHEDULE_DESC="maandelijks op dag $day_of_month om $backup_time"
        ;;
    4)
        echo -e "${YELLOW}Voer een aangepast cron schema in (minuut uur dag_maand maand dag_week):${NC}"
        echo -e "${YELLOW}Bijvoorbeeld: 0 3 * * 1-5 voor elke werkdag om 03:00${NC}"
        read -p "Cron schema: " custom_schedule
        
        # Valideer of het een geldig cron schema is (simpele check)
        if [[ ! $custom_schedule =~ ^[0-9*,-/]+" "+[0-9*,-/]+" "+[0-9*,-/]+" "+[0-9*,-/]+" "+[0-9*,-/]+$ ]]; then
            echo -e "${RED}Ongeldig cron schema.${NC}"
            exit 1
        fi
        
        # Maak cron regel
        CRON_ENTRY="$custom_schedule ${BACKUP_SCRIPT} >> ${LOGFILE} 2>&1"
        SCHEDULE_DESC="aangepast schema: $custom_schedule"
        ;;
    5)
        # Verwijder alle geplande backups voor dit script
        echo -e "${YELLOW}Alle geplande backups verwijderen...${NC}"
        (crontab -l 2>/dev/null | grep -v "${BACKUP_SCRIPT}") | crontab -
        
        echo -e "${GREEN}Alle geplande backups zijn verwijderd.${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Ongeldige optie.${NC}"
        exit 1
        ;;
esac

# Configureer de cron job
echo -e "${YELLOW}Configureren van backup ${SCHEDULE_DESC}...${NC}"

# Verwijder eventuele bestaande backup cron jobs voor dit script en voeg nieuwe toe
(crontab -l 2>/dev/null | grep -v "${BACKUP_SCRIPT}"; echo "$CRON_ENTRY") | crontab -

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Backup planning voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Database backups zijn gepland: ${SCHEDULE_DESC}${NC}"
echo -e "${YELLOW}Log bestand: ${LOGFILE}${NC}"
echo
echo -e "${YELLOW}Je kunt dit schema later wijzigen door dit script opnieuw uit te voeren.${NC}"
echo -e "${YELLOW}Of bekijk de huidige planning met: crontab -l${NC}"