#!/bin/bash
set -e

# Check if we need to run migrations
if [ "${RUN_MIGRATIONS}" = "true" ]; then
    echo "Running database migrations..."
    python force_migrate.py
    
    # Exit code controleren
    if [ $? -ne 0 ]; then
        echo "Database migrations failed, exiting..."
        exit 1
    fi
fi

# Run any other deployment scripts if needed
if [ -f "deployment/setup.sh" ]; then
    echo "Running setup script..."
    bash deployment/setup.sh
fi

# Start the application
exec "$@"
