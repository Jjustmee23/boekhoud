# Veelgestelde Vragen (FAQ)

## Installatie Problemen

### Q: Mijn domein werkt niet na installatie, wat moet ik doen?
A: Volg deze stappen om het probleem op te lossen:
1. Controleer of je DNS-instellingen correct zijn ingesteld met een A-record dat naar je server-IP wijst
2. Voer het troubleshooting-script uit: `sudo /opt/boekhoudapp/troubleshoot-domain.sh`
3. Controleer of poorten 80 en 443 open staan: `sudo ufw status`
4. Bekijk de nginx logs: `docker logs nginx-proxy`
5. Zorg ervoor dat de DOMAIN waarde in je .env bestand correct is
6. Herstart alle containers: `docker compose restart`

### Q: Het SSL-certificaat wordt niet uitgegeven, hoe los ik dit op?
A: Let's Encrypt kan soms vertragen bij het uitgeven van certificaten. Volg deze stappen:
1. Controleer of je domein correct naar je server wijst (DNS A-record)
2. Bekijk de logs van de acme-companion container: `docker logs acme-companion`
3. Controleer of je e-mailadres correct is ingesteld in het .env bestand
4. Forceer een vernieuwing van het certificaat: `docker exec acme-companion /app/force_renew`
5. Controleer of er geen rate-limiting is op Let's Encrypt (max 5 certificaten per domein per week)

### Q: De installatie loopt vast bij het genereren van DH-parameters, wat nu?
A: Het genereren van DH-parameters kan enkele minuten duren op minder krachtige servers. Als het te lang duurt of vastloopt:
1. Druk Ctrl+C om het script te onderbreken
2. Maak handmatig de DH-parameters met een lagere bit-waarde: `openssl dhparam -out nginx/ssl/dhparam.pem 1024`
3. Hervat het installatiescript handmatig vanaf het punt waar het was gebleven

## Beheer Problemen

### Q: Hoe wijzig ik het admin wachtwoord?
A: Je kunt het admin wachtwoord wijzigen door in te loggen in de applicatie, naar het admin gedeelte te gaan en daar je wachtwoord te wijzigen. Als je het admin wachtwoord bent vergeten, kun je het resetten met de volgende stappen:
1. Wijzig het wachtwoord in de database: `docker exec -it db psql -U postgres -d boekhouding -c "UPDATE users SET password_hash='nieuw_hash' WHERE email='admin@email.com';"`
2. Of voeg een nieuw admin account toe via de applicatie interface

### Q: Hoe maak ik een backup van mijn gegevens?
A: Er zijn verschillende manieren om een backup te maken:
1. Gebruik het beheerscript: `sudo /opt/boekhoudapp/beheer.sh` en kies optie 7
2. Maak handmatig een database dump: `docker exec db pg_dumpall -c -U postgres > backup.sql`
3. Maak een volledige backup van de applicatiemap: `sudo tar -czf boekhoudapp_backup.tar.gz /opt/boekhoudapp`

### Q: Hoe herstel ik een backup?
A: Om een database backup te herstellen:
1. Gebruik het beheerscript: `sudo /opt/boekhoudapp/beheer.sh` en kies optie 8
2. Of herstel handmatig: `cat backup.sql | docker exec -i db psql -U postgres`

### Q: Hoe update ik de applicatie naar een nieuwere versie?
A: De eenvoudigste manier is het automatische update-script gebruiken:
1. Voer uit: `sudo /opt/boekhoudapp/update-app.sh`
2. Het script maakt automatisch backups, haalt de nieuwste code op en herstart alles

Alternatief kun je manueel updaten:
1. Maak eerst een backup van je database: `docker exec -t db pg_dumpall -c -U postgres > backup.sql`
2. Stop alle containers: `docker compose down`
3. Update de code via git: `git pull`
4. Start de containers opnieuw: `docker compose up -d`
5. Of gebruik het beheerscript en kies optie 9

## Gebruik Problemen

### Q: Hoe kan ik e-mails configureren met Microsoft 365 / Office 365?
A: Om e-mails te configureren met Microsoft 365:
1. Bewerk het .env bestand: `sudo nano /opt/boekhoudapp/./env`
2. Vul de volgende velden in:
   ```
   MS_GRAPH_CLIENT_ID=jouw_client_id
   MS_GRAPH_CLIENT_SECRET=jouw_client_secret
   MS_GRAPH_TENANT_ID=jouw_tenant_id
   MS_GRAPH_SENDER_EMAIL=jouw_email@domein.nl
   ```
3. Herstart de containers: `docker compose restart`

### Q: Hoe voeg ik extra gebruikers toe aan het systeem?
A: Er zijn twee manieren om gebruikers toe te voegen:
1. Als admin, log in en ga naar het gebruikersbeheer om nieuwe gebruikers toe te voegen
2. Schakel registratie in door ENABLE_REGISTRATION=True in te stellen in je .env bestand

### Q: Hoe kan ik de layout of het uiterlijk van de applicatie aanpassen?
A: Om het uiterlijk aan te passen:
1. De templates staan in de map templates/
2. CSS-bestanden staan in static/css/
3. Pas deze bestanden aan volgens je wensen
4. Herstart de containers: `docker compose restart`

## Technische Problemen

### Q: De applicatie is traag, hoe kan ik de prestaties verbeteren?
A: Om de prestaties te verbeteren:
1. Zorg voor voldoende resources op je server (RAM, CPU)
2. Optimaliseer de database: `docker exec db vacuumdb --all --analyze -U postgres`
3. Controleer de logs op veelvoorkomende fouten: `docker compose logs -f`
4. Schakel debug mode uit in het .env bestand
5. Overweeg om een krachtigere server te gebruiken

### Q: Hoe kan ik logging bekijken en problemen diagnosticeren?
A: Er zijn verschillende manieren om logs te bekijken:
1. Gebruik het beheerscript: `sudo /opt/boekhoudapp/beheer.sh` en kies optie 5
2. Bekijk alle logs: `docker compose logs -f`
3. Bekijk logs van een specifieke container: `docker logs app` of `docker logs db`
4. De applicatie logs staan ook in de map `/opt/boekhoudapp/logs/`

### Q: Hoe kan ik een custom domein configureren?
A: Om een custom domein te configureren:
1. Zorg ervoor dat je DNS A-record naar je server-IP wijst
2. Bewerk het .env bestand en wijzig de DOMAIN waarde: `sudo nano /opt/boekhoudapp/.env`
3. Herstart alle containers: `docker compose restart`
4. Wacht tot het nieuwe SSL-certificaat is uitgegeven (dit kan enkele minuten duren)

### Q: Kan ik meerdere domeinen configureren voor dezelfde applicatie?
A: Ja, dit is mogelijk met nginx-proxy:
1. Voeg extra domeinen toe aan je .env bestand, gescheiden door komma's: `DOMAIN=domein1.nl,domein2.nl`
2. Zorg ervoor dat alle domeinen correct zijn geconfigureerd in je DNS
3. Herstart alle containers: `docker compose restart`
4. Let's Encrypt zal automatisch certificaten uitgeven voor alle domeinen

## Beveiliging

### Q: Hoe veilig is deze installatie?
A: De installatie biedt een goede basisbeveiliging:
1. SSL/TLS-versleuteling voor alle verkeer
2. Sterke DH-parameters voor verbeterde SSL-veiligheid
3. Firewall die alleen noodzakelijke poorten openstelt
4. Containerisatie voor isolatie van componenten
5. Automatisch gegenereerde sterke wachtwoorden

### Q: Hoe kan ik de beveiliging verder verbeteren?
A: Om de beveiliging verder te verbeteren:
1. Schakel registratie uit na het aanmaken van alle benodigde accounts: `ENABLE_REGISTRATION=False` in .env
2. Wijzig regelmatig wachtwoorden
3. Installeer fail2ban om brute-force aanvallen te blokkeren
4. Houd het systeem up-to-date met `sudo apt update && sudo apt upgrade`
5. Maak regelmatig backups
6. Overweeg een firewall op applicatieniveau zoals ModSecurity

### Q: Hoe kan ik op de hoogte blijven van beveiligingsupdates?
A: Om op de hoogte te blijven van beveiligingsupdates:
1. Meld je aan voor de nieuwsbrief van Ubuntu Security Notices
2. Stel automatische updates in voor kritieke beveiligingsupdates
3. Controleer regelmatig op updates voor de applicatie
4. Gebruik het beheerscript optie 9 om het systeem bij te werken