#!/bin/bash
# Script om te controleren of logbestanden bestaan en toegankelijk zijn

# Locaties
LOG_DIR="/app/logs"
LOG_FILE="$LOG_DIR/app.log"
JSON_LOG_FILE="$LOG_DIR/app.json.log"
ERROR_LOG_FILE="$LOG_DIR/error.log"

echo "Controle van logbestanden en rechten in Docker container"
echo "--------------------------------------------------------"

# Controleer of het logdirectory bestaat
if [ -d "$LOG_DIR" ]; then
  echo "✓ Logdirectory bestaat: $LOG_DIR"
  
  # Controleer permissies
  PERMS=$(stat -c "%a" "$LOG_DIR")
  OWNER=$(stat -c "%U:%G" "$LOG_DIR")
  
  echo "  - Permissies: $PERMS"
  echo "  - Eigenaar: $OWNER"
  
  # Controleer of de appuser toegang heeft
  if su -c "test -w $LOG_DIR" appuser; then
    echo "✓ appuser heeft schrijfrechten voor het logdirectory"
  else
    echo "✗ appuser heeft GEEN schrijfrechten voor het logdirectory"
  fi
else
  echo "✗ Logdirectory bestaat NIET: $LOG_DIR"
  exit 1
fi

# Controleer individuele logbestanden
for LOG in "$LOG_FILE" "$JSON_LOG_FILE" "$ERROR_LOG_FILE"; do
  if [ -f "$LOG" ]; then
    echo "✓ Logbestand bestaat: $LOG"
    
    # Controleer permissies
    PERMS=$(stat -c "%a" "$LOG")
    OWNER=$(stat -c "%U:%G" "$LOG")
    
    echo "  - Permissies: $PERMS"
    echo "  - Eigenaar: $OWNER"
    
    # Controleer of de appuser toegang heeft
    if su -c "test -w $LOG" appuser; then
      echo "✓ appuser heeft schrijfrechten voor het logbestand"
    else
      echo "✗ appuser heeft GEEN schrijfrechten voor het logbestand"
    fi
  else
    echo "✗ Logbestand bestaat NIET: $LOG"
  fi
done

# Probeer een test bestand aan te maken als appuser
echo "Testbestand aanmaken als appuser..."
if su -c "touch $LOG_DIR/test_write_permissions.tmp" appuser; then
  echo "✓ Testbestand succesvol aangemaakt"
  su -c "rm $LOG_DIR/test_write_permissions.tmp" appuser
else
  echo "✗ Kon GEEN testbestand aanmaken als appuser"
fi

echo "--------------------------------------------------------"
echo "Controlescript voltooid"