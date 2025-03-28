"""
Script om de workspace tabel te updaten met het is_active veld

Dit script moet worden uitgevoerd bij het upgraden van de applicatie
om de database structuur bij te werken.
"""

from app import app, db
from models import Workspace
import logging

def migrate_workspace_table():
    """
    Controleert en voegt ontbrekende kolommen toe aan de workspace tabel
    """
    try:
        with app.app_context():
            # Alle kolommen die we willen controleren en toevoegen indien nodig
            columns_to_check = [
                {"name": "is_active", "type": "BOOLEAN DEFAULT TRUE", "description": "activeert/deactiveert werkruimte"},
                {"name": "updated_at", "type": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "description": "laatste update datum"},
            ]
            
            from sqlalchemy import text
            conn = db.engine.connect()
            
            for column in columns_to_check:
                column_name = column["name"]
                column_type = column["type"]
                column_desc = column["description"]
                
                # Check of de kolom bestaat
                result = conn.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = 'workspaces' AND column_name = '{column_name}';"))
                column_exists = result.fetchone() is not None
                
                if not column_exists:
                    print(f"Kolom '{column_name}' bestaat nog niet. Voeg deze toe...")
                    conn.execute(text(f"ALTER TABLE workspaces ADD COLUMN {column_name} {column_type};"))
                    conn.commit()
                    print(f"Kolom '{column_name}' ({column_desc}) is succesvol toegevoegd aan de 'workspaces' tabel.")
                    logging.info(f"Database migratie: '{column_name}' kolom toegevoegd aan workspaces tabel")
                else:
                    print(f"Kolom '{column_name}' bestaat al. Geen actie nodig.")
            
            conn.close()
                
    except Exception as e:
        print(f"Er is een fout opgetreden bij het migreren van de database: {str(e)}")
        logging.error(f"Database migratie fout: {str(e)}")

if __name__ == "__main__":
    print("Start migratie van workspace tabel...")
    migrate_workspace_table()
    print("Migratie voltooid.")