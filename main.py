from app import app

# Importeer alle routes
import basic_routes  # Eerste import van basic routes voor login & dashboard
import routes
import subscription_routes
import routes.admin_routes
from routes import *  # Import expliciet alle functies uit routes.py

# Import mollie service
from mollie_service import mollie_service

# Toon alle routes voor debugging
print("Alle routes:")
for rule in app.url_map.iter_rules():
    print(f"Route: {rule}, Endpoint: {rule.endpoint}")

# Start de applicatie met debug=True als deze direct wordt aangeroepen
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
