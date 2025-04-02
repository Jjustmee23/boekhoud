# Gebruikshandleiding voor Installatie op een Privé Server

Deze handleiding helpt u bij het opzetten van deze op Flask gebaseerde factureringsapplicatie op uw privé Ubuntu 22.04 server met Docker, PostgreSQL en SSL-ondersteuning.

## Vereisten

Voordat u begint, zorg ervoor dat u beschikt over:

1. Een schone Ubuntu 22.04 server met root-toegang
2. Een domeinnaam die naar het IP-adres van uw server verwijst
3. Basiskennis van de Linux-commandoregel

## Stap 1: Initiële Serverinstallatie

Maak verbinding met uw server via SSH:

```bash
ssh root@uw-server-ip
```

Update het systeem:

```bash
apt-get update && apt-get upgrade -y
```

Maak een niet-root gebruiker aan met sudo-rechten (optioneel maar aanbevolen):

```bash
adduser uwgebruikersnaam
usermod -aG sudo uwgebruikersnaam
```

Schakel over naar de nieuwe gebruiker:

```bash
su - uwgebruikersnaam
```

## Stap 2: Repository Klonen

Installeer Git als het nog niet geïnstalleerd is:

```bash
sudo apt-get install git -y
```

Kloon de repository:

```bash
git clone https://github.com/Jjustmee23/boekhoud.git /opt/invoicing-app
cd /opt/invoicing-app
```

## Stap 3: Voer het Installatiescript Uit

Maak het setup-script uitvoerbaar en voer het uit:

```bash
chmod +x deployment/setup.sh
sudo ./deployment/setup.sh
```

Dit script zal:
- Uw systeem updaten
- Docker en Docker Compose installeren
- De firewall (UFW) configureren
- Noodzakelijke directories aanmaken

Log uit en log opnieuw in, of voer uit:

```bash
newgrp docker
```

## Stap 4: Configureer Omgevingsvariabelen

Maak uw omgevingsbestand aan:

```bash
cp .env.example .env
```

Bewerk het bestand om uw specifieke instellingen toe te voegen:

```bash
nano .env
```

Configureer minimaal:
- Database-inloggegevens
- Session secret
- E-mailinstellingen als u e-mailfunctionaliteit gebruikt
- Domeinnaam

Voorbeeld:
```
# Database Configuratie
POSTGRES_USER=uw_db_gebruiker
POSTGRES_PASSWORD=uw_veilige_wachtwoord
POSTGRES_DB=invoicing
DATABASE_URL=postgresql://uw_db_gebruiker:uw_veilige_wachtwoord@db:5432/invoicing

# Flask Configuratie
SESSION_SECRET=uw_zeer_veilige_willekeurige_string
FLASK_ENV=production

# Domein Instellingen
DOMAIN_NAME=uwdomein.nl
```

## Stap 5: De Applicatie Implementeren

Maak het deployment-script uitvoerbaar:

```bash
chmod +x deployment/deploy.sh
```

Voer het deployment-script uit:

```bash
./deployment/deploy.sh
```

Tijdens de implementatie wordt u gevraagd of u SSL-certificaten wilt instellen met Let's Encrypt. Als u ja kiest:

1. Voer uw domeinnaam in wanneer daarom wordt gevraagd
2. Het script zal automatisch:
   - Let's Encrypt-certificaten instellen
   - Nginx configureren met SSL
   - Automatische vernieuwing voor certificaten instellen

Als u al SSL-certificaten heeft, plaats ze in:
- `nginx/ssl/fullchain.pem`
- `nginx/ssl/privkey.pem`

## Stap 6: Automatische Updates en Back-ups Instellen

Maak de scripts uitvoerbaar:

```bash
chmod +x deployment/backup.sh
chmod +x deployment/update.sh
chmod +x deployment/system_update.sh
```

Stel regelmatige database back-ups in (dagelijks om 2 uur 's nachts):

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/invoicing-app/deployment/backup.sh") | crontab -
```

Stel regelmatige systeemupdates in (wekelijks op zondag om 3 uur 's nachts):

```bash
sudo bash -c '(crontab -l 2>/dev/null; echo "0 3 * * 0 /opt/invoicing-app/deployment/system_update.sh") | crontab -'
```

## Stap 7: Updaten vanaf GitHub

Wanneer u wilt updaten vanaf GitHub zonder gegevens te verliezen:

```bash
cd /opt/invoicing-app
./deployment/update.sh
```

Dit zal:
1. Een database back-up maken
2. De laatste wijzigingen van GitHub ophalen
3. De applicatie indien nodig herbouwen
4. De services herstarten

## Directe Installatie (Zonder Docker)

Als u de voorkeur geeft aan een directe installatie zonder Docker:

```bash
chmod +x deployment/direct_install.sh
sudo ./deployment/direct_install.sh
```

Dit script zal:
1. Alle benodigde pakketten installeren
2. Een PostgreSQL-database instellen
3. Een Python virtual environment aanmaken
4. De applicatie configureren
5. Nginx instellen
6. Een systemd-service aanmaken

## Probleemoplossing

### Applicatielogs Controleren

```bash
cd /opt/invoicing-app
docker-compose logs -f
```

### Containerstatus Controleren

```bash
docker-compose ps
```

### Databaseverbinding Controleren

```bash
docker-compose exec db psql -U uw_db_gebruiker -d invoicing
```

### De Applicatie Opnieuw Starten

```bash
docker-compose down
docker-compose up -d
```

### Nginx-logs Bekijken

```bash
docker-compose logs nginx
```

### SSL-certificaatstatus Controleren

```bash
certbot certificates
```

## Veiligheidsaanbevelingen

1. **Houd uw server up-to-date**: Regelmatige updates zijn cruciaal voor veiligheid.
2. **Beveilig database-wachtwoorden**: Gebruik sterke, unieke wachtwoorden.
3. **Beperk SSH-toegang**: Overweeg alleen op sleutel gebaseerde authenticatie te gebruiken.
4. **Regelmatige back-ups**: Test af en toe uw back-up herstelproces.
5. **Firewall-configuratie**: Open alleen poorten die noodzakelijk zijn.
6. **Monitoring**: Overweeg monitoring voor uw server in te stellen.

## Geavanceerde Configuratie

Voor meer geavanceerde configuratieopties, bekijk de volgende bestanden:

- `docker-compose.yml`: Pas container-instellingen aan.
- `nginx/conf.d/app.conf`: Pas Nginx-instellingen aan.
- `Dockerfile`: Wijzig het containeropbouwproces.

## Ondersteuning

Als u problemen ondervindt, kunt u:

1. De logs controleren zoals beschreven in het probleemoplossinggedeelte
2. De projectdocumentatie raadplegen
3. Een issue aanmaken op de GitHub-repository: https://github.com/Jjustmee23/boekhoud