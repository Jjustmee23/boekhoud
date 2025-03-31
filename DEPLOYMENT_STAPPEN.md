# Boekhoud Systeem - Stapsgewijze Deployment Handleiding

Deze handleiding biedt een gedetailleerde stapsgewijze instructie voor het deployen van het Boekhoud Systeem op een schone Ubuntu 22.04 server.

## 1. Server voorbereiden

```bash
# Update pakketten
sudo apt update && sudo apt upgrade -y

# Installeer essentiële software
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release git
```

## 2. Docker installeren

```bash
# Docker GPG key toevoegen
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Docker repository toevoegen
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installeer Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Start en enable Docker
sudo systemctl enable --now docker

# Voeg je gebruiker toe aan de docker groep (vermijd sudo voor docker commando's)
sudo usermod -aG docker $USER
# Log uit en weer in om de wijzigingen toe te passen
```

## 3. Docker Compose installeren

```bash
# Download Docker Compose
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose

# Maak uitvoerbaar
sudo chmod +x /usr/local/bin/docker-compose

# Maak symbolische link
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# Controleer de installatie
docker-compose --version
```

## 4. Nginx installeren

```bash
# Installeer Nginx
sudo apt install -y nginx

# Start en enable Nginx
sudo systemctl enable --now nginx
```

## 5. Project installeren

### Optie A: Via het one-command installatiescript

```bash
# Download het installatiescript
wget https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/one-command-install.sh

# Maak uitvoerbaar
chmod +x one-command-install.sh

# Voer het script uit
sudo ./one-command-install.sh
```

### Optie B: Handmatige installatie

```bash
# Maak installatiemap
sudo mkdir -p /opt/boekhoud
cd /opt/boekhoud

# Clone de repository
sudo git clone https://github.com/Jjustmee23/boekhoud.git .

# Maak scripts uitvoerbaar
sudo chmod +x *.sh

# Maak configuratiebestand
sudo cp .env.example .env

# Bewerk het .env bestand met je eigen instellingen
sudo nano .env
```

## 6. Docker containers configureren en starten

```bash
# Ga naar projectmap
cd /opt/boekhoud

# Start Docker containers
sudo docker-compose up -d

# Controleer of containers draaien
sudo docker-compose ps
```

## 7. Nginx als reverse proxy configureren

```bash
# Maak Nginx configuratiebestand
sudo nano /etc/nginx/sites-available/boekhoud
```

Voeg de volgende configuratie toe (vervang "jouw-domein.nl" met je eigen domein of IP):

```nginx
server {
    listen 80;
    server_name jouw-domein.nl;

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
```

```bash
# Activeer de site
sudo ln -s /etc/nginx/sites-available/boekhoud /etc/nginx/sites-enabled/

# Verwijder default site (optioneel)
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuratie
sudo nginx -t

# Herstart Nginx
sudo systemctl restart nginx
```

## 8. SSL configureren (Let's Encrypt)

```bash
# Installeer Certbot
sudo apt install -y certbot python3-certbot-nginx

# Vraag SSL certificaat aan
sudo certbot --nginx -d jouw-domein.nl
```

## 9. Firewall instellen (optioneel maar aanbevolen)

```bash
# Installeer ufw als het nog niet geïnstalleerd is
sudo apt install -y ufw

# Configureer firewall om SSH, HTTP en HTTPS toe te staan
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Activeer firewall (let op: dit kan SSH-verbindingen verbreken als SSH niet is toegestaan)
sudo ufw enable
```

## 10. Automatische backups instellen

```bash
# Ga naar projectmap
cd /opt/boekhoud

# Stel automatische dagelijkse backups in
sudo ./schedule-backups.sh
```

## 11. Periodieke updates instellen (optioneel)

```bash
# Maak een script voor automatische updates
sudo nano /opt/boekhoud/auto-update.sh
```

Voeg toe:

```bash
#!/bin/bash
cd /opt/boekhoud
./deploy.sh
```

```bash
# Maak uitvoerbaar
sudo chmod +x /opt/boekhoud/auto-update.sh

# Voeg toe aan crontab (wekelijkse updates op zondag om 3:30 uur)
(crontab -l 2>/dev/null; echo "30 3 * * 0 /opt/boekhoud/auto-update.sh > /var/log/boekhoud-update.log 2>&1") | crontab -
```

## 12. Testen of alles werkt

Open een webbrowser en navigeer naar je domein of IP-adres:
- http://jouw-domein.nl (of https:// als je SSL hebt geconfigureerd)

## Beheercommando's

### Containers beheren

```bash
# Containers starten (als ze niet draaien)
cd /opt/boekhoud
docker-compose up -d

# Containers stoppen
cd /opt/boekhoud
docker-compose down

# Logs bekijken
cd /opt/boekhoud
docker-compose logs -f

# Specifieke container herstarten (bijv. web)
cd /opt/boekhoud
docker-compose restart web
```

### Database backups

```bash
# Handmatig backup maken
cd /opt/boekhoud
./backup-database.sh

# Backup herstellen
cd /opt/boekhoud
./restore-database.sh
```

### Updates uitvoeren

```bash
# Update applicatie vanuit Git
cd /opt/boekhoud
./deploy.sh
```

### Logging en monitoring

```bash
# Logs bekijken
cd /opt/boekhoud
docker-compose logs -f

# Geavanceerde monitoring (optioneel)
cd /opt/boekhoud
docker stats
```

## Troubleshooting

### Applicatie is niet bereikbaar

1. Controleer of containers draaien:
```bash
cd /opt/boekhoud
docker-compose ps
```

2. Controleer logs voor fouten:
```bash
cd /opt/boekhoud
docker-compose logs -f web
```

3. Controleer Nginx status:
```bash
sudo systemctl status nginx
sudo nginx -t
```

4. Controleer firewall:
```bash
sudo ufw status
```

### Database problemen

1. Controleer database container:
```bash
cd /opt/boekhoud
docker-compose logs db
```

2. Controleer database verbinding:
```bash
cd /opt/boekhoud
docker-compose exec db pg_isready -h localhost -U postgres
```

3. Herstart database:
```bash
cd /opt/boekhoud
docker-compose restart db
```

### Schijfruimte problemen

1. Controleer schijfruimte:
```bash
df -h
```

2. Oude containers, images en volumes opruimen:
```bash
docker system prune -a --volumes
```

3. Oude backup bestanden opruimen:
```bash
find /opt/boekhoud/backups -name "*.sql.gz" -type f -mtime +30 -delete
```

## Conclusie

Je Boekhoud Systeem is nu geïnstalleerd en operationeel! Zorg ervoor dat je regelmatig backups maakt, de beveiligingsupdates bijhoudt, en het systeem regelmatig test op functionaliteit.