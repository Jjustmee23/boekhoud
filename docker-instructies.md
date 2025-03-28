# Docker Instructies voor Facturatie & Boekhouding Systeem

## Vereisten

- Docker geïnstalleerd op uw systeem (versie 19.03.0+)
- Docker Compose geïnstalleerd op uw systeem (versie 1.27.0+)

## Opzetten en starten

1. Zorg ervoor dat u zich in de hoofdmap van het project bevindt waar `docker-compose.yml` staat

2. Start de containers:

```bash
# Aanbevolen voor ontwikkeling
docker-compose up -d

# Of met het bouwen van de images (na wijzigingen)
docker-compose up -d --build
```

3. De applicatie is nu beschikbaar op http://localhost:5000

## Docker Compose Commando

> **Let op**: Vanaf Docker Compose V2 is het aanbevolen format `docker compose` (zonder streepje) in plaats van `docker-compose`. Gebruik het format dat past bij uw Docker-versie.

## Database gegevens

- PostgreSQL draait op: localhost:5432
- Database naam: facturatie
- Gebruikersnaam: postgres
- Wachtwoord: postgres

## Beheer

### Services stoppen

```bash
docker compose down
```

### Services stoppen en volumes verwijderen (wist alle data)

```bash
docker compose down -v
```

### Logbestanden bekijken

```bash
# Alle logs bekijken
docker compose logs -f

# Alleen logs van de webapplicatie
docker compose logs -f web

# Alleen logs van de database
docker compose logs -f db
```

### Container opnieuw bouwen na wijzigingen

```bash
docker compose build web
docker compose up -d
```

### Containers en hun status bekijken

```bash
docker compose ps
```

### Uitvoering van gezondheidscontroles bekijken

```bash
docker compose ps
docker inspect --format "{{json .State.Health }}" facturatie-web-1 | jq
```

## Geüploade bestanden

De map `static/uploads` wordt gemount als een volume, zodat geüploade facturen bewaard blijven, zelfs als u de containers opnieuw opbouwt of verwijdert.

## Beveiliging

Voor productiegebruik:

1. Wijzig de wachtwoorden en sleutels in een `.env` bestand (niet in `docker-compose.yml`):
   ```
   # Voorbeeld .env bestand
   POSTGRES_PASSWORD=sterk_wachtwoord_hier
   SESSION_SECRET=lang_random_sessie_sleutel_hier
   MOLLIE_API_KEY=uw_mollie_api_sleutel
   MOLLIE_WEBHOOK_URL=https://uw-domein.nl/subscription/webhook
   MOLLIE_REDIRECT_URL=https://uw-domein.nl/subscription/success
   ```

2. Voeg in productie het volgende toe aan docker-compose.yml:
   ```yaml
   web:
     env_file:
       - .env
   db:
     env_file:
       - .env
   ```

3. Zorg ervoor dat gevoelige gegevens zoals Mollie API-sleutels nooit worden opgeslagen in publieke repository's of Docker images. Gebruik altijd omgevingsvariabelen of secrets management.

4. Gebruik voor productie een reverse proxy zoals Traefik of Nginx met SSL:
   ```yaml
   # Voorbeeld voor Traefik labels in docker-compose.yml
   web:
     labels:
       - "traefik.enable=true"
       - "traefik.http.routers.facturatie.rule=Host(`facturatie.uwdomein.nl`)"
       - "traefik.http.routers.facturatie.entrypoints=websecure"
       - "traefik.http.routers.facturatie.tls.certresolver=myresolver"
   ```

5. Beperk netwerktoegang tot alleen noodzakelijke poorten

## Problemen oplossen

### Database verbindingsproblemen

Als de applicatie niet kan verbinden met de database, controleer:

```bash
# Bekijk de status van containers
docker compose ps

# Controleer de gezondheidscontrole van de database
docker inspect --format "{{json .State.Health }}" facturatie-db-1 | jq

# Bekijk de database logs
docker compose logs db
```

Zorg ervoor dat zowel de 'web' als 'db' services draaien en gezond zijn.

### Mollie API Problemen

Als betalingen via Mollie niet werken:

```bash
# Controleer de logs van de webapplicatie voor Mollie API-fouten
docker compose logs -f web | grep Mollie

# Zorg dat uw MOLLIE_API_KEY correct is ingesteld in .env

# Controleer of uw webhook URL publiekelijk toegankelijk is
# De webhook URL moet vanaf het internet bereikbaar zijn, niet alleen lokaal
```

Zorg er voor de productie-omgeving voor dat uw webhook URL (zoals ingesteld in MOLLIE_WEBHOOK_URL) publiekelijk toegankelijk is, zodat Mollie betaalstatusupdates kan sturen. Voor tests kunt u een service zoals ngrok gebruiken.

### Permissie problemen voor geüploade bestanden

Als er problemen zijn met het uploaden van bestanden, controleer de permissies van de 'static/uploads' directory:

```bash
# Geef volledige toegang tot de uploads map
sudo chmod -R 777 static/uploads

# Of gebruik een betere benadering met gebruiker en groep
sudo chown -R 1000:1000 static/uploads
sudo chmod -R 755 static/uploads
```

### Container opnieuw starten

```bash
docker compose restart web
```

### Volledig systeem opnieuw opzetten (herstart met schone database)

```bash
# Stop en verwijder alle containers, networks, volumes, en images
docker compose down -v --remove-orphans
docker compose up -d --build
```

## Systeembronnen controleren

```bash
# Bekijk resource gebruik
docker stats
```