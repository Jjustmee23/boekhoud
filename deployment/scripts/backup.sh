#!/bin/bash
# Backup script voor de Flask facturatie-applicatie
# Uitvoeren vanaf de applicatiemap

set -e  # Stop bij fouten

APP_DIR="/opt/invoice-app"
BACKUP_DIR="${APP_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Controleer of we in de applicatiemap zijn
if [ ! -d "${APP_DIR}" ]; then
    echo "Fout: Applicatiemap ${APP_DIR} niet gevonden."
    echo "Zorg ervoor dat je dit script uitvoert op de server waar de applicatie draait."
    exit 1
fi

# Maak backup-map aan als deze nog niet bestaat
mkdir -p "${BACKUP_DIR}"

echo "=== Backup starten voor Flask facturatie-applicatie ==="
echo "Tijdstempel: ${TIMESTAMP}"

# Database backup
echo ">> Database backup maken..."
if [ -f "${APP_DIR}/docker-compose.yml" ]; then
    # Docker installatie
    cd "${APP_DIR}"
    docker compose exec -T db pg_dump -U postgres invoicing > "${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"
else
    # Directe installatie
    echo "Geen docker-compose.yml gevonden, directe PostgreSQL-backup uitvoeren..."
    sudo -u postgres pg_dump invoicing > "${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"
fi

# Comprimeer de backup
echo ">> Backup comprimeren..."
gzip "${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"

# Configuratiebestanden backup
echo ">> Configuratiebestanden backup maken..."
tar -czf "${BACKUP_DIR}/config_backup_${TIMESTAMP}.tar.gz" -C "${APP_DIR}" .env

# Optioneel: oudere backups verwijderen (ouder dan 30 dagen)
echo ">> Oude backups opruimen (>30 dagen)..."
find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" -mtime +30 -delete
find "${BACKUP_DIR}" -name "config_backup_*.tar.gz" -mtime +30 -delete

# Toon informatie over beschikbare backups
echo "=== Backup voltooid ==="
echo "Database backup: ${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"
echo "Config backup: ${BACKUP_DIR}/config_backup_${TIMESTAMP}.tar.gz"
echo ""
echo "Aantal beschikbare database backups: $(find "${BACKUP_DIR}" -name "db_backup_*.sql.gz" | wc -l)"
echo "Meest recente backups:"
ls -lt "${BACKUP_DIR}" | head -n 5

echo ""
echo "Om te herstellen vanaf een backup:"
echo "1. Decomprimeer de backup: gunzip ${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql.gz"
echo "2. Voor Docker installatie:"
echo "   cat ${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql | docker compose exec -T db psql -U postgres invoicing"
echo "3. Voor directe installatie:"
echo "   sudo -u postgres psql invoicing < ${BACKUP_DIR}/db_backup_${TIMESTAMP}.sql"