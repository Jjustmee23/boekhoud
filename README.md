# Facturatie & Boekhouding Systeem

Een compleet facturatie en boekhoudsysteem voor Belgische en Nederlandse bedrijven. Deze applicatie draait op Flask en is geoptimaliseerd voor gebruik in een Docker-omgeving.

## Functies

- Volledige facturatie met BTW berekening voor BE/NL
- Klanten- en leveranciersbeheer
- Kostenplaatsregistratie
- Rapportages en dashboards
- Documentbeheer en bestandsbeheer
- Meertalig (Nederlands, Engels, Frans)
- Gebruikersbeheer met verschillende permissieniveaus
- Workspace-functionaliteit voor meerdere bedrijven/afdelingen
- E-mail integratie (Microsoft Graph API / SMTP / OAuth2)
- Betaalintegratie (Mollie API)
- Automatische backups en database beheer

## Installatie

### Eén-Regel Installatie (Ubuntu 22.04)

Voor de snelste installatie, kopieer en plak deze regel in je terminal:

```bash
sudo bash -c "$(wget -qO- https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/one-command-install.sh)"
```

### Stap-voor-Stap Installatie (Ubuntu 22.04)

1. Download het installatiescript:

```bash
wget https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/ubuntu-setup.sh
chmod +x ubuntu-setup.sh
```

2. Voer het installatiescript uit:

```bash
sudo ./ubuntu-setup.sh
```

3. Volg de instructies in de terminal om de installatie te voltooien.

Voor gedetailleerde installatie-instructies, zie [INSTALLATIE.md](INSTALLATIE.md) of de verkorte versie [QUICK-INSTALL.md](QUICK-INSTALL.md).

### Docker Compose (Voor ervaren gebruikers)

Als je al Docker en Docker Compose hebt geïnstalleerd, kun je het systeem starten met:

```bash
git clone https://github.com/Jjustmee23/boekhoud.git
cd boekhoud
cp .env.example .env
# Bewerk het .env bestand met de juiste instellingen
docker-compose up -d
```

## Configuratie

De belangrijkste configuratie vindt plaats in het `.env` bestand. Kopieer `.env.example` naar `.env` en pas de instellingen aan:

```bash
cp .env.example .env
nano .env
```

Configureer de volgende instellingen:

- Database instellingen (gebruikersnaam, wachtwoord, database naam)
- Applicatie geheime sleutel (voor sessies)
- E-mail instellingen (SMTP of Microsoft OAuth2)
- Betalingsprovider instellingen (Mollie)
- SSL/TLS instellingen (optioneel)
- Logging en monitoring opties

## Veiligheid

Het systeem is voorzien van meerdere veiligheidsmaatregelen:

- **SSL/TLS Encryptie**: Automatische configuratie via Let's Encrypt
- **Database beveiliging**: Veilige wachtwoorden en beperkte toegang
- **Backup & Herstel**: Geautomatiseerde database backups
- **Gebruikers authenticatie**: Veilige login met wachtwoord hashing
- **Geïsoleerde containers**: Docker containers draaien in een veilige omgeving
- **Firewall configuratie**: Automatische instelling van UFW tijdens installatie
- **Permissie beheer**: Gebruikersrollen met verschillende toegangsniveaus

## Beheer

### Start en stop

```bash
# Start containers
docker-compose up -d

# Stop containers
docker-compose down

# Herstart web container
docker-compose restart web
```

### Logs bekijken

```bash
# Alle logs
docker-compose logs -f

# Alleen web logs
docker-compose logs -f web
```

### Updates

```bash
# Update het systeem
./deploy.sh
```

### Backups

```bash
# Handmatige backup
./backup-database.sh

# Backup planning instellen
sudo ./schedule-backups.sh

# Backup herstellen
./restore-database.sh
```

## Documentatie

- [Installatie handleiding](INSTALLATIE.md)
- [Gebruikershandleiding](docs/GEBRUIKERS.md)
- [Beheerdershandleiding](docs/BEHEERDERS.md)
- [Ontwikkelaarshandleiding](docs/ONTWIKKELAARS.md)

## Technische details

Deze applicatie is gebouwd met:

- **Backend**: Python + Flask
- **Database**: PostgreSQL
- **Frontend**: HTML, CSS, JavaScript (Bootstrap 5)
- **Containerization**: Docker + Docker Compose
- **Webserver**: Gunicorn + Nginx
- **PDF-generatie**: WeasyPrint
- **Email**: SMTP of Microsoft Graph API met OAuth2
- **Authenticatie**: Flask-Login + JWT
- **Deployment**: Geautomatiseerde scripts voor installatie, updates, en backups
- **Logging**: Gestructureerde logging met JSON-format
- **Beveiliging**: SSL/TLS via Certbot (Let's Encrypt)
- **Betalingen**: Mollie API integratie

## Systeemvereisten

- Ubuntu 22.04 LTS (aanbevolen)
- Docker en Docker Compose
- 2GB RAM (minimaal)
- 10GB vrije schijfruimte (minimaal)
- Publieke IP of domein voor toegang via internet

## Licentie

Zie het [LICENTIE.md](LICENTIE.md) bestand voor details.

## Contact

Voor vragen of ondersteuning:

- Email: support@jouwbedrijf.nl
- Website: https://www.jouwbedrijf.nl/support