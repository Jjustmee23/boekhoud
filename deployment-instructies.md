# Deployment Instructies

Dit document beschrijft hoe je de facturatie-applicatie kunt implementeren en bijwerken op je eigen privéserver.

## Vereisten

- Een server met Docker en Docker Compose geïnstalleerd
- SSH-toegang tot de server
- Git geïnstalleerd op je lokale machine
- Basiskennis van de terminal/commandoregel

## Eerste implementatie

### 1. Servervoorbereiding

Zorg ervoor dat Docker en Docker Compose zijn geïnstalleerd op je server:

```bash
# Docker installeren
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose installeren
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.6/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Applicatie klonen

Kopieer de applicatie naar je server:

```bash
# Maak een directory voor de applicatie
mkdir -p /opt/facturatie-app

# Kopieer met het deploy script
./deploy.sh user@jouw-server.nl jouw-gebruiker /opt/facturatie-app
```

### 3. Configuratie

Maak een `.env` bestand op je server in de `/opt/facturatie-app` directory:

```bash
# SSH naar je server
ssh user@jouw-server.nl

# Ga naar de app directory
cd /opt/facturatie-app

# Maak het .env bestand op basis van het voorbeeld
cp .env.example .env

# Bewerk het .env bestand om je instellingen aan te passen
nano .env
```

Vul alle benodigde omgevingsvariabelen in, zoals:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `SESSION_SECRET` (genereer een sterke random string)
- Email instellingen
- Mollie API-sleutels

### 4. Starten van de applicatie

Start de applicatie voor de eerste keer:

```bash
cd /opt/facturatie-app
docker-compose up -d
```

De applicatie is nu toegankelijk via `http://jouw-server.nl:5000`

## Updates uitvoeren

### Gebruik het deploy script

Het eenvoudigste is om het `deploy.sh` script te gebruiken om updates uit te voeren:

```bash
# Vanaf je lokale ontwikkelomgeving
./deploy.sh user@jouw-server.nl jouw-gebruiker /opt/facturatie-app
```

Dit script zal:
1. Een database backup maken voordat wijzigingen worden doorgevoerd
2. De code kopiëren naar je server
3. De containers opnieuw bouwen en opstarten
4. Controleren op eventuele fouten in de logs

### Handmatig updaten

Als je handmatig wilt updaten, volg dan deze stappen:

1. SSH naar je server:
   ```bash
   ssh user@jouw-server.nl
   ```

2. Ga naar de applicatie directory:
   ```bash
   cd /opt/facturatie-app
   ```

3. Maak een database backup:
   ```bash
   docker-compose exec db pg_dump -U postgres facturatie > /tmp/backup_$(date +%Y%m%d_%H%M%S).sql
   ```

4. Pull de laatste wijzigingen (als je Git gebruikt):
   ```bash
   git pull origin main
   ```

5. Build en herstart de web container:
   ```bash
   docker-compose build web
   docker-compose up -d --no-deps web
   ```

6. Controleer de logs op fouten:
   ```bash
   docker-compose logs --tail=50 web
   ```

## Database beheer

### Backup maken

Maak een volledige backup van de database:

```bash
cd /opt/facturatie-app
./backup-database.sh
```

### Backup herstellen

Herstel een eerdere database backup:

```bash
cd /opt/facturatie-app
./restore-database.sh /pad/naar/backup.sql
```

## Belangrijk: De database wordt NIET verwijderd bij updates

De Docker setup is zo geconfigureerd dat de database gegevens worden opgeslagen in een named volume (`facturatie_postgres_data`). Dit betekent dat de database behouden blijft, zelfs wanneer je de containers opnieuw bouwt of bijwerkt.

De database wordt alleen verwijderd als je expliciet één van deze acties uitvoert:
1. `docker-compose down -v` (verwijdert alle volumes)
2. `docker volume rm facturatie_postgres_data` (verwijdert specifiek het database volume)

## Troubleshooting

### De applicatie start niet op

Controleer de logs voor fouten:

```bash
docker-compose logs web
```

### Database connectie problemen

Controleer of de database container draait:

```bash
docker-compose ps db
```

Controleer de database logs:

```bash
docker-compose logs db
```

## Contact

Als je problemen ondervindt met de deployment die je niet kunt oplossen, neem dan contact op met de ontwikkelaar/beheerder van deze applicatie.