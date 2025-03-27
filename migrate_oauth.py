"""
Script om de database te migreren om OAuth tokens voor gebruikers toe te voegen.
Dit maakt een nieuwe 'user_oauth_tokens' tabel aan en voegt nieuwe velden toe aan de 'email_settings' tabel.
"""

import os
import time
import logging
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Logging configureren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Laad environment variables
load_dotenv()

# Maak een simpele Flask app en engine met SQLAlchemy
app = Flask(__name__)
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/mydatabase')
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

# Definieer een minimale versie van de tabel structuur voor de migratie
class UserOAuthToken(Base):
    __tablename__ = 'user_oauth_tokens'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    workspace_id = Column(Integer, ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
    provider = Column(String(20), nullable=False)  # 'microsoft', 'google', etc.
    
    # OAuth gegevens
    access_token = Column(String(2048))
    refresh_token = Column(String(2048))
    token_expiry = Column(DateTime)
    email = Column(String(120))
    display_name = Column(String(120))
    
    # Bijhouden wanneer tokens zijn gewijzigd
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    
    # Maak combinatie van user_id, workspace_id en provider uniek
    __table_args__ = (
        UniqueConstraint('user_id', 'workspace_id', 'provider', name='uix_user_workspace_provider'),
    )

def add_columns_to_email_settings():
    """Voeg nieuwe OAuth-gerelateerde kolommen toe aan de email_settings tabel"""
    try:
        with engine.connect() as conn:
            # Controleer of kolommen al bestaan
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='email_settings' AND column_name='use_user_oauth'")
            if result.rowcount == 0:
                logger.info("Column 'use_user_oauth' toevoegen aan email_settings tabel...")
                conn.execute("ALTER TABLE email_settings ADD COLUMN use_user_oauth BOOLEAN DEFAULT FALSE")
            
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='email_settings' AND column_name='allow_microsoft_oauth'")
            if result.rowcount == 0:
                logger.info("Column 'allow_microsoft_oauth' toevoegen aan email_settings tabel...")
                conn.execute("ALTER TABLE email_settings ADD COLUMN allow_microsoft_oauth BOOLEAN DEFAULT TRUE")
            
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='email_settings' AND column_name='allow_google_oauth'")
            if result.rowcount == 0:
                logger.info("Column 'allow_google_oauth' toevoegen aan email_settings tabel...")
                conn.execute("ALTER TABLE email_settings ADD COLUMN allow_google_oauth BOOLEAN DEFAULT FALSE")
            
            result = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name='email_settings' AND column_name='oauth_scopes'")
            if result.rowcount == 0:
                logger.info("Column 'oauth_scopes' toevoegen aan email_settings tabel...")
                conn.execute("ALTER TABLE email_settings ADD COLUMN oauth_scopes VARCHAR(1024) DEFAULT 'mail.send'")
            
            logger.info("Email settings tabel succesvol bijgewerkt.")
    except Exception as e:
        logger.error(f"Fout bij het toevoegen van kolommen aan email_settings: {e}")
        raise

def create_user_oauth_tokens_table():
    """Maak de user_oauth_tokens tabel aan als deze nog niet bestaat"""
    try:
        # Controleer of tabel bestaat
        with engine.connect() as conn:
            result = conn.execute("SELECT to_regclass('public.user_oauth_tokens')")
            table_exists = result.scalar() is not None
        
        if not table_exists:
            logger.info("Tabel user_oauth_tokens aanmaken...")
            # Maak de tabel
            UserOAuthToken.__table__.create(engine, checkfirst=True)
            logger.info("Tabel user_oauth_tokens succesvol aangemaakt.")
        else:
            logger.info("Tabel user_oauth_tokens bestaat al.")
    except Exception as e:
        logger.error(f"Fout bij het maken van user_oauth_tokens tabel: {e}")
        raise

def run_migration():
    logger.info("Start migratie voor OAuth ondersteuning...")
    
    try:
        # Voeg nieuwe kolommen toe aan email_settings
        add_columns_to_email_settings()
        
        # Maak nieuwe tabel voor user_oauth_tokens
        create_user_oauth_tokens_table()
        
        logger.info("Migratie succesvol afgerond!")
    except Exception as e:
        logger.error(f"Migratie gefaald: {e}")
        raise

if __name__ == "__main__":
    run_migration()