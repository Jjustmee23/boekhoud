#!/bin/bash
# Direct backup script for non-Docker installation
# This script creates a backup of the PostgreSQL database and application files

set -e  # Exit on error

# Configuration
APP_DIR="/opt/invoicing-app"  # Application directory
BACKUP_DIR="$APP_DIR/backups" # Backup directory
RETENTION_DAYS=30             # Number of days to keep backups

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Timestamp for the backup file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_BACKUP="$BACKUP_DIR/invoicing_db_$TIMESTAMP.sql"
CONFIG_BACKUP="$BACKUP_DIR/invoicing_config_$TIMESTAMP.tar.gz"

# Backup the database
echo "Creating database backup: $DB_BACKUP"
sudo -u postgres pg_dump invoicing > "$DB_BACKUP"

# Compress the database backup
gzip "$DB_BACKUP"
echo "Database backup compressed: $DB_BACKUP.gz"

# Backup configuration files
echo "Creating configuration backup: $CONFIG_BACKUP"
tar -czf "$CONFIG_BACKUP" -C "$APP_DIR" .env nginx/conf.d

# Delete old backups
echo "Deleting backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "*.gz" -type f -mtime +$RETENTION_DAYS -delete

echo "Backup completed successfully!"
echo "-----------------------------------"
echo "Database backup: $DB_BACKUP.gz"
echo "Configuration backup: $CONFIG_BACKUP"