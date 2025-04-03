# Stapsgewijze Handleiding voor Deployment Scripts

Deze handleiding legt uit hoe je de deployment scripts kunt gebruiken om het Flask Boekhoud-/Facturatiesysteem te installeren op een eigen server.

## 1. Scripts Downloaden

### Optie 1: Clone de repository

Als je toegang hebt tot GitHub, kun je de volledige repository klonen:

```bash
git clone https://github.com/Jjustmee23/boekhoud.git
cd boekhoud/deployment
```

### Optie 2: Individuele scripts downloaden

Als je geen toegang hebt tot GitHub of alleen de deployment scripts nodig hebt:

```bash
mkdir -p deployment/scripts
cd deployment/scripts

# Download de basis installatiescripts
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/scripts/setup_flask_app.sh
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/scripts/direct_install.sh
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/scripts/update.sh
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/scripts/backup.sh
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/scripts/system_update.sh

# Download de documentatie
cd ..
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/README.md
curl -O https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/deployment/INSTALLATIE_CHECKLIST.md

# Maak de scripts uitvoerbaar
chmod +x scripts/*.sh
```

## 2. Gebruik van setup_deployment.sh

De `setup_deployment.sh` is een hulpscript om alle deployment bestanden op de juiste locatie te zetten:

```bash
sudo ./setup_deployment.sh
```

Dit script zal:
1. Een map `/opt/invoice-app` aanmaken (indien deze nog niet bestaat)
2. Alle installatiescripts naar die map kopiëren
3. De scripts uitvoerbaar maken

## 3. Keuze van Installatiemethode

Je hebt de keuze uit twee installatiemethoden:

### Docker-installatie (Aanbevolen)

Voor moderne servers met Docker ondersteuning:

```bash
cd /opt/invoice-app
sudo ./setup_flask_app.sh
```

De Docker-installatie:
- Installeert Docker en Docker Compose
- Configureert containers voor de applicatie en database
- Zorgt voor een geïsoleerde omgeving
- Maakt updates en migraties eenvoudiger

### Directe Installatie

Voor servers waar Docker niet beschikbaar is:

```bash
cd /opt/invoice-app
sudo ./direct_install.sh
```

De directe installatie:
- Installeert alle benodigde pakketten rechtstreeks op het systeem
- Configureert een virtuele Python-omgeving
- Stelt een Systemd-service in om de applicatie te draaien
- Kan lichtere systeemeisen hebben dan Docker

## 4. Onderhoudstaken

### Updates Uitvoeren

Om de applicatie bij te werken naar de nieuwste versie:

```bash
cd /opt/invoice-app
sudo ./update.sh
```

### Database Backups Maken

Om een backup van de database te maken:

```bash
cd /opt/invoice-app
sudo ./backup.sh
```

### Systeemupdates Uitvoeren

Voor algemene systeemonderhoud:

```bash
cd /opt/invoice-app
sudo ./system_update.sh
```

## 5. Automatisch Onderhoud

Je kunt cron jobs instellen voor automatisch onderhoud:

```bash
# Open de crontab editor
sudo crontab -e

# Voeg de volgende regels toe:
# Dagelijkse backup om 2:00 's nachts
0 2 * * * /opt/invoice-app/backup.sh

# Wekelijkse systeemupdates op zondag om 3:00 's nachts
0 3 * * 0 /opt/invoice-app/system_update.sh
```

## 6. Nuttige Commando's

### Docker Installatie

```bash
# Containers controleren
docker compose -f /opt/invoice-app/docker-compose.yml ps

# Logs bekijken
docker compose -f /opt/invoice-app/docker-compose.yml logs -f

# Container herstarten
docker compose -f /opt/invoice-app/docker-compose.yml restart web
```

### Directe Installatie

```bash
# Service status controleren
sudo systemctl status flask-app

# Service herstarten
sudo systemctl restart flask-app

# Logs bekijken
sudo journalctl -u flask-app -f
```

## 7. Troubleshooting

Als je problemen ondervindt, controleer dan:

1. Logs van de applicatie (zie commando's hierboven)
2. Nginx logs: `sudo tail -f /var/log/nginx/error.log`
3. Database verbinding: 
   - Docker: `docker compose -f /opt/invoice-app/docker-compose.yml exec db psql -U postgres -c "SELECT version();"`
   - Direct: `sudo -u postgres psql -c "SELECT version();"`
4. Firewall status: `sudo ufw status`