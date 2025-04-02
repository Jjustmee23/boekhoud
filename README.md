# Factuur en Administratie Applicatie

Een uitgebreide webapplicatie voor facturatie en administratie, gebouwd met Flask en optimaal voor Benelux bedrijven. Deze repository bevat ook volledige deploy scripts voor installatie op een eigen server.

## Beschrijving

Deze applicatie biedt een complete oplossing voor facturatie, boekhouding en administratie voor bedrijven in België en Nederland. Het systeem is ontwikkeld met Flask en heeft een PostgreSQL database voor gegevensopslag.

### Functionaliteiten

- Facturatie en offertes
- Klantenbeheer
- Werkruimtes voor verschillende bedrijven
- E-mail integratie via Microsoft Graph API of standaard SMTP
- Betalingsverwerking via Mollie
- Abonnementen en licentiebeheer
- Rapportage en analyses
- BTW-berekeningen voor de Benelux
- Meertalige ondersteuning (Nederlands, Engels, Frans)
- Gebruikersbeheer met verschillende rechten

## Snelle Start voor Lokale Ontwikkeling

### Vereisten

- Python 3.11 of hoger
- PostgreSQL database
- De benodigde Python-packages zijn opgenomen in requirements.txt

### Stappen voor Lokale Installatie

1. **Kloon de repository**
   ```bash
   git clone https://github.com/Jjustmee23/boekhoud.git
   cd boekhoud
   ```

2. **Maak een virtuele Python-omgeving aan**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Voor Windows: venv\Scripts\activate
   ```

3. **Installeer de benodigde pakketten**
   ```bash
   pip install -r deployment/requirements.txt
   ```

4. **Configureer de omgevingsvariabelen**
   ```bash
   cp .env.example .env
   # Bewerk het .env bestand met uw eigen instellingen
   ```

5. **Start de applicatie**
   ```bash
   python main.py
   ```

6. **Open de applicatie**
   De webapplicatie is nu beschikbaar op `http://localhost:5000`

## Productie Deployment

Deze applicatie kan op twee manieren op een productieserver worden geïnstalleerd:

1. **Docker Installatie** (aanbevolen)
2. **Directe Installatie** (zonder Docker)

### Vereisten voor Productie Deployment

- Ubuntu 22.04 server
- Root- of sudo-toegang
- Domeinnaam die naar het server IP-adres wijst (voor SSL-configuratie)

### Docker Installatie (Aanbevolen)

1. **Voer het setup script uit**
   ```bash
   chmod +x deployment/setup.sh
   sudo ./deployment/setup.sh
   ```

2. **Configureer uw .env bestand**
   ```bash
   cp .env.example .env
   nano .env  # Pas uw instellingen aan
   ```

3. **Deploy de applicatie**
   ```bash
   chmod +x deployment/deploy.sh
   ./deployment/deploy.sh
   ```
   Volg de instructies voor het instellen van SSL-certificaten.

4. **Configureer automatische backups en updates**
   ```bash
   chmod +x deployment/backup.sh deployment/update.sh deployment/system_update.sh
   (crontab -l 2>/dev/null; echo "0 2 * * * /opt/invoicing-app/deployment/backup.sh") | crontab -
   ```

### Directe Installatie (Zonder Docker)

1. **Voer het directe installatiescript uit**
   ```bash
   chmod +x deployment/direct_install.sh
   sudo ./deployment/direct_install.sh
   ```

2. **Volg de instructies op het scherm**
   Het script zal u vragen om uw domeinnaam en andere instellingen.

## Onderhoud

### Updates Uitvoeren

Updates kunnen veilig worden uitgevoerd zonder dataverlies:

```bash
cd /opt/invoicing-app
./deployment/update.sh
```

### Database Backups

Er worden automatisch dagelijkse backups gemaakt. Handmatige backups kunnen worden gemaakt met:

```bash
./deployment/backup.sh  # Voor Docker installatie
./deployment/direct_backup.sh  # Voor directe installatie
```

### SSL Certificaten Vernieuwen

SSL-certificaten worden automatisch vernieuwd. Handmatige vernieuwing indien nodig:

```bash
# Voor Docker installatie
docker-compose stop nginx
certbot renew
docker-compose start nginx

# Voor directe installatie
sudo certbot renew
sudo systemctl restart nginx
```

## Configuratie Opties

### Database Instellingen

Configureer PostgreSQL-verbinding in het `.env` bestand:
```
POSTGRES_USER=dbuser
POSTGRES_PASSWORD=uw_wachtwoord
POSTGRES_DB=invoicing
DATABASE_URL=postgresql://dbuser:uw_wachtwoord@db:5432/invoicing
```

### E-mail Configuratie

De applicatie ondersteunt zowel Microsoft Graph API als standaard SMTP:

**Microsoft Graph API (Office 365):**
```
MS_CLIENT_ID=uw_client_id
MS_CLIENT_SECRET=uw_client_secret
MS_TENANT_ID=uw_tenant_id
MS_USER_EMAIL=uw_email@voorbeeld.nl
```

**SMTP:**
```
SMTP_SERVER=smtp.voorbeeld.nl
SMTP_PORT=587
SMTP_USER=uw_gebruiker
SMTP_PASSWORD=uw_wachtwoord
MAIL_USE_TLS=True
```

### Betalingen (Mollie)

Configureer Mollie voor betalingsverwerking:
```
MOLLIE_API_KEY=uw_mollie_api_sleutel
MOLLIE_WEBHOOK_URL=https://uw_domein.nl/webhook/mollie
```

## Aanvullende Documentatie

Raadpleeg deze bestanden voor gedetailleerde informatie:

- [INSTALLATION.md](INSTALLATION.md) - Gedetailleerde installatie-instructies in het Engels
- [GEBRUIKSHANDLEIDING.md](GEBRUIKSHANDLEIDING.md) - Gedetailleerde installatie-instructies in het Nederlands
- [FAQ.md](FAQ.md) - Veelgestelde vragen
- [deployment/README.md](deployment/README.md) - Informatie over de deployment scripts

## Systeemarchitectuur

Het systeem bestaat uit de volgende componenten:

1. **Flask Webapplicatie** - De kern van het systeem
2. **PostgreSQL Database** - Voor gegevensopslag
3. **Nginx** - Als reverse proxy en voor SSL-terminatie
4. **Gunicorn** - WSGI HTTP Server voor Python

### Bestandsstructuur

```
├── deployment/        # Deployment scripts en configuraties
├── nginx/             # Nginx configuratie
├── static/            # Statische bestanden (CSS, JS, afbeeldingen)
├── templates/         # HTML templates
├── .env.example       # Voorbeeld omgevingsvariabelen
├── Dockerfile         # Docker configuratie
├── docker-compose.yml # Docker Compose configuratie
├── main.py            # Applicatie entrypoint
└── models.py          # Database modellen
```

## Ondersteuning

Voor ondersteuning bij installatie of gebruik:

- Raadpleeg de [FAQ.md](FAQ.md) voor veelgestelde vragen
- Controleer de [INSTALLATION.md](INSTALLATION.md) voor gedetailleerde instructies
- Neem contact op met de ontwikkelaar via GitHub: [https://github.com/Jjustmee23](https://github.com/Jjustmee23)