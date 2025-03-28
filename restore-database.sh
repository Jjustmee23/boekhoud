#!/bin/bash
# Script voor het herstellen van een PostgreSQL database backup

# Functie om alle beschikbare backups weer te geven
show_backups() {
    echo "Beschikbare backups:"
    local count=1
    for backup in $(ls -1 ./db_backups/*.sql ./db_backups/*.sql.gz 2>/dev/null); do
        echo "$count) $backup"
        ((count++))
    done
}

# Controleer of docker-compose beschikbaar is
if ! command -v docker-compose &> /dev/null; then
    echo "docker-compose kon niet gevonden worden. Installeer docker-compose of gebruik de volledige pad."
    exit 1
fi

# Controleer of er backups beschikbaar zijn
backup_count=$(ls -1 ./db_backups/*.sql ./db_backups/*.sql.gz 2>/dev/null | wc -l)
if [ $backup_count -eq 0 ]; then
    echo "Geen backup bestanden gevonden in ./db_backups/"
    exit 1
fi

# Haal database variabelen uit .env bestand of gebruik standaardwaarden
if [ -f ./.env ]; then
    source ./.env
fi

DB_USER=${POSTGRES_USER:-postgres}
DB_PASSWORD=${POSTGRES_PASSWORD:-postgres}
DB_NAME=${POSTGRES_DB:-facturatie}

# Toon beschikbare backups en vraag gebruiker om een keuze
show_backups
read -p "Kies een backup om te herstellen (nummer): " backup_number

# Verkrijg het backup bestand op basis van de keuze
selected_backup=$(ls -1 ./db_backups/*.sql ./db_backups/*.sql.gz 2>/dev/null | sed -n "${backup_number}p")

if [ -z "$selected_backup" ]; then
    echo "Ongeldige keuze, probeer opnieuw."
    exit 1
fi

echo "Je hebt gekozen om te herstellen vanaf: $selected_backup"
read -p "WAARSCHUWING: Dit zal alle huidige data in de database $DB_NAME overschrijven. Doorgaan? (j/n): " confirm

if [ "$confirm" != "j" ] && [ "$confirm" != "J" ]; then
    echo "Hersteloperatie geannuleerd."
    exit 0
fi

# Bepaal of het een gecomprimeerd bestand is
is_compressed=false
if [[ "$selected_backup" == *.gz ]]; then
    is_compressed=true
fi

echo "Starten met herstellen van database $DB_NAME..."

# Herstel de database
if [ "$is_compressed" = true ]; then
    echo "Uitpakken van gecomprimeerde backup..."
    gunzip -c "$selected_backup" | docker-compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"
else
    cat "$selected_backup" | docker-compose exec -T db psql -U "$DB_USER" -d "$DB_NAME"
fi

# Controleer of het herstel is gelukt
if [ $? -eq 0 ]; then
    echo "Database herstel voltooid!"
else
    echo "Fout bij het herstellen van de database!"
    exit 1
fi