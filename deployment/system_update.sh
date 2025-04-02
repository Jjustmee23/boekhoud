#!/bin/bash
# System update script
# This script updates the server OS and Docker components
# It should be run periodically via cron

set -e  # Exit on error

# Log file
LOG_FILE="/var/log/system_update.log"

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "Starting system update"

# Update package lists
log "Updating package lists"
apt-get update -y >> "$LOG_FILE" 2>&1

# Apply security updates only
log "Applying security updates"
unattended-upgrades -v >> "$LOG_FILE" 2>&1

# Update Docker and docker-compose if available
if [ -x "$(command -v docker)" ]; then
    log "Checking for Docker updates"
    apt-get install --only-upgrade docker-ce docker-ce-cli containerd.io -y >> "$LOG_FILE" 2>&1
fi

# Clean up old Docker images, containers, and volumes
if [ -x "$(command -v docker)" ]; then
    log "Cleaning up Docker resources"
    # Remove unused Docker resources
    docker system prune -af --volumes >> "$LOG_FILE" 2>&1
fi

log "System update completed"