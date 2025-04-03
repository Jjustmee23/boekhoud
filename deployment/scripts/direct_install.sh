#!/bin/bash
# Direct install script voor Flask facturatie-applicatie (zonder Docker)
# Dit script installeert de applicatie direct op het systeem

set -e  # Stop bij fouten

# ------------------------------------------------------------------------------
# Configurabele variabelen
# ------------------------------------------------------------------------------
PROJECT_DIR="/opt/invoice-app"
VENV_DIR="/opt/invoice-app-venv"
USER="www-data"
GROUP="www-data"

# ------------------------------------------------------------------------------
# 1. Check of het script als root draait
# ------------------------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo "Dit script moet als root of via sudo worden uitgevoerd."
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Installeer benodigde systeem pakketten
# ------------------------------------------------------------------------------
install_system_packages() {
    echo ">> Systeem updaten..."
    apt-get update
    apt-get upgrade -y

    echo ">> Installeren van benodigde pakketten..."
    apt-get install -y python3 python3-pip python3-venv postgresql postgresql-contrib \
                       nginx certbot python3-certbot-nginx ufw git \
                       build-essential libpq-dev libffi-dev

    echo ">> PostgreSQL en Nginx activeren..."
    systemctl enable postgresql
    systemctl start postgresql
    systemctl enable nginx
    systemctl start nginx
}

# ------------------------------------------------------------------------------
# 3. Setup PostgreSQL database
# ------------------------------------------------------------------------------
setup_database() {
    echo ">> PostgreSQL database aanmaken..."
    read -p "Geef de naam van de PostgreSQL-database: " DB_NAME
    DB_NAME=${DB_NAME:-invoicing}
    
    # Maak database aan
    sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME};"
    
    # Maak gebruiker aan met beperkte rechten voor de applicatie
    read -sp "Geef een wachtwoord voor de database gebruiker 'flask_app': " DB_PASSWORD
    echo
    sudo -u postgres psql -c "CREATE USER flask_app WITH PASSWORD '${DB_PASSWORD}';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO flask_app;"
    
    echo ">> Database ${DB_NAME} en gebruiker 'flask_app' succesvol aangemaakt."
}

# ------------------------------------------------------------------------------
# 4. Clone repository en setup virtuele omgeving
# ------------------------------------------------------------------------------
setup_application() {
    GITHUB_REPO="https://github.com/Jjustmee23/boekhoud.git"
    echo ">> GitHub repository is ingesteld op $GITHUB_REPO"
    
    # Kloon of update
    if [ ! -d "$PROJECT_DIR" ]; then
        echo ">> Clonen van repo naar $PROJECT_DIR..."
        git clone "$GITHUB_REPO" "$PROJECT_DIR"
    else
        echo ">> Repo bestaat al in $PROJECT_DIR, we doen git pull..."
        cd "$PROJECT_DIR"
        git pull
    fi
    
    # Maak virtuele omgeving
    echo ">> Python virtuele omgeving aanmaken in ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    
    # Installeer dependencies
    echo ">> Dependencies installeren..."
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip
    
    if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
        pip install -r "${PROJECT_DIR}/requirements.txt"
    else
        echo ">> Geen requirements.txt gevonden, standaard pakketten installeren..."
        pip install flask flask-sqlalchemy flask-login psycopg2-binary python-dotenv gunicorn \
                    email-validator requests msal mollie-api-python weasyprint pandas openpyxl pyjwt trafilatura
        
        # Maak requirements.txt aan voor toekomstige updates
        pip freeze > "${PROJECT_DIR}/requirements.txt"
    fi
    
    # Installeer gunicorn voor productie
    pip install gunicorn
    
    # Zet rechten
    echo ">> Rechten instellen..."
    chown -R "${USER}:${GROUP}" "${PROJECT_DIR}"
    chown -R "${USER}:${GROUP}" "${VENV_DIR}"
    
    # Maak benodigde mappen als ze niet bestaan
    mkdir -p "${PROJECT_DIR}/static"
    mkdir -p "${PROJECT_DIR}/uploads"
    mkdir -p "${PROJECT_DIR}/logs"
    mkdir -p "${PROJECT_DIR}/backups"
    
    chown -R "${USER}:${GROUP}" "${PROJECT_DIR}/static"
    chown -R "${USER}:${GROUP}" "${PROJECT_DIR}/uploads" 
    chown -R "${USER}:${GROUP}" "${PROJECT_DIR}/logs"
    
    # Controleer of .env bestand bestaat, zo niet, maak een template
    if [ ! -f "${PROJECT_DIR}/.env" ]; then
        echo ">> .env bestand aanmaken..."
        # Genereer een willekeurige string voor SESSION_SECRET
        SESSION_SECRET=$(openssl rand -hex 32)
        
        cat > "${PROJECT_DIR}/.env" <<EOF
# Flask applicatie instellingen
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=${SESSION_SECRET}

# Database instellingen
DATABASE_URL=postgresql://flask_app:${DB_PASSWORD}@localhost:5432/${DB_NAME}

# Email instellingen
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@outlook.com
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret

# Betalingsprovider instellingen
MOLLIE_API_KEY=your-mollie-api-key
EOF
    fi
    
    echo ">> Applicatie setup voltooid."
}

# ------------------------------------------------------------------------------
# 5. Configureer Systemd service
# ------------------------------------------------------------------------------
setup_systemd_service() {
    echo ">> Systemd service configureren..."
    
    # Maak systemd service bestand
    cat > /etc/systemd/system/flask-app.service <<EOF
[Unit]
Description=Flask Facturatie Applicatie
After=network.target postgresql.service

[Service]
User=${USER}
Group=${GROUP}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin"
ExecStart=${VENV_DIR}/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    echo ">> Systemd service activeren..."
    systemctl daemon-reload
    systemctl enable flask-app
    systemctl start flask-app
    
    # Controleer of de service is gestart
    if systemctl is-active --quiet flask-app; then
        echo ">> Flask applicatie service is succesvol gestart."
    else
        echo ">> Fout: Flask applicatie service kon niet worden gestart."
        systemctl status flask-app
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# 6. Configureer Nginx als reverse proxy
# ------------------------------------------------------------------------------
configure_nginx() {
    echo ">> Nginx configureren als reverse proxy..."
    
    read -p "Geef het domein voor je applicatie (bijv. invoice.midaweb.be): " DOMAIN
    
    # Maak Nginx configuratie bestand
    cat > /etc/nginx/sites-available/flask-app <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${PROJECT_DIR}/static/;
    }
    
    # Verhoog de grootte van te uploaden bestanden (standaard 1m in Nginx)
    client_max_body_size 10M;
}
EOF

    # Verwijder de default site en activeer de Flask app site
    rm -f /etc/nginx/sites-enabled/default
    ln -sf /etc/nginx/sites-available/flask-app /etc/nginx/sites-enabled/
    
    # Test de configuratie en herlaad Nginx
    nginx -t && systemctl reload nginx
    
    echo ">> Nginx configuratie voltooid."
    
    # SSL configuratie via Certbot
    read -p "Wil je SSL configureren met Let's Encrypt? (Y/n): " SETUP_SSL
    SETUP_SSL=${SETUP_SSL:-Y}
    
    if [[ "$SETUP_SSL" =~ ^[Yy]$ ]]; then
        read -p "Geef een geldig e-mailadres voor SSL-registratie: " CERT_EMAIL
        certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${CERT_EMAIL}"
        
        echo ">> SSL configuratie voltooid. Je site is nu bereikbaar via HTTPS."
        echo ">> Let's Encrypt certificaat zal automatisch vernieuwd worden."
    else
        echo ">> SSL configuratie overgeslagen."
    fi
}

# ------------------------------------------------------------------------------
# 7. Configureer Firewall
# ------------------------------------------------------------------------------
configure_firewall() {
    echo ">> Firewall configureren..."
    
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    
    echo "y" | ufw enable
    
    echo ">> Firewall configuratie voltooid."
}

# ------------------------------------------------------------------------------
# 8. Admin gebruiker aanmaken
# ------------------------------------------------------------------------------
create_admin_user() {
    echo
    read -p "Wil je een admin gebruiker aanmaken? (Y/n): " CREATE_ADMIN
    CREATE_ADMIN=${CREATE_ADMIN:-Y}
    
    if [[ "$CREATE_ADMIN" =~ ^[Yy]$ ]]; then
        read -p "Geef admin username: " ADMIN_USERNAME
        read -p "Geef admin email: " ADMIN_EMAIL
        read -sp "Geef admin wachtwoord: " ADMIN_PASSWORD
        echo
        
        cd "${PROJECT_DIR}"
        source "${VENV_DIR}/bin/activate"
        
        # Voer Python code uit om admin gebruiker aan te maken
        python3 - <<EOF
import os
import sys
sys.path.insert(0, '${PROJECT_DIR}')

from dotenv import load_dotenv
load_dotenv()

# Importeer app en modellen
from app import db
from models import User
from werkzeug.security import generate_password_hash

# Controleer of database tabellen bestaan, zo niet, maak ze aan
db.create_all()

# Controleer of de gebruiker al bestaat
existing_user = User.query.filter_by(username="${ADMIN_USERNAME}").first()

if not existing_user:
    # Maak admin gebruiker aan
    new_user = User(
        username="${ADMIN_USERNAME}",
        email="${ADMIN_EMAIL}",
        password_hash=generate_password_hash("${ADMIN_PASSWORD}")
    )
    
    # Voor een admin rol
    # Je moet mogelijk je eigen User model aanpassen
    try:
        new_user.is_admin = True
    except:
        print("Waarschuwing: kon is_admin niet instellen, controleer het User model")
    
    db.session.add(new_user)
    db.session.commit()
    print("Admin gebruiker succesvol aangemaakt.")
else:
    print("Gebruiker met deze username bestaat al.")
EOF
        
        echo ">> Admin gebruiker aangemaakt (als deze nog niet bestond)."
    fi
}

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
echo "=== (1) Installeren van systeem pakketten ==="
install_system_packages

echo "=== (2) Setup van PostgreSQL database ==="
setup_database

echo "=== (3) Applicatie setup (repository, virtuele omgeving) ==="
setup_application

echo "=== (4) Configureren van Systemd service ==="
setup_systemd_service

echo "=== (5) Configureren van Nginx reverse proxy ==="
configure_nginx

echo "=== (6) Configureren van Firewall (UFW) ==="
configure_firewall

echo "=== (7) Admin gebruiker aanmaken ==="
create_admin_user

echo "=== INSTALLATIE VOLTOOID ==="
echo "Je Flask facturatie-applicatie is nu geïnstalleerd en draait op je server."
echo "Controleer of alles correct werkt door je domein te bezoeken in de browser."
echo
echo "Behulpzame commando's:"
echo "- Applicatie status controleren: sudo systemctl status flask-app"
echo "- Applicatie herstarten: sudo systemctl restart flask-app"
echo "- Logs bekijken: sudo journalctl -u flask-app"
echo "- Update uitvoeren: ${PROJECT_DIR}/update.sh"
echo "- Backup maken: ${PROJECT_DIR}/backup.sh"