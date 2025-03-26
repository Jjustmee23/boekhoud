from flask import Blueprint

# Create blueprints for different sections of the app
main_blueprint = Blueprint('main', __name__)
invoice_blueprint = Blueprint('invoice', __name__)
customer_blueprint = Blueprint('customer', __name__)
report_blueprint = Blueprint('report', __name__)
upload_blueprint = Blueprint('upload', __name__)

# Import routes to register them with blueprints
from .main_routes import *
from .invoice_routes import *
from .customer_routes import *
from .report_routes import *
from .upload_routes import *

# Error handlers
from .error_handlers import not_found_error, internal_error