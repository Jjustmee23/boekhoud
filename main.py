from app import app, initialize_app
import routes
import subscription_routes
import subscription_admin_routes
import backup_routes
import whmcs_routes
from mollie_service import mollie_service

# Initialize the application, create database tables and add sample data
with app.app_context():
    initialize_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
