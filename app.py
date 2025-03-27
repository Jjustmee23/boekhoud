import os
import logging
from datetime import datetime
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File handler for general logs
file_handler = logging.FileHandler('logs/app.log')
file_handler.setFormatter(log_formatter)

# File handler for error logs
error_handler = logging.FileHandler('logs/error.log')
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(log_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(error_handler)
root_logger.addHandler(console_handler)

# Log de MS Graph API configuratiegegevens (alleen voor debug)
logging.info(f"MS_GRAPH_CLIENT_ID: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_ID') else 'Niet ingesteld'}")
logging.info(f"MS_GRAPH_CLIENT_SECRET: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_SECRET') else 'Niet ingesteld'}")
logging.info(f"MS_GRAPH_TENANT_ID: {'Ingesteld' if os.environ.get('MS_GRAPH_TENANT_ID') else 'Niet ingesteld'}")
logging.info(f"MS_GRAPH_SENDER_EMAIL: {'Ingesteld' if os.environ.get('MS_GRAPH_SENDER_EMAIL') else 'Niet ingesteld'}")

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize database
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Log in om toegang te krijgen tot deze pagina.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

def init_sample_data():
    """Function to add sample data to the database if none exists"""
    # Import here to avoid circular imports
    from models import Customer, Invoice

    # Only initialize if no data exists
    if Customer.query.count() == 0 and Invoice.query.count() == 0:
        # Add sample data for testing
        try:
            # Sample customers
            customer1 = Customer(
                company_name="Example Company BVBA",
                vat_number="BE0123456789",
                email="info@example.com",
                street="Voorbeeldstraat",
                house_number="123",
                postal_code="1000",
                city="Brussels",
                country="België"
            )
            
            customer2 = Customer(
                company_name="Test Business NV",
                vat_number="BE9876543210",
                email="contact@test-business.be",
                street="Testlaan",
                house_number="45",
                postal_code="2000",
                city="Antwerp",
                country="België"
            )
            
            db.session.add(customer1)
            db.session.add(customer2)
            db.session.commit()
            
            app.logger.info("Sample data initialized successfully")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error initializing sample data: {str(e)}")

# Create a function to initialize the app
def create_default_admin():
    """Create the default admin user if it doesn't exist"""
    from models import User
    
    # Check if the admin user already exists
    existing_user = User.query.filter_by(username='admin').first()
    if existing_user:
        return
    
    # Create new admin user
    user = User(username='admin', email='admin@example.com')
    user.set_password('admin123')
    user.is_admin = True
    user.is_super_admin = True
    user.password_change_required = True
    
    # Save to database
    db.session.add(user)
    db.session.commit()
    app.logger.info('Default admin user created successfully!')

def initialize_app():
    """Initialize the application, create database tables and add sample data"""
    with app.app_context():
        # Import models to ensure they're registered with SQLAlchemy
        import models
        
        # Create all database tables
        db.create_all()
        
        # Create default admin user
        create_default_admin()
        
        # Add initial data if needed
        init_sample_data()

# Import routes at the end to avoid circular imports
from routes import *

# Initialize the app after all imports
initialize_app()
