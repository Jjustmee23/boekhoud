"""
Migratiescript om de nieuwe kolommen voor gedeelde mailbox toe te voegen aan de email_settings tabel.
"""

import os
import logging
import sys
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Zorg ervoor dat we de app modules kunnen importeren
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import EmailSettings
import sqlalchemy as sa
from sqlalchemy.sql import text

def add_shared_mailbox_columns():
    """
    Voegt de kolommen toe voor gedeelde mailbox ondersteuning aan de email_settings tabel
    """
    try:
        with app.app_context():
            # Controleer of de kolommen al bestaan
            inspector = sa.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('email_settings')]
            
            # Controleer en voeg elke kolom toe indien nodig
            if 'ms_graph_shared_mailbox' not in columns:
                logger.info("Kolom 'ms_graph_shared_mailbox' toevoegen aan email_settings tabel")
                db.session.execute(text(
                    "ALTER TABLE email_settings ADD COLUMN ms_graph_shared_mailbox VARCHAR(100)"
                ))
                
            if 'ms_graph_use_shared_mailbox' not in columns:
                logger.info("Kolom 'ms_graph_use_shared_mailbox' toevoegen aan email_settings tabel")
                db.session.execute(text(
                    "ALTER TABLE email_settings ADD COLUMN ms_graph_use_shared_mailbox BOOLEAN DEFAULT FALSE"
                ))
                
            # Commit de wijzigingen
            db.session.commit()
            logger.info("Migratie voltooid: Kolommen voor gedeelde mailbox toegevoegd aan email_settings tabel")
            
    except Exception as e:
        logger.error(f"Fout bij het uitvoeren van de migratie: {str(e)}")
        db.session.rollback()
        raise

if __name__ == "__main__":
    logger.info("Start migratie voor het toevoegen van gedeelde mailbox kolommen")
    add_shared_mailbox_columns()
    logger.info("Migratie voltooid!")