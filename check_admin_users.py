from app import app
from models import User

with app.app_context():
    users = User.query.filter_by(is_admin=True).all()
    print('Admins:')
    for user in users:
        print(f'- {user.username} (super_admin: {user.is_super_admin})')