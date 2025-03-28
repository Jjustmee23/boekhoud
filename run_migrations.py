#!/usr/bin/env python3
"""
Database Migratie Script
Dit script voert database migraties uit bij het opstarten van de Docker container
"""

import os
import sys
import logging
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('db_migrations')

# Database settings
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    logger.error("DATABASE_URL environment variable not set")
    sys.exit(1)

# Connect to db with retry
def get_db_connection(retries=5, delay=2):
    """Get a database connection with retry logic"""
    attempt = 0
    while attempt < retries:
        try:
            engine = create_engine(db_url)
            conn = engine.connect()
            logger.info("Database connection established")
            return conn
        except SQLAlchemyError as e:
            attempt += 1
            logger.warning(f"Database connection failed (attempt {attempt}/{retries}): {str(e)}")
            if attempt >= retries:
                logger.error("Max retries reached. Could not connect to database.")
                sys.exit(1)
            time.sleep(delay)

def apply_migrations(conn):
    """Apply database migrations"""
    logger.info("Starting database migrations")
    
    # List of migrations to apply
    migrations = [
        {
            "description": "Add is_new_user column to users table", 
            "sql": "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_new_user BOOLEAN DEFAULT TRUE;",
            "verify_sql": "SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='is_new_user'"
        }
        # Add more migrations here as needed
    ]
    
    for migration in migrations:
        logger.info(f"Applying migration: {migration['description']}")
        
        # Check if migration needs to be applied
        try:
            result = conn.execute(text(migration['verify_sql']))
            if result.rowcount > 0:
                logger.info(f"Migration already applied: {migration['description']}")
                continue
        except SQLAlchemyError as e:
            logger.warning(f"Error checking migration status: {str(e)}")
        
        # Apply migration
        try:
            conn.execute(text(migration['sql']))
            conn.commit()
            logger.info(f"Successfully applied migration: {migration['description']}")
        except ProgrammingError as e:
            if "already exists" in str(e):
                logger.info(f"Column already exists: {migration['description']}")
            else:
                logger.error(f"Error applying migration: {str(e)}")
                raise
        except SQLAlchemyError as e:
            logger.error(f"Error applying migration: {str(e)}")
            raise
    
    logger.info("Completed all database migrations")

def main():
    """Main entry point"""
    try:
        logger.info("Starting database migration process")
        conn = get_db_connection()
        apply_migrations(conn)
        conn.close()
        logger.info("Migration process completed successfully")
    except Exception as e:
        logger.error(f"Migration process failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()