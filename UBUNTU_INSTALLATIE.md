# Snelle Installatie voor Ubuntu 22.04

Dit is een verkorte handleiding voor het installeren van het Facturatie & Boekhouding Systeem op een schone Ubuntu 22.04 server.

## 1. Systeem voorbereiden

Update het systeem:

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

## 2. Installatiescript downloaden

```bash
wget https://raw.githubusercontent.com/gebruiker/facturatie-systeem/main/ubuntu-setup.sh
chmod +x ubuntu-setup.sh
```

## 3. Installatiescript uitvoeren

```bash
sudo ./ubuntu-setup.sh
```

Volg de vragen tijdens de installatie:
- Installatie directory (standaard: /opt/facturatie)
- Domeinnaam (optioneel, laat leeg voor IP-gebaseerde toegang)
- GitHub repository URL (optioneel)

## 4. Na de installatie

- Bewaar de getoonde database wachtwoorden
- Controleer of alles werkt door naar http://SERVER_IP in je browser te gaan
- (Als je een domeinnaam hebt ingesteld) Ga naar https://JOUW_DOMEIN

## 5. Basisbeheer

Start/stop containers:
```bash
cd /opt/facturatie
docker-compose up -d    # Start
docker-compose down     # Stop
```

Bekijk logs:
```bash
cd /opt/facturatie
docker-compose logs -f
```

Maak een backup:
```bash
cd /opt/facturatie
./backup-database.sh
```

Update systeem:
```bash
cd /opt/facturatie
./deploy.sh
```

## 6. Probleemoplossing

Als er iets niet werkt:

1. Controleer de logs:
```bash
cd /opt/facturatie
docker-compose logs -f
```

2. Herstart de containers:
```bash
cd /opt/facturatie
docker-compose restart
```

3. Controleer Nginx:
```bash
sudo nginx -t
sudo systemctl status nginx
```

## 7. Meer informatie

Voor gedetailleerde instructies, zie de volledige documentatie in INSTALLATIE.md