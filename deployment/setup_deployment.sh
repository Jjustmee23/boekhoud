#!/bin/bash
# Script voor het opzetten van de deployment omgeving
# Dit script kopieert alle deployment bestanden naar de juiste locaties

set -e  # Stop bij fouten

# Directories
TARGET_DIR="/opt/invoice-app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Deploymnet Setup ==="
echo "Datum: $(date)"
echo

# Controleer of het script als root draait
if [ "$EUID" -ne 0 ]; then
    echo "Dit script moet als root of via sudo worden uitgevoerd."
    exit 1
fi

# Maak de doelmap aan als deze nog niet bestaat
mkdir -p "$TARGET_DIR"

# Kopieer de deployment scripts
echo ">> Deployment scripts kopiëren..."
cp -v "$SCRIPT_DIR/scripts/"*.sh "$TARGET_DIR/"
chmod +x "$TARGET_DIR/"*.sh

# Kopieer de documentatie
echo ">> Documentatie kopiëren..."
cp -v "$SCRIPT_DIR/README.md" "$TARGET_DIR/INSTALLATIE.md"
cp -v "$SCRIPT_DIR/INSTALLATIE_CHECKLIST.md" "$TARGET_DIR/INSTALLATIE_CHECKLIST.md"

echo ">> Deployment setup voltooid."
echo "Gebruik nu één van de volgende scripts:"
echo "  - Voor Docker installatie: $TARGET_DIR/setup_flask_app.sh"
echo "  - Voor directe installatie: $TARGET_DIR/direct_install.sh"