# Facturatie Systeem - Installatiehandleiding voor Ubuntu 22.04

Dit document bevat eenvoudige commando's om het facturatie systeem te installeren, op te starten en te updaten op een Ubuntu 22.04 server.

## Inhoudsopgave
1. [Vereisten](#vereisten)
2. [Initiële installatie](#initiële-installatie)
3. [Applicatie starten](#applicatie-starten)
4. [Applicatie updaten](#applicatie-updaten)
5. [Database backup & herstel](#database-backup--herstel)
6. [Problemen oplossen](#problemen-oplossen)

## Vereisten

Zorg dat je systeem up-to-date is en installeer de benodigde software:

```bash
# Update pakkettenlijst en upgrade bestaande pakketten
sudo apt update && sudo apt upgrade -y

# Installeer vereiste pakketten
sudo apt install -y git docker.io docker-compose python3-pip curl postgresql-client
```

Start en enable Docker:

```bash
sudo systemctl start docker
sudo systemctl enable docker

# Voeg huidige gebruiker toe aan docker groep (vereist uitloggen en weer inloggen)
sudo usermod -aG docker $USER
```

> **Belangrijk**: Log uit en log weer in om de docker groep wijzigingen toe te passen.

## Initiële installatie

### Stap 1: Clone de repository

```bash
# Maak een map voor de applicatie
mkdir -p ~/facturatie
cd ~/facturatie

# Clone de repository
git clone https://github.com/jouw-gebruikersnaam/facturatie-systeem.git .
```

### Stap 2: Configureer de applicatie

```bash
# Maak een .env bestand van het voorbeeld
cp .env.example .env

# Bewerk het .env bestand met je eigen instellingen
nano .env
```

Zorg dat je ten minste de volgende variabelen configureert:
- `DATABASE_URL`: Connectie string voor de PostgreSQL database
- `SESSION_SECRET`: Een willekeurige string om sessies te beveiligen
- Overige API sleutels en instellingen

### Stap 3: Bouw en start de applicatie met Docker

```bash
# Maak de scripts uitvoerbaar
chmod +x *.sh

# Start de applicatie met Docker Compose
docker-compose up -d
```

De applicatie is nu beschikbaar op http://localhost:5000

## Applicatie starten

### Applicatie starten met Docker Compose

```bash
cd ~/facturatie
docker-compose up -d
```

### Applicatie stoppen

```bash
cd ~/facturatie
docker-compose down
```

## Applicatie updaten

### Methode 1: Volledig update script

```bash
cd ~/facturatie
./deploy.sh
```

Dit script haalt de laatste wijzigingen op, maakt een backup van de database en herstart de applicatie.

### Methode 2: Test update script

```bash
cd ~/facturatie
./test-deploy.sh
```

Dit script doet een update zonder de productiedatabase te beïnvloeden. Gebruik deze optie om wijzigingen te testen.

### Methode 3: Handmatige update

```bash
cd ~/facturatie

# Haal de laatste wijzigingen op
git pull

# Herstart containers (rebuild als nodig)
docker-compose up -d --build
```

## Database backup & herstel

### Database backup maken

```bash
cd ~/facturatie
./backup-database.sh
```

Backups worden opgeslagen in de `db_backups` map met timestamp.

### Database herstellen

```bash
cd ~/facturatie
./restore-database.sh
```

Volg de instructies in het herstelscript om een specifieke backup te selecteren.

## Problemen oplossen

### Bekijk applicatie logs

```bash
# Bekijk de laatste 100 regels logs
docker-compose logs --tail=100 web

# Logs volgen (Ctrl+C om te stoppen)
docker-compose logs -f web
```

### Controleer database verbinding

```bash
# Test database connectie vanuit container
docker-compose exec web python -c "from app import db; print('Database verbinding OK' if db.engine.connect() else 'Fout')"
```

### Herstart de applicatie

```bash
cd ~/facturatie
docker-compose restart web
```

### Run database migraties handmatig

```bash
cd ~/facturatie
docker-compose exec web python run_migrations.py
```

### Container shell toegang

```bash
docker-compose exec web /bin/bash
```

## Één-commando installatie (alles in één keer)

Kopieer en plak het volgende om de applicatie in één keer te installeren:

```bash
sudo apt update && sudo apt upgrade -y && \
sudo apt install -y git docker.io docker-compose python3-pip curl postgresql-client && \
sudo systemctl start docker && \
sudo systemctl enable docker && \
sudo usermod -aG docker $USER && \
mkdir -p ~/facturatie && \
cd ~/facturatie && \
git clone https://github.com/jouw-gebruikersnaam/facturatie-systeem.git . && \
cp .env.example .env && \
echo "Bewerk het .env bestand voordat je doorgaat!" && \
echo "Voer uit: nano .env" && \
echo "Na het bewerken van .env, voer uit: chmod +x *.sh && docker-compose up -d"
```

> **Belangrijk**: Na het uitvoeren van bovenstaand commando moet je nog steeds het .env bestand bewerken en opnieuw inloggen om de docker groep wijzigingen toe te passen.