# Factuur en Administratie Applicatie

Een uitgebreide webapplicatie voor facturatie en administratie, gebouwd met Flask en optimaal voor Benelux bedrijven.

## Beschrijving

Deze applicatie biedt een complete oplossing voor facturatie, boekhouding en administratie voor bedrijven in België en Nederland. Het systeem is ontwikkeld met Flask en heeft een PostgreSQL database voor gegevensopslag.

### Functionaliteiten

- Facturatie en offertes
- Klantenbeheer
- Werkruimtes voor verschillende bedrijven
- E-mail integratie via Microsoft Graph API
- Betalingsverwerking via Mollie
- Abonnementen en licentiebeheer
- Rapportage en analyses
- BTW-berekeningen voor de Benelux
- Meertalige ondersteuning
- Gebruikersbeheer met verschillende rechten

## Installatie en Configuratie

### Vereisten

- Python 3.11 of hoger
- PostgreSQL database
- De benodigde Python-packages zijn opgenomen in requirements.txt

### Configuratie

1. **Database instellingen**

   Zorg ervoor dat de PostgreSQL database is geconfigureerd en stel de juiste verbindingsgegevens in via de `DATABASE_URL` omgevingsvariabele.

2. **E-mail configuratie**

   Voor e-mailfunctionaliteit kan Microsoft Graph API worden gebruikt, configureer de volgende variabelen:
   - MS_GRAPH_CLIENT_ID
   - MS_GRAPH_CLIENT_SECRET
   - MS_GRAPH_TENANT_ID
   - MS_GRAPH_SENDER_EMAIL

3. **Betalingen (Mollie)**

   Voor betalingsverwerking, stel de Mollie API-sleutel in:
   - MOLLIE_API_KEY

### Applicatie Starten

```bash
# Start de applicatie
python main.py
```

De webapplicatie is standaard beschikbaar op `http://localhost:5000`

## Ondersteuning

Voor ondersteuning, neem contact op via e-mail op [jouw-email].