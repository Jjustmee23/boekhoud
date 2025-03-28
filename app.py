import os
import logging
import logging.handlers
import json
from datetime import datetime
from flask import Flask, session, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Maak logs directory aan als deze niet bestaat
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Configureer uitgebreid logging systeem
def setup_logging():
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Formaat voor console logs
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Formaat voor bestandslogs (uitgebreider)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - '
        '%(message)s'
    )
    
    # JSON formaat voor gestructureerde logs
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "lineno": record.lineno,
            }
            # Voeg exception info toe indien aanwezig
            if record.exc_info:
                log_record["exception"] = self.formatException(record.exc_info)
            
            # Voeg extra context toe
            if hasattr(record, 'request_id'):
                log_record["request_id"] = record.request_id
            if hasattr(record, 'user_id'):
                log_record["user_id"] = record.user_id
                
            return json.dumps(log_record)
    
    # Console handler (alleen info en hoger)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Bestand handler voor alle logs
    all_log_file = os.path.join(logs_dir, 'app.log')
    file_handler = logging.handlers.RotatingFileHandler(
        all_log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Bestand handler voor alleen error logs
    error_log_file = os.path.join(logs_dir, 'error.log')
    error_file_handler = logging.handlers.RotatingFileHandler(
        error_log_file, maxBytes=10*1024*1024, backupCount=5
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_file_handler)
    
    # JSON log bestand voor gestructureerde logging
    json_log_file = os.path.join(logs_dir, 'app.json.log')
    json_handler = logging.handlers.RotatingFileHandler(
        json_log_file, maxBytes=10*1024*1024, backupCount=5
    )
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(json_handler)
    
    return root_logger

# Initialiseer het logging systeem
logger = setup_logging()

# Log de MS Graph API configuratiegegevens
logger.info(f"MS_GRAPH_CLIENT_ID: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_ID') else 'Niet ingesteld'}")
logger.info(f"MS_GRAPH_CLIENT_SECRET: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_SECRET') else 'Niet ingesteld'}")
logger.info(f"MS_GRAPH_TENANT_ID: {'Ingesteld' if os.environ.get('MS_GRAPH_TENANT_ID') else 'Niet ingesteld'}")
logger.info(f"MS_GRAPH_SENDER_EMAIL: {'Ingesteld' if os.environ.get('MS_GRAPH_SENDER_EMAIL') else 'Niet ingesteld'}")

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

# Logging configuratie voor de app
app.config['LOG_LEVEL'] = os.environ.get('LOG_LEVEL', 'INFO')
app.config['LOG_TO_STDOUT'] = os.environ.get('LOG_TO_STDOUT', 'true').lower() == 'true'
app.config['SHOW_LOGS_IN_ADMIN'] = os.environ.get('SHOW_LOGS_IN_ADMIN', 'true').lower() == 'true'
app.config['LOG_RETENTION_DAYS'] = int(os.environ.get('LOG_RETENTION_DAYS', '30'))

# Configureer request context logger
app.logger = logger

# Request middleware voor het toevoegen van contextinformatie aan logs
@app.before_request
def log_request_info():
    # Voeg een uniek request ID toe voor traceerbaarheid
    request_id = os.urandom(6).hex()
    setattr(request, 'id', request_id)
    
    # Log de basis request info
    app.logger.info(
        f"Request {request_id}: {request.method} {request.path} from {request.remote_addr}",
        extra={
            'request_id': request_id, 
            'method': request.method,
            'path': request.path,
            'ip': request.remote_addr
        }
    )
    
    # Als er een gebruiker is ingelogd, voeg gebruikersinformatie toe
    if current_user.is_authenticated:
        setattr(request, 'user_id', current_user.id)
        app.logger.info(
            f"User {current_user.id} ({current_user.username}) accessing {request.path}",
            extra={'user_id': current_user.id, 'username': current_user.username}
        )

@app.after_request
def log_response_info(response):
    # Log response code en verwerkte tijd
    request_id = getattr(request, 'id', 'unknown')
    status_code = response.status_code
    
    # Log niveau bepalen op basis van status code
    if 200 <= status_code < 400:
        app.logger.info(
            f"Request {request_id} completed with status {status_code}",
            extra={'request_id': request_id, 'status_code': status_code}
        )
    elif 400 <= status_code < 500:
        app.logger.warning(
            f"Request {request_id} completed with client error {status_code}",
            extra={'request_id': request_id, 'status_code': status_code}
        )
    else:
        app.logger.error(
            f"Request {request_id} completed with server error {status_code}",
            extra={'request_id': request_id, 'status_code': status_code}
        )
    
    return response

# Error handlers om fouten naar logs te schrijven
@app.errorhandler(404)
def page_not_found(e):
    request_id = getattr(request, 'id', 'unknown')
    app.logger.warning(
        f"404 Not Found: {request.path} (Request ID: {request_id})",
        extra={'request_id': request_id, 'path': request.path}
    )
    return "Pagina niet gevonden", 404

@app.errorhandler(500)
def internal_server_error(e):
    request_id = getattr(request, 'id', 'unknown')
    app.logger.error(
        f"500 Internal Server Error: {str(e)} (Request ID: {request_id})",
        extra={'request_id': request_id, 'error': str(e)}
    )
    return "Er is een interne serverfout opgetreden", 500

# Initialize database
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Verwijst naar de 'login' route in routes.py
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
