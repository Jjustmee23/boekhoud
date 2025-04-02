#!/bin/bash
# Server setup script for Ubuntu 22.04
# Run as root or with sudo privileges

set -e  # Exit on error

# Update system
echo "Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install dependencies
echo "Installing dependencies..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw

# Install Docker
echo "Installing Docker..."
if ! [ -x "$(command -v docker)" ]; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $USER
    systemctl enable docker
    systemctl start docker
    apt-get install -y docker-compose-plugin
    echo "Docker installed successfully!"
else
    echo "Docker already installed"
fi

# Configure firewall
echo "Configuring firewall..."
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable

# Create app directory
echo "Creating app directory..."
mkdir -p /opt/invoicing-app
chown -R $USER:$USER /opt/invoicing-app

echo "Server setup complete!"
echo "Please run 'newgrp docker' or log out and back in to apply Docker group changes."
echo "Next, clone your repository to /opt/invoicing-app and run deployment/deploy.sh"