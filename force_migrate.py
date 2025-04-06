#!/usr/bin/env python
"""
Script om database migraties te forceren in Docker omgeving.
Dit script reset de SQLAlchemy cache en voert alle migraties geforceerd uit.
"""
import logging
import sys
import os
from sqlalchemy import inspect, Table, MetaData, Column, text
from flask import Flask

# Configureer logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialiseer Flask app voor context
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")

# Importeer database en modellen
from database import db
db.init_app(app)

def drop_column_if_exists(table_name, column_name):
    """Verwijder een kolom als deze bestaat, anders doe niets"""
    with db.engine.connect() as conn:
        try:
            # Controleer of de kolom bestaat
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name='{table_name}' AND column_name='{column_name}'
                )
            """))
            exists = result.scalar()
            
            if exists:
                logger.info(f"Kolom {column_name} in tabel {table_name} bestaat, wordt verwijderd...")
                # Als de kolom bestaat, verwijder deze
                conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {column_name}"))
                logger.info(f"Kolom {column_name} in tabel {table_name} is verwijderd")
                return True
            else:
                logger.info(f"Kolom {column_name} in tabel {table_name} bestaat niet")
                return False
        except Exception as e:
            logger.error(f"Fout bij check/drop kolom {column_name} in {table_name}: {str(e)}")
            return False

def force_rebuild_table(table_name):
    """Maak een kopie van een tabel, drop de originele, en maak deze opnieuw aan"""
    with db.engine.connect() as conn:
        try:
            # Maak een tijdelijke tabel
            conn.execute(text(f"CREATE TABLE {table_name}_temp AS SELECT * FROM {table_name}"))
            logger.info(f"Tijdelijke tabel {table_name}_temp aangemaakt")
            
            # Drop de originele tabel
            conn.execute(text(f"DROP TABLE {table_name}"))
            logger.info(f"Tabel {table_name} verwijderd")
            
            # SQLAlchemy zal de tabel opnieuw aanmaken met de juiste structuur
            # We importeren hier de models om de table-definities te laden
            import models
            
            # Maak de tabel opnieuw aan met de correcte structuur
            db.metadata.create_all(bind=db.engine, tables=[models.__dict__[table_class].__table__ 
                                                         for table_class in dir(models) 
                                                         if hasattr(models.__dict__[table_class], '__tablename__') 
                                                         and models.__dict__[table_class].__tablename__ == table_name])
            logger.info(f"Tabel {table_name} opnieuw aangemaakt met juiste structuur")
            
            # Kopieer data terug
            # We moeten de kolommen expliciet specificeren om alleen gemeenschappelijke kolommen te kopiëren
            inspector = inspect(db.engine)
            original_columns = [col['name'] for col in inspector.get_columns(table_name)]
            temp_columns = [col['name'] for col in inspector.get_columns(f"{table_name}_temp")]
            
            # Vind gemeenschappelijke kolommen
            common_columns = list(set(original_columns).intersection(set(temp_columns)))
            columns_str = ", ".join(common_columns)
            
            # Kopieer data terug
            conn.execute(text(f"INSERT INTO {table_name} ({columns_str}) SELECT {columns_str} FROM {table_name}_temp"))
            logger.info(f"Data gekopieerd van {table_name}_temp naar {table_name}")
            
            # Verwijder de tijdelijke tabel
            conn.execute(text(f"DROP TABLE {table_name}_temp"))
            logger.info(f"Tijdelijke tabel {table_name}_temp verwijderd")
            
            return True
        except Exception as e:
            logger.error(f"Fout bij forceren van tabel rebuild voor {table_name}: {str(e)}")
            return False

def force_migrate():
    """Forceer database migraties door de SQLAlchemy cache te resetten en migraties opnieuw uit te voeren"""
    logger.info("Start geforceerde migratie...")
    
    # Reset SQLAlchemy metadata
    db.metadata.clear()
    logger.info("SQLAlchemy metadata cleared")
    
    # Importeer alle models om de metadata te vernieuwen
    import models
    logger.info("Models opnieuw geïmporteerd")
    
    # Voer migraties uit
    with app.app_context():
        try:
            # Voer de SQL migraties uit voor WHMCS velden en missing columns
            from migrate_database import migrate_whmcs_fields
            migrate_whmcs_fields()
            logger.info("WHMCS velden migratie succesvol uitgevoerd")
            
            # Controleer of due_date bestaat in invoices tabel
            inspector = inspect(db.engine)
            invoice_columns = [col['name'] for col in inspector.get_columns('invoices')]
            
            if 'due_date' not in invoice_columns:
                logger.warning("Kolom 'due_date' niet gevonden in invoices tabel, probeer geforceerde tabel rebuild")
                success = force_rebuild_table('invoices')
                if success:
                    logger.info("Invoices tabel succesvol herbouwd")
                else:
                    logger.error("Kon invoices tabel niet herbouwen")
            else:
                logger.info("Kolom 'due_date' bestaat al in invoices tabel")
                
            # Controleer of notes bestaat in invoices tabel
            if 'notes' not in invoice_columns:
                logger.warning("Kolom 'notes' niet gevonden in invoices tabel, wordt toegevoegd")
                with db.engine.connect() as conn:
                    conn.execute(text("""
                        ALTER TABLE invoices 
                        ADD COLUMN IF NOT EXISTS notes TEXT
                    """))
                logger.info("Kolom 'notes' toegevoegd aan invoices tabel")
            else:
                logger.info("Kolom 'notes' bestaat al in invoices tabel")
                
            # Controleer of bidirectionele relaties correct zijn
            # Dit lost het probleem op met Workspace/BackupSettings relatie
            db.create_all()
            logger.info("Database schema gesynchroniseerd")
            
            return True
        except Exception as e:
            logger.error(f"Fout bij geforceerde migratie: {str(e)}")
            return False

def create_docker_migration_script():
    """Maak een script dat in Docker kan worden uitgevoerd om migraties te forceren"""
    script_content = """#!/bin/bash
# Script om database migraties te forceren in Docker
echo "Start geforceerde database migratie..."
cd /app
python force_migrate.py
if [ $? -eq 0 ]; then
    echo "Database migratie succesvol uitgevoerd"
    exit 0
else
    echo "Fout bij database migratie"
    exit 1
fi
"""
    with open('force_migrate.sh', 'w') as f:
        f.write(script_content)
    
    os.chmod('force_migrate.sh', 0o755)
    logger.info("Docker migratie script aangemaakt: force_migrate.sh")
    
if __name__ == "__main__":
    with app.app_context():
        logger.info("Start geforceerde database migratie")
        success = force_migrate()
        
        # Maak ook een shell script voor Docker
        create_docker_migration_script()
        
        if success:
            logger.info("Geforceerde database migratie voltooid")
            sys.exit(0)
        else:
            logger.error("Geforceerde database migratie mislukt")
            sys.exit(1)