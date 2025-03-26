from app import app, db
import logging

"""
Migration script to add is_super_admin column to the users table
"""

def migrate_database():
    try:
        # Check if the column exists first
        with db.engine.connect() as conn:
            result = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='users' AND column_name='is_super_admin'"
            )
            column_exists = result.fetchone() is not None
            
            if not column_exists:
                print("Adding is_super_admin column to users table...")
                # Add column
                conn.execute("ALTER TABLE users ADD COLUMN is_super_admin BOOLEAN DEFAULT FALSE")
                
                # Set first admin user as super admin
                conn.execute(
                    "UPDATE users SET is_super_admin = TRUE "
                    "WHERE is_admin = TRUE ORDER BY id LIMIT 1"
                )
                print("Migration completed successfully!")
            else:
                print("Column is_super_admin already exists, no migration needed.")
                
    except Exception as e:
        logging.error(f"Error during migration: {str(e)}")
        print(f"Migration failed: {str(e)}")

if __name__ == "__main__":
    with app.app_context():
        migrate_database()