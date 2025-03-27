"""
Test script om te controleren of de versleuteling van client secret correct werkt
"""
import os
import logging
from app import app, db
from models import EmailSettings

# Logging configureren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_secret_storage():
    """Test of client secrets correct worden opgeslagen zonder versleuteling"""
    with app.app_context():
        # Bestaande instellingen ophalen of nieuwe aanmaken
        settings = EmailSettings.query.filter_by(workspace_id=None).first()
        
        if not settings:
            logger.info("Geen systeem-instellingen gevonden, nieuwe aanmaken...")
            settings = EmailSettings(
                workspace_id=None,
                use_ms_graph=True,
                ms_graph_client_id="test-client-id",
                ms_graph_client_secret="test-secret-value",
                ms_graph_tenant_id="test-tenant-id",
                ms_graph_sender_email="test@example.com",
                default_sender_name="Test Sender"
            )
            db.session.add(settings)
            db.session.commit()
            logger.info("Nieuwe instellingen aangemaakt")
        
        # Controleer of encrypt_secret en decrypt_secret correct werken
        test_secret = "TestGeheimeSleutel123"
        encrypted = EmailSettings.encrypt_secret(test_secret)
        decrypted = EmailSettings.decrypt_secret(encrypted)
        
        logger.info(f"Originele secret: {test_secret}")
        logger.info(f"Gecodeerde secret: {encrypted}")
        logger.info(f"Gedecodeerde secret: {decrypted}")
        
        if test_secret == encrypted and test_secret == decrypted:
            logger.info("SUCCESS: Versleuteling uitgeschakeld - geheime sleutel blijft ongewijzigd")
        else:
            logger.error("ERROR: Versleuteling werkt niet zoals verwacht")
        
        # Update de bestaande instellingen met een test waarde
        old_secret = settings.ms_graph_client_secret
        settings.ms_graph_client_secret = "NieuwTestSecret456"
        db.session.commit()
        
        # Haal de instellingen opnieuw op om te controleren of de waarde correct is opgeslagen
        refreshed = EmailSettings.query.filter_by(workspace_id=None).first()
        logger.info(f"Oude secret: {old_secret}")
        logger.info(f"Nieuwe secret (ingesteld): NieuwTestSecret456")
        logger.info(f"Nieuwe secret (opgehaald): {refreshed.ms_graph_client_secret}")
        
        if refreshed.ms_graph_client_secret == "NieuwTestSecret456":
            logger.info("SUCCESS: Secret correct opgeslagen in database zonder versleuteling")
        else:
            logger.error("ERROR: Secret niet correct opgeslagen in database")
        
        # Reset naar de originele waarde
        settings.ms_graph_client_secret = old_secret
        db.session.commit()
        logger.info("Originele waarde hersteld")

if __name__ == "__main__":
    test_secret_storage()