"""
Database configuratie module om de SQLAlchemy instantie te centraliseren
en circulaire importen tussen app.py en models.py te voorkomen.
"""
from flask_sqlalchemy import SQLAlchemy

# Maak een SQLAlchemy instantie die later aan de app wordt gekoppeld
db = SQLAlchemy()