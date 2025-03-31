#!/usr/bin/env python3
"""
Database migratie script
Dit script maakt of update de database tabellen voor het facturatie systeem
"""

import os
import sys
import logging
import importlib
import inspect
import time
from sqlalchemy import inspect as sa_inspect
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

# Configureer logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Creëer een minimale Flask app voor database migraties"""
    app = Flask(__name__)
    
    # Database configuratie van environment variabelen
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True
    }
    
    return app

def perform_migrations():
    """Voer database migraties uit"""
    
    # Wacht op database beschikbaarheid (max 60 seconden)
    logger.info("Wachten op database verbinding...")
    db_available = False
    max_attempts = 30
    
    for attempt in range(max_attempts):
        try:
            # Maak een test-app aan om de database te testen
            app = create_app()
            db = SQLAlchemy(app)
            
            with app.app_context():
                db.engine.connect()
                db_available = True
                logger.info("Database verbinding succesvol!")
                break
        except SQLAlchemyError as e:
            if attempt < max_attempts - 1:
                logger.info(f"Wachten op database... ({attempt+1}/{max_attempts})")
                time.sleep(2)
            else:
                logger.error(f"Kon geen verbinding maken met de database: {e}")
                sys.exit(1)
    
    if not db_available:
        logger.error("Kon geen verbinding maken met de database na meerdere pogingen")
        sys.exit(1)
    
    # Maak app en database objecten voor migratie
    app = create_app()
    db = SQLAlchemy(app)
    
    # Laad alle modellen
    try:
        from models import User
        logger.info("Models module geladen")
    except ImportError:
        logger.error("Kon de models module niet laden")
        sys.exit(1)
    
    # Fixeer tabellen door ontbrekende kolommen toe te voegen
    with app.app_context():
        fix_user_table(db)
        
        # Andere tabellen kunnen hier worden toegevoegd
        
        # Maak alle tabellen aan (alleen als ze nog niet bestaan)
        logger.info("Database tabellen aanmaken/updaten...")
        db.create_all()
        
        # Controleer of admin gebruiker bestaat
        admin_exists = False
        try:
            admin_exists = bool(User.query.filter_by(username='admin').first())
        except ProgrammingError:
            # Als kolommen missen, wordt hierboven een exceptie gegenereerd
            logger.warning("Kon niet controleren of admin bestaat - nieuwe kolommen aangemaakt")
        
        if not admin_exists:
            logger.info("Admin gebruiker aanmaken...")
            from werkzeug.security import generate_password_hash
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash('admin'),
                is_admin=True,
                is_super_admin=True
            )
            
            # Voeg is_new_user toe als het bestaat
            if hasattr(User, 'is_new_user'):
                admin.is_new_user = False
                
            db.session.add(admin)
            db.session.commit()
            logger.info("Admin gebruiker aangemaakt: admin/admin")
        else:
            logger.info("Admin gebruiker bestaat al, geen nieuwe aangemaakt")
    
    logger.info("Database migratie voltooid!")

def fix_user_table(db):
    """
    Controleer en fix de User tabel indien nodig
    Voegt ontbrekende kolommen toe aan de users tabel
    """
    
    from models import User
    
    inspector = sa_inspect(db.engine)
    
    if not inspector.has_table('users'):
        logger.info("Tabel 'users' bestaat niet, wordt aangemaakt tijdens create_all")
        return
    
    # Controleer of is_new_user kolom bestaat in het model maar niet in de database
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    # Fix voor is_new_user kolom
    if hasattr(User, 'is_new_user') and 'is_new_user' not in columns:
        logger.info("Kolom 'is_new_user' ontbreekt in users tabel, wordt toegevoegd...")
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE users ADD COLUMN is_new_user BOOLEAN DEFAULT TRUE'))
                conn.commit()
            logger.info("Kolom 'is_new_user' succesvol toegevoegd!")
        except SQLAlchemyError as e:
            logger.error(f"Fout bij toevoegen van 'is_new_user' kolom: {e}")
            
    # Fix voor workspace_id kolom
    if hasattr(User, 'workspace_id') and 'workspace_id' not in columns:
        logger.info("Kolom 'workspace_id' ontbreekt in users tabel, wordt toegevoegd...")
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE users ADD COLUMN workspace_id INTEGER'))
                conn.commit()
            logger.info("Kolom 'workspace_id' succesvol toegevoegd!")
        except SQLAlchemyError as e:
            logger.error(f"Fout bij toevoegen van 'workspace_id' kolom: {e}")
            
    # Fix voor password_change_required kolom
    if hasattr(User, 'password_change_required') and 'password_change_required' not in columns:
        logger.info("Kolom 'password_change_required' ontbreekt in users tabel, wordt toegevoegd...")
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE users ADD COLUMN password_change_required BOOLEAN DEFAULT FALSE'))
                conn.commit()
            logger.info("Kolom 'password_change_required' succesvol toegevoegd!")
        except SQLAlchemyError as e:
            logger.error(f"Fout bij toevoegen van 'password_change_required' kolom: {e}")

if __name__ == "__main__":
    logger.info("Database migratie script gestart")
    perform_migrations()