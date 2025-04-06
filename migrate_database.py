"""
Database migratie script voor het toevoegen van WHMCS-velden aan bestaande tabellen
"""
import os
import sys
import logging
from datetime import datetime

# Configureer logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask en SQLAlchemy imports
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, Table, Column, Integer, Boolean, DateTime, String
from sqlalchemy.sql import text

# Gebruik de database module voor de bestaande SQLAlchemy instantie
from database import db
# Maak een tijdelijke Flask-app voor de database-verbinding
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Initialiseer de bestaande db instantie met deze app
db.init_app(app)

def add_column_if_not_exists(table_name, column_name, column_type):
    """Voeg een kolom toe aan een tabel als deze nog niet bestaat"""
    try:
        # Controleer of kolom al bestaat
        with db.engine.connect() as conn:
            query = text(f"""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = '{table_name}' AND column_name = '{column_name}'
            """)
            result = conn.execute(query)
            column_exists = result.fetchone() is not None
        
        if not column_exists:
            # Voeg kolom toe als deze niet bestaat
            with db.engine.connect() as conn:
                # SQLAlchemy type naar PostgreSQL type converteren
                pg_type = {
                    Integer: 'INTEGER',
                    Boolean: 'BOOLEAN',
                    DateTime: 'TIMESTAMP',
                    String: f'VARCHAR({column_type.length})' if hasattr(column_type, 'length') else 'VARCHAR',
                }[type(column_type)]
                
                # NULL/NOT NULL en DEFAULT-waarden instellen
                nullable = '' if column_type.nullable else 'NOT NULL'
                default = f"DEFAULT {column_type.default.arg}" if column_type.default and hasattr(column_type.default, 'arg') else ''
                
                # ALTER TABLE uitvoeren
                query = text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {pg_type} {nullable} {default}")
                conn.execute(query)
                
            logger.info(f"Kolom {column_name} toegevoegd aan tabel {table_name}")
            return True
        else:
            logger.info(f"Kolom {column_name} bestaat al in tabel {table_name}")
            return False
    except Exception as e:
        logger.error(f"Fout bij toevoegen van kolom {column_name} aan tabel {table_name}: {str(e)}")
        return False

def migrate_whmcs_fields():
    """
    Voeg WHMCS-gerelateerde velden toe aan bestaande tabellen
    """
    logger.info("Start migratie van WHMCS-velden...")
    
    # Voer directe SQL-queries uit voor het toevoegen van kolommen
    with db.engine.connect() as conn:
        try:
            # WHMCS-velden voor Customer
            conn.execute(text("""
                ALTER TABLE customers 
                ADD COLUMN IF NOT EXISTS whmcs_client_id INTEGER,
                ADD COLUMN IF NOT EXISTS synced_from_whmcs BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS whmcs_last_sync TIMESTAMP
            """))
            logger.info("WHMCS-velden toegevoegd aan customers tabel")
        except Exception as e:
            logger.error(f"Fout bij toevoegen van WHMCS-velden aan customers tabel: {str(e)}")
        
        try:
            # WHMCS-velden voor Invoice en ontbrekende due_date kolom
            conn.execute(text("""
                ALTER TABLE invoices 
                ADD COLUMN IF NOT EXISTS due_date DATE,
                ADD COLUMN IF NOT EXISTS whmcs_invoice_id INTEGER,
                ADD COLUMN IF NOT EXISTS synced_from_whmcs BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS whmcs_last_sync TIMESTAMP
            """))
            logger.info("WHMCS-velden en ontbrekende kolommen toegevoegd aan invoices tabel")
        except Exception as e:
            logger.error(f"Fout bij toevoegen van WHMCS-velden aan invoices tabel: {str(e)}")
        
        try:
            # WHMCS-velden voor SystemSettings
            conn.execute(text("""
                ALTER TABLE system_settings 
                ADD COLUMN IF NOT EXISTS whmcs_api_url VARCHAR(255),
                ADD COLUMN IF NOT EXISTS whmcs_api_identifier VARCHAR(255),
                ADD COLUMN IF NOT EXISTS whmcs_api_secret VARCHAR(255),
                ADD COLUMN IF NOT EXISTS whmcs_api_token VARCHAR(255),
                ADD COLUMN IF NOT EXISTS whmcs_auto_sync BOOLEAN DEFAULT FALSE,
                ADD COLUMN IF NOT EXISTS whmcs_last_sync TIMESTAMP
            """))
            logger.info("WHMCS-velden toegevoegd aan system_settings tabel")
        except Exception as e:
            logger.error(f"Fout bij toevoegen van WHMCS-velden aan system_settings tabel: {str(e)}")
    
    logger.info("Migratie van WHMCS-velden voltooid")

if __name__ == "__main__":
    with app.app_context():
        migrate_whmcs_fields()