#!/bin/bash
# System update script voor de Flask applicatie server
# Voert systeem updates uit en herstart services indien nodig

set -e  # Stop bij fouten

echo "=== System update script voor Flask Applicatie Server ==="
echo "Datum: $(date)"
echo

echo ">> Stap 1: Pakketbronnen bijwerken..."
apt-get update

echo ">> Stap 2: Pakketten upgraden..."
apt-get upgrade -y

echo ">> Stap 3: Kernel en systeem pakketten upgraden (dist-upgrade)..."
apt-get dist-upgrade -y

echo ">> Stap 4: Niet-benodigde pakketten verwijderen..."
apt-get autoremove -y
apt-get autoclean

# Controleer of er een reboot nodig is
if [ -f /var/run/reboot-required ]; then
    echo ">> Systeem heeft een reboot nodig..."
    
    # Als Docker draait, zorg ervoor dat containers netjes stoppen
    if command -v docker &> /dev/null; then
        if systemctl is-active --quiet docker; then
            echo ">> Docker containers stoppen voor reboot..."
            
            # Als er een docker-compose.yml bestaat in het project directory
            if [ -f "/opt/invoice-app/docker-compose.yml" ]; then
                cd /opt/invoice-app
                docker compose down || true
            fi
        fi
    fi
    
    # Als Flask applicatie draait als systemd service
    if systemctl is-active --quiet flask-app; then
        echo ">> Flask applicatie stoppen voor reboot..."
        systemctl stop flask-app || true
    fi
    
    # Als PostgreSQL draait als systemd service
    if systemctl is-active --quiet postgresql; then
        echo ">> PostgreSQL netjes afsluiten voor reboot..."
        systemctl stop postgresql || true
    fi
    
    echo ">> Systeem rebooten over 10 seconden..."
    sleep 10
    reboot
else
    echo ">> Geen reboot nodig."
    
    # Herstart alleen services die mogelijk zijn bijgewerkt
    echo ">> Belangrijke services herstarten..."
    
    # Herstart Nginx als het actief is
    if systemctl is-active --quiet nginx; then
        echo ">> Nginx herstarten..."
        systemctl restart nginx || true
    fi
    
    # Als docker actief is, herstart containers
    if command -v docker &> /dev/null && systemctl is-active --quiet docker; then
        if [ -f "/opt/invoice-app/docker-compose.yml" ]; then
            echo ">> Docker containers herstarten..."
            cd /opt/invoice-app
            docker compose restart || true
        fi
    fi
    
    # Als Flask app draait als systemd service
    if systemctl is-active --quiet flask-app; then
        echo ">> Flask applicatie herstarten..."
        systemctl restart flask-app || true
    fi
fi

echo ">> Systeem update voltooid."