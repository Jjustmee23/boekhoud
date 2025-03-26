from app import app, db
from models import User

def create_admin_user():
    with app.app_context():
        # Check if the user already exists
        existing_user = User.query.filter_by(username='admin').first()
        if existing_user:
            print("Admin user already exists!")
            return
        
        # Create new admin user
        user = User(username='admin', email='admin@example.com')
        user.set_password('admin123')
        user.is_admin = True
        user.is_super_admin = True
        
        # Save to database
        db.session.add(user)
        db.session.commit()
        print('Admin user created successfully!')

if __name__ == "__main__":
    create_admin_user()