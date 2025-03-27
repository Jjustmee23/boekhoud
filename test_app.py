import logging
logging.basicConfig(level=logging.DEBUG)

from app import app
from models import User

with app.app_context():
    print('Database check - User count:', User.query.count())