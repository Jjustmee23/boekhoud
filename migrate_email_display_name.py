"""
Migratie script om het ms_graph_display_name veld toe te voegen aan de email_settings tabel.
"""
import os
import sys
from datetime import datetime
from app import app, db
import logging

# Voeg SQLAlchemy imports toe
from sqlalchemy import Column, String
from sqlalchemy.sql import text

def migrate_database():
    """Voeg het ms_graph_display_name veld toe aan de email_settings tabel"""
    try:
        with app.app_context():
            # Maak een verbinding met de database
            connection = db.engine.connect()
            
            print("Start migratie: ms_graph_display_name toevoegen aan email_settings tabel")
            
            # Controleer of de kolom al bestaat
            result = connection.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='email_settings' AND column_name='ms_graph_display_name'"
            ))
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                # Voeg de kolom toe als deze nog niet bestaat
                connection.execute(text(
                    "ALTER TABLE email_settings "
                    "ADD COLUMN ms_graph_display_name varchar(100) DEFAULT 'MidaWeb'"
                ))
                print("Kolom ms_graph_display_name toegevoegd aan tabel email_settings")
                
                # Update bestaande records
                connection.execute(text(
                    "UPDATE email_settings SET ms_graph_display_name = 'MidaWeb' "
                    "WHERE ms_graph_display_name IS NULL"
                ))
                print("Bestaande records bijgewerkt met standaardwaarde 'MidaWeb'")
            else:
                print("Kolom ms_graph_display_name bestaat al, geen migratie nodig")
                
            connection.close()
            print("Migratie voltooid")
            
    except Exception as e:
        print(f"Fout bij het uitvoeren van de migratie: {str(e)}")
        logging.error(f"Migratiefout: {str(e)}")
        return False
        
    return True

if __name__ == "__main__":
    print("Start migratie voor toevoegen ms_graph_display_name...")
    success = migrate_database()
    if success:
        print("Migratie succesvol voltooid")
    else:
        print("Migratie gefaald")
        sys.exit(1)