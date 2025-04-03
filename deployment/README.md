# Installatie Handleiding voor Flask Facturatiesysteem

Deze handleiding helpt je bij het installeren van het Flask facturatiesysteem op je eigen Ubuntu 22.04 server. Er zijn twee installatiemethoden beschikbaar:

1. Docker-installatie (aanbevolen): Eenvoudiger te beheren en te upgraden
2. Directe installatie: Voor servers waar Docker niet beschikbaar is

## Vereisten

Voordat je begint, zorg ervoor dat je beschikt over:

1. Een schone Ubuntu 22.04 server met root-toegang
2. Een domeinnaam die naar je server IP-adres verwijst
3. Basiskennis van de Linux-commandoregel

## Optie 1: Docker Installatie (Aanbevolen)

### Stap 1: Scripts downloaden

Maak verbinding met je server via SSH:

```bash
ssh root@je-server-ip
```

Download de installatiescripts:

```bash
mkdir -p /tmp/installer
cd /tmp/installer
curl -O https://raw.githubusercontent.com/jouw-repository/jouw-branch/setup_flask_app.sh
curl -O https://raw.githubusercontent.com/jouw-repository/jouw-branch/update.sh
curl -O https://raw.githubusercontent.com/jouw-repository/jouw-branch/backup.sh
chmod +x setup_flask_app.sh update.sh backup.sh
```

### Stap 2: Voer het installatiescript uit

```bash
sudo ./setup_flask_app.sh
```

Het script zal je door de volgende stappen leiden:
- Docker en Docker Compose installeren
- Nginx en Certbot installeren
- Firewall configureren
- Repository van je applicatie klonen
- Docker containers opzetten en starten
- Nginx en SSL configureren
- Een admin gebruiker aanmaken

### Stap 3: Toegang tot je applicatie

Na voltooiing is je applicatie beschikbaar op het domein dat je hebt opgegeven tijdens de installatie.

## Optie 2: Directe Installatie (Zonder Docker)

### Stap 1: Scripts downloaden

Maak verbinding met je server via SSH:

```bash
ssh root@je-server-ip
```

Download de installatiescripts:

```bash
mkdir -p /tmp/installer
cd /tmp/installer
curl -O https://raw.githubusercontent.com/jouw-repository/jouw-branch/direct_install.sh
curl -O https://raw.githubusercontent.com/jouw-repository/jouw-branch/update.sh
curl -O https://raw.githubusercontent.com/jouw-repository/jouw-branch/backup.sh
chmod +x direct_install.sh update.sh backup.sh
```

### Stap 2: Voer het directe installatiescript uit

```bash
sudo ./direct_install.sh
```

Het script zal je door de volgende stappen leiden:
- Systeem pakketten installeren
- PostgreSQL database opzetten
- Repository klonen en virtuele omgeving instellen
- Systemd service configureren
- Nginx als reverse proxy instellen
- Firewall configureren
- Een admin gebruiker aanmaken

### Stap 3: Toegang tot je applicatie

Na voltooiing is je applicatie beschikbaar op het domein dat je hebt opgegeven tijdens de installatie.

## Updates en Backups

### Updates uitvoeren

Om je applicatie te updaten naar de laatste versie:

```bash
cd /opt/invoice-app
sudo ./update.sh
```

### Backups maken

Om een backup van je database te maken:

```bash
cd /opt/invoice-app
sudo ./backup.sh
```

Backups worden opgeslagen in de `/opt/invoice-app/backups` map.

### Een backup herstellen

Voor Docker installatie:
```bash
# Decomprimeer de backup file (indien gecomprimeerd)
gunzip /opt/invoice-app/backups/db_backup_20230101_120000.sql.gz

# Herstel de database
cat /opt/invoice-app/backups/db_backup_20230101_120000.sql | docker compose exec -T db psql -U postgres invoicing
```

Voor directe installatie:
```bash
# Decomprimeer de backup file (indien gecomprimeerd)
gunzip /opt/invoice-app/backups/db_backup_20230101_120000.sql.gz

# Herstel de database
sudo -u postgres psql invoicing < /opt/invoice-app/backups/db_backup_20230101_120000.sql
```

## Probleemoplossing

### Docker Installatie

Logs bekijken:
```bash
cd /opt/invoice-app
docker compose logs -f
```

Services controleren:
```bash
docker compose ps
```

### Directe Installatie

Applicatie status controleren:
```bash
sudo systemctl status flask-app
```

Logs bekijken:
```bash
sudo journalctl -u flask-app
```

### Algemene Problemen

1. **Applicatie niet bereikbaar**: Controleer de firewall en Nginx configuratie
   ```bash
   sudo ufw status
   sudo nginx -t
   sudo systemctl status nginx
   ```

2. **Database problemen**: Controleer de database verbinding
   ```bash
   # Voor Docker
   docker compose exec db psql -U postgres -c "SELECT version();"
   
   # Voor directe installatie
   sudo -u postgres psql -c "SELECT version();"
   ```

3. **SSL problemen**: Controleer Certbot logs
   ```bash
   sudo systemctl status certbot.timer
   sudo certbot renew --dry-run
   ```