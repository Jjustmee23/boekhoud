#!/bin/bash
# Database backup script
# This script creates a backup of the PostgreSQL database
# It can be scheduled via cron to run regularly

set -e  # Exit on error

# Configuration
APP_DIR="/opt/invoicing-app"  # Application directory
BACKUP_DIR="$APP_DIR/backups" # Backup directory
RETENTION_DAYS=30             # Number of days to keep backups

# Source environment variables
if [ -f "$APP_DIR/.env" ]; then
    source "$APP_DIR/.env"
else
    echo "Error: .env file not found!"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Timestamp for the backup file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

# Perform database backup
echo "Creating database backup: $BACKUP_FILE"
cd "$APP_DIR"
docker-compose exec -T db pg_dump -U "${POSTGRES_USER:-dbuser}" -d "${POSTGRES_DB:-invoicing}" > "$BACKUP_FILE"

# Compress the backup file
gzip "$BACKUP_FILE"
echo "Backup compressed: $BACKUP_FILE.gz"

# Delete old backups
echo "Deleting backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.gz" -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed successfully!"