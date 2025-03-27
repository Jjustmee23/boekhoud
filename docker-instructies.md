# Docker Instructies voor Facturatie & Boekhouding Systeem

## Vereisten

- Docker geïnstalleerd op uw systeem
- Docker Compose geïnstalleerd op uw systeem
- Microsoft Azure applicatie voor OAuth (voor e-mailfunctionaliteit)

## Opzetten en starten

1. Zorg ervoor dat u zich in de hoofdmap van het project bevindt waar `docker-compose.yml` staat

2. Maak een `.env` bestand aan in de hoofdmap met de volgende variabelen voor Microsoft OAuth:

```
MS_GRAPH_CLIENT_ID=uw_client_id
MS_GRAPH_CLIENT_SECRET=uw_client_secret
MS_GRAPH_TENANT_ID=uw_tenant_id
MS_GRAPH_SENDER_EMAIL=email@uwdomein.com
```

3. Start de containers:

```bash
docker-compose up -d
```

3. De applicatie is nu beschikbaar op http://localhost:5000

## Database gegevens

- PostgreSQL draait op: localhost:5432
- Database naam: facturatie
- Gebruikersnaam: postgres
- Wachtwoord: postgres

## Beheer

### Services stoppen

```bash
docker-compose down
```

### Logbestanden bekijken

```bash
docker-compose logs -f web
```

### Container opnieuw bouwen na wijzigingen

```bash
docker-compose build web
docker-compose up -d
```

## Geüploade bestanden

De map `static/uploads` wordt gemount als een volume, zodat geüploade facturen bewaard blijven, zelfs als u de containers opnieuw opbouwt of verwijdert.

## Microsoft Azure App configuratie

Voor de OAuth-functionaliteit moet u een app registreren in de Microsoft Azure portal:

1. Ga naar [Azure Portal](https://portal.azure.com) en navigeer naar Azure Active Directory
2. Ga naar 'App Registrations' en klik op 'New Registration'
3. Voer een naam in voor uw applicatie
4. Selecteer 'Accounts in any organizational directory and personal Microsoft accounts'
5. Voer uw redirect URL in: `https://uw-domein.com/auth/microsoft/callback`
6. Ga naar 'API Permissions' en voeg de volgende permissions toe:
   - Microsoft Graph > Delegated permissions > Mail.Send
   - Microsoft Graph > Delegated permissions > User.Read (optioneel)
7. Klik op 'Grant admin consent' voor deze permissies
8. Ga naar 'Certificates & Secrets' en maak een nieuwe Client Secret aan
9. Noteer de volgende waardes voor uw `.env` bestand:
   - Client ID: te vinden in Overview pagina
   - Client Secret: de geheime sleutel die u zojuist heeft aangemaakt
   - Tenant ID: te vinden in de Overview pagina
   
Zorg ervoor dat u het correcte e-mailadres instelt in de `MS_GRAPH_SENDER_EMAIL` variabele. Dit bepaalt namens welk e-mailadres de e-mails worden verzonden.

## Beveiliging

Voor productiegebruik:

1. Wijzig de wachtwoorden en sleutels in `docker-compose.yml`
2. Sla uw OAuth geheimen veilig op in het `.env` bestand en zorg dat dit niet in versiebeheer wordt opgenomen
3. Overweeg een reverse proxy zoals Nginx met SSL te gebruiken
4. Beperk netwerktoegang tot alleen noodzakelijke poorten

## Problemen oplossen

### Database verbindingsproblemen

Als de applicatie niet kan verbinden met de database, controleer:

```bash
docker-compose ps
```

Zorg ervoor dat zowel de 'web' als 'db' services draaien.

### Permissie problemen voor geüploade bestanden

Als er problemen zijn met het uploaden van bestanden, controleer de permissies van de 'static/uploads' directory:

```bash
sudo chmod -R 777 static/uploads
```

### Container opnieuw starten

```bash
docker-compose restart web
```