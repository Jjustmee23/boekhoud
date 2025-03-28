from app import app
import routes
import subscription_routes

# Import mollie service
from mollie_service import mollie_service

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
