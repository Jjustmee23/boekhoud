#!/bin/bash
# One-command installatie script voor Boekhoud Systeem
# Dit script downloadt en voert het ubuntu-setup.sh script uit

set -e  # Script stopt bij een fout

# Kleuren voor output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # Geen kleur

echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Boekhoud Systeem - One-Command Install${NC}"
echo -e "${YELLOW}====================================================${NC}"

# Controleer of script als root wordt uitgevoerd
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Dit script moet worden uitgevoerd als root (gebruik sudo).${NC}"
    exit 1
fi

# Controleer of het systeem Ubuntu is
if ! grep -q "Ubuntu" /etc/os-release; then
    echo -e "${RED}Dit script is ontworpen voor Ubuntu. Andere systemen worden niet officieel ondersteund.${NC}"
    echo -e "${RED}Huidige OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d '"' -f 2)${NC}"
    read -p "Wil je toch doorgaan? (j/n): " continue_anyway
    if [[ "$continue_anyway" != "j" && "$continue_anyway" != "J" ]]; then
        echo -e "${YELLOW}Installatie geannuleerd.${NC}"
        exit 1
    fi
fi

# Controleer internetverbinding
echo -e "${YELLOW}Internetverbinding controleren...${NC}"
if ! ping -c 1 google.com &> /dev/null; then
    echo -e "${RED}Geen internetverbinding. Controleer je netwerk.${NC}"
    exit 1
fi

# Installeer wget als het nog niet geïnstalleerd is
if ! command -v wget &> /dev/null; then
    echo -e "${YELLOW}wget installeren...${NC}"
    apt-get update && apt-get install -y wget || {
        echo -e "${RED}Kan wget niet installeren. Installatie afgebroken.${NC}"
        exit 1
    }
fi

# Maak tijdelijke map voor installatie
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo -e "${YELLOW}Installatiescript downloaden...${NC}"
wget -q https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/ubuntu-setup.sh -O "${TEMP_DIR}/ubuntu-setup.sh" || {
    echo -e "${RED}Kan installatiescript niet downloaden. Controleer de URL.${NC}"
    exit 1
}

# Maak script uitvoerbaar
chmod +x "${TEMP_DIR}/ubuntu-setup.sh"

echo -e "${YELLOW}Voordat we beginnen:${NC}"
echo -e "${YELLOW}- Het installatiescript vraagt je waar je de applicatie wilt installeren${NC}"
echo -e "${YELLOW}- Je kunt optioneel een domeinnaam opgeven voor SSL-configuratie${NC}"
echo -e "${YELLOW}- Je kunt optioneel een GitHub repository URL opgeven${NC}"
echo

# Wacht op bevestiging
read -p "Druk op Enter om door te gaan met de installatie..."

# Voer het installatieproces uit
echo -e "${YELLOW}Installatie starten...${NC}"
"${TEMP_DIR}/ubuntu-setup.sh"

# Check of installatie succesvol was
if [ $? -eq 0 ]; then
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${GREEN}One-command installatie voltooid!${NC}"
    echo -e "${GREEN}====================================================${NC}"
    echo -e "${YELLOW}De applicatie zou nu beschikbaar moeten zijn op het opgegeven domein of IP-adres.${NC}"
    echo -e "${YELLOW}Raadpleeg INSTALLATIE.md voor meer informatie over beheer en configuratie.${NC}"
else
    echo -e "${RED}====================================================${NC}"
    echo -e "${RED}Er is een fout opgetreden tijdens de installatie.${NC}"
    echo -e "${RED}====================================================${NC}"
    echo -e "${YELLOW}Probeer het volgende:${NC}"
    echo -e "${YELLOW}1. Controleer de foutmeldingen hierboven${NC}"
    echo -e "${YELLOW}2. Controleer of je systeem voldoet aan de minimale vereisten${NC}"
    echo -e "${YELLOW}3. Probeer de handmatige installatie-instructies in INSTALLATIE.md${NC}"
fi