"""
Script to recreate the database from our models.
"""

import os
from app import app, db
from models import Workspace, User
from datetime import datetime
from werkzeug.security import generate_password_hash

def recreate_database():
    """Drop all tables and recreate them from models"""
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("Dropped all existing tables")
        
        # Create all tables
        db.create_all()
        print("Created all tables from models")
        
        # Create default workspace
        default_workspace = Workspace(
            name="Default Workspace",
            description="Default workspace for existing data",
            created_at=datetime.now()
        )
        db.session.add(default_workspace)
        db.session.commit()
        print(f"Created default workspace with ID: {default_workspace.id}")
        
        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin123"), 
            is_admin=True,
            is_super_admin=True,
            created_at=datetime.now(),
            workspace_id=None  # Super admins have NULL workspace_id
        )
        db.session.add(admin_user)
        
        # Create regular user
        regular_user = User(
            username="user",
            email="user@example.com",
            password_hash=generate_password_hash("user123"),
            is_admin=False,
            is_super_admin=False,
            created_at=datetime.now(),
            workspace_id=default_workspace.id
        )
        db.session.add(regular_user)
        
        db.session.commit()
        print("Created admin and regular users")
        
        print("Database recreation completed successfully")

if __name__ == "__main__":
    recreate_database()