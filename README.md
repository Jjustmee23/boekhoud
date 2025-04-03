# Flask Facturatiesysteem

Een uitgebreid facturatie- en boekhoudoplossing op basis van Flask, speciaal gemaakt voor Belgische en Nederlandse bedrijven. Het biedt geavanceerde servermanagement, flexibiliteit in deployment en regio-specifieke financiële tools.

## Kern Technologieën

- Flask web framework
- Python backend met workspace administratie
- Docker containerisatie en geautomatiseerde deployment
- PostgreSQL database integratie
- MSAL Microsoft Authenticatie
- Geavanceerde Benelux BTW-berekeningen
- Meertalige ondersteuning met geautomatiseerde installatie

## Installatie

Voor gedetailleerde installatie-instructies, zie:
- [Volledige Installatie Handleiding](deployment/README.md)
- [Installatie Checklist](deployment/INSTALLATIE_CHECKLIST.md)

## Deployment Scripts

De volgende deployment scripts zijn beschikbaar in de `deployment/scripts` map:

- `setup_flask_app.sh` - Hoofdinstallatiescript voor Docker-gebaseerde installatie
- `direct_install.sh` - Installatiescript voor directe installatie zonder Docker
- `update.sh` - Script voor het bijwerken van de applicatie
- `backup.sh` - Script voor het maken van database backups
- `system_update.sh` - Script voor systeemupgrades en onderhoud

## Ontwikkeling

Om de ontwikkelomgeving te starten:

```bash
# Start de applicatie in debug mode
python main.py
```

## Licentie

Dit project is eigendom van de auteur en wordt uitsluitend gelicentieerd voor gebruik volgens de voorwaarden in de licentieovereenkomst.