# Facturatie & Boekhouding Systeem - Installatie Handleiding

Deze handleiding helpt bij het installeren en configureren van het Facturatie & Boekhouding Systeem op een schone Ubuntu 22.04 server.

## Inhoudsopgave

1. [Vereisten](#vereisten)
2. [Installatie](#installatie)
3. [Configuratie](#configuratie)
4. [Beheer](#beheer)
5. [Backup & Herstel](#backup--herstel)
6. [Updaten](#updaten)
7. [Probleemoplossing](#probleemoplossing)

## Vereisten

- Ubuntu 22.04 LTS server (clean install)
- Minimaal 2GB RAM
- Minimaal 10GB vrije schijfruimte
- Superuser (sudo) toegang
- Internettoegang
- (Optioneel) Een domeinnaam die naar de server wijst

## Installatie

### Optie 1: Automatische installatie (aanbevolen)

1. Download de installer:

```bash
wget https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/ubuntu-setup.sh
```

2. Maak het script uitvoerbaar:

```bash
chmod +x ubuntu-setup.sh
```

3. Voer het installatiescript uit:

```bash
sudo ./ubuntu-setup.sh
```

4. Volg de instructies op het scherm. Je wordt gevraagd om:
   - Installatielocatie (standaard: /opt/boekhoud)
   - Domeinnaam (optioneel)
   - GitHub repository URL (optioneel)

### Optie 2: Handmatige installatie

Als je de automatische installatie niet kunt gebruiken, volg dan deze stappen:

1. Installeer de benodigde software:

```bash
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release git nginx
```

2. Installeer Docker:

```bash
# Docker GPG key toevoegen
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Docker repository toevoegen
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installeer Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Start en enable Docker
sudo systemctl enable --now docker
```

3. Installeer Docker Compose:

```bash
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
```

4. Maak de installatiedirectory aan:

```bash
sudo mkdir -p /opt/boekhoud
```

5. Haal de code op:

```bash
# Via Git
sudo git clone https://github.com/Jjustmee23/boekhoud.git /opt/boekhoud

# Of kopieer de bestanden handmatig naar /opt/boekhoud
```

6. Ga naar de installatiedirectory:

```bash
cd /opt/boekhoud
```

7. Maak het .env bestand aan:

```bash
cp .env.example .env
```

8. Bewerk het .env bestand en pas de instellingen aan:

```bash
sudo nano .env
```

9. Maak de scripts uitvoerbaar:

```bash
sudo chmod +x *.sh
```

10. Start de Docker containers:

```bash
sudo docker-compose up -d
```

11. Configureer Nginx:

```bash
# Maak een Nginx configuratie bestand aan
sudo nano /etc/nginx/sites-available/boekhoud

# Voeg de volgende inhoud toe:
server {
    listen 80;
    server_name jouw-domein.nl;  # Of gebruik 'server_name _;' voor alle domeinen

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/boekhoud/static/;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    client_max_body_size 100M;
}

# Activeer de configuratie
sudo ln -sf /etc/nginx/sites-available/boekhoud /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

12. (Optioneel) Configureer SSL:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d jouw-domein.nl
```

## Configuratie

### Omgevingsvariabelen

De belangrijkste instellingen zijn opgeslagen in het `.env` bestand in de hoofddirectory:

- `DB_USER`: Database gebruikersnaam (standaard: postgres)
- `DB_PASSWORD`: Database wachtwoord
- `DB_NAME`: Database naam (standaard: boekhoud)
- `DB_HOST`: Database host (standaard: db)
- `DB_PORT`: Database poort (standaard: 5432)
- `SESSION_SECRET`: Geheime sleutel voor sessies
- `TZ`: Tijdzone (standaard: Europe/Amsterdam)
- `SMTP_*`: SMTP instellingen voor e-mail
- `MS_*`: Microsoft OAuth2 instellingen (optioneel)
- `MOLLIE_API_KEY`: Mollie API Key (optioneel)

### Docker Compose

De Docker-omgeving is gedefinieerd in `docker-compose.yml` en bestaat uit:

- **web**: De Flask webapplicatie
- **db**: PostgreSQL database
- **nginx**: Nginx reverse proxy (optioneel)

## Beheer

### Start/Stop Containers

Containers starten:

```bash
cd /opt/boekhoud
docker-compose up -d
```

Containers stoppen:

```bash
cd /opt/boekhoud
docker-compose down
```

Web container herstarten:

```bash
cd /opt/boekhoud
docker-compose restart web
```

### Logs bekijken

Alle logs bekijken:

```bash
cd /opt/boekhoud
docker-compose logs -f
```

Alleen web container logs:

```bash
cd /opt/boekhoud
docker-compose logs -f web
```

### Database toegang

Toegang tot de database shell:

```bash
cd /opt/boekhoud
docker-compose exec db psql -U postgres boekhoud
```

## Backup & Herstel

### Database backup maken

Handmatig een backup maken:

```bash
cd /opt/boekhoud
./backup-database.sh
```

De backups worden opgeslagen in de `backups` directory.

### Geautomatiseerde backups instellen

Configureer geautomatiseerde backups:

```bash
cd /opt/boekhoud
sudo ./schedule-backups.sh
```

Volg de instructies om dagelijkse, wekelijkse of maandelijkse backups in te stellen.

### Database herstel

Een database backup herstellen:

```bash
cd /opt/boekhoud
./restore-database.sh
```

Volg de instructies om de backup te selecteren en te herstellen.

## Updaten

Het systeem updaten:

```bash
cd /opt/boekhoud
./deploy.sh
```

Dit script haalt de nieuwste code op, maakt een backup van de database, bouwt de containers opnieuw en start ze.

## Probleemoplossing

### Algemene stappen

1. Controleer de logs:

```bash
cd /opt/boekhoud
docker-compose logs -f
```

2. Controleer de container status:

```bash
cd /opt/boekhoud
docker-compose ps
```

3. Herstart de containers:

```bash
cd /opt/boekhoud
docker-compose restart
```

### Veelvoorkomende problemen

#### Database connectie fouten

```bash
cd /opt/boekhoud
docker-compose restart db
```

#### Permissie problemen

```bash
cd /opt/boekhoud
sudo chown -R $(whoami):$(whoami) .
```

#### Poort is al in gebruik

```bash
sudo netstat -tulpn | grep 5000
# Stop het proces dat deze poort gebruikt
```

#### Nginx foutmeldingen

```bash
sudo nginx -t
# Controleer op configuratiefouten
```

### Nog steeds problemen?

Bezoek onze ondersteuningspagina of neem contact op via support@jouwbedrijf.nl

---

© 2025 Boekhoud Systeem