# Deployment Instructies

Deze documentatie bevat gedetailleerde instructies voor het installeren, configureren en onderhouden van het facturatie systeem. De instructies zijn geschreven voor Ubuntu 22.04 LTS servers maar kunnen ook op andere Linux-distributies werken met kleine aanpassingen.

## Inhoudsopgave

1. [Systeemvereisten](#systeemvereisten)
2. [Installatie](#installatie)
   - [Automatische installatie](#automatische-installatie)
   - [Handmatige installatie](#handmatige-installatie)
3. [Configuratie](#configuratie)
4. [Applicatie starten](#applicatie-starten)
5. [Updates](#updates)
6. [Backup en herstel](#backup-en-herstel)
7. [Automatische backups](#automatische-backups)
8. [Probleemoplossing](#probleemoplossing)
9. [Beveiligingstips](#beveiligingstips)

## Systeemvereisten

- Ubuntu 22.04 LTS (aanbevolen)
- Minimaal 2 GB RAM
- 10 GB vrije schijfruimte
- Internetverbinding
- Sudo/root toegang
- Open poorten:
  - 80/443 (voor HTTP/HTTPS)
  - 5000 (voor ontwikkeling)

## Installatie

### Automatische installatie

De snelste manier om het systeem te installeren is met één van de volgende scripts:

#### One-command installatie

```bash
wget -O install.sh https://raw.githubusercontent.com/jouw-gebruikersnaam/facturatie-systeem/main/one-command-install.sh && chmod +x install.sh && sudo ./install.sh
```

Deze installatie zal automatisch:
1. Alle benodigde software installeren
2. Docker en NGINX configureren
3. Je vragen naar je domein en een SSL certificaat aanvragen
4. Alles configureren voor grote bestandsuploads (tot 1GB)

#### Interactieve installatie

```bash
wget -O setup-ubuntu.sh https://raw.githubusercontent.com/jouw-gebruikersnaam/facturatie-systeem/main/setup-ubuntu.sh && chmod +x setup-ubuntu.sh && sudo ./setup-ubuntu.sh
```

De interactieve installatie geeft je meer controle over het installatieproces en zal je door de volgende stappen leiden:
1. Software installatie
2. Repository configuratie
3. Docker setup
4. Optionele domein configuratie met NGINX
5. Optionele SSL certificaat aanvraag via Let's Encrypt

### Handmatige installatie

Voor meer controle over het installatieproces, volg deze stappen:

1. **Benodigde software installeren**

   ```bash
   sudo apt update
   sudo apt install -y git docker.io docker-compose python3-pip curl postgresql-client
   ```

2. **Docker starten**

   ```bash
   sudo systemctl start docker
   sudo systemctl enable docker
   ```

3. **Repository klonen**

   ```bash
   sudo mkdir -p /var/www/facturatie
   sudo git clone https://github.com/jouw-gebruikersnaam/facturatie-systeem.git /var/www/facturatie
   ```

4. **Rechten instellen**

   ```bash
   sudo chown -R $USER:$USER /var/www/facturatie
   cd /var/www/facturatie
   chmod +x *.sh
   ```

5. **Configuratiebestand maken**

   ```bash
   cp .env.example .env
   nano .env  # Bewerk de configuratie naar wens
   ```

## Configuratie

Het belangrijkste configuratiebestand is `.env`. De volgende variabelen zijn essentieel:

- `DATABASE_URL`: Database verbinding string (postgresql://user:pass@host:port/dbname)
- `FLASK_SECRET_KEY`: Random geheim voor Flask sessies
- `MOLLIE_API_KEY`: API sleutel voor Mollie betalingen
- `MICROSOFT_CLIENT_ID` en `MICROSOFT_CLIENT_SECRET`: Voor Microsoft 365 integratie

Voorbeeld configuratie:

```
DATABASE_URL=postgresql://postgres:password@db:5432/facturatie
FLASK_SECRET_KEY=your-secret-key-here
MOLLIE_API_KEY=test_yourapikey
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret
MICROSOFT_REDIRECT_URI=https://yourdomain.com/ms-auth-callback
```

## Applicatie starten

Na installatie en configuratie, start de applicatie:

```bash
cd /var/www/facturatie
docker-compose up -d
```

De applicatie is nu beschikbaar op:
- Ontwikkeling: http://localhost:5000
- Productie: https://yourdomain.com (na configuratie van reverse proxy)

## Updates

Om de applicatie te updaten naar de nieuwste versie:

```bash
cd /var/www/facturatie
./deploy.sh
```

Het deploy script zal:
1. Een backup maken van de database
2. De nieuwste code ophalen van de repository
3. Docker containers herbouwen en herstarten
4. Database migraties uitvoeren

## Backup en herstel

### Database backup maken

```bash
cd /var/www/facturatie
./backup-database.sh
```

Backups worden opgeslagen in de `db_backups` map met datum en tijd in de bestandsnaam.

### Database herstellen

```bash
cd /var/www/facturatie
./restore-database.sh db_backups/backup-2025-03-31.sql.gz
```

## Automatische backups

Stel automatische dagelijkse, wekelijkse of maandelijkse backups in:

```bash
cd /var/www/facturatie
./schedule-backups.sh
```

Volg de interactieve prompts om de backup frequentie en retentieperiode in te stellen.

## Probleemoplossing

### Logs bekijken

```bash
cd /var/www/facturatie
docker-compose logs -f web
```

### Algemene problemen

**Probleem**: Docker containers starten niet
**Oplossing**: Controleer de logs en zorg dat alle poorten beschikbaar zijn

```bash
docker-compose logs
sudo lsof -i :5000  # Controleer of poort 5000 in gebruik is
```

**Probleem**: Database migratie fouten
**Oplossing**: Probeer de migratie handmatig uit te voeren

```bash
cd /var/www/facturatie
docker-compose exec web python run_migrations.py
```

**Probleem**: "Permission denied" fouten
**Oplossing**: Controleer bestandsrechten en Docker permissies

```bash
sudo chown -R $USER:$USER /var/www/facturatie
sudo usermod -aG docker $USER  # Log uit en weer in na deze commando
```

## Beveiligingstips

1. **Firewall instellen**:

   ```bash
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   sudo ufw enable
   ```

2. **Fail2ban installeren**:

   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```

3. **HTTPS instellen** met Let's Encrypt:

   ```bash
   sudo apt install -y certbot
   sudo certbot certonly --standalone -d yourdomain.com
   ```

4. **Regelmatige updates**:

   ```bash
   sudo apt update
   sudo apt upgrade -y
   ```

5. **Backups op externe locatie**:
   Configureer een script om backups naar een externe locatie te kopiëren (bijv. AWS S3, Google Cloud Storage).

## Domein configuratie

Om je applicatie beschikbaar te maken via een domeinnaam (bijv. facturatie.mijnbedrijf.nl), moet je NGINX configureren als reverse proxy en optioneel SSL certificaten aanvragen.

### NGINX installeren en configureren

Je kunt NGINX handmatig configureren of het meegeleverde script gebruiken:

```bash
cd /var/www/facturatie
sudo ./nginx-setup.sh
```

Het script zal je vragen naar:
1. Je domein (bijv. facturatie.mijnbedrijf.nl)
2. Of je een subdomein wilt gebruiken
3. E-mailadres voor SSL certificaat meldingen
4. Of je een SSL certificaat wilt aanvragen

### Handmatige NGINX configuratie

Als je liever handmatig configureert:

1. Installeer NGINX en Certbot:
   ```bash
   sudo apt install -y nginx certbot python3-certbot-nginx
   ```

2. Maak een NGINX configuratiebestand:
   ```bash
   sudo nano /etc/nginx/sites-available/facturatie.conf
   ```

3. Voeg de volgende configuratie toe (vervang DOMEIN.NL door je eigen domein):
   ```
   server {
       listen 80;
       server_name DOMEIN.NL;
       
       # Grote bestanden toestaan
       client_max_body_size 1024M;
       
       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           
           # Lange verbindingen toestaan voor uploads
           proxy_connect_timeout 600;
           proxy_send_timeout 600;
           proxy_read_timeout 600;
           send_timeout 600;
       }
   }
   ```

4. Activeer de configuratie:
   ```bash
   sudo ln -s /etc/nginx/sites-available/facturatie.conf /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. SSL configureren met Certbot:
   ```bash
   sudo certbot --nginx -d DOMEIN.NL
   ```

### SSL certificaat vernieuwing

Certificaten worden automatisch vernieuwd door een systemd timer. Je kunt dit controleren met:

```bash
sudo systemctl status certbot.timer
```

Als de timer niet actief is, kun je deze inschakelen:

```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### Testen van vernieuwing

Test of certificaat vernieuwing correct werkt:

```bash
sudo certbot renew --dry-run
```

## Grote bestandsuploads configureren

Het systeem is geconfigureerd om bestandsuploads tot 1GB te ondersteunen. Deze configuratie bestaat uit meerdere lagen:

### 1. NGINX configuratie

NGINX is geconfigureerd om grote uploads te accepteren met de volgende instellingen:

```
client_max_body_size 1024M;
proxy_connect_timeout 600;
proxy_send_timeout 600;
proxy_read_timeout 600;
send_timeout 600;
```

Deze instellingen staan in het NGINX configuratiebestand en worden automatisch toegepast door het `nginx-setup.sh` script.

### 2. Flask applicatie configuratie

De Flask applicatie moet ook worden geconfigureerd om grote uploads te accepteren. Dit gebeurt in het `flask-config-uploads.py` bestand:

```python
# In je Flask app (bijvoorbeeld main.py)
from flask_config_uploads import configure_large_uploads, configure_storage_path

app = Flask(__name__)
app = configure_large_uploads(app)  # Configureert uploads tot 1GB
app = configure_storage_path(app, 'static/uploads')  # Bepaalt upload locatie
```

### 3. Docker configuratie

De Docker container moet voldoende resources hebben voor grote uploads. In de `docker-compose.yml` zijn de volgende configuraties belangrijk:

```yaml
web:
  environment:
    - MAX_CONTENT_LENGTH=1073741824  # 1GB in bytes
  volumes:
    - uploads_data:/app/static/uploads  # Persistent volume voor uploads
    - tmp_data:/tmp  # Tijdelijke opslag voor uploads
  command: gunicorn --bind 0.0.0.0:5000 --timeout 600 --workers 4 --threads 2 main:app

volumes:
  uploads_data:  # Persistent volume voor uploads
  tmp_data:      # Voor tijdelijke opslag
```

### 4. PHP configuratie (indien van toepassing)

Als je PHP gebruikt, worden de volgende instellingen automatisch aangepast:

```
upload_max_filesize = 1024M
post_max_size = 1024M
memory_limit = 1024M
max_execution_time = 600
max_input_time = 600
```

### Testen van grote uploads

Om te testen of grote bestandsuploads correct werken:

1. Maak een groot testbestand:
   ```bash
   dd if=/dev/urandom of=testfile.bin bs=1M count=500
   ```

2. Upload dit bestand via je applicatie interface

3. Controleer de logs voor foutmeldingen:
   ```bash
   docker-compose logs web
   sudo tail -f /var/log/nginx/error.log
   ```