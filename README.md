# Factuur en Administratie Applicatie

Een uitgebreide webapplicatie voor facturatie en administratie, gebouwd met Flask en optimaal voor Benelux bedrijven.

## Docker Installatie Handleiding

Deze handleiding beschrijft hoe je de applicatie kunt installeren op je eigen Ubuntu 22.04 server met Docker, inclusief domeinconfirugatie en SSL.

### Vereisten

- Ubuntu 22.04 server
- Een domeinnaam die naar je server IP wijst
- Basiskennis van Linux en Docker

### Installatiestappen

1. **Kopieer de codebase naar je server**

   ```bash
   git clone https://github.com/Jjustmee23/boekhoud.git /path/to/app
   cd /path/to/app
   ```

2. **Maak het installatiescript uitvoerbaar**

   ```bash
   chmod +x install-docker.sh
   ```

3. **Voer het installatiescript uit**

   ```bash
   sudo ./install-docker.sh
   ```

   Beantwoord de vragen over je domeinnaam en e-mailadres.

4. **Configureer de applicatie**

   Bewerk het `.env` bestand om je API sleutels in te stellen:
   
   ```bash
   nano .env
   ```
   
   Voeg toe of bewerk:
   - Microsoft Graph API instellingen (voor e-mail)
   - Mollie API sleutel (voor betalingen)

5. **Herstart de applicatie na configuratie**

   ```bash
   docker compose restart
   ```

6. **Controleer of alles werkt**

   Open je browser en ga naar https://jouw-domein.nl

### Docker Commando's

Hier zijn enkele nuttige commando's voor het beheren van je installatie:

```bash
# Start de applicatie
docker compose up -d

# Stop de applicatie
docker compose down

# Bekijk logs
docker compose logs -f

# Bekijk status van containers
docker compose ps

# Herstart de applicatie (na wijzigingen in .env)
docker compose restart
```

### Database Backups Maken

Je kunt als volgt een backup maken van de PostgreSQL database:

```bash
docker compose exec postgres pg_dump -U facturatie_user facturatie > backup.sql
```

Terugzetten van een backup:

```bash
cat backup.sql | docker compose exec -T postgres psql -U facturatie_user facturatie
```

### Updates Installeren

Om de applicatie bij te werken:

1. Zorg voor een backup van de database
2. Pull de nieuwste code
3. Bouw en herstart de containers

```bash
git pull
docker compose down
docker compose up -d --build
```

### Troubleshooting

- **Applicatie is niet bereikbaar**: Controleer of je domein correct naar het IP van je server wijst en of poorten 80 en 443 open staan in je firewall.
- **SSL certificaat werkt niet**: Controleer of je domeinnaam correct is ingesteld en of je e-mailadres geldig is.
- **E-mail werkt niet**: Controleer je Microsoft Graph API instellingen in het `.env` bestand.
- **Foutmeldingen bekijken**: Check de logs met `docker compose logs -f`.
- **Problemen met nginx-proxy of acme-companion**: Controleer of de volumes en container namen correct zijn ingesteld. Herstart de containers met `docker compose restart`.
- **Problemen met dhparam.pem**: Als je problemen hebt met het dhparam.pem bestand, kun je dit handmatig genereren met `./nginx/dhparam-generator.sh` of gebruik het commando `openssl dhparam -out nginx/ssl/dhparam.pem 2048`.

### Ondersteuning

Voor ondersteuning, neem contact op via e-mail op [jouw-email].