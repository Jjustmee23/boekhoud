"""
Migratiescript om de e-mailinstellingen model uit te breiden met nieuwe velden.
Dit script voegt de volgende velden toe:
- smtp_use_ssl (Boolean, default True)
- smtp_use_tls (Boolean, default False)
- default_sender_name (String, default 'MidaWeb')
- reply_to (String, nullable)

Als het ms_graph_display_name veld nog bestaat, wordt dit verwijderd.
"""
import os
import sys
from datetime import datetime
import psycopg2
from psycopg2 import sql

def migrate_database():
    """Voeg nieuwe velden toe aan de email_settings tabel"""
    try:
        # Verbinding maken met de database
        DATABASE_URL = os.environ.get("DATABASE_URL")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False  # We willen transacties gebruiken
        cursor = conn.cursor()
        
        # Transactie beginnen
        try:
            # Controleer of de tabel bestaat
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'email_settings'
                );
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                print("De email_settings tabel bestaat niet. Migratie wordt overgeslagen.")
                return
            
            # Controleer welke kolommen al bestaan
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'email_settings';
            """)
            existing_columns = [col[0] for col in cursor.fetchall()]
            print(f"Bestaande kolommen: {existing_columns}")
            
            # Voeg nieuwe kolommen toe als ze nog niet bestaan
            if 'smtp_use_ssl' not in existing_columns:
                cursor.execute("ALTER TABLE email_settings ADD COLUMN smtp_use_ssl BOOLEAN DEFAULT TRUE")
                print("Kolom smtp_use_ssl is toegevoegd")
            
            if 'smtp_use_tls' not in existing_columns:
                cursor.execute("ALTER TABLE email_settings ADD COLUMN smtp_use_tls BOOLEAN DEFAULT FALSE")
                print("Kolom smtp_use_tls is toegevoegd")
            
            if 'default_sender_name' not in existing_columns:
                cursor.execute("ALTER TABLE email_settings ADD COLUMN default_sender_name VARCHAR(100) DEFAULT 'MidaWeb'")
                print("Kolom default_sender_name is toegevoegd")
            
            if 'reply_to' not in existing_columns:
                cursor.execute("ALTER TABLE email_settings ADD COLUMN reply_to VARCHAR(100)")
                print("Kolom reply_to is toegevoegd")
            
            # Verwijder de ms_graph_display_name kolom als deze bestaat
            if 'ms_graph_display_name' in existing_columns:
                cursor.execute("ALTER TABLE email_settings DROP COLUMN ms_graph_display_name")
                print("Kolom ms_graph_display_name is verwijderd")
            
            # Commit de transactie
            conn.commit()
            print("Migratie succesvol afgerond!")
            
        except Exception as e:
            conn.rollback()
            print(f"Fout tijdens migratie, transactie teruggedraaid: {str(e)}")
            raise e
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        print(f"Fout bij het migreren van de database: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    from app import app
    with app.app_context():
        migrate_database()