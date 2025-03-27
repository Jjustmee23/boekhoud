"""
Migratie script om e-mail instellingen te converteren van Microsoft Graph API naar Microsoft 365 SMTP met OAuth 2.0

Dit script:
1. Controleert of er instellingen zijn om te migreren
2. Kopieert de relevante instellingen (client_id, client_secret, tenant_id, sender_email)
3. Update de instellingen in de database
"""
import os
import logging
from dotenv import load_dotenv
from flask import Flask
from app import db

# Configureer logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Laad .env bestand voor toegang tot eventuele omgevingsvariabelen
load_dotenv()

def migrate_email_settings():
    """
    Migrateer van Microsoft Graph API naar Microsoft 365 SMTP met OAuth 2.0
    Dezelfde instellingen worden gebruikt, maar de manier waarop ze worden gebruikt verschilt
    """
    from models import EmailSettings
    
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    db.init_app(app)
    
    with app.app_context():
        # Haal alle e-mailinstellingen op (zowel systeem als per workspace)
        email_settings_list = EmailSettings.query.all()
        
        if not email_settings_list:
            logger.info("Geen e-mail instellingen gevonden om te migreren.")
            return
        
        migrated_count = 0
        
        for settings in email_settings_list:
            try:
                # Instellingen zijn al aanwezig, controleer of migratie nodig is
                if settings.use_ms_graph and settings.ms_graph_client_id and settings.ms_graph_client_secret:
                    # Instellingen zijn al aanwezig in het juiste formaat
                    logger.info(f"E-mail instellingen voor workspace_id={settings.workspace_id} al geconfigureerd.")
                    migrated_count += 1
                    continue
                
                # Probeer instellingen te migreren van omgevingsvariabelen als er nog geen zijn
                if not settings.ms_graph_client_id:
                    settings.ms_graph_client_id = os.environ.get("MS_GRAPH_CLIENT_ID", "")
                
                if not settings.ms_graph_client_secret:
                    secret = os.environ.get("MS_GRAPH_CLIENT_SECRET", "")
                    if secret:
                        settings.ms_graph_client_secret = EmailSettings.encrypt_secret(secret)
                
                if not settings.ms_graph_tenant_id:
                    settings.ms_graph_tenant_id = os.environ.get("MS_GRAPH_TENANT_ID", "")
                
                if not settings.ms_graph_sender_email:
                    settings.ms_graph_sender_email = os.environ.get("MS_GRAPH_SENDER_EMAIL", "")
                
                # Schakel MS Graph in als alle benodigde velden aanwezig zijn
                if all([settings.ms_graph_client_id, settings.ms_graph_client_secret,
                        settings.ms_graph_tenant_id, settings.ms_graph_sender_email]):
                    settings.use_ms_graph = True
                    migrated_count += 1
                    logger.info(f"E-mail instellingen succesvol gemigreerd voor workspace_id={settings.workspace_id}")
                else:
                    logger.warning(f"Onvolledige instellingen voor workspace_id={settings.workspace_id}, migratie overgeslagen.")
                
                db.session.commit()
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Fout bij migreren van e-mail instellingen voor workspace_id={settings.workspace_id}: {str(e)}")
        
        # Maak systeeminstellingen aan als deze nog niet bestaan
        system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
        if not system_settings:
            try:
                # Probeer systeeminstellingen te maken van omgevingsvariabelen
                client_id = os.environ.get("MS_GRAPH_CLIENT_ID", "")
                client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET", "")
                tenant_id = os.environ.get("MS_GRAPH_TENANT_ID", "")
                sender_email = os.environ.get("MS_GRAPH_SENDER_EMAIL", "")
                
                if all([client_id, client_secret, tenant_id, sender_email]):
                    system_settings = EmailSettings(
                        workspace_id=None,
                        use_ms_graph=True,
                        ms_graph_client_id=client_id,
                        ms_graph_client_secret=EmailSettings.encrypt_secret(client_secret),
                        ms_graph_tenant_id=tenant_id,
                        ms_graph_sender_email=sender_email,
                        default_sender_name=os.environ.get("EMAIL_FROM_NAME", "MidaWeb")
                    )
                    db.session.add(system_settings)
                    db.session.commit()
                    logger.info("Systeembrede e-mail instellingen succesvol aangemaakt van omgevingsvariabelen.")
                    migrated_count += 1
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Fout bij aanmaken van systeembrede e-mail instellingen: {str(e)}")
        
        logger.info(f"E-mail instellingen migratie voltooid. {migrated_count} instellingen gemigreerd.")

if __name__ == "__main__":
    migrate_email_settings()