"""
Hulpscript om te testen of admin credentials correct worden verwerkt
"""
import os
import logging
from app import app, db
from models import EmailSettings

# Logging configureren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Toon de huidige email instellingen"""
    with app.app_context():
        # Systeeminstellingen ophalen
        system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
        
        if system_settings:
            logger.info("Systeem e-mailinstellingen gevonden:")
            logger.info(f"Client ID: {system_settings.ms_graph_client_id}")
            # Verberg een deel van de client secret voor veiligheid
            if system_settings.ms_graph_client_secret:
                secret_length = len(system_settings.ms_graph_client_secret)
                visible_part = 4 if secret_length > 8 else min(2, secret_length)
                masked_secret = (
                    system_settings.ms_graph_client_secret[:visible_part] + 
                    "*" * (secret_length - visible_part)
                )
                logger.info(f"Client Secret: {masked_secret} (lengte: {secret_length})")
                
                # Controleer of het een gecodeerde waarde lijkt
                if system_settings.ms_graph_client_secret.startswith("Nm"):
                    logger.warning("Let op: Client Secret lijkt een gecodeerde waarde te zijn (begint met 'Nm')")
            else:
                logger.info("Client Secret: Niet ingesteld")
                
            logger.info(f"Tenant ID: {system_settings.ms_graph_tenant_id}")
            logger.info(f"Sender Email: {system_settings.ms_graph_sender_email}")
            logger.info(f"MS Graph ingeschakeld: {system_settings.use_ms_graph}")
        else:
            logger.warning("Geen systeem e-mailinstellingen gevonden")

        # Bekijk ook de omgevingsvariabelen
        logger.info("\nOmgevingsvariabelen:")
        client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
        client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
        tenant_id = os.environ.get("MS_GRAPH_TENANT_ID")
        sender_email = os.environ.get("MS_GRAPH_SENDER_EMAIL")
        
        logger.info(f"MS_GRAPH_CLIENT_ID: {'Ingesteld' if client_id else 'Niet ingesteld'}")
        logger.info(f"MS_GRAPH_CLIENT_SECRET: {'Ingesteld' if client_secret else 'Niet ingesteld'}")
        logger.info(f"MS_GRAPH_TENANT_ID: {'Ingesteld' if tenant_id else 'Niet ingesteld'}")
        logger.info(f"MS_GRAPH_SENDER_EMAIL: {'Ingesteld' if sender_email else 'Niet ingesteld'}")

if __name__ == "__main__":
    main()