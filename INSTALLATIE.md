# Installatie van Boekhoudapplicatie

Dit document beschrijft hoe je de boekhoudapplicatie volledig automatisch kunt installeren op een Ubuntu 22.04 server.

## Vereisten

Voordat je begint met de installatie, zorg ervoor dat je het volgende hebt:

1. Een server met Ubuntu 22.04 (minimaal 2GB RAM, 2 CPU cores en 20GB schijfruimte aanbevolen)
2. Een domeinnaam die je wilt gebruiken voor de applicatie
3. Root-toegang tot de server
4. DNS-instellingen die je domeinnaam naar het IP-adres van je server verwijzen (A-record)

## Snelle Installatie (één command)

Om de applicatie in één keer te installeren, voer je het volgende commando uit op je server:

```bash
wget -O installeer-boekhoud-app.sh https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/installeer-boekhoud-app.sh && chmod +x installeer-boekhoud-app.sh && sudo ./installeer-boekhoud-app.sh
```

Volg de instructies op het scherm om de installatie te voltooien.

## Stap-voor-Stap Installatie

Als je liever stap voor stap installeert, volg dan deze instructies:

1. Log in op je server via SSH:
   ```bash
   ssh gebruiker@jouw-server-ip
   ```

2. Download het installatiescript:
   ```bash
   wget -O installeer-boekhoud-app.sh https://raw.githubusercontent.com/Jjustmee23/boekhoud/main/installeer-boekhoud-app.sh
   ```

3. Maak het script uitvoerbaar:
   ```bash
   chmod +x installeer-boekhoud-app.sh
   ```

4. Voer het script uit als root:
   ```bash
   sudo ./installeer-boekhoud-app.sh
   ```

5. Volg de instructies op het scherm en vul de gevraagde informatie in:
   - Domeinnaam voor de applicatie
   - E-mailadres voor SSL-certificaten en admin account
   - Database wachtwoord (of laat het script er een genereren)
   - Installatiemap (of accepteer de standaardmap)

6. Wacht tot de installatie is voltooid. Dit kan enkele minuten duren.

7. Na installatie kun je inloggen op je applicatie via:
   ```
   https://jouw-domein.nl
   ```

## Wat het Script Doet

Het installatiescript voert de volgende acties uit:

1. Updaten van het systeem en installeren van benodigde pakketten
2. Installeren van Docker en Docker Compose
3. Configureren van de firewall (UFW) met poorten 80, 443 en 22 open
4. Aanmaken van de applicatiemap en structuur
5. Genereren van DH-parameters voor verbeterde SSL-veiligheid
6. Aanmaken van het .env configuratiebestand
7. Opstarten van de Docker-containers
8. Aanmaken van beheer- en troubleshooting-scripts

## Na de Installatie

Na installatie krijg je:

1. Een volledig werkende boekhoudapplicatie op je domein
2. Een beheerscript (`beheer.sh`) voor eenvoudig onderhoud
3. Een troubleshooting-script (`troubleshoot-domain.sh`) om problemen op te lossen
4. Automatische SSL-certificaten via Let's Encrypt
5. Een beveiligde PostgreSQL database
6. Automatische backups (via het beheerscript)

## Beheer en Updates van de Applicatie

### Dagelijks beheer

Na installatie kun je de applicatie beheren met het meegeleverde beheerscript:

```bash
sudo /opt/boekhoudapp/beheer.sh
```

Dit script biedt de volgende opties:

1. Start alle containers
2. Stop alle containers
3. Herstart alle containers
4. Bekijk container status
5. Bekijk logs
6. Troubleshooting uitvoeren
7. Database backup maken
8. Database backup herstellen
9. Systeem updaten

### Automatische Updates

Voor het volledig automatisch bijwerken van de applicatie, gebruik het update-script:

```bash
sudo /opt/boekhoudapp/update-app.sh
```

Dit script zal:
1. Automatisch backups maken van de database en configuratie
2. De nieuwste code ophalen
3. Ontbrekende afhankelijkheden installeren
4. De applicatie herstarten

Het update-script behoudt al je aangepaste instellingen en gegevens en rolt automatisch terug bij problemen.

## Troubleshooting

Als je problemen ondervindt, gebruik dan het troubleshooting-script:

```bash
sudo /opt/boekhoudapp/troubleshoot-domain.sh
```

Dit script zal diagnostische informatie geven en suggesties doen voor het oplossen van veelvoorkomende problemen.

## Veiligheid

De installatie zorgt voor:

1. Automatische SSL-certificaten voor versleutelde verbindingen
2. Sterke DH-parameters voor verbeterde SSL-veiligheid
3. Firewall-configuratie die alleen noodzakelijke poorten openstelt
4. Veilige wachtwoorden voor database en admin account
5. Gecontroleerde containerisatie via Docker

## Support

Voor ondersteuning, raadpleeg:

- De documentatie in de GEBRUIKSHANDLEIDING.md en README.md bestanden
- Gebruik het troubleshooting-script voor diagnose
- Neem contact op met de ontwikkelaar via [contactinfo]