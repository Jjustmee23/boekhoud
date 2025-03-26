"""
Migration script to add workspace functionality to the application.
This creates the workspaces table and adds workspace_id columns to related tables.
"""

import os
import sys
import sqlalchemy as sa
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL environment variable not set")
    sys.exit(1)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Define models for migration
class Workspace(Base):
    __tablename__ = 'workspaces'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(String(200))
    created_at = Column(DateTime, default=datetime.now)

def migrate_database():
    """Create workspaces table and update other tables to add workspace_id"""
    
    # Create the session
    session = Session()
    
    try:
        # Check if workspaces table already exists and create it if needed
        workspace_exists = engine.dialect.has_table(engine.connect(), 'workspaces')
        if not workspace_exists:
            # Create the workspaces table
            Workspace.__table__.create(engine, checkfirst=True)
            print("Created workspaces table")
            
            # Create default workspace
            default_workspace = Workspace(
                name="Default Workspace",
                description="Default workspace for existing data"
            )
            session.add(default_workspace)
            session.commit()
            default_workspace_id = default_workspace.id
        else:
            # Get the default workspace ID if it already exists
            default_workspace = session.query(Workspace).filter_by(name="Default Workspace").first()
            if not default_workspace:
                default_workspace = Workspace(
                    name="Default Workspace",
                    description="Default workspace for existing data"
                )
                session.add(default_workspace)
                session.commit()
            default_workspace_id = default_workspace.id
            
        print(f"Using default workspace with ID: {default_workspace_id}")
            
        # Check and update users table
        with engine.connect() as conn:
            # Check if users.workspace_id column exists
            user_workspace_exists = False
            for row in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='workspace_id'"
            )):
                user_workspace_exists = True
                
            if not user_workspace_exists:
                print("Adding workspace_id to users table")
                # Add workspace_id column to users table
                conn.execute(sa.text(
                    f"""
                    ALTER TABLE users 
                    ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
                    
                    UPDATE users 
                    SET workspace_id = {default_workspace_id};
                    
                    -- Don't make workspace_id NOT NULL - super admins need NULL workspace_id
                    
                    -- Make username and email unique per workspace
                    CREATE UNIQUE INDEX IF NOT EXISTS uix_user_username_workspace
                    ON users (username, workspace_id);
                    
                    CREATE UNIQUE INDEX IF NOT EXISTS uix_user_email_workspace
                    ON users (email, workspace_id);
                    """
                ))
            else:
                print("users.workspace_id already exists")
                
            # Check if users.password_change_required column exists
            password_change_required_exists = False
            for row in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='password_change_required'"
            )):
                password_change_required_exists = True
                
            if not password_change_required_exists:
                print("Adding password_change_required to users table")
                conn.execute(sa.text(
                    """
                    -- Add password_change_required column
                    ALTER TABLE users
                    ADD COLUMN password_change_required BOOLEAN DEFAULT FALSE;
                    """
                ))
            else:
                print("users.password_change_required already exists")
                
            # Check if customers.workspace_id column exists
            customer_workspace_exists = False
            for row in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='customers' AND column_name='workspace_id'"
            )):
                customer_workspace_exists = True
                
            if not customer_workspace_exists:
                print("Adding workspace_id to customers table")
                # Add workspace_id column to customers table
                conn.execute(sa.text(
                    f"""
                    ALTER TABLE customers 
                    ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
                    
                    UPDATE customers 
                    SET workspace_id = {default_workspace_id};
                    
                    ALTER TABLE customers 
                    ALTER COLUMN workspace_id SET NOT NULL;
                    """
                ))
            else:
                print("customers.workspace_id already exists")
                
            # Check if invoices.workspace_id column exists
            invoice_workspace_exists = False
            for row in conn.execute(sa.text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='invoices' AND column_name='workspace_id'"
            )):
                invoice_workspace_exists = True
                
            if not invoice_workspace_exists:
                print("Adding workspace_id to invoices table")
                # Add workspace_id column to invoices table
                conn.execute(sa.text(
                    f"""
                    ALTER TABLE invoices 
                    ADD COLUMN workspace_id INTEGER REFERENCES workspaces(id);
                    
                    UPDATE invoices 
                    SET workspace_id = {default_workspace_id};
                    
                    ALTER TABLE invoices 
                    ALTER COLUMN workspace_id SET NOT NULL;
                    
                    -- Drop old invoice_number unique constraint if it exists
                    ALTER TABLE invoices 
                    DROP CONSTRAINT IF EXISTS invoices_invoice_number_key;
                    
                    -- Make invoice_number unique per workspace
                    CREATE UNIQUE INDEX IF NOT EXISTS uix_invoice_number_workspace
                    ON invoices (invoice_number, workspace_id);
                    """
                ))
            else:
                print("invoices.workspace_id already exists")
                
            # Update super_admin users to use NULL workspace_id (access to all workspaces)
            conn.execute(sa.text(
                """
                UPDATE users
                SET workspace_id = NULL
                WHERE is_super_admin = TRUE;
                """
            ))
                
            conn.commit()
            
        print("Migration completed successfully")
    except Exception as e:
        session.rollback()
        print(f"Migration failed: {str(e)}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    migrate_database()