#!/bin/bash
# Script om een dhparam.pem bestand te genereren

# Controleer of we in de nginx map zijn
if [ ! -d "ssl" ]; then
  mkdir -p ssl
fi

# Genereer een sterke 4096-bit dhparam bestand
echo "Genereren van dhparam.pem bestand (dit kan enkele minuten duren)..."
openssl dhparam -out ssl/dhparam.pem 4096

echo "dhparam.pem bestand succesvol gegenereerd in nginx/ssl/dhparam.pem"