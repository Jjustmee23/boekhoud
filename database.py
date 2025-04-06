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
    """
    try:
        inspector = inspect(engine)
        all_columns = inspector.get_columns(table_name)
        column_names = [col['name'] for col in all_columns]
        logger.info(f"Tabel {table_name} kolommen vernieuwd: {', '.join(column_names)}")
        return True
    except Exception as e:
        logger.error(f"Fout bij vernieuwen van tabel metadata voor {table_name}: {str(e)}")
        return False