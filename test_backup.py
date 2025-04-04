"""
Test script voor de backup functionaliteit.
"""
import os
import logging
from app import app, db
from models import Workspace, BackupSettings
from backup_service import BackupService

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_backup_service():
    """Test de backup service functionaliteit."""
    with app.app_context():
        # Maak een BackupService instantie
        backup_service = BackupService(app, db)
        
        # Haal de eerste werkruimte op om te testen
        workspace = Workspace.query.first()
        
        if not workspace:
            logger.error("Geen werkruimtes gevonden om te testen.")
            return
        
        logger.info(f"Test backup voor werkruimte: {workspace.name} (ID: {workspace.id})")
        
        # Controleer of er al backup_settings bestaan voor deze werkruimte
        backup_settings = BackupSettings.query.filter_by(workspace_id=workspace.id).first()
        
        # Als er geen instellingen zijn, maak ze aan met standaardwaarden
        if not backup_settings:
            logger.info(f"Geen backup instellingen gevonden voor werkruimte {workspace.name}, aanmaken...")
            backup_settings = BackupSettings(
                workspace_id=workspace.id,
                plan='free',
                backup_enabled=True,
                include_uploads=True,
                auto_backup_enabled=False,
                auto_backup_interval='daily',
                auto_backup_time='02:00',
                retention_days=7
            )
            db.session.add(backup_settings)
            db.session.commit()
            logger.info("Backup instellingen aangemaakt.")
        
        # Test het maken van een backup
        logger.info("Start het maken van een test backup...")
        backup_info = backup_service.create_backup(
            workspace_id=workspace.id,
            include_uploads=True,
            backup_name="test_backup"
        )
        
        logger.info(f"Backup info: {backup_info}")
        
        # Lijst alle backups
        backups = backup_service.list_backups(workspace_id=workspace.id)
        logger.info(f"Beschikbare backups: {backups}")
        
        # Test het herstellen van de backup
        if backups:
            latest_backup = backups[0]
            backup_path = os.path.join(os.environ.get("BACKUP_DIR", "backups"), latest_backup['filename'])
            
            logger.info(f"Test het herstellen van backup: {backup_path}")
            result = backup_service.restore_backup(
                backup_path=backup_path,
                workspace_id=workspace.id,
                include_uploads=True
            )
            
            logger.info(f"Herstel resultaat: {'Succesvol' if result else 'Mislukt'}")
        
        logger.info("Backup test voltooid.")

if __name__ == "__main__":
    test_backup_service()