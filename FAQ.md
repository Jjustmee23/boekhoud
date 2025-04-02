# Veelgestelde Vragen (FAQ)

## Gebruikersbeheer

### Q: Hoe wijzig ik het admin wachtwoord?
A: Je kunt het admin wachtwoord wijzigen door in te loggen in de applicatie, naar het admin gedeelte te gaan en daar je wachtwoord te wijzigen. Als je het admin wachtwoord bent vergeten, kun je het resetten door een wijziging in de database te maken.

### Q: Hoe voeg ik extra gebruikers toe aan het systeem?
A: Er zijn twee manieren om gebruikers toe te voegen:
1. Als admin, log in en ga naar het gebruikersbeheer om nieuwe gebruikers toe te voegen.
2. Schakel registratie in door ENABLE_REGISTRATION=True in te stellen in je .env bestand.

## Database Beheer

### Q: Hoe maak ik een backup van mijn gegevens?
A: Je kunt een backup maken van de PostgreSQL database met de volgende stappen:
1. Gebruik het `pg_dump` commando om een database dump te maken.
2. Maak regelmatig backups om gegevensverlies te voorkomen.

### Q: Hoe herstel ik een backup?
A: Om een database backup te herstellen:
1. Gebruik het `psql` commando om de backup in te laden in de database.
2. Zorg ervoor dat de applicatie is gestopt voordat je een hersteloperatie uitvoert.

## E-mail Configuratie

### Q: Hoe kan ik e-mails configureren met Microsoft 365 / Office 365?
A: Om e-mails te configureren met Microsoft 365:
1. Maak een `.env` bestand aan in de hoofdmap van de applicatie.
2. Vul de volgende velden in:
   ```
   MS_GRAPH_CLIENT_ID=jouw_client_id
   MS_GRAPH_CLIENT_SECRET=jouw_client_secret
   MS_GRAPH_TENANT_ID=jouw_tenant_id
   MS_GRAPH_SENDER_EMAIL=jouw_email@domein.nl
   ```
3. Herstart de applicatie om de wijzigingen toe te passen.

## Aanpassingen en Uitbreidingen

### Q: Hoe kan ik de layout of het uiterlijk van de applicatie aanpassen?
A: Om het uiterlijk aan te passen:
1. De templates staan in de map templates/
2. CSS-bestanden staan in static/css/
3. Pas deze bestanden aan volgens je wensen
4. Herstart de applicatie om de wijzigingen toe te passen

## Prestaties en Probleemoplossing

### Q: De applicatie is traag, hoe kan ik de prestaties verbeteren?
A: Om de prestaties te verbeteren:
1. Zorg voor voldoende resources op je server (RAM, CPU)
2. Optimaliseer de database met regelmatige onderhoudstaken
3. Controleer de logs op veelvoorkomende fouten
4. Schakel debug mode uit in het .env bestand als je in productie bent
5. Zorg voor adequate database indexen

### Q: Hoe kan ik logging bekijken en problemen diagnosticeren?
A: De applicatielogs kun je vinden in de map 'logs/' in de applicatiemap. Er zijn verschillende logbestanden beschikbaar:
1. app.log - Algemene applicatie logs
2. error.log - Foutmeldingen
3. app.json.log - Gedetailleerde logs in JSON-formaat

## Beveiliging

### Q: Hoe kan ik de beveiliging verbeteren?
A: Om de beveiliging verder te verbeteren:
1. Schakel registratie uit na het aanmaken van alle benodigde accounts: `ENABLE_REGISTRATION=False` in .env
2. Wijzig regelmatig wachtwoorden
3. Zorg voor up-to-date software en afhankelijkheden
4. Maak regelmatig backups
5. Gebruik HTTPS wanneer de applicatie publiek toegankelijk is