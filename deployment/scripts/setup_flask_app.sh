#!/bin/bash
set -e

# ------------------------------------------------------------------------------
# Configurabele variabelen
# ------------------------------------------------------------------------------
PROJECT_DIR="/opt/invoice-app"

# ------------------------------------------------------------------------------
# 1. Check of het script als root draait
# ------------------------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo "Dit script moet als root of via sudo worden uitgevoerd."
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Oude Docker verwijderen + Docker CE + Compose v2 installeren
# ------------------------------------------------------------------------------
install_docker_official() {
    echo ">> [Docker] Stap 1: Oude Docker-pakketten verwijderen..."
    apt-get remove -y docker docker-engine docker.io containerd runc || true
    apt-get autoremove -y
    apt-get update

    echo ">> [Docker] Stap 2: Vereisten voor Docker-repo toevoegen..."
    apt-get install -y ca-certificates curl gnupg

    echo ">> [Docker] Stap 3: Docker GPG-sleutel en repo instellen..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo ">> [Docker] Stap 4: Docker-repository toevoegen (jammy stable)..."
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
      https://download.docker.com/linux/ubuntu \
      jammy stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    echo ">> [Docker] Stap 5: Docker CE + Compose-plugin installeren..."
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    echo ">> [Docker] Stap 6: Docker activeren en starten..."
    systemctl enable docker
    systemctl start docker
    if ! systemctl is-active --quiet docker; then
        echo "Fout: Docker-daemon kon niet worden gestart."
        exit 1
    fi
    echo ">> [Docker] Docker en Docker Compose v2 succesvol geïnstalleerd."
}

# ------------------------------------------------------------------------------
# 3. Installeer andere dependencies: Git, Nginx, Certbot, UFW
# ------------------------------------------------------------------------------
install_other_dependencies() {
    echo ">> Installeren van Git, Nginx, Certbot en UFW..."
    apt-get install -y git nginx certbot python3-certbot-nginx ufw

    echo ">> Certbot timer activeren (automatisch SSL-hernieuwing)..."
    systemctl enable certbot.timer
    systemctl start certbot.timer
}

# ------------------------------------------------------------------------------
# 4. Firewall configureren (UFW)
# ------------------------------------------------------------------------------
configure_firewall() {
    echo ">> UFW: Openen van SSH + Nginx (80/443) poorten..."
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw --force enable
}

# ------------------------------------------------------------------------------
# 5. Vervang replit-links in Dockerfile (indien nodig)
# ------------------------------------------------------------------------------
replace_replit_links() {
    if [ -f "$PROJECT_DIR/Dockerfile" ]; then
        echo ">> Dockerfile gevonden in ${PROJECT_DIR}."
        read -p "Geef de vervangende URL op voor replit-links (bijv. jouw-domein.nl): " REPLACEMENT_URL
        sed -i "s|replit\.com|${REPLACEMENT_URL}|g" "$PROJECT_DIR/Dockerfile"
        echo ">> Alle verwijzingen naar replit zijn vervangen door ${REPLACEMENT_URL}."
    else
        echo ">> Geen Dockerfile gevonden in ${PROJECT_DIR}; replit-links overslaan."
    fi
}

# ------------------------------------------------------------------------------
# 6. Check of Gunicorn in de Dockerfile wordt geïnstalleerd
# ------------------------------------------------------------------------------
ensure_gunicorn_installed() {
    if [ -f "$PROJECT_DIR/Dockerfile" ]; then
        if ! grep -q "pip install gunicorn" "$PROJECT_DIR/Dockerfile"; then
            echo ">> Gunicorn ontbreekt; we voegen dit toe aan de Dockerfile..."
            if grep -q "pip install -r requirements.txt" "$PROJECT_DIR/Dockerfile"; then
                sed -i '/pip install -r requirements.txt/a RUN pip install gunicorn' "$PROJECT_DIR/Dockerfile"
                echo ">> RUN pip install gunicorn is toegevoegd na pip install -r requirements.txt."
            else
                sed -i '/^COPY /a RUN pip install gunicorn' "$PROJECT_DIR/Dockerfile"
                echo ">> RUN pip install gunicorn is toegevoegd na COPY-commando."
            fi
        else
            echo ">> Gunicorn is al aanwezig in de Dockerfile."
        fi
    else
        echo ">> Geen Dockerfile gevonden, we maken een nieuwe aan."
        create_default_dockerfile
    fi
}

# ------------------------------------------------------------------------------
# 7. Functie om een standaard Dockerfile te maken (indien nodig)
# ------------------------------------------------------------------------------
create_default_dockerfile() {
    echo ">> Creëren van standaard Dockerfile voor Flask applicatie..."
    mkdir -p "$PROJECT_DIR"
    cat > "$PROJECT_DIR/Dockerfile" <<'EOF'
FROM python:3.9-slim

WORKDIR /app

# Installeer systeem dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Kopieer requirements en installeer Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Kopieer de applicatie code
COPY . .

# Poort waarop de applicatie draait
EXPOSE 5000

# Start Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "main:app"]
EOF
    echo ">> Dockerfile succesvol aangemaakt in $PROJECT_DIR/Dockerfile"
}

# ------------------------------------------------------------------------------
# 8. Functie om een standaard .env bestand te maken (indien nodig)
# ------------------------------------------------------------------------------
create_default_env() {
    ENV_PATH="$PROJECT_DIR/.env"
    if [ -f "$ENV_PATH" ]; then
        echo "Er bestaat al een .env bestand, dus we doen niets."
    else
        echo "Geen .env bestand gevonden. We plaatsen een standaard .env..."
        
        # Genereer een willekeurige string voor SESSION_SECRET
        SESSION_SECRET=$(openssl rand -hex 32)
        
        cat > "$ENV_PATH" <<EOF
# Flask applicatie instellingen
FLASK_APP=main.py
FLASK_ENV=production
SESSION_SECRET=${SESSION_SECRET}

# Database instellingen
DATABASE_URL=postgresql://postgres:postgres@db:5432/invoicing

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
        echo ">> .env bestand succesvol aangemaakt in $ENV_PATH"
    fi
}

# ------------------------------------------------------------------------------
# 9. Functie om een standaard requirements.txt te maken (indien nodig)
# ------------------------------------------------------------------------------
create_default_requirements() {
    REQ_PATH="$PROJECT_DIR/requirements.txt"
    if [ -f "$REQ_PATH" ]; then
        echo "Er bestaat al een requirements.txt bestand, dus we doen niets."
    else
        echo "Geen requirements.txt gevonden. We plaatsen een standaard requirements.txt..."
        cat > "$REQ_PATH" <<EOF
flask==2.0.1
flask-sqlalchemy==2.5.1
flask-login==0.5.0
psycopg2-binary==2.9.1
python-dotenv==0.19.0
gunicorn==20.1.0
email-validator==1.1.3
requests==2.26.0
msal==1.16.0
mollie-api-python==2.11.0
weasyprint==53.0
pandas==1.3.3
openpyxl==3.0.9
pyjwt==2.1.0
trafilatura==1.0.0
EOF
        echo ">> requirements.txt bestand succesvol aangemaakt in $REQ_PATH"
    fi
}

# ------------------------------------------------------------------------------
# 10. Functie: Gebruiker kiest of hij eigen configuratie uploadt, of default wil
# ------------------------------------------------------------------------------
ensure_configuration() {
    echo
    read -p "Wil je je eigen configuratiebestanden uploaden in $PROJECT_DIR/ (Y/n)? " upload_choice
    upload_choice=${upload_choice:-Y}

    if [[ "$upload_choice" =~ ^[Yy]$ ]]; then
        echo "Je kunt nu je eigen configuratiebestanden uploaden naar: $PROJECT_DIR/"
        echo "(Bijv. via scp: scp ./main.py root@server:$PROJECT_DIR/main.py )"
        echo
        echo "Als je klaar bent met uploaden, druk Enter om verder te gaan."
        read -r

        # Check Dockerfile
        if [ ! -f "$PROJECT_DIR/Dockerfile" ]; then
            read -p "Geen Dockerfile gevonden. Wil je de standaard Dockerfile gebruiken? (Y/n): " use_default_dockerfile
            use_default_dockerfile=${use_default_dockerfile:-Y}
            if [[ "$use_default_dockerfile" =~ ^[Yy]$ ]]; then
                create_default_dockerfile
            fi
        fi

        # Check .env file
        if [ ! -f "$PROJECT_DIR/.env" ]; then
            read -p "Geen .env bestand gevonden. Wil je een standaard .env bestand maken? (Y/n): " use_default_env
            use_default_env=${use_default_env:-Y}
            if [[ "$use_default_env" =~ ^[Yy]$ ]]; then
                create_default_env
            fi
        fi

        # Check requirements.txt
        if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
            read -p "Geen requirements.txt gevonden. Wil je een standaard requirements.txt maken? (Y/n): " use_default_req
            use_default_req=${use_default_req:-Y}
            if [[ "$use_default_req" =~ ^[Yy]$ ]]; then
                create_default_requirements
            fi
        fi
    else
        # Gebruiker kiest N -> maak de standaard configuratiebestanden
        create_default_dockerfile
        create_default_env
        create_default_requirements
    fi
}

# ------------------------------------------------------------------------------
# 11. Setup de applicatie: repo klonen, docker-compose.yml genereren
# ------------------------------------------------------------------------------
setup_application() {
    GITHUB_REPO="https://github.com/Jjustmee23/boekhoud.git"
    echo ">> GitHub repository is ingesteld op $GITHUB_REPO"
    read -p "Geef de naam van de PostgreSQL-database: " DB_NAME
    DB_NAME=${DB_NAME:-invoicing}

    echo
    echo "Hoeveel Gunicorn workers wil je gebruiken? (vuistregel: (2 * CPU) + 1)"
    read -p "Bijv. 17 bij 8-core server: " WORKERS
    WORKERS=${WORKERS:-4}
    echo ">> We gebruiken $WORKERS Gunicorn workers."

    # Kloon of update
    if [ ! -d "$PROJECT_DIR" ]; then
        echo ">> Clonen van repo naar $PROJECT_DIR..."
        git clone "$GITHUB_REPO" "$PROJECT_DIR"
    else
        echo ">> Repo bestaat al in $PROJECT_DIR, we doen git pull..."
        cd "$PROJECT_DIR"
        git pull
    fi

    replace_replit_links
    ensure_gunicorn_installed
    ensure_configuration

    echo ">> Genereren van docker-compose.yml..."
    cat > "$PROJECT_DIR/docker-compose.yml" <<EOL
services:
  db:
    image: postgres:latest
    container_name: flask_db
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  web:
    build: .
    container_name: flask_web
    restart: always
    command: gunicorn --workers=${WORKERS} --bind 0.0.0.0:5000 main:app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/${DB_NAME}
    env_file:
      - .env
    ports:
      - "5000:5000"
    depends_on:
      - db

volumes:
  postgres_data:
EOL

    cd "$PROJECT_DIR"
    echo ">> Docker Compose: bouwen en containers starten..."
    docker compose up -d --build

    echo ">> Flask applicatie is gestart."
}

# ------------------------------------------------------------------------------
# 12. Admin gebruiker aanmaken (pas op het eind)
# ------------------------------------------------------------------------------
create_admin_user() {
    echo
    read -p "Wil je een admin gebruiker aanmaken? (Y/n): " create_admin
    create_admin=${create_admin:-Y}
    if [[ "$create_admin" =~ ^[Yy]$ ]]; then
        read -p "Geef admin username: " admin_username
        read -p "Geef admin email: " admin_email
        read -sp "Geef admin wachtwoord: " admin_password
        echo
        echo ">> Aanmaken admin gebruiker..."
        docker compose exec web python - <<EOF
from app import db
from models import User
from werkzeug.security import generate_password_hash
import os

# Controleer of de gebruiker al bestaat
existing_user = User.query.filter_by(username="${admin_username}").first()
if not existing_user:
    # Maak de admin gebruiker aan
    new_user = User(
        username="${admin_username}",
        email="${admin_email}",
        password_hash=generate_password_hash("${admin_password}")
    )
    # Voor een admin rol, dit kan variëren afhankelijk van je applicatie
    # Je moet mogelijk je eigen User model aanpassen
    new_user.is_admin = True
    
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
# 13. Configureer Nginx met multi-(sub)domein SSL via Certbot
# ------------------------------------------------------------------------------
configure_nginx_ssl() {
    echo "Geef je domein(en) op (spatie-gescheiden) bijv: invoice.midaweb.be www.invoice.midaweb.be"
    read -r DOMAINS
    read -p "Zijn dit correct A-record(s) naar deze server? (Y/n): " A_RECORD
    A_RECORD=${A_RECORD:-Y}
    read -p "Geef een geldig e-mailadres voor SSL-registratie (Let's Encrypt): " CERT_EMAIL

    # Bouw server_name line + certbot -d argumenten
    server_name_line=""
    certbot_domains=""
    for domain in $DOMAINS; do
        server_name_line="$server_name_line $domain"
        certbot_domains="$certbot_domains -d $domain"
    done

    NGINX_CONF="/etc/nginx/sites-available/flask_app.conf"
    echo ">> Creëren minimal HTTP-config in $NGINX_CONF voor: $server_name_line"
    cat > "$NGINX_CONF" <<EOL
server {
    listen 80;
    server_name$server_name_line;

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
}
EOL

    rm -f /etc/nginx/sites-enabled/default
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/

    nginx -t && systemctl reload nginx

    if [[ "$A_RECORD" =~ ^[Yy]$ ]]; then
        echo ">> Certbot --nginx $certbot_domains"
        certbot --nginx $certbot_domains --non-interactive --agree-tos --email "$CERT_EMAIL"
        echo ">> Certbot is klaar. Controleer of HTTPS actief is."
    else
        echo ">> SSL niet aangevraagd: domein(en) is/zijn geen A-record(s)."
    fi

    echo ">> Nginx + SSL setup (multi-domein) voltooid."
}

# ------------------------------------------------------------------------------
# 14. Update-functie (voor code-updates en herbuild)
# ------------------------------------------------------------------------------
update_application() {
    cd "$PROJECT_DIR"
    
    echo ">> Maken van backup..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="$PROJECT_DIR/backups"
    mkdir -p "$backup_dir"
    
    # Database backup
    docker compose exec -T db pg_dump -U postgres -d invoicing > "$backup_dir/db_backup_$timestamp.sql"
    echo ">> Database backup gemaakt: $backup_dir/db_backup_$timestamp.sql"
    
    echo ">> Git pull uitvoeren..."
    git pull

    echo ">> Containers opnieuw bouwen en starten..."
    docker compose down
    docker compose up -d --build

    echo ">> Update voltooid!"
}

# ------------------------------------------------------------------------------
# 15. Backup-functie
# ------------------------------------------------------------------------------
backup_application() {
    cd "$PROJECT_DIR"
    
    echo ">> Maken van backup..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    backup_dir="$PROJECT_DIR/backups"
    mkdir -p "$backup_dir"
    
    # Database backup
    docker compose exec -T db pg_dump -U postgres -d invoicing > "$backup_dir/db_backup_$timestamp.sql"
    echo ">> Database backup gemaakt: $backup_dir/db_backup_$timestamp.sql"
    
    # Optioneel: Comprimeren van de backup
    gzip "$backup_dir/db_backup_$timestamp.sql"
    echo ">> Backup gecomprimeerd: $backup_dir/db_backup_$timestamp.sql.gz"
    
    # Optioneel: Backups ouder dan 30 dagen verwijderen
    find "$backup_dir" -name "db_backup_*.sql.gz" -mtime +30 -delete
    echo ">> Oude backups (>30 dagen) zijn verwijderd."
}

# ------------------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------------------
if [ "$1" == "update" ]; then
    update_application
    exit 0
fi

if [ "$1" == "backup" ]; then
    backup_application
    exit 0
fi

echo "=== (1) Install Docker + Docker Compose v2 ==="
install_docker_official

echo "=== (2) Installeer overige dependencies (Nginx, Certbot, enz.) ==="
install_other_dependencies

echo "=== (3) Firewall configureren (UFW) ==="
configure_firewall

echo "=== (4) Setup van de applicatie (repository klonen, docker-compose.yml) ==="
setup_application

echo "=== (5) Nginx + SSL configureren (multi-domein support) ==="
configure_nginx_ssl

echo "=== (6) Admin gebruiker aanmaken (optioneel) ==="
create_admin_user

echo "=== KLAAR! ==="
echo "Gebruik voor updates: sudo ./setup_flask_app.sh update"
echo "Gebruik voor backups: sudo ./setup_flask_app.sh backup"