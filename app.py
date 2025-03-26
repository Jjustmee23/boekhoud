import os
import logging
from datetime import datetime
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create SQLAlchemy model class
class Base(DeclarativeBase):
    pass

# Create SQLAlchemy instance
db = SQLAlchemy(model_class=Base)

# Create the app factory function
def create_app():
    # Create Flask app
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "a secret key")

    # Configure the database connection
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # Initialize app with Flask extensions
    db.init_app(app)

    # Import and register blueprints
    from routes import (
        main_blueprint, 
        invoice_blueprint, 
        customer_blueprint, 
        report_blueprint, 
        upload_blueprint
    )
    
    # Register blueprints with the app
    app.register_blueprint(main_blueprint)
    app.register_blueprint(invoice_blueprint, url_prefix='/invoices')
    app.register_blueprint(customer_blueprint, url_prefix='/customers')
    app.register_blueprint(report_blueprint, url_prefix='/reports')
    app.register_blueprint(upload_blueprint, url_prefix='/uploads')
    
    # Register error handlers
    from routes import not_found_error, internal_error
    app.register_error_handler(404, not_found_error)
    app.register_error_handler(500, internal_error)
    
    # Ensure all tables are created
    with app.app_context():
        db.create_all()
    
    return app

# Create application instance
app = create_app()
