from app import app, db
from models import User

with app.app_context():
    user = User.query.filter_by(username='danny1').first()
    if user:
        user.is_admin = True
        db.session.commit()
        print(f"Gebruiker {user.username} is nu een admin (is_admin={user.is_admin})")
    else:
        print("Gebruiker niet gevonden")
