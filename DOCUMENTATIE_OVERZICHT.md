# Boekhoud Systeem - Documentatie Overzicht

Dit document biedt een overzicht van alle beschikbare documentatie voor het Boekhoud Systeem.

## Installatie en Setup

| Document | Beschrijving |
|----------|-------------|
| [INSTALLATIE.md](INSTALLATIE.md) | Complete installatie handleiding met gedetailleerde uitleg en opties |
| [UBUNTU_INSTALLATIE.md](UBUNTU_INSTALLATIE.md) | Verkorte installatiegids speciaal voor Ubuntu 22.04 |
| [SNELLE_INSTALLATIE.md](SNELLE_INSTALLATIE.md) | Beknopte stapsgewijze installatie-instructies |
| [DEPLOYMENT_STAPPEN.md](DEPLOYMENT_STAPPEN.md) | Gedetailleerde deployment handleiding met uitgebreide instructies |
| [one-command-install.sh](one-command-install.sh) | Script voor automatische installatie in één commando |
| [ubuntu-setup.sh](ubuntu-setup.sh) | Script voor automatische setup op Ubuntu 22.04 |

## Dagelijks Beheer

| Document | Beschrijving |
|----------|-------------|
| [DOCKER_BEHEER.md](DOCKER_BEHEER.md) | Handleiding voor het beheren van Docker containers |
| [database-beheer.md](database-beheer.md) | Informatie over database persistentie en backup procedures |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Gids voor het oplossen van veelvoorkomende problemen |

## Scripts en Tools

| Script | Beschrijving |
|--------|-------------|
| [backup-database.sh](backup-database.sh) | Script om database backups te maken |
| [restore-database.sh](restore-database.sh) | Script om database backups te herstellen |
| [deploy.sh](deploy.sh) | Script om updates te deployen en containers te herstarten |
| [schedule-backups.sh](schedule-backups.sh) | Script om automatische backups in te stellen |

## Technische Documentatie

| Onderdeel | Beschrijving |
|-----------|-------------|
| [docker-compose.yml](docker-compose.yml) | Docker Compose configuratie voor containerorkestratie |
| [Dockerfile](Dockerfile) | Definitie van de Docker image voor de applicatie |
| [.env.example](.env.example) | Voorbeeld configuratiebestand met omgevingsvariabelen |

## Configuratie en Aanpassing

Het systeem kan worden aangepast via verschillende configuratiebestanden:

1. **Omgevingsvariabelen** - `.env` bestand (gebaseerd op `.env.example`)
2. **Docker configuratie** - `docker-compose.yml` en `Dockerfile`
3. **Nginx configuratie** - Onder `/etc/nginx/sites-available/boekhoud` of `/opt/boekhoud/nginx/conf.d/default.conf`

## Veelgebruikte Commando's

### Applicatie starten/stoppen
```bash
cd /opt/boekhoud
docker-compose up -d      # Starten
docker-compose down       # Stoppen
```

### Logs bekijken
```bash
cd /opt/boekhoud
docker-compose logs -f
```

### Updates deployen
```bash
cd /opt/boekhoud
./deploy.sh
```

### Database backup maken
```bash
cd /opt/boekhoud
./backup-database.sh
```

## Ondersteuning

Als je hulp nodig hebt met de installatie of het gebruik van het Boekhoud Systeem, raadpleeg eerst de TROUBLESHOOTING.md gids. Als je probleem daarmee niet opgelost is, neem dan contact op met de systeembeheerder of de ontwikkelaar van het systeem.