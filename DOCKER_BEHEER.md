# Docker Container Beheer - Boekhoud Systeem

Deze handleiding bevat beknopte instructies voor het dagelijks beheer van de Docker containers die het Boekhoud Systeem draaien.

## Container Beheer

### Containers starten
```bash
cd /opt/boekhoud
docker-compose up -d
```

### Containers stoppen
```bash
cd /opt/boekhoud
docker-compose down
```

### Containers herstarten
```bash
cd /opt/boekhoud
docker-compose restart
```

### Specifieke container herstarten
```bash
cd /opt/boekhoud
docker-compose restart web  # Alleen de web container herstarten
docker-compose restart db   # Alleen de database container herstarten
```

### Container status controleren
```bash
cd /opt/boekhoud
docker-compose ps
```

## Logging en Monitoring

### Logs bekijken
```bash
cd /opt/boekhoud
docker-compose logs -f     # Alle logs streamen
docker-compose logs -f web # Alleen web logs streamen
docker-compose logs -f db  # Alleen database logs streamen
```

### Container statistieken bekijken
```bash
cd /opt/boekhoud
docker stats
```

### Disk usage controleren
```bash
cd /opt/boekhoud
docker system df
```

## Database Beheer

### Database backup maken
```bash
cd /opt/boekhoud
./backup-database.sh
```

### Database backup herstellen
```bash
cd /opt/boekhoud
./restore-database.sh
```

### Directe toegang tot database
```bash
cd /opt/boekhoud
docker-compose exec db psql -U postgres boekhoud
```

### Database connectie controleren
```bash
cd /opt/boekhoud
docker-compose exec db pg_isready
```

## Updates en Onderhoud

### Applicatie bijwerken
```bash
cd /opt/boekhoud
./deploy.sh
```

### Docker images opruimen (schijfruimte vrijmaken)
```bash
cd /opt/boekhoud
docker-compose down
docker system prune -a  # Verwijdert alle niet-gebruikte containers, netwerken en images
docker-compose up -d
```

### Container opnieuw opbouwen
```bash
cd /opt/boekhoud
docker-compose build --no-cache web
docker-compose up -d
```

## Troubleshooting

### Container start niet
```bash
cd /opt/boekhoud
docker-compose logs web  # Check logs voor fouten
docker-compose down
docker-compose up -d     # Probeer opnieuw te starten
```

### Onvoldoende schijfruimte
```bash
# Controleer beschikbare ruimte
df -h

# Verwijder oude logs
docker-compose logs web > /dev/null

# Ruim Docker op
docker system prune -a --volumes
```

### Database problemen
```bash
cd /opt/boekhoud
docker-compose restart db  # Herstart database
docker-compose logs db     # Controleer logs
```

### Applicatie is langzaam
```bash
cd /opt/boekhoud
docker stats              # Controleer resource gebruik
docker-compose restart    # Herstart alle containers
```

## Backup Beheer

### Oude backups opruimen
```bash
cd /opt/boekhoud
find backups -name "*.sql.gz" -type f -mtime +30 -delete  # Verwijder backups ouder dan 30 dagen
```

### Externe backup maken
```bash
cd /opt/boekhoud
./backup-database.sh
# Kopieer de backup naar een externe locatie
rsync -avz backups/* gebruiker@externe-server:/backup/boekhoud/
```

## Nginx Beheer

### Nginx configuratie testen
```bash
sudo nginx -t
```

### Nginx herstarten
```bash
sudo systemctl restart nginx
```

### Nginx logs bekijken
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```