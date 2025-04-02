#!/bin/bash
# Direct installation script (non-Docker)
# This installs the application directly on the server without Docker

set -e  # Exit on error

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if running as root or with sudo
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root or with sudo"
fi

# Update system packages
log "Updating system packages..."
apt-get update || error "Failed to update package list"
apt-get upgrade -y || warn "Failed to upgrade packages"

# Install dependencies
log "Installing system dependencies..."
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    postgresql \
    postgresql-contrib \
    nginx \
    certbot \
    python3-certbot-nginx \
    libpq-dev \
    build-essential \
    git \
    curl \
    || error "Failed to install dependencies"

# Create application directory
APP_DIR="/opt/invoicing-app"
log "Creating application directory at $APP_DIR..."
mkdir -p $APP_DIR || error "Failed to create application directory"

# Clone repository if not already done
if [ ! -d "$APP_DIR/.git" ]; then
    log "Cloning repository..."
    # This would be your actual repository
    # git clone https://github.com/yourusername/your-repo.git $APP_DIR
    # For now, we'll assume the current directory is the repository
    cp -r . $APP_DIR || error "Failed to copy application files"
fi

# Set up Python virtual environment
log "Setting up Python virtual environment..."
cd $APP_DIR
python3 -m venv venv || error "Failed to create virtual environment"
source venv/bin/activate || error "Failed to activate virtual environment"

# Install Python dependencies
log "Installing Python dependencies..."
pip install --upgrade pip || warn "Failed to upgrade pip"
pip install -r deployment/requirements.txt || error "Failed to install Python dependencies"

# Set up database
log "Setting up PostgreSQL database..."
# Check if PostgreSQL is running
systemctl is-active --quiet postgresql || systemctl start postgresql

# Create database user and database if they don't exist
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='dbuser'" | grep -q 1; then
    log "Creating database user..."
    sudo -u postgres psql -c "CREATE USER dbuser WITH PASSWORD 'dbpassword';" || error "Failed to create database user"
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='invoicing'" | grep -q 1; then
    log "Creating database..."
    sudo -u postgres psql -c "CREATE DATABASE invoicing OWNER dbuser;" || error "Failed to create database"
fi

# Create environment file
if [ ! -f "$APP_DIR/.env" ]; then
    log "Creating .env file..."
    cp $APP_DIR/.env.example $APP_DIR/.env || error "Failed to create .env file"
    # Generate a random secret key
    SECRET_KEY=$(openssl rand -hex 24)
    sed -i "s/replace_with_secure_random_string/$SECRET_KEY/g" $APP_DIR/.env || warn "Failed to set random secret key"
    warn "Please edit the .env file with your specific configuration"
    warn "  nano $APP_DIR/.env"
else
    warn ".env file already exists. Not overwriting."
fi

# Configure Nginx
log "Configuring Nginx..."
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled

# Create Nginx configuration file
cat > /etc/nginx/sites-available/invoicing << EOF
server {
    listen 80;
    server_name _;  # Replace with your domain name

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/invoicing /etc/nginx/sites-enabled/ || warn "Failed to enable Nginx site"

# Check Nginx configuration
nginx -t || warn "Nginx configuration test failed"

# Restart Nginx
systemctl restart nginx || warn "Failed to restart Nginx"

# Setup systemd service
log "Setting up systemd service..."
cat > /etc/systemd/system/invoicing.service << EOF
[Unit]
Description=Invoicing Application
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 4 --bind 127.0.0.1:5000 main:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd configuration
systemctl daemon-reload || warn "Failed to reload systemd configuration"

# Set permissions
log "Setting permissions..."
chown -R www-data:www-data $APP_DIR || warn "Failed to set directory ownership"
chmod -R 750 $APP_DIR || warn "Failed to set directory permissions"

# Enable and start service
log "Starting application service..."
systemctl enable invoicing || warn "Failed to enable service"
systemctl start invoicing || warn "Failed to start service"

# Setup Let's Encrypt (optional)
read -p "Do you want to set up SSL with Let's Encrypt? (y/n): " setup_ssl
if [ "$setup_ssl" == "y" ]; then
    read -p "Enter your domain name (e.g., example.com): " domain_name
    if [ -n "$domain_name" ]; then
        log "Setting up SSL with Let's Encrypt for $domain_name..."
        certbot --nginx -d $domain_name || warn "Failed to set up SSL certificates"
    else
        warn "No domain name provided. Skipping SSL setup."
    fi
fi

# Setup cron job for automatic backups
log "Setting up daily database backups..."
BACKUP_SCRIPT="$APP_DIR/deployment/direct_backup.sh"
cat > $BACKUP_SCRIPT << EOF
#!/bin/bash
# Backup script for direct installation

BACKUP_DIR="$APP_DIR/backups"
TIMESTAMP=\$(date +%Y%m%d_%H%M%S)
mkdir -p \$BACKUP_DIR
sudo -u postgres pg_dump invoicing > "\$BACKUP_DIR/invoicing_\$TIMESTAMP.sql"
find "\$BACKUP_DIR" -name "*.sql" -type f -mtime +30 -delete
EOF

chmod +x $BACKUP_SCRIPT || warn "Failed to make backup script executable"

# Add cron job
(crontab -l 2>/dev/null; echo "0 2 * * * $BACKUP_SCRIPT") | crontab - || warn "Failed to set up backup cron job"

log "Direct installation completed successfully!"
log "--------------------------------------"
log "The application should now be running."
log ""
log "To check service status: systemctl status invoicing"
log "To view logs: journalctl -u invoicing"
log "To stop the service: systemctl stop invoicing"
log "To restart the service: systemctl restart invoicing"
log ""
log "Database backups will run daily at 2 AM."
log "Backups are stored in $APP_DIR/backups"
log ""
warn "Important: Make sure to edit the .env file with your specific configuration!"
warn "  nano $APP_DIR/.env"
warn "After editing, restart the service: systemctl restart invoicing"