# Installatie Checklist voor Flask Facturatiesysteem

Gebruik deze checklist om ervoor te zorgen dat je installatieproces volledig is uitgevoerd en alle onderdelen correct werken.

## 1. Voorbereiding

- [ ] Server is een schone Ubuntu 22.04 installatie
- [ ] Server heeft tenminste 2GB RAM en 10GB vrije schijfruimte
- [ ] Je hebt een domein dat naar het IP-adres van de server verwijst (A record)
- [ ] Je hebt root of sudo toegang tot de server
- [ ] Firewall van je hosting provider staat verkeer toe op poorten 22, 80 en 443

## 2. Installatie

### Voor Docker Installatie:

- [ ] `setup_flask_app.sh` script uitgevoerd
- [ ] Docker en Docker Compose geïnstalleerd (controleer met `docker -v` en `docker compose version`)
- [ ] Nginx en Certbot geïnstalleerd (controleer met `nginx -v` en `certbot --version`)
- [ ] Repository succesvol gekloond
- [ ] Docker containers draaien (controleer met `docker compose ps`)
- [ ] Nginx geconfigureerd als reverse proxy
- [ ] SSL certificaat succesvol aangevraagd en geïnstalleerd
- [ ] Admin gebruiker aangemaakt

### Voor Directe Installatie:

- [ ] `direct_install.sh` script uitgevoerd
- [ ] PostgreSQL geïnstalleerd en draait (controleer met `systemctl status postgresql`)
- [ ] Python virtuele omgeving aangemaakt
- [ ] Dependencies geïnstalleerd
- [ ] Flask applicatie service geconfigureerd en draait (controleer met `systemctl status flask-app`)
- [ ] Nginx geconfigureerd als reverse proxy
- [ ] SSL certificaat succesvol aangevraagd en geïnstalleerd
- [ ] Admin gebruiker aangemaakt

## 3. Verificatie

- [ ] Website is bereikbaar via HTTP (wordt automatisch doorgestuurd naar HTTPS)
- [ ] Website is bereikbaar via HTTPS
- [ ] Login pagina werkt correct
- [ ] Admin gebruiker kan inloggen
- [ ] Dashboard wordt correct weergegeven
- [ ] Database connectie werkt (inloggen werkt, gegevens kunnen worden opgeslagen)
- [ ] Bestanden kunnen worden geüpload
- [ ] PDFs kunnen worden gegenereerd (facturen, rapporten)
- [ ] E-mail functionaliteit werkt (indien geconfigureerd)

## 4. Onderhoud Setup

- [ ] Update scripts (`update.sh` en `system_update.sh`) zijn uitvoerbaar (`chmod +x`)
- [ ] Backup script (`backup.sh`) is uitvoerbaar (`chmod +x`)
- [ ] Cron jobs ingesteld voor automatische updates en backups

### Aanbevolen Cron Jobs

Voor regelmatige database backups (dagelijks om 2 uur 's nachts):
```
0 2 * * * /opt/invoice-app/backup.sh
```

Voor regelmatige systeemupdates (wekelijks op zondag om 3 uur 's nachts):
```
0 3 * * 0 /opt/invoice-app/system_update.sh
```

## 5. Beveiliging Checklist

- [ ] Firewall (UFW) is ingeschakeld en correct geconfigureerd
- [ ] SSH gebruikt sleutelgebaseerde authenticatie (geen wachtwoorden)
- [ ] PostgreSQL gebruikt sterke wachtwoorden
- [ ] Admin gebruiker heeft een sterk wachtwoord
- [ ] `.env` bestand heeft juiste permissies (alleen leesbaar voor applicatie-gebruiker)
- [ ] Applicatie draait als niet-root gebruiker
- [ ] SSL is correct geconfigureerd met moderne ciphers
- [ ] HTTP toegang wordt automatisch doorgestuurd naar HTTPS

## 6. Applicatie Instellingen

- [ ] Database URL correct geconfigureerd
- [ ] Email instellingen correct geconfigureerd (indien van toepassing)
- [ ] Betalingsprovider instellingen correct geconfigureerd (indien van toepassing)
- [ ] Aanpasbare applicatie-instellingen geconfigureerd (bijv. bedrijfsnaam, logo, etc.)

## 7. Monitoring en Logging

- [ ] Applicatie logs worden correct opgeslagen
- [ ] Nginx logs worden correct opgeslagen
- [ ] Error logs worden gecontroleerd
- [ ] Schijfruimte wordt gemonitord
- [ ] Database prestaties worden gemonitord