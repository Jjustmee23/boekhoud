import os
import logging
from datetime import datetime
from flask import Flask, session

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

# Import routes after app creation to avoid circular imports
from routes import *

# Initialize sample data if needed (for development only)
def init_app():
    from models import customers, invoices, get_next_invoice_number
    
    # Only initialize if no data exists
    if not customers and not invoices:
        # Add some initial data for testing
        from models import add_customer, add_invoice
        
        # Sample customers
        customer1 = add_customer(
            name="Example Company BVBA",
            address="Voorbeeldstraat 123, 1000 Brussels, Belgium",
            vat_number="BE0123456789",
            email="info@example.com"
        )
        
        customer2 = add_customer(
            name="Test Business NV",
            address="Testlaan 45, 2000 Antwerp, Belgium",
            vat_number="BE9876543210",
            email="contact@test-business.be"
        )

# Initialize the app when imported
init_app()
