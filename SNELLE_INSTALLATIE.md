# Snelle Installatie Boekhoud Systeem

Dit document bevat beknopte stappen voor het installeren van het Boekhoud Systeem op een schone Ubuntu 22.04 server.

## 1. Server voorbereiden
```bash
# Update pakketten
sudo apt update && sudo apt upgrade -y

# Installeer benodigde pakketten
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release git
```

## 2. Docker en Docker Compose installeren
```bash
# Docker GPG key en repository toevoegen
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Installeer Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Download en installeer Docker Compose
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
```

## 3. Installatie via one-command script
```bash
# Download het one-command installatiescript
wget https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/one-command-install.sh

# Maak het uitvoerbaar
chmod +x one-command-install.sh

# Voer het installatiescript uit
sudo ./one-command-install.sh
```
Volg de instructies op het scherm en geef waar nodig input.

## 4. Nginx installeren en configureren
```bash
# Installeer Nginx
sudo apt install -y nginx

# Maak een Nginx configuratie
sudo nano /etc/nginx/sites-available/boekhoud
```

Voeg deze configuratie toe (vervang 'jouw-domein.nl' met je eigen domein of IP):
```
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
    }
    
    client_max_body_size 100M;
}
```

```bash
# Activeer de configuratie
sudo ln -s /etc/nginx/sites-available/boekhoud /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test en herstart Nginx
sudo nginx -t
sudo systemctl restart nginx
```

## 5. SSL configureren (optioneel maar aanbevolen)
```bash
# Installeer Certbot
sudo apt install -y certbot python3-certbot-nginx

# Configureer SSL
sudo certbot --nginx -d jouw-domein.nl
```

## 6. Firewall instellingen (optioneel maar aanbevolen)
```bash
# Configureer firewall
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

## 7. Automatische backups instellen
```bash
# Ga naar de installatiemap
cd /opt/boekhoud

# Configureer dagelijkse backups
sudo ./schedule-backups.sh
```

## Updates deployen

Wanneer je nieuwe wijzigingen wilt deployen:
```bash
# Ga naar de installatiemap
cd /opt/boekhoud

# Voer het deployment script uit
./deploy.sh
```

## Veelgebruikte commando's

**Containers beheren:**
```bash
cd /opt/boekhoud
docker-compose up -d      # Start containers
docker-compose down       # Stop containers
docker-compose restart    # Herstart alle containers
docker-compose restart web # Herstart alleen de web container
docker-compose logs -f    # Bekijk logs
```

**Database backups:**
```bash
cd /opt/boekhoud
./backup-database.sh      # Maak een backup
./restore-database.sh     # Herstel een backup
```

**Troubleshooting:**
```bash
# Controleer container status
docker-compose ps

# Controleer Nginx status
sudo systemctl status nginx

# Controleer logs
docker-compose logs -f
sudo journalctl -u nginx
```

## Omgevingsvariabelen configureren

Als je instellingen wilt aanpassen, bewerk het .env bestand:
```bash
# Bewerk het .env bestand
nano /opt/boekhoud/.env
```

Na het aanpassen van het .env bestand, herstart de containers:
```bash
docker-compose down
docker-compose up -d
```