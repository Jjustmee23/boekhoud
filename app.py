import os
import logging
from datetime import datetime
from flask import Flask, session
from flask_login import LoginManager
from dotenv import load_dotenv

# Import SQLAlchemy instantie
from database import db

# Load environment variables from .env file
load_dotenv()

# Set up logging
import logging.handlers
import json
from datetime import datetime

# Zorg ervoor dat logs directory bestaat
os.makedirs('logs', exist_ok=True)

# Hoofdlogger configuratie
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Formatters
standard_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Aangepaste JSON formatter klasse
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'path': record.pathname,
            'line': record.lineno,
            'function': record.funcName
        }
        
        if record.exc_info:
            log_data['exception'] = str(record.exc_info[1])
            
        return json.dumps(log_data)

json_formatter = JsonFormatter()

# Console handler voor ontwikkeling
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(standard_formatter)
logger.addHandler(console_handler)

# Roterende bestandshandler voor alle logs
file_handler = logging.handlers.RotatingFileHandler(
    'logs/app.log',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(standard_formatter)
logger.addHandler(file_handler)

# JSON-formathandler voor analyse
json_handler = logging.handlers.RotatingFileHandler(
    'logs/app.json.log',
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=5
)
json_handler.setLevel(logging.DEBUG)
json_handler.setFormatter(json_formatter)
logger.addHandler(json_handler)

# Alleen fouten naar aparte log
error_handler = logging.handlers.RotatingFileHandler(
    'logs/error.log',
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=10
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(standard_formatter)
logger.addHandler(error_handler)

# Log de MS Graph API configuratiegegevens (alleen voor debug)
logging.info(f"MS_GRAPH_CLIENT_ID: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_ID') else 'Niet ingesteld'}")
logging.info(f"MS_GRAPH_CLIENT_SECRET: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_SECRET') else 'Niet ingesteld'}")
logging.info(f"MS_GRAPH_TENANT_ID: {'Ingesteld' if os.environ.get('MS_GRAPH_TENANT_ID') else 'Niet ingesteld'}")
logging.info(f"MS_GRAPH_SENDER_EMAIL: {'Ingesteld' if os.environ.get('MS_GRAPH_SENDER_EMAIL') else 'Niet ingesteld'}")

# Create Flask app
app = Flask(__name__)
# Stel secret key in vanuit .env file of gebruik een fallback voor development
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    if os.environ.get("FLASK_ENV") == "production":
        logging.error("SESSION_SECRET is niet ingesteld in .env bestand! De applicatie is niet veilig.")
        # In productie moet de secret key in .env staan, anders stoppen we
        raise ValueError("SESSION_SECRET moet worden ingesteld in het .env bestand voor productiegebruik.")
    else:
        # Voor development gebruiken we een statische key
        logging.warning("SESSION_SECRET is niet ingesteld in .env bestand. Fallback key wordt gebruikt, NIET GEBRUIKEN IN PRODUCTIE!")
        session_secret = "ontwikkeling_test_key_niet_gebruiken_in_productie"
app.secret_key = session_secret

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize database with the app
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Log in om toegang te krijgen tot deze pagina.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

# Context processor toevoegen om huidige jaar beschikbaar te maken in alle templates
@app.context_processor
def inject_year():
    return {'current_year': datetime.now().year}

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

# Import routes at the end to avoid circular imports
from routes import *

# Registreer logs_monitor blueprint
try:
    from logs_monitor import logs_bp, register_error_notification_handlers
    app.register_blueprint(logs_bp)
    register_error_notification_handlers(app)
    app.logger.info("Logs monitoring system geregistreerd")
except ImportError as e:
    app.logger.error(f"Fout bij het registreren van logs monitoring system: {str(e)}")

# Registreer de onboarding blueprint
try:
    from onboarding_routes import onboarding_bp
    app.register_blueprint(onboarding_bp)
    app.logger.info("Onboarding tutorial system geregistreerd")
except ImportError as e:
    app.logger.error(f"Fout bij het registreren van onboarding tutorial system: {str(e)}")

# Voeg custom Jinja2 filters toe
import json
@app.template_filter('fromjson')
def fromjson_filter(value):
    """Convert a JSON string to Python object"""
    try:
        return json.loads(value)
    except:
        return {}

@app.template_filter('split')
def split_filter(value, delimiter=','):
    """Split a string by delimiter"""
    if not value:
        return []
    return value.split(delimiter)

# App initialization is handled in main.py

def run_migrations():
    """Run database migrations to ensure compatibility with new code"""
    with app.app_context():
        try:
            # Import the migration module
            from migrate_database import migrate_whmcs_fields
            # Run the migration
            migrate_whmcs_fields()
            app.logger.info("Database migraties succesvol uitgevoerd")
        except Exception as e:
            app.logger.error(f"Fout bij uitvoeren van database migraties: {str(e)}")

def initialize_app():
    """Initialize the application, create database tables and register blueprints"""
    with app.app_context():
        # Import the models to ensure they are picked up by SQLAlchemy
        from models import User, Customer, Invoice, Workspace, SystemSettings
        
        # Eerst migraties uitvoeren, dan tabellen aanmaken/bijwerken
        run_migrations()
        
        # Vernieuw de tabel-metadata voor specifieke tabellen om kolommen correct te laden
        from database import refresh_table_metadata
        refresh_table_metadata(db.engine, 'invoices')
        refresh_table_metadata(db.engine, 'customers')
        refresh_table_metadata(db.engine, 'workspaces')
        refresh_table_metadata(db.engine, 'system_settings')
        
        # Vernieuw de metadata in SQLAlchemy zodat het de nieuwste schema-wijzigingen gebruikt
        db.metadata.clear()
        from models import User, Customer, Invoice, Workspace, SystemSettings  # Opnieuw importeren om metadata te vernieuwen
        
        # Create all tables
        db.create_all()
        
        # Create default admin user
        create_default_admin()
        
        # Register blueprints
        from whmcs_routes import whmcs_bp
        app.register_blueprint(whmcs_bp)
        
        # Tijdelijk uitgeschakeld om opstart te versnellen
        # init_sample_data()
