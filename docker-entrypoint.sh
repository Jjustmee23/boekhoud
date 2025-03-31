#!/bin/bash
set -e

# Function to check if PostgreSQL is ready
check_postgres() {
    echo "Checking if PostgreSQL is ready..."
    until pg_isready -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER}; do
        echo "PostgreSQL is unavailable - sleeping"
        sleep 2
    done
    echo "PostgreSQL is up - executing command"
}

# Create directories if they don't exist
mkdir -p /app/static/uploads
mkdir -p /app/backups

# Check if we need to wait for the database
if [ -n "$DB_HOST" ]; then
    check_postgres
fi

# Execute the provided command or start the application
exec "$@"