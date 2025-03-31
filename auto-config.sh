#!/bin/bash
# Automatische configuratie generator voor facturatie systeem
# Dit script genereert een werkende .env configuratie en zorgt voor database setup

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

# Functie om random string te genereren
generate_random_string() {
    length=${1:-32}
    tr -dc A-Za-z0-9 </dev/urandom | head -c $length
}

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Automatische Configuratie Generator${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Bepaal installatie directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${YELLOW}Installatie directory: ${SCRIPT_DIR}${NC}"

# Controleer of .env.example bestaat
if [ ! -f "${SCRIPT_DIR}/.env.example" ]; then
    echo -e "${YELLOW}.env.example niet gevonden, een basis .env bestand wordt gemaakt...${NC}"
    EXAMPLE_EXISTS=0
else
    echo -e "${YELLOW}.env.example gevonden, dit wordt als basis gebruikt...${NC}"
    EXAMPLE_EXISTS=1
fi

# Stel bestandsnaam voor .env in
ENV_FILE="${SCRIPT_DIR}/.env"
echo -e "${YELLOW}Configuratie bestand: ${ENV_FILE}${NC}"

# Controleer of .env al bestaat
if [ -f "${ENV_FILE}" ]; then
    echo -e "${YELLOW}.env bestand bestaat al.${NC}"
    if [ "$1" == "--force" ]; then
        echo -e "${YELLOW}--force optie gebruikt, bestaand bestand wordt overschreven.${NC}"
        rm -f "${ENV_FILE}"
    else
        echo -e "${YELLOW}Om veiligheidsredenen wordt het bestaande bestand niet overschreven.${NC}"
        echo -e "${YELLOW}Gebruik --force om toch te overschrijven.${NC}"
        echo -e "${YELLOW}Huidige file behouden, verdere configuratie wordt overgeslagen.${NC}"
        exit 0
    fi
fi

# Maak een tijdelijk .env bestand
TEMP_ENV=$(mktemp)

# Als .env.example bestaat, gebruik dit als basis
if [ $EXAMPLE_EXISTS -eq 1 ]; then
    cp "${SCRIPT_DIR}/.env.example" "${TEMP_ENV}"
else
    # Maak een basis .env bestand
    cat > "${TEMP_ENV}" << EOF
# Automatisch gegenereerde configuratie door auto-config.sh
# Gegenereerd op: $(date)

# Database configuratie
DATABASE_URL=postgresql://postgres:password@db:5432/facturatie

# Flask secret key (willekeurig gegenereerd)
FLASK_SECRET_KEY=

# Applicatie instellingen
FLASK_ENV=production
FLASK_DEBUG=0

# Upload configuratie
UPLOAD_FOLDER=static/uploads
MAX_CONTENT_LENGTH=1073741824

# Email configuratie
MAIL_SERVER=
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

# Mollie configuratie voor betalingen
MOLLIE_API_KEY=

# Microsoft OAuth configuratie
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=

# Domein configuratie
DOMAIN_NAME=
EOF
fi

# Vraag domein informatie
echo -e "${YELLOW}Domein configuratie:${NC}"
read -p "Voer je domein in (bijv. mijnbedrijf.nl) of druk Enter voor localhost: " DOMAIN_NAME
DOMAIN_NAME=${DOMAIN_NAME:-localhost}

# Genereer een willekeurige Flask secret key
FLASK_SECRET_KEY=$(generate_random_string 64)
echo -e "${YELLOW}Willekeurige Flask secret key gegenereerd.${NC}"

# Genereer willekeurig wachtwoord voor database
DB_PASSWORD=$(generate_random_string 16)
echo -e "${YELLOW}Willekeurig database wachtwoord gegenereerd.${NC}"

# Update database connection string
if grep -q "DATABASE_URL" "${TEMP_ENV}"; then
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/facturatie|g" "${TEMP_ENV}"
else
    echo "DATABASE_URL=postgresql://postgres:${DB_PASSWORD}@db:5432/facturatie" >> "${TEMP_ENV}"
fi

# Update Flask secret key
if grep -q "FLASK_SECRET_KEY" "${TEMP_ENV}"; then
    sed -i "s|FLASK_SECRET_KEY=.*|FLASK_SECRET_KEY=${FLASK_SECRET_KEY}|g" "${TEMP_ENV}"
else
    echo "FLASK_SECRET_KEY=${FLASK_SECRET_KEY}" >> "${TEMP_ENV}"
fi

# Update domein naam
if grep -q "DOMAIN_NAME" "${TEMP_ENV}"; then
    sed -i "s|DOMAIN_NAME=.*|DOMAIN_NAME=${DOMAIN_NAME}|g" "${TEMP_ENV}"
else
    echo "DOMAIN_NAME=${DOMAIN_NAME}" >> "${TEMP_ENV}"
fi

# Update Microsoft redirect URI als domein is ingesteld
if [ "${DOMAIN_NAME}" != "localhost" ]; then
    REDIRECT_URI="https://${DOMAIN_NAME}/ms-auth-callback"
    if grep -q "MICROSOFT_REDIRECT_URI" "${TEMP_ENV}"; then
        sed -i "s|MICROSOFT_REDIRECT_URI=.*|MICROSOFT_REDIRECT_URI=${REDIRECT_URI}|g" "${TEMP_ENV}"
    fi
fi

# Vraag of gebruiker e-mail wil configureren
echo -e "${YELLOW}Wil je e-mailconfiguratie nu instellen? Dit is optioneel.${NC}"
read -p "E-mail configureren? (j/n): " SETUP_EMAIL
if [[ "$SETUP_EMAIL" =~ ^[jJ] ]]; then
    read -p "SMTP Server (bijv. smtp.gmail.com): " MAIL_SERVER
    read -p "SMTP Poort [587]: " MAIL_PORT
    MAIL_PORT=${MAIL_PORT:-587}
    read -p "SMTP Gebruikersnaam (e-mailadres): " MAIL_USERNAME
    read -p "SMTP Wachtwoord of app-wachtwoord: " MAIL_PASSWORD
    read -p "Standaard afzender (bijv. 'Bedrijfsnaam <noreply@example.com>'): " MAIL_SENDER
    
    # Update e-mail configuratie
    if [ -n "$MAIL_SERVER" ]; then
        sed -i "s|MAIL_SERVER=.*|MAIL_SERVER=${MAIL_SERVER}|g" "${TEMP_ENV}"
        sed -i "s|MAIL_PORT=.*|MAIL_PORT=${MAIL_PORT}|g" "${TEMP_ENV}"
        sed -i "s|MAIL_USERNAME=.*|MAIL_USERNAME=${MAIL_USERNAME}|g" "${TEMP_ENV}"
        sed -i "s|MAIL_PASSWORD=.*|MAIL_PASSWORD=${MAIL_PASSWORD}|g" "${TEMP_ENV}"
        sed -i "s|MAIL_DEFAULT_SENDER=.*|MAIL_DEFAULT_SENDER=${MAIL_SENDER}|g" "${TEMP_ENV}"
    fi
fi

# Vraag of gebruiker Mollie betalingen wil configureren
echo -e "${YELLOW}Wil je Mollie-betalingen configureren? Dit is optioneel.${NC}"
read -p "Mollie configureren? (j/n): " SETUP_MOLLIE
if [[ "$SETUP_MOLLIE" =~ ^[jJ] ]]; then
    read -p "Mollie API Key: " MOLLIE_API_KEY
    
    # Update Mollie configuratie
    if [ -n "$MOLLIE_API_KEY" ]; then
        sed -i "s|MOLLIE_API_KEY=.*|MOLLIE_API_KEY=${MOLLIE_API_KEY}|g" "${TEMP_ENV}"
    fi
fi

# Vraag of gebruiker Microsoft OAuth wil configureren
echo -e "${YELLOW}Wil je Microsoft OAuth configureren? Dit is optioneel.${NC}"
read -p "Microsoft OAuth configureren? (j/n): " SETUP_MICROSOFT
if [[ "$SETUP_MICROSOFT" =~ ^[jJ] ]]; then
    read -p "Microsoft Client ID: " MICROSOFT_CLIENT_ID
    read -p "Microsoft Client Secret: " MICROSOFT_CLIENT_SECRET
    
    # Update Microsoft configuratie
    if [ -n "$MICROSOFT_CLIENT_ID" ]; then
        sed -i "s|MICROSOFT_CLIENT_ID=.*|MICROSOFT_CLIENT_ID=${MICROSOFT_CLIENT_ID}|g" "${TEMP_ENV}"
        sed -i "s|MICROSOFT_CLIENT_SECRET=.*|MICROSOFT_CLIENT_SECRET=${MICROSOFT_CLIENT_SECRET}|g" "${TEMP_ENV}"
    fi
fi

# Kopieer het tijdelijke bestand naar de definitieve locatie
cp "${TEMP_ENV}" "${ENV_FILE}"
rm -f "${TEMP_ENV}"

echo -e "${GREEN}.env bestand succesvol aangemaakt: ${ENV_FILE}${NC}"

# Database configuratie voorbereiden voor docker-compose
# Controleer of docker-compose.yml bestaat en vervang database wachtwoord
if [ -f "${SCRIPT_DIR}/docker-compose.yml" ]; then
    echo -e "${YELLOW}docker-compose.yml gevonden, database wachtwoord bijwerken...${NC}"
    
    # Maak backup van docker-compose.yml
    cp "${SCRIPT_DIR}/docker-compose.yml" "${SCRIPT_DIR}/docker-compose.yml.bak"
    
    # Update database wachtwoord in docker-compose.yml
    if grep -q "POSTGRES_PASSWORD" "${SCRIPT_DIR}/docker-compose.yml"; then
        sed -i "s|POSTGRES_PASSWORD:.*|POSTGRES_PASSWORD: \"${DB_PASSWORD}\"|g" "${SCRIPT_DIR}/docker-compose.yml"
    else
        echo -e "${YELLOW}POSTGRES_PASSWORD niet gevonden in docker-compose.yml.${NC}"
        echo -e "${YELLOW}Voeg handmatig toe: POSTGRES_PASSWORD: \"${DB_PASSWORD}\"${NC}"
    fi
fi

echo -e "${GREEN}====================================================${NC}"
echo -e "${GREEN}Configuratie voltooid!${NC}"
echo -e "${GREEN}====================================================${NC}"
echo -e "${YELLOW}Database wachtwoord: ${DB_PASSWORD}${NC}"
echo -e "${YELLOW}Deze gegevens zijn opgeslagen in ${ENV_FILE}${NC}"
echo
echo -e "${YELLOW}Je kunt nu het systeem starten met:${NC}"
echo -e "${YELLOW}cd ${SCRIPT_DIR} && docker-compose up -d${NC}"