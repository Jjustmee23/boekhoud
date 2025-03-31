# Gebruikshandleiding Facturatie Applicatie

Deze handleiding helpt je bij het opzetten en gebruik van de facturatie applicatie nadat deze is geïnstalleerd op je server.

## 1. Eerste inloggen

Na de installatie met Docker kun je inloggen op de applicatie via je domein:

- **URL**: https://jouw-domein.nl
- **Standaard gebruikersnaam**: admin
- **Standaard wachtwoord**: admin123

**Belangrijk**: Wijzig direct na je eerste inloggen het wachtwoord via het profiel menu!

## 2. Systeeminstellingen configureren

Voordat je de applicatie kunt gebruiken, moet je enkele basisinstellingen configureren:

1. Ga naar **Admin > Instellingen**
2. Configureer:
   - Bedrijfsgegevens (naam, adres, BTW-nummer)
   - E-mail instellingen
   - Betalingsopties (Mollie)
   - Standaard BTW-tarieven

## 3. Workspaces aanmaken

De applicatie werkt met workspaces (werkruimtes) voor verschillende klantomgevingen:

1. Ga naar **Admin > Workspaces**
2. Klik op **Nieuwe Workspace**
3. Vul de gegevens in:
   - Naam
   - Beschrijving
   - Klantgegevens
   - Gebruikers met toegang

## 4. Gebruikers toevoegen

Je kunt meerdere gebruikers toegang geven tot de applicatie:

1. Ga naar **Admin > Gebruikers**
2. Klik op **Nieuwe Gebruiker**
3. Vul de gebruikersgegevens in
4. Ken rollen en permissions toe
5. Selecteer de workspaces waartoe de gebruiker toegang heeft

## 5. Klanten beheren

Per workspace kun je klanten beheren:

1. Selecteer de workspace
2. Ga naar **Klanten**
3. Klik op **Nieuwe Klant** om een klant toe te voegen
4. Vul alle benodigde informatie in:
   - Bedrijfsgegevens
   - Contactpersonen
   - BTW-nummer
   - Facturatie-instellingen

## 6. Facturen aanmaken en versturen

Je kunt facturen aanmaken, bewerken en versturen:

1. Ga naar **Facturen**
2. Klik op **Nieuwe Factuur**
3. Selecteer de klant
4. Voeg factuurregels toe
5. Stel factuurdatum en vervaldatum in
6. Bewaar de factuur
7. Verstuur de factuur via e-mail met de "Versturen" knop

## 7. Betalingen bijhouden

Betalingen worden automatisch bijgewerkt als je Mollie gebruikt:

1. Ga naar **Facturen**
2. Bekijk de status van betalingen
3. Handmatige betalingen kun je registreren via de factuurdetailpagina

## 8. Rapportages genereren

De applicatie biedt verschillende rapportages:

1. Ga naar **Rapportages**
2. Kies het type rapport:
   - Omzetoverzicht
   - BTW-aangifte
   - Debiteuren
   - Winstgevendheid

## 9. Logs bekijken

Als beheerder kun je systeemlogboeken bekijken:

1. Ga naar **Admin > Logboeken**
2. Bekijk de verschillende logbestanden
3. Gebruik filters om specifieke events te vinden

## 10. Backup en restore

Regelmatige backups zijn belangrijk:

1. Gebruik de commando's in README.md om database backups te maken
2. Sla ook uploadbestanden op die in de static/uploads map staan
3. Test regelmatig of je backups kunnen worden teruggezet

## Ondersteuning

Voor verdere ondersteuning, raadpleeg de documentatie of neem contact op met de ontwikkelaar.