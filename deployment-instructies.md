# Deployment Instructies

Deze documentatie bevat gedetailleerde instructies voor het installeren, configureren en onderhouden van het facturatie systeem. De instructies zijn geschreven voor Ubuntu 22.04 LTS servers maar kunnen ook op andere Linux-distributies werken met kleine aanpassingen.

## Inhoudsopgave

1. [Systeemvereisten](#systeemvereisten)
2. [Installatie](#installatie)
   - [Automatische installatie](#automatische-installatie)
   - [Handmatige installatie](#handmatige-installatie)
3. [Configuratie](#configuratie)
4. [Applicatie starten](#applicatie-starten)
5. [Updates](#updates)
6. [Backup en herstel](#backup-en-herstel)
7. [Automatische backups](#automatische-backups)
8. [Probleemoplossing](#probleemoplossing)
9. [Beveiligingstips](#beveiligingstips)

## Systeemvereisten

- Ubuntu 22.04 LTS (aanbevolen)
- Minimaal 2 GB RAM
- 10 GB vrije schijfruimte
- Internetverbinding
- Sudo/root toegang
- Open poorten:
  - 80/443 (voor HTTP/HTTPS)
  - 5000 (voor ontwikkeling)

## Installatie

### Automatische installatie

De snelste manier om het systeem te installeren is met één van de volgende scripts:

#### One-command installatie

```bash
wget -O install.sh https://raw.githubusercontent.com/jouw-gebruikersnaam/facturatie-systeem/main/one-command-install.sh && chmod +x install.sh && sudo ./install.sh
```

#### Interactieve installatie

```bash
wget -O setup-ubuntu.sh https://raw.githubusercontent.com/jouw-gebruikersnaam/facturatie-systeem/main/setup-ubuntu.sh && chmod +x setup-ubuntu.sh && sudo ./setup-ubuntu.sh
```

### Handmatige installatie

Voor meer controle over het installatieproces, volg deze stappen:

1. **Benodigde software installeren**

   ```bash
   sudo apt update
   sudo apt install -y git docker.io docker-compose python3-pip curl postgresql-client
   ```

2. **Docker starten**

   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

3. **Repository klonen**

   ```bash
   sudo mkdir -p /var/www/facturatie
   sudo git clone https://github.com/jouw-gebruikersnaam/facturatie-systeem.git /var/www/facturatie
   ```

4. **Rechten instellen**

   ```bash
   sudo chown -R $USER:$USER /var/www/facturatie
   cd /var/www/facturatie
   chmod +x *.sh
   ```

5. **Configuratiebestand maken**

   ```bash
   cp .env.example .env
   nano .env  # Bewerk de configuratie naar wens
   ```

## Configuratie

Het belangrijkste configuratiebestand is `.env`. De volgende variabelen zijn essentieel:

- `DATABASE_URL`: Database verbinding string (postgresql://user:pass@host:port/dbname)
- `FLASK_SECRET_KEY`: Random geheim voor Flask sessies
- `MOLLIE_API_KEY`: API sleutel voor Mollie betalingen
- `MICROSOFT_CLIENT_ID` en `MICROSOFT_CLIENT_SECRET`: Voor Microsoft 365 integratie

Voorbeeld configuratie:

```
DATABASE_URL=postgresql://postgres:password@db:5432/facturatie
FLASK_SECRET_KEY=your-secret-key-here
MOLLIE_API_KEY=test_yourapikey
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret
MICROSOFT_REDIRECT_URI=https://yourdomain.com/ms-auth-callback
```

## Applicatie starten

Na installatie en configuratie, start de applicatie:

```bash
cd /var/www/facturatie
docker-compose up -d
```

De applicatie is nu beschikbaar op:
- Ontwikkeling: http://localhost:5000
- Productie: https://yourdomain.com (na configuratie van reverse proxy)

## Updates

Om de applicatie te updaten naar de nieuwste versie:

```bash
cd /var/www/facturatie
./deploy.sh
```

Het deploy script zal:
1. Een backup maken van de database
2. De nieuwste code ophalen van de repository
3. Docker containers herbouwen en herstarten
4. Database migraties uitvoeren

## Backup en herstel

### Database backup maken

```bash
cd /var/www/facturatie
./backup-database.sh
```

Backups worden opgeslagen in de `db_backups` map met datum en tijd in de bestandsnaam.

### Database herstellen

```bash
cd /var/www/facturatie
./restore-database.sh db_backups/backup-2025-03-31.sql.gz
```

## Automatische backups

Stel automatische dagelijkse, wekelijkse of maandelijkse backups in:

```bash
cd /var/www/facturatie
./schedule-backups.sh
```

Volg de interactieve prompts om de backup frequentie en retentieperiode in te stellen.

## Probleemoplossing

### Logs bekijken

```bash
cd /var/www/facturatie
docker-compose logs -f web
```

### Algemene problemen

**Probleem**: Docker containers starten niet
**Oplossing**: Controleer de logs en zorg dat alle poorten beschikbaar zijn

```bash
docker-compose logs
sudo lsof -i :5000  # Controleer of poort 5000 in gebruik is
```

**Probleem**: Database migratie fouten
**Oplossing**: Probeer de migratie handmatig uit te voeren

```bash
cd /var/www/facturatie
docker-compose exec web python run_migrations.py
```

**Probleem**: "Permission denied" fouten
**Oplossing**: Controleer bestandsrechten en Docker permissies

```bash
sudo chown -R $USER:$USER /var/www/facturatie
sudo usermod -aG docker $USER  # Log uit en weer in na deze commando
```

## Beveiligingstips

1. **Firewall instellen**:

   ```bash
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   sudo ufw enable
   ```

2. **Fail2ban installeren**:

   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```

3. **HTTPS instellen** met Let's Encrypt:

   ```bash
   sudo apt install -y certbot
   sudo certbot certonly --standalone -d yourdomain.com
   ```

4. **Regelmatige updates**:

   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

5. **Backups op externe locatie**:
   Configureer een script om backups naar een externe locatie te kopiëren (bijv. AWS S3, Google Cloud Storage).