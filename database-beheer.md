# Database Beheer Documentatie

Dit document beschrijft hoe de database persistentie en backup procedures werken in dit project.

## Overzicht van Database Persistentie

De PostgreSQL database is geconfigureerd voor maximale gegevensintegriteit en gegevensbehoud via Docker volumes. Zelfs wanneer containers worden herstart of verwijderd, blijven de gegevens behouden.

### Belangrijke componenten:

1. **Benoemde volumes**: In `docker-compose.yml` gebruiken we een specifiek benoemd volume (`facturatie_postgres_data`) zodat het volume ook na het verwijderen van de containers blijft bestaan.

2. **WAL (Write-Ahead Logging)**: Het systeem is ingesteld met `wal_level=logical` wat uitgebreide logging mogelijk maakt en betere gegevensbescherming biedt.

3. **Archivering**: Automatische archivering van database bestanden naar de map `db_backups/` waardoor configuratieonafhankelijke backups mogelijk zijn.

## Backup Procedures

### Handmatige Backups

De `backup-database.sh` script kan op elk moment worden uitgevoerd om een volledige backup van de database te maken:

```bash
./backup-database.sh
```

Dit script:
- Maakt een SQL dump van de gehele database
- Comprimeert deze automatisch (instelbaar in het script)
- Slaat het bestand op in de map `db_backups/` met datum/tijd in de bestandsnaam

### Database Herstel

Om een vorige backup te herstellen, gebruik het script `restore-database.sh`:

```bash
./restore-database.sh
```

Dit script:
- Toont een lijst van beschikbare backups
- Vraagt bevestiging voor het herstellen (aangezien dit bestaande gegevens zal overschrijven)
- Voert het herstelproces uit

### Geplande Backups

Om automatische backups in te stellen, gebruik het script `schedule-backups.sh`:

```bash
./schedule-backups.sh
```

Dit configureert een dagelijkse backup via cron om 2:00 uur 's nachts.

## Beste Praktijken

1. **Regelmatige backups**: Zorg voor dagelijkse automatische backups
2. **Offsite opslag**: Kopieer backups regelmatig naar een andere locatie (niet in de Docker container)
3. **Backup testen**: Test periodiek of backups correct hersteld kunnen worden
4. **Rotatie**: Implementeer backup rotatie om oude backups te verwijderen en opslagruimte te besparen

## Troubleshooting

### Database container start niet

Controleer de rechten op de volumes map:

```bash
ls -la db_backups/
```

Als de rechten niet correct zijn, corrigeer ze:

```bash
sudo chown -R $(id -u):$(id -g) db_backups/
```

### Backup script werkt niet

Als het backup script niet werkt, controleer of de database container draait:

```bash
docker-compose ps
```

En controleer de logs:

```bash
docker-compose logs db
```