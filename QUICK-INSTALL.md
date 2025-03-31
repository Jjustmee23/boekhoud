# Snelle Installatie Handleiding (Ubuntu 22.04)

Deze handleiding bevat de absolute minimale stappen om het facturatie systeem te installeren op een Ubuntu 22.04 server.

## Stap 1: Installatie script downloaden

Kopieer en plak het volgende commando om het installatie script te downloaden:

```bash
wget -O setup-ubuntu.sh https://raw.githubusercontent.com/jouw-gebruikersnaam/facturatie-systeem/main/setup-ubuntu.sh && chmod +x setup-ubuntu.sh
```

## Stap 2: Installatie script uitvoeren

```bash
sudo ./setup-ubuntu.sh
```

Volg de instructies van het installatie script:
1. Bevestig de installatie
2. Geef een installatiepad op (standaard: /var/www/facturatie)
3. Vul de Git repository URL in
4. Configureer het .env bestand
5. Start de Docker containers

## Stap 3: Controleer de installatie

```bash
cd /var/www/facturatie
docker-compose ps
```

De applicatie zou nu moeten draaien op http://localhost:5000

## Basisbeheer commando's

### Applicatie starten
```bash
cd /var/www/facturatie
docker-compose up -d
```

### Applicatie stoppen
```bash
cd /var/www/facturatie
docker-compose down
```

### Updates ophalen
```bash
cd /var/www/facturatie
./deploy.sh
```

### Database backup maken
```bash
cd /var/www/facturatie
./backup-database.sh
```

### Logs bekijken
```bash
cd /var/www/facturatie
docker-compose logs -f web
```

Voor meer gedetailleerde instructies, raadpleeg de [volledige README.md](README.md) en [deployment-instructies.md](deployment-instructies.md).