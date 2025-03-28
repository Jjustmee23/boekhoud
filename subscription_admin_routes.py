"""
Routes voor abonnementenbeheer door administrators
"""
import os
import json
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import app, db
from models import Workspace, Subscription, Payment, User, MollieSettings
from utils import format_currency, admin_required, super_admin_required
from mollie_service import mollie_service

# Admin abonnementen dashboard
@app.route('/admin/subscriptions')
@login_required
@admin_required
def admin_subscriptions():
    """Toon abonnementen beheerdashboard voor admins"""
    
    # Haal alle abonnementen op
    subscriptions = Subscription.query.all()
    
    # Huidige datum voor statusberekeningen
    now = datetime.now()
    
    return render_template(
        'admin/subscriptions_dashboard.html',
        subscriptions=subscriptions,
        now=now,
        format_currency=format_currency
    )

# Nieuw abonnement aanmaken
@app.route('/admin/subscriptions/new')
@login_required
@admin_required
def new_subscription():
    """Toon formulier voor nieuw abonnement"""
    now = datetime.now()
    return render_template(
        'admin/edit_subscription_form.html',
        subscription=None,
        format_currency=format_currency,
        now=now
    )

# Bestaand abonnement bewerken
@app.route('/admin/subscriptions/edit/<int:subscription_id>')
@login_required
@admin_required
def admin_edit_subscription(subscription_id):
    """Toon formulier voor bewerken abonnement"""
    
    # Haal abonnement op
    subscription = Subscription.query.get_or_404(subscription_id)
    now = datetime.now()
    
    return render_template(
        'admin/edit_subscription_form.html',
        subscription=subscription,
        format_currency=format_currency,
        now=now
    )

# Bekijk abonnementdetails
@app.route('/admin/subscriptions/view/<int:subscription_id>')
@login_required
@admin_required
def view_subscription(subscription_id):
    """Toon abonnementdetails"""
    
    # Haal abonnement op
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Huidige datum voor statusberekeningen
    now = datetime.now()
    
    return render_template(
        'admin/view_subscription.html',
        subscription=subscription,
        now=now,
        format_currency=format_currency
    )

# Maak nieuw abonnement
@app.route('/admin/subscriptions/create', methods=['POST'])
@login_required
@admin_required
def admin_create_subscription():
    """Verwerk het aanmaken van een nieuw abonnement"""
    
    # Haal formuliergegevens op
    name = request.form.get('name')
    description = request.form.get('description')
    price_monthly = float(request.form.get('price_monthly') or 0)
    price_yearly = float(request.form.get('price_yearly') or 0)
    max_users = int(request.form.get('max_users') or 1)
    max_invoices_per_month = int(request.form.get('max_invoices_per_month') or 50)
    price_per_extra_user = float(request.form.get('price_per_extra_user') or 0)
    is_active = 'is_active' in request.form
    
    # Verwerk feature selecties
    features = {
        'facturen': True,  # Altijd aanwezig
        'klantenbeheer': True,  # Altijd aanwezig
        'basis_rapporten': True,  # Altijd aanwezig
        'geavanceerde_rapporten': 'features[geavanceerde_rapporten]' in request.form,
        'documentverwerking': 'features[documentverwerking]' in request.form,
        'email_integratie': 'features[email_integratie]' in request.form,
        'api_toegang': 'features[api_toegang]' in request.form,
        'prioriteit_support': 'features[prioriteit_support]' in request.form,
        'dedicated_account_manager': 'features[dedicated_account_manager]' in request.form,
        'eerste_maand_gratis': 'features[eerste_maand_gratis]' in request.form
    }
    features_json = json.dumps(features)
    
    # Maak nieuw abonnement
    subscription = Subscription(
        name=name,
        description=description,
        price_monthly=price_monthly,
        price_yearly=price_yearly,
        max_users=max_users,
        max_invoices_per_month=max_invoices_per_month,
        price_per_extra_user=price_per_extra_user,
        is_active=is_active,
        features=features_json
    )
    
    try:
        db.session.add(subscription)
        db.session.commit()
        flash(f'Abonnement "{name}" succesvol aangemaakt!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij aanmaken abonnement: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van het abonnement', 'danger')
    
    return redirect(url_for('admin_subscriptions'))

# Update bestaand abonnement
@app.route('/admin/subscriptions/save/<int:subscription_id>', methods=['POST'])
@login_required
@admin_required
def save_subscription(subscription_id):
    """Verwerk het bijwerken van een bestaand abonnement"""
    
    # Haal abonnement op
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Haal formuliergegevens op
    subscription.name = request.form.get('name')
    subscription.description = request.form.get('description')
    subscription.price_monthly = float(request.form.get('price_monthly') or 0)
    subscription.price_yearly = float(request.form.get('price_yearly') or 0)
    subscription.max_users = int(request.form.get('max_users') or 1)
    subscription.max_invoices_per_month = int(request.form.get('max_invoices_per_month') or 50)
    subscription.price_per_extra_user = float(request.form.get('price_per_extra_user') or 0)
    subscription.is_active = 'is_active' in request.form
    
    # Verwerk feature selecties
    features = {
        'facturen': True,  # Altijd aanwezig
        'klantenbeheer': True,  # Altijd aanwezig
        'basis_rapporten': True,  # Altijd aanwezig
        'geavanceerde_rapporten': 'features[geavanceerde_rapporten]' in request.form,
        'documentverwerking': 'features[documentverwerking]' in request.form,
        'email_integratie': 'features[email_integratie]' in request.form,
        'api_toegang': 'features[api_toegang]' in request.form,
        'prioriteit_support': 'features[prioriteit_support]' in request.form,
        'dedicated_account_manager': 'features[dedicated_account_manager]' in request.form,
        'eerste_maand_gratis': 'features[eerste_maand_gratis]' in request.form
    }
    subscription.features = json.dumps(features)
    
    try:
        db.session.commit()
        flash(f'Abonnement "{subscription.name}" succesvol bijgewerkt!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij bijwerken abonnement: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van het abonnement', 'danger')
    
    return redirect(url_for('admin_subscriptions'))

# Toggle abonnement actief/inactief
@app.route('/admin/subscriptions/toggle/<int:subscription_id>')
@login_required
@admin_required
def toggle_subscription(subscription_id):
    """Toggle actief/inactief status van een abonnement"""
    
    # Haal abonnement op
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Toggle status
    subscription.is_active = not subscription.is_active
    
    try:
        db.session.commit()
        status = "geactiveerd" if subscription.is_active else "gedeactiveerd"
        flash(f'Abonnement "{subscription.name}" {status}!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij wijzigen status abonnement: {str(e)}")
        flash('Er is een fout opgetreden bij het wijzigen van de status', 'danger')
    
    return redirect(url_for('admin_subscriptions'))

# Verwijder een abonnement
@app.route('/admin/subscriptions/delete/<int:subscription_id>')
@login_required
@admin_required
def admin_delete_subscription(subscription_id):
    """Verwijder een abonnement"""
    
    # Haal abonnement op
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Controleer of het abonnement in gebruik is
    if len(subscription.workspaces) > 0:
        flash(f'Abonnement "{subscription.name}" is in gebruik door werkruimtes en kan niet worden verwijderd', 'warning')
        return redirect(url_for('admin_subscriptions'))
    
    try:
        db.session.delete(subscription)
        db.session.commit()
        flash(f'Abonnement "{subscription.name}" is verwijderd', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij verwijderen abonnement: {str(e)}")
        flash('Er is een fout opgetreden bij het verwijderen van het abonnement', 'danger')
    
    return redirect(url_for('admin_subscriptions'))

# Abonnementenbeheer voor werkruimte (door admin)
@app.route('/admin/subscription-plans')
@login_required
@admin_required
def admin_subscription_plans():
    """Toon pagina voor abonnementskeuze voor huidige werkruimte"""
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal actieve abonnementen op
    subscriptions = Subscription.query.filter_by(is_active=True).all()
    
    # Huidige datum voor statusberekeningen
    now = datetime.now()
    
    return render_template(
        'subscription_plans.html',
        subscriptions=subscriptions,
        workspace=workspace,
        now=now,
        format_currency=format_currency
    )
    
# Mollie instellingen (alleen super admins)
@app.route('/admin/mollie-settings-admin')
@login_required
@super_admin_required
def admin_mollie_settings_config():
    """Toon en beheer Mollie betalingsinstellingen (alleen voor super admins)"""
    
    # Haal huidige Mollie instellingen op
    mollie_settings = MollieSettings.query.first()
    
    # Als geen instellingen bestaan, maak een nieuw object
    if not mollie_settings:
        mollie_settings = MollieSettings()
        
    # Huidige status van Mollie API controleren
    mollie_api_status = False
    api_error = None
    
    if mollie_settings.api_key:
        try:
            status = mollie_service.check_api_status(mollie_settings.api_key)
            mollie_api_status = status['success']
            if not mollie_api_status:
                api_error = status.get('error', 'Onbekende fout bij het controleren van de Mollie API status.')
        except Exception as e:
            logging.error(f"Fout bij controleren Mollie API status: {str(e)}")
            api_error = str(e)
    
    # Haal recente betalingen op
    recent_payments = Payment.query.order_by(Payment.created_at.desc()).limit(10).all()
    
    return render_template(
        'admin/mollie_settings.html',
        mollie_settings=mollie_settings,
        mollie_api_status=mollie_api_status,
        api_error=api_error,
        recent_payments=recent_payments,
        now=datetime.now(),
        format_currency=format_currency
    )

# Update Mollie instellingen
@app.route('/admin/mollie-settings/update-admin', methods=['POST'])
@login_required
@super_admin_required
def update_mollie_settings_admin():
    """Update Mollie betalingsinstellingen"""
    
    # Haal huidige Mollie instellingen op of maak nieuwe
    mollie_settings = MollieSettings.query.first()
    if not mollie_settings:
        mollie_settings = MollieSettings()
        db.session.add(mollie_settings)
    
    # Update instellingen vanuit formulier
    mollie_settings.api_key = request.form.get('api_key')
    mollie_settings.webhook_url = request.form.get('webhook_url')
    mollie_settings.redirect_url = request.form.get('redirect_url')
    mollie_settings.company_name = request.form.get('company_name')
    mollie_settings.email = request.form.get('email')
    mollie_settings.locale = request.form.get('locale')
    
    # Opslaan in database
    try:
        db.session.commit()
        flash('Mollie instellingen zijn bijgewerkt!', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij bijwerken Mollie instellingen: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de Mollie instellingen', 'danger')
    
    return redirect(url_for('admin_mollie_settings_config'))

# Test Mollie API verbinding
@app.route('/admin/mollie-settings/test')
@login_required
@super_admin_required
def test_mollie_connection():
    """Test de verbinding met de Mollie API"""
    
    # Haal huidige Mollie instellingen op
    mollie_settings = MollieSettings.query.first()
    
    if not mollie_settings or not mollie_settings.api_key:
        flash('Mollie API-sleutel is niet geconfigureerd', 'warning')
        return redirect(url_for('admin_mollie_settings_config'))
    
    # Test verbinding
    try:
        status = mollie_service.check_api_status(mollie_settings.api_key)
        if status['success']:
            flash('Verbinding met Mollie API succesvol!', 'success')
        else:
            flash(f'Fout bij verbinden met Mollie API: {status.get("error", "Onbekende fout")}', 'danger')
    except Exception as e:
        logging.error(f"Fout bij testen Mollie verbinding: {str(e)}")
        flash(f'Fout bij verbinden met Mollie API: {str(e)}', 'danger')
    
    return redirect(url_for('admin_mollie_settings_config'))