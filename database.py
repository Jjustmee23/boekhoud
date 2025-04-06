"""
Database configuratie module om de SQLAlchemy instantie te centraliseren
en circulaire importen tussen app.py en models.py te voorkomen.
"""
import os
import logging
from flask_sqlalchemy import SQLAlchemy

def get_database_url():
    """
    Bepaalt de juiste database URL op basis van de omgeving (Docker of Replit)
    """
    # Haal de database URL uit de omgevingsvariabelen
    database_url = os.environ.get("DATABASE_URL")
    
    # Controleer of we in een Docker container zitten
    in_docker = os.path.exists('/.dockerenv')
    
    # Als we in Docker zitten, maar geen database URL hebben, gebruik de standaard Docker URL
    if in_docker and not database_url:
        # Standaard Docker PostgreSQL URL
        database_url = "postgresql://dbuser:dbpassword@db:5432/invoicing"
        logging.info("In Docker omgeving: standaard Docker database URL gebruikt")
    
    # Als we niet in Docker zitten en een Docker-specifieke URL hebben (met 'db' erin)
    elif not in_docker and database_url and 'db' in database_url:
        # Replit PostgreSQL URL
        database_url = "postgresql://neondb_owner:npg_8mlCGVSz2tDU@ep-young-breeze-a5mg2988.us-east-2.aws.neon.tech/neondb?sslmode=require"
        logging.warning("Docker database URL gedetecteerd maar we zijn niet in Docker - Replit database URL gebruikt")
    
    # Als we geen database URL hebben maar wel in Replit zitten
    elif not database_url:
        # Replit PostgreSQL URL
        database_url = "postgresql://neondb_owner:npg_8mlCGVSz2tDU@ep-young-breeze-a5mg2988.us-east-2.aws.neon.tech/neondb?sslmode=require"
        logging.info("Geen database URL gevonden, Replit database URL gebruikt")
    
    return database_url

# Maak een SQLAlchemy instantie die later aan de app wordt gekoppeld
db = SQLAlchemy()

def init_app_db(app):
    """
    Initialiseert de database met de correcte URL op basis van de omgeving
    """
    # Stel de database URL in
    app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
        # Optimaliseer poolinggedrag voor betere connectiviteit
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 60
    }
    
    # Initialiseer de database
    db.init_app(app)
    
def refresh_table_metadata():
    """
    Vernieuwt de SQLAlchemy metadata om tabelwijzigingen te herkennen
    """
    try:
        # Haal de metadata van elke tabel op en vernieuw deze
        for table in db.metadata.tables.values():
            # Zorg ervoor dat extend_existing is ingeschakeld
            table.extend_existing = True
            # Als de tabel al bestaat, vernieuw de metadata
            if db.engine.dialect.has_table(db.engine.connect(), table.name):
                # Haal de kolommen op en werk de metadata bij
                table.append_column = True
        logging.info("Metadata succesvol vernieuwd voor alle tabellen")
    except Exception as e:
        logging.error(f"Fout bij het vernieuwen van metadata: {str(e)}")
        raise