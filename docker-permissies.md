# Docker Permissie Fixes

## Probleem

Bij het opstarten van de Docker container was er een probleem waarbij de gebruiker in de container (appuser) geen schrijfrechten had voor het bestand `/app/logs/app.log`. Dit gebeurt vaak wanneer een host-directory (zoals `./logs`) als volume wordt gekoppeld, waarbij de permissies van de host-directory de permissies in de container overschrijven.

## Oplossing

De volgende aanpassingen zijn gedaan om het permissieprobleem op te lossen:

### 1. Dockerfile wijzigingen

- Permissies van `/app/logs` en `/app/static/uploads` aangepast naar `777` (rwx voor owner, group, en others)
- `USER appuser` commando verwijderd zodat we als root kunnen starten
- `gosu` en `sudo` toegevoegd aan de geïnstalleerde pakketten
- Een Docker entrypoint script toegevoegd dat:
  - Als root draait bij het opstarten
  - De juiste permissies instelt voor de logbestanden en directories
  - Daarna switcht naar de appuser voor het draaien van de applicatie

### 2. docker-compose.yml wijzigingen

- Volumes met expliciete `rw` (read-write) permissies gedefinieerd
- `user` instelling verwijderd om het entrypoint script te laten werken

### 3. Toegevoegde bestanden

- `docker-entrypoint.sh`: Script voor het instellen van de juiste rechten
- `check-logs.sh`: Script voor het controleren van logdirectories en -rechten

## Hoe het werkt

1. Bij het opstarten van de container, draait deze als root
2. Het entrypoint script:
   - Maakt de logs/ en static/uploads/ directories aan als deze nog niet bestaan
   - Stelt de correcte permissies in (777) 
   - Wijzigt de eigenaar naar appuser:appuser
   - Schakelt dan over naar de appuser (via gosu) om de applicatie te starten
3. De applicatie draait als appuser en heeft nu volledige schrijftoegang tot de gedeelde volumes

## Testen

Je kunt de nieuwe configuratie testen door:

```bash
docker-compose build
docker-compose up -d
docker-compose exec web ./check-logs.sh
```

Het check-logs.sh script zal aangeven of de logbestanden bestaan en of de appuser daar schrijfrechten toe heeft.

## Aandachtspunten

- De permissie `777` is zeer ruim en mogelijk niet ideaal voor productieomgevingen
- Als alternatief zou je kunnen overwegen om:
  1. Een specifieke gebruikersgroep aan te maken en de container en host-gebruiker in die groep te plaatsen
  2. setgid bits te gebruiken op de gedeelde directories
  3. Een docker-compose plugin voor volume permissies te gebruiken