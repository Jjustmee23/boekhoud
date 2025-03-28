#!/bin/sh
set -e

# Controleer of we als root draaien (voor rechten)
if [ "$(id -u)" = "0" ]; then
  # Maak logbestanden aan als deze niet bestaan
  mkdir -p /app/logs
  touch /app/logs/app.log /app/logs/app.json.log /app/logs/error.log

  # Zet juiste rechten op logbestanden en directories
  chmod -R 777 /app/logs
  chown -R appuser:appuser /app/logs

  # Maak static/uploads directory als deze niet bestaat
  mkdir -p /app/static/uploads/subscriptions
  chmod -R 777 /app/static/uploads
  chown -R appuser:appuser /app/static/uploads
  
  # Voer database migraties uit als appuser
  echo "Voer database migraties uit..."
  gosu appuser python /app/run_migrations.py
  
  # Voer het commando uit als appuser
  echo "Rechten ingesteld, start applicatie als appuser..."
  exec gosu appuser "$@"
else
  # Als we niet als root draaien, direct uitvoeren
  echo "Start applicatie direct..."
  
  # Voer database migraties uit
  echo "Voer database migraties uit..."
  python /app/run_migrations.py
  
  exec "$@"
fi