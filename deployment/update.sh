#!/bin/bash
# Application update script from GitHub
# Run from the application directory

set -e  # Exit on error

# Check if Git is installed
if ! [ -x "$(command -v git)" ]; then
    echo "Error: Git is not installed. Please run setup.sh first."
    exit 1
fi

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "Error: This is not a Git repository."
    exit 1
fi

# Get current branch
current_branch=$(git symbolic-ref --short HEAD)
echo "Current branch: $current_branch"

# Create a backup of the database
echo "Creating database backup..."
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="backups"
mkdir -p $backup_dir

# Use docker-compose to backup the database
docker-compose exec -T db pg_dump -U ${POSTGRES_USER:-dbuser} -d ${POSTGRES_DB:-invoicing} > "$backup_dir/db_backup_$timestamp.sql"
echo "Database backup created: $backup_dir/db_backup_$timestamp.sql"

# Pull the latest changes from the remote repository
echo "Pulling latest changes from Git repository..."
git pull

# Check if requirements have changed
if [ -f "deployment/requirements.txt" ] && [ -f "deployment/requirements.txt.old" ]; then
    if ! cmp --silent "deployment/requirements.txt" "deployment/requirements.txt.old"; then
        echo "Requirements have changed. Updating docker image..."
        # We need to rebuild the image
        docker-compose build web
    fi
fi

# Save the current requirements file for future comparison
cp deployment/requirements.txt deployment/requirements.txt.old

# Restart the application
echo "Restarting the application..."
docker-compose down
docker-compose up -d

echo "Application update completed successfully!"