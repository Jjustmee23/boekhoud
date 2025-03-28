from app import app
from flask import Blueprint, render_template, redirect, url_for, send_from_directory
from flask_login import login_required, current_user

# Direct naar routes.py verwijzen voor de root URL

# Importeer de routes in de juiste volgorde
import routes  # Dit bevat de basale routes zoals / en /dashboard
import subscription_routes
from mollie_service import mollie_service

# Importeer de blueprints, maar de registratie gebeurt al in routes.py
from routes.log_viewer import log_bp

# Omdat sommige routes niet correct worden geregistreerd,
# voegen we deze hier handmatig toe
@app.route('/login')
def login_redirect():
    """Redirect naar de login route in routes.py"""
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard_redirect():
    """Redirect naar de dashboard route in routes.py"""
    # We proberen de dashboard-functie aan te roepen uit routes.py
    return redirect('/')

# Directe route naar de logs
@app.route('/logs-redirect')
@login_required
def logs_redirect():
    """Directe toegang tot de logs via een eigen pagina"""
    if not current_user.is_admin:
        return render_template('error.html', error='Geen toegang tot deze functie', code=403)
    return redirect('/logs/')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
