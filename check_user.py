from app import app, db
from models import User
import json

with app.app_context():
    users = User.query.filter(User.username.like('%danny%')).all()
    result = [{'id': u.id, 'username': u.username, 'is_admin': u.is_admin, 'is_super_admin': u.is_super_admin, 'workspace_id': u.workspace_id} for u in users]
    print(json.dumps(result))
