# Troubleshooting Gids - Boekhoud Systeem

Deze gids helpt je bij het oplossen van veelvoorkomende problemen met het Boekhoud Systeem.

## Applicatie is niet bereikbaar

### Probleem: Website toont "Connection refused" of laadt niet

**Oplossing:**

1. **Controleer of containers draaien:**
   ```bash
   cd /opt/boekhoud
   docker-compose ps
   ```
   
   Als containers niet draaien (status is niet "Up"), start ze:
   ```bash
   docker-compose up -d
   ```

2. **Controleer logs voor errors:**
   ```bash
   docker-compose logs -f web
   ```
   
   Zoek naar errors zoals "Error binding to port" of "Database connection failed".

3. **Controleer Nginx:**
   ```bash
   sudo systemctl status nginx
   sudo nginx -t
   ```
   
   Als er problemen zijn, herstart Nginx:
   ```bash
   sudo systemctl restart nginx
   ```

4. **Controleer poort 5000:**
   ```bash
   sudo netstat -tuln | grep 5000
   ```
   
   Als de poort niet in gebruik is, controleer de web container:
   ```bash
   docker-compose restart web
   ```

## Database problemen

### Probleem: "Database connection error" in logs

**Oplossing:**

1. **Controleer database container:**
   ```bash
   cd /opt/boekhoud
   docker-compose ps db
   ```

2. **Bekijk database logs:**
   ```bash
   docker-compose logs -f db
   ```

3. **Test database connectie:**
   ```bash
   docker-compose exec db pg_isready
   ```
   
   Als dit faalt, herstart de database:
   ```bash
   docker-compose restart db
   ```
   
4. **Controleer omgevingsvariabelen:**
   ```bash
   cat .env | grep DB_
   ```
   
   Zorg dat de database instellingen correct zijn.

5. **Als alles faalt, herstel de database:**
   ```bash
   ./restore-database.sh
   ```

## Login problemen

### Probleem: Kan niet inloggen of krijgt steeds "Invalid credentials"

**Oplossing:**

1. **Controleer sessie configuratie:**
   ```bash
   cat .env | grep SESSION_SECRET
   ```
   
   Zorg dat SESSION_SECRET is ingesteld en niet is gewijzigd.

2. **Reset het admin wachtwoord:**
   ```bash
   docker-compose exec web python reset_admin_password.py
   ```
   
   Volg de instructies om een nieuw wachtwoord in te stellen.

3. **Controleer browser cookies:**
   Verwijder cookies voor de site en probeer opnieuw.

## Prestatieproblemen

### Probleem: Applicatie is langzaam of loopt vast

**Oplossing:**

1. **Controleer resource gebruik:**
   ```bash
   cd /opt/boekhoud
   docker stats
   ```
   
   Zoek naar containers die veel CPU of geheugen gebruiken.

2. **Controleer database performance:**
   ```bash
   docker-compose exec db psql -U postgres -d boekhoud -c "SELECT count(*) FROM pg_stat_activity;"
   ```
   
   Een hoog aantal connecties kan duiden op een probleem.

3. **Controleer disk usage:**
   ```bash
   df -h
   docker system df
   ```
   
   Als de schijf bijna vol is:
   ```bash
   docker system prune -a
   ```

4. **Herstart de containers:**
   ```bash
   docker-compose restart
   ```

## Update problemen

### Probleem: Errors tijdens updates of deployment

**Oplossing:**

1. **Controleer deployment logs:**
   ```bash
   cd /opt/boekhoud
   ./deploy.sh
   ```
   
   Let op errors tijdens de update.

2. **Controleer git status:**
   ```bash
   git status
   ```
   
   Als er lokale wijzigingen zijn die conflicteren:
   ```bash
   git reset --hard origin/main
   ```

3. **Handmatig opnieuw opbouwen:**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

## Backups en herstelproblemen

### Probleem: Backup script geeft errors

**Oplossing:**

1. **Controleer backups directory permissies:**
   ```bash
   cd /opt/boekhoud
   ls -la backups
   ```
   
   Als er permissie problemen zijn:
   ```bash
   sudo chmod -R 755 backups
   sudo chown -R $(whoami):$(whoami) backups
   ```

2. **Controleer beschikbare schijfruimte:**
   ```bash
   df -h
   ```
   
   Als er weinig ruimte is, ruim oude backups op:
   ```bash
   find backups -name "*.sql.gz" -type f -mtime +30 -delete
   ```

3. **Handmatig een backup maken:**
   ```bash
   docker-compose exec db pg_dump -U postgres boekhoud | gzip > backups/manual_backup_$(date +%Y%m%d_%H%M%S).sql.gz
   ```

## Email problemen

### Probleem: Geen emails worden verzonden

**Oplossing:**

1. **Controleer email instellingen:**
   ```bash
   cat .env | grep SMTP
   cat .env | grep MS_
   ```
   
   Zorg dat de juiste email provider is geconfigureerd.

2. **Test email connectie:**
   ```bash
   docker-compose exec web python -c "from email_service import EmailService; print(EmailService().is_configured())"
   ```
   
   Dit zou True moeten teruggeven als het correct is geconfigureerd.

3. **Controleer logs voor email errors:**
   ```bash
   docker-compose logs -f web | grep -i "email\|smtp\|mail"
   ```

## SSL/HTTPS problemen

### Probleem: SSL certificaat waarschuwingen of errors

**Oplossing:**

1. **Controleer certificaat status:**
   ```bash
   sudo certbot certificates
   ```

2. **Vernieuw het certificaat:**
   ```bash
   sudo certbot renew --force-renewal
   ```

3. **Test Nginx configuratie:**
   ```bash
   sudo nginx -t
   ```

4. **Herstart Nginx:**
   ```bash
   sudo systemctl restart nginx
   ```

## Algemene troubleshooting stappen

Als geen van de bovenstaande oplossingen werkt:

1. **Verzamel alle logs:**
   ```bash
   cd /opt/boekhoud
   docker-compose logs > all_logs.txt
   ```

2. **Controleer systeem resources:**
   ```bash
   top
   free -h
   df -h
   ```

3. **Herstart alle services:**
   ```bash
   docker-compose down
   docker system prune
   docker-compose up -d
   sudo systemctl restart nginx
   ```

4. **Als alles faalt, overweeg een schone installatie:**
   ```bash
   cd /opt/boekhoud
   ./backup-database.sh
   docker-compose down
   cp .env .env.backup
   cp -r backups /tmp/boekhoud_backups
   cd ..
   sudo rm -rf boekhoud
   # Voer vervolgens de installatie opnieuw uit en herstel de laatste backup
   ```