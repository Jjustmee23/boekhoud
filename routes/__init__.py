"""
Routes package initializatie
"""

# Importeren van login_required en andere utils
from flask import Blueprint, flash, redirect, url_for
from flask_login import current_user, login_required

# Utils voor blueprints
def check_auth_for_blueprint():
    """Controleert of een gebruiker is ingelogd en stel de route in"""
    if not current_user.is_authenticated:
        flash('Je moet ingelogd zijn om deze pagina te bekijken.', 'warning')
        return redirect(url_for('login'))