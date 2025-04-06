"""
Database configuratie module om de SQLAlchemy instantie te centraliseren
en circulaire importen tussen app.py en models.py te voorkomen.
"""
import logging
from sqlalchemy import inspect
from flask_sqlalchemy import SQLAlchemy

# Configureer logging
logger = logging.getLogger(__name__)

# Maak een SQLAlchemy instantie die later aan de app wordt gekoppeld
db = SQLAlchemy()

def refresh_table_metadata(engine, table_name):
    """
    Vernieuw de metadata voor een specifieke tabel.
    Dit lost problemen op met schema wijzigingen die niet worden opgepikt door SQLAlchemy.
    
    Deze functie inspecteet de actuele database kolommen en 
    zorgt dat de SQLAlchemy-metadata volledig gesynchroniseerd is.
    """
    try:
        inspector = inspect(engine)
        all_columns = inspector.get_columns(table_name)
        column_names = [col['name'] for col in all_columns]
        
        # Update de tabeldefinitie in SQLAlchemy model metadata
        if table_name in db.metadata.tables:
            # Zorg ervoor dat de tabel object alle kolommen kent
            for col_name in column_names:
                if col_name not in db.metadata.tables[table_name].columns:
                    # Force reflection om nieuwe kolommen op te halen
                    db.metadata.tables[table_name].columns._reset_exported()
                    
        logger.info(f"Tabel {table_name} kolommen vernieuwd: {', '.join(column_names)}")
        return True
    except Exception as e:
        logger.error(f"Fout bij vernieuwen van tabel metadata voor {table_name}: {str(e)}")
        return False