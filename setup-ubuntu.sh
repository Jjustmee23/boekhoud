#!/bin/bash
# Installatiebestand voor het opzetten van de facturatie-applicatie op Ubuntu 22.04
# Dit script installeert alle benodigde afhankelijkheden en configureert de applicatie

# Kleuren voor terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Log functie
log() {
    echo -e "${GREEN}[SETUP]${NC} $1"
}

# Waarschuwing functie
warn() {
    echo -e "${YELLOW}[WAARSCHUWING]${NC} $1"
}

# Controleer of het script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    warn "Dit script moet als root worden uitgevoerd. Gebruik 'sudo ./setup-ubuntu.sh'"
    exit 1
fi

# Directory waar de applicatie staat
APP_DIR=$(pwd)
log "Applicatiemap: $APP_DIR"

# Werk pakketlijsten bij
log "Pakketlijsten bijwerken..."
apt update

# Installeer benodigde systeempakketten
log "Benodigde systeempakketten installeren..."
apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx python3-dev libpq-dev supervisor build-essential libssl-dev libffi-dev

# Postgres setup
log "PostgreSQL database instellen..."
# Start PostgreSQL als deze nog niet draait
systemctl start postgresql
systemctl enable postgresql

# Maak een database en gebruiker aan
DB_NAME="facturatie"
DB_USER="facturatie_user"
DB_PASSWORD=$(openssl rand -base64 12) # Genereer een willekeurig wachtwoord

# Maak gebruiker en database aan
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -c "ALTER USER $DB_USER WITH SUPERUSER;"

log "Database $DB_NAME aangemaakt met gebruiker $DB_USER"

# Maak een Python virtual environment aan
log "Python virtual environment aanmaken..."
python3 -m venv venv
source venv/bin/activate

# Installeer Python afhankelijkheden
log "Python afhankelijkheden installeren..."
pip install --upgrade pip
pip install -r requirements.txt || {
    # Als requirements.txt niet bestaat, installeer dan de benodigde pakketten
    log "requirements.txt niet gevonden, installeer benodigde pakketten..."
    pip install flask flask-login flask-sqlalchemy gunicorn psycopg2-binary python-dotenv email-validator msal openpyxl pandas trafilatura weasyprint mollie-api-python pyjwt requests
    
    # Maak een requirements.txt bestand aan
    pip freeze > requirements.txt
    log "requirements.txt aangemaakt"
}

# Maak de .env bestand aan
log "Configuratiebestand .env aanmaken..."
SECRET_KEY=$(openssl rand -base64 24)

cat > .env << EOL
# Database configuratie
DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME

# Flask configuratie
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=$SECRET_KEY

# Email configuratie (Microsoft Graph API)
# Vul hier je eigen Microsoft Graph API gegevens in
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_TENANT_ID=
MS_GRAPH_SENDER_EMAIL=

# Mollie API configuratie
# Vul hier je eigen Mollie API sleutel in
MOLLIE_API_KEY=
EOL

log ".env bestand aangemaakt. Vul de ontbrekende API sleutels aan."

# Maak logs map aan
log "Logs map aanmaken..."
mkdir -p logs
chmod 755 logs

# Maak uploads map aan
log "Uploads map aanmaken..."
mkdir -p static/uploads
chmod 755 static/uploads

# Configureer gunicorn systemd service
log "Gunicorn systemd service configureren..."
cat > /etc/systemd/system/facturatie.service << EOL
[Unit]
Description=Facturatie Application
After=network.target postgresql.service

[Service]
User=$USER
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 --timeout 120 main:app
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Configureer Nginx
log "Nginx configureren..."
cat > /etc/nginx/sites-available/facturatie << EOL
server {
    listen 80;
    server_name _;  # Vervang door je domeinnaam als je die hebt

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $APP_DIR/static;
    }

    client_max_body_size 10M;
}
EOL

# Activeer de Nginx site
ln -s /etc/nginx/sites-available/facturatie /etc/nginx/sites-enabled/ || true
rm -f /etc/nginx/sites-enabled/default || true

# Test Nginx configuratie
nginx -t

# Start services
log "Services starten..."
systemctl daemon-reload
systemctl start facturatie
systemctl enable facturatie
systemctl restart nginx
systemctl enable nginx

# Toon de database inloggegevens
log "Installatie voltooid!"
log "De applicatie draait nu op http://je-server-ip"
log ""
log "Database inloggegevens (bewaar deze op een veilige plaats):"
log "  Database naam: $DB_NAME"
log "  Gebruikersnaam: $DB_USER"
log "  Wachtwoord: $DB_PASSWORD"
log ""
log "Vergeet niet de benodigde API sleutels in te vullen in het .env bestand!"
log "Om toegang te krijgen tot de applicatie, gebruik de standaard login:"
log "  Gebruikersnaam: admin"
log "  Wachtwoord: admin123"
log "Wijzig dit wachtwoord onmiddellijk na de eerste login!"