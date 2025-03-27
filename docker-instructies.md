# Docker Instructies voor Facturatie & Boekhouding Systeem

## Vereisten

- Docker geïnstalleerd op uw systeem
- Docker Compose geïnstalleerd op uw systeem

## Opzetten en starten

1. Zorg ervoor dat u zich in de hoofdmap van het project bevindt waar `docker-compose.yml` staat

2. Start de containers:

```bash
docker-compose up -d
```

3. De applicatie is nu beschikbaar op http://localhost:5000

## Database gegevens

- PostgreSQL draait op: localhost:5432
- Database naam: facturatie
- Gebruikersnaam: postgres
- Wachtwoord: postgres

## Beheer

### Services stoppen

```bash
docker-compose down
```

### Logbestanden bekijken

```bash
docker-compose logs -f web
```

### Container opnieuw bouwen na wijzigingen

```bash
docker-compose build web
docker-compose up -d
```

## Geüploade bestanden

De map `static/uploads` wordt gemount als een volume, zodat geüploade facturen bewaard blijven, zelfs als u de containers opnieuw opbouwt of verwijdert.

## Beveiliging

Voor productiegebruik:

1. Wijzig de wachtwoorden en sleutels in `docker-compose.yml`
2. Overweeg een reverse proxy zoals Nginx met SSL te gebruiken
3. Beperk netwerktoegang tot alleen noodzakelijke poorten

## Problemen oplossen

### Database verbindingsproblemen

Als de applicatie niet kan verbinden met de database, controleer:

```bash
docker-compose ps
```

Zorg ervoor dat zowel de 'web' als 'db' services draaien.

### Permissie problemen voor geüploade bestanden

Als er problemen zijn met het uploaden van bestanden, controleer de permissies van de 'static/uploads' directory:

```bash
sudo chmod -R 777 static/uploads
```

### Container opnieuw starten

```bash
docker-compose restart web
```