"""
Routes voor abonnementen en Mollie betalingen
"""
import os
import json
import logging
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from app import app, db
from models import Workspace, Subscription, Payment, User, MollieSettings
from mollie_service import mollie_service
from utils import format_currency, super_admin_required

# Werkruimte dashboard voor admins
@app.route('/workspace/dashboard')
@login_required
def workspace_dashboard():
    """Dashboard voor werkruimte eigenaren met overzicht en statistieken"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de werkruimte op (super admins moeten een werkruimte gekozen hebben)
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Importeer modellen
    from models import Customer, Invoice, User
    
    # Verzamel statistieken
    users_count = User.query.filter_by(workspace_id=workspace.id).count()
    customers_count = Customer.query.filter_by(workspace_id=workspace.id).count()
    invoices_count = Invoice.query.filter_by(workspace_id=workspace.id).count()
    
    # Bereken totale omzet
    invoices = Invoice.query.filter_by(workspace_id=workspace.id).all()
    total_revenue = sum(invoice.amount_incl_vat for invoice in invoices)
    total_revenue_format = format_currency(total_revenue)
    
    # Bereken recente facturen
    recent_invoices = Invoice.query.filter_by(workspace_id=workspace.id).order_by(Invoice.date.desc()).limit(5).all()
    
    # Bereken recente klanten
    recent_customers = Customer.query.filter_by(workspace_id=workspace.id).order_by(Customer.id.desc()).limit(5).all()
    
    # Bereken facturen deze maand (voor controle van abonnementslimiet)
    current_month = datetime.now().month
    current_year = datetime.now().year
    monthly_invoice_count = Invoice.query.filter_by(workspace_id=workspace.id).filter(
        db.extract('month', Invoice.date) == current_month,
        db.extract('year', Invoice.date) == current_year
    ).count()
    
    # Bereid chartdata voor: facturen per maand voor het afgelopen jaar
    from utils import get_months
    current_year = datetime.now().year
    months = get_months(current_year)
    
    # Initialiseer data arrays
    invoice_data = [0] * 12
    revenue_data = [0] * 4
    
    # Bereken facturen per maand
    for i, month_num in enumerate(range(1, 13)):
        count = Invoice.query.filter_by(workspace_id=workspace.id).filter(
            db.extract('month', Invoice.date) == month_num,
            db.extract('year', Invoice.date) == current_year
        ).count()
        invoice_data[i] = count
    
    # Bereken omzet per kwartaal
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    for invoice in invoices:
        if invoice.date.year == current_year:
            quarter = (invoice.date.month - 1) // 3
            if 0 <= quarter < 4:  # Controleer of het een geldig kwartaal is
                revenue_data[quarter] += invoice.amount_incl_vat
    
    return render_template(
        'workspace_dashboard.html',
        workspace=workspace,
        users_count=users_count,
        customers_count=customers_count,
        invoices_count=invoices_count,
        total_revenue_format=total_revenue_format,
        recent_invoices=recent_invoices,
        recent_customers=recent_customers,
        monthly_invoice_count=monthly_invoice_count,
        months=months,
        quarters=quarters,
        invoice_data=invoice_data,
        revenue_data=revenue_data,
        format_currency=format_currency,
        now=datetime.now()
    )

# Werkruimte beheer voor admins
# Deze functie is verwijderd en geïntegreerd in de admin() functie in routes.py

@app.route('/workspace/settings', methods=['GET', 'POST'])
@login_required
def update_workspace_settings():
    """Toon en update werkruimte instellingen"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal e-mailinstellingen op voor deze werkruimte
    from models import EmailSettings
    email_settings = EmailSettings.query.filter_by(workspace_id=workspace.id).first()
    
    if request.method == 'POST':
        # Update werkruimte
        workspace.name = request.form.get('name')
        workspace.description = request.form.get('description', '')
        workspace.domain = request.form.get('domain', '')
        
        try:
            db.session.commit()
            flash('Werkruimte instellingen bijgewerkt', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Fout bij updaten werkruimte: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de werkruimte', 'danger')
    
    # GET verzoek - toon werkruimte instellingen formulier
    return render_template('workspace_settings.html',
                          workspace=workspace,
                          email_settings=email_settings,
                          now=datetime.now())

@app.route('/workspace/users/create', methods=['POST'])
@login_required
def create_workspace_user():
    """Maak een nieuwe gebruiker in de werkruimte"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of er ruimte is voor extra gebruikers
    current_users = User.query.filter_by(workspace_id=workspace.id).count()
    max_users = 0
    
    if workspace.subscription:
        max_users = workspace.subscription.max_users + workspace.extra_users
    
    if current_users >= max_users and max_users > 0:
        flash('Je hebt het maximale aantal gebruikers bereikt. Upgrade je abonnement of koop extra gebruikers.', 'warning')
        return redirect(url_for('admin'))
    
    # Maak nieuwe gebruiker
    from models import create_user
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form
    password_change_required = 'password_change_required' in request.form
    
    # Controleer of gebruikersnaam/e-mail al bestaat in deze werkruimte
    existing_user = User.query.filter(
        (User.username == username) & (User.workspace_id == workspace.id) |
        (User.email == email) & (User.workspace_id == workspace.id)
    ).first()
    
    if existing_user:
        flash('Gebruikersnaam of e-mail is al in gebruik binnen deze werkruimte', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # Maak gebruiker
        user = create_user(username, email, password, is_admin, False)
        
        # Wijs toe aan werkruimte
        user.workspace_id = workspace.id
        user.password_change_required = password_change_required
        
        db.session.commit()
        
        flash(f'Gebruiker {username} aangemaakt', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij aanmaken gebruiker: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van de gebruiker', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/workspace/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_workspace_user(user_id):
    """Bewerk een gebruiker in de werkruimte"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    # Haal gebruiker op
    user = User.query.get(user_id)
    if not user or user.workspace_id != current_user.workspace_id:
        flash('Gebruiker niet gevonden in je werkruimte', 'danger')
        return redirect(url_for('admin'))
    
    # Voorkom dat iemand zichzelf uit admin rechten haalt
    if user.id == current_user.id and request.method == 'POST' and 'is_admin' not in request.form:
        flash('Je kunt je eigen admin rechten niet intrekken', 'warning')
        return redirect(url_for('edit_workspace_user', user_id=user_id))
    
    # Verwerk formulier
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        is_admin = 'is_admin' in request.form
        
        try:
            from models import update_user
            update_user(user_id, email, new_password if new_password else None, is_admin)
            flash(f'Gebruiker {user.username} bijgewerkt', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            logging.error(f"Fout bij bijwerken gebruiker: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de gebruiker', 'danger')
    
    return render_template('edit_workspace_user.html', user=user, now=datetime.now())

@app.route('/workspace/users/<int:user_id>/delete', methods=['GET', 'POST'])
@login_required
def delete_workspace_user(user_id):
    """Verwijder een gebruiker uit de werkruimte"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    # Haal gebruiker op
    user = User.query.get(user_id)
    if not user or user.workspace_id != current_user.workspace_id:
        flash('Gebruiker niet gevonden in je werkruimte', 'danger')
        return redirect(url_for('admin'))
    
    # Voorkom dat iemand zichzelf verwijdert
    if user.id == current_user.id:
        flash('Je kunt je eigen account niet verwijderen', 'warning')
        return redirect(url_for('admin'))
    
    try:
        from models import delete_user
        if delete_user(user_id):
            flash(f'Gebruiker {user.username} verwijderd', 'success')
        else:
            flash('Kan gebruiker niet verwijderen', 'danger')
    except Exception as e:
        logging.error(f"Fout bij verwijderen gebruiker: {str(e)}")
        flash('Er is een fout opgetreden bij het verwijderen van de gebruiker', 'danger')
    
    return redirect(url_for('admin'))

# Abonnementen routes
@app.route('/workspace/select-subscription')
@login_required
def select_subscription():
    """Toon beschikbare abonnementen voor de werkruimte"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal beschikbare abonnementen op
    subscriptions = Subscription.query.filter_by(is_active=True).all()
    
    # Bereid features voor in subscriptions
    for subscription in subscriptions:
        if subscription.features:
            try:
                # Als features al een dict is, maak er een features_list van
                if isinstance(subscription.features, dict):
                    features_dict = subscription.features
                    subscription.features_list = list(features_dict.keys())
                # Als features een string is (JSON), converteer naar een lijst
                else:
                    features_dict = json.loads(subscription.features)
                    if isinstance(features_dict, list):
                        subscription.features_list = features_dict
                    else:
                        subscription.features_list = [
                            key for key, value in features_dict.items() if value is True
                        ]
            except Exception as e:
                logging.error(f"Fout bij verwerken features: {str(e)}")
                subscription.features_list = []
        else:
            subscription.features_list = []
    
    return render_template(
        'subscriptions.html',
        workspace=workspace,
        subscriptions=subscriptions,
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/workspace/process-subscription', methods=['POST'])
@login_required
def process_subscription():
    """Verwerk een abonnementskeuze"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal abonnement en periode op
    subscription_id = request.form.get('subscription_id')
    period = request.form.get('period', 'monthly')
    
    if not subscription_id:
        flash('Geen abonnement geselecteerd', 'danger')
        return redirect(url_for('select_subscription'))
    
    # Controleer of abonnement bestaat
    subscription = Subscription.query.get(subscription_id)
    if not subscription or not subscription.is_active:
        flash('Ongeldig abonnement geselecteerd', 'danger')
        return redirect(url_for('select_subscription'))
        
    # Maak betaling aan via Mollie
    payment_data = mollie_service.create_payment(workspace.id, subscription.id, period)
    
    if not payment_data:
        flash('Er is een fout opgetreden bij het aanmaken van de betaling. Controleer de Mollie instellingen of probeer het later opnieuw.', 'danger')
        return redirect(url_for('select_subscription'))
    
    # Sla het gekozen abonnement tijdelijk op in de database
    workspace.subscription_id = subscription.id
    workspace.billing_cycle = period
    db.session.commit()
    
    # Redirect naar betaalpagina
    return redirect(payment_data['payment_url'])

@app.route('/payment/return')
@login_required
def payment_return():
    """Pagina die getoond wordt na terugkeer van Mollie betaalpagina"""
    return render_template('payment_completed.html', now=datetime.now())

@app.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    """Webhook voor Mollie betalingen"""
    # Mollie stuurt een id parameter met het payment ID
    payment_id = request.form.get('id')
    
    if not payment_id:
        return 'No payment ID provided', 400
    
    # Verwerk de betaling
    if mollie_service.process_payment_webhook(payment_id):
        return 'Webhook processed', 200
    else:
        return 'Failed to process webhook', 500

@app.route('/workspace/update-extra-users', methods=['GET', 'POST'])
@login_required
def update_extra_users():
    """Pas het aantal extra gebruikers aan"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of er een abonnement is
    if not workspace.subscription_id:
        flash('Je hebt nog geen abonnement gekozen', 'warning')
        return redirect(url_for('admin'))
    
    # Verwerk formulier
    if request.method == 'POST':
        try:
            extra_users = int(request.form.get('extra_users', 0))
            if extra_users < 0:
                extra_users = 0
            
            workspace.extra_users = extra_users
            db.session.commit()
            
            flash('Aantal extra gebruikers bijgewerkt', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Fout bij updaten extra gebruikers: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van het aantal extra gebruikers', 'danger')
        
        return redirect(url_for('admin'))
    
    # Toon formulier
    return render_template(
        'update_extra_users.html',
        workspace=workspace,
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/workspace/subscription')
@login_required
def workspace_subscription():
    """Beheer abonnement voor huidige werkruimte"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(current_user.workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal alle beschikbare abonnementen op
    subscriptions = Subscription.query.filter_by(is_active=True).all()
    
    # Bereid features voor in subscriptions
    for subscription in subscriptions:
        if subscription.features:
            try:
                # Als features al een dict is, maak er een features_list van
                if isinstance(subscription.features, dict):
                    features_dict = subscription.features
                    subscription.features_list = list(features_dict.keys())
                # Als features een string is (JSON), converteer naar een lijst
                else:
                    features_dict = json.loads(subscription.features)
                    subscription.features_list = [
                        key for key, value in features_dict.items() if value is True
                    ]
            except Exception as e:
                logging.error(f"Fout bij verwerken features: {str(e)}")
                subscription.features_list = []
        else:
            subscription.features_list = []
    
    # Haal de betalingen op voor deze werkruimte
    payments = Payment.query.filter_by(workspace_id=workspace.id)\
                           .order_by(Payment.created_at.desc())\
                           .limit(10).all()
    
    now = datetime.now()
    
    return render_template(
        'subscription_plans.html',
        workspace=workspace,
        subscriptions=subscriptions,
        payments=payments,
        now=now,
        format_currency=format_currency
    )

@app.route('/workspace/change-subscription')
@login_required
def change_subscription():
    """Wijzig het abonnement van de werkruimte"""
    # Dit is een redirect naar select_subscription
    flash('Selecteer hieronder een nieuw abonnement', 'info')
    return redirect(url_for('select_subscription'))

@app.route('/workspace/cancel-subscription')
@login_required
def cancel_subscription():
    """Zeg het abonnement op"""
    # Controleer of de gebruiker een admin is
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('Je hebt geen toegang tot deze functie', 'danger')
        return redirect(url_for('dashboard'))
    
    # Controleer of werkruimte bestaat
    if not current_user.workspace_id:
        flash('Je moet eerst een werkruimte kiezen', 'warning')
        return redirect(url_for('dashboard'))
    
    # Update workspace subscription info
    workspace = Workspace.query.get(current_user.workspace_id)
    if workspace:
        workspace.subscription_end_date = datetime.now() + timedelta(days=30)  # Geef 30 dagen toegang
        try:
            db.session.commit()
            flash('Je abonnement is opgezegd. Je hebt nog toegang tot het einde van de huidige periode.', 'success')
        except Exception as e:
            db.session.rollback()
            logging.error(f"Fout bij opzeggen abonnement: {str(e)}")
            flash('Er is een fout opgetreden bij het opzeggen van je abonnement. Probeer het opnieuw of neem contact op met de beheerder.', 'danger')
    else:
        flash('Werkruimte niet gevonden', 'danger')
    
    return redirect(url_for('admin'))

# Admin routes voor abonnementen en Mollie
@app.route('/admin/mollie-settings', methods=['GET'])
@login_required
@super_admin_required
def admin_mollie_settings():
    """Beheer van Mollie instellingen (enkel super admins)"""
    
    # Haal Mollie instellingen op, gebruik de kolommen die daadwerkelijk in de database bestaan
    try:
        # Gebruik specifieke kolommen in plaats van alle kolommen
        mollie_settings = db.session.query(
            MollieSettings.id,
            MollieSettings.api_key_test,
            MollieSettings.api_key_live,
            MollieSettings.is_test_mode,
            MollieSettings.webhook_url,
            MollieSettings.redirect_url,
            MollieSettings.is_system_default,
            MollieSettings.workspace_id,
            MollieSettings.created_at,
            MollieSettings.updated_at
        ).first()
        
        if not mollie_settings:
            # Maak een nieuwe instantie als er geen instellingen zijn
            mollie_settings = MollieSettings(
                api_key_test="",
                api_key_live="",
                is_test_mode=True,
                webhook_url="",
                redirect_url="",
                is_system_default=True
            )
            db.session.add(mollie_settings)
            db.session.commit()
    except Exception as e:
        app.logger.error(f"Fout bij ophalen Mollie instellingen: {str(e)}")
        # Maak een nieuwe instantie als er iets mis gaat bij het ophalen
        mollie_settings = MollieSettings(
            api_key_test="",
            api_key_live="",
            is_test_mode=True,
            webhook_url="",
            redirect_url="",
            is_system_default=True
        )
    
    # Haal abonnementen op
    subscriptions = Subscription.query.all()
    
    # Haal recente betalingen op
    payments = Payment.query.order_by(Payment.created_at.desc()).limit(20).all()
    
    # Huidige datum voor templates
    now = datetime.now()
    
    return render_template(
        'admin_mollie_settings.html',
        mollie_settings=mollie_settings,
        subscriptions=subscriptions,
        now=now,
        payments=payments,
        format_currency=format_currency
    )

@app.route('/admin/update-mollie-settings', methods=['POST'])
@login_required
@super_admin_required
def update_mollie_settings():
    """Update Mollie instellingen"""
    
    # Haal formuliergegevens op
    api_key = request.form.get('api_key')
    is_test_mode = 'is_test_mode' in request.form
    webhook_url = request.form.get('webhook_url')
    redirect_url = request.form.get('redirect_url')
    
    # Update instellingen
    result = mollie_service.update_settings(
        api_key=api_key,
        is_test_mode=is_test_mode,
        webhook_url=webhook_url,
        redirect_url=redirect_url
    )
    
    if result:
        flash('Mollie instellingen bijgewerkt', 'success')
    else:
        flash('Er is een fout opgetreden bij het bijwerken van de Mollie instellingen', 'danger')
    
    return redirect(url_for('admin_mollie_settings'))

@app.route('/admin/create-subscription', methods=['POST'])
@login_required
@super_admin_required
def create_subscription():
    """Maak een nieuw abonnement aan"""
    
    # Haal formuliergegevens op
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    try:
        price_monthly = float(request.form.get('price_monthly', 0))
        price_yearly = float(request.form.get('price_yearly', 0))
        max_users = int(request.form.get('max_users', 1))
        max_invoices_per_month = int(request.form.get('max_invoices_per_month', 50))
        price_per_extra_user = float(request.form.get('price_per_extra_user', 0))
    except (ValueError, TypeError):
        flash('Ongeldige numerieke waarden ingevuld', 'danger')
        return redirect(url_for('admin_mollie_settings'))
    
    is_active = request.form.get('is_active') == 'true'
    
    # Verwerk features (één per regel) naar JSON array
    features_input = request.form.get('features', '')
    features_list = [line.strip() for line in features_input.split('\n') if line.strip()]
    features_json = json.dumps(features_list)
    
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
        flash(f'Abonnement "{name}" aangemaakt', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij aanmaken abonnement: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van het abonnement', 'danger')
    
    return redirect(url_for('admin_mollie_settings'))

@app.route('/admin/edit-subscription/<int:subscription_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_subscription(subscription_id):
    """Bewerk een abonnement"""
    
    # Haal abonnement op
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        flash('Abonnement niet gevonden', 'danger')
        return redirect(url_for('admin_mollie_settings'))
    
    # Verwerk formulier
    if request.method == 'POST':
        subscription.name = request.form.get('name')
        subscription.description = request.form.get('description', '')
        
        try:
            subscription.price_monthly = float(request.form.get('price_monthly', 0))
            subscription.price_yearly = float(request.form.get('price_yearly', 0))
            subscription.max_users = int(request.form.get('max_users', 1))
            subscription.max_invoices_per_month = int(request.form.get('max_invoices_per_month', 50))
            subscription.price_per_extra_user = float(request.form.get('price_per_extra_user', 0))
        except (ValueError, TypeError):
            flash('Ongeldige numerieke waarden ingevuld', 'danger')
            return redirect(url_for('edit_subscription', subscription_id=subscription_id))
        
        subscription.is_active = request.form.get('is_active') == 'true'
        
        # Verwerk features (één per regel) naar JSON array
        features_input = request.form.get('features', '')
        features_list = [line.strip() for line in features_input.split('\n') if line.strip()]
        subscription.features = json.dumps(features_list)
        
        try:
            db.session.commit()
            flash(f'Abonnement "{subscription.name}" bijgewerkt', 'success')
            return redirect(url_for('admin_mollie_settings'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Fout bij bijwerken abonnement: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van het abonnement', 'danger')
    
    # Features voorbereiden voor weergave
    features_text = ""
    if subscription.features:
        try:
            features_list = json.loads(subscription.features)
            features_text = "\n".join(features_list)
        except:
            features_text = ""
    
    return render_template(
        'edit_subscription.html',
        subscription=subscription,
        features_text=features_text,
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/admin/delete-subscription/<int:subscription_id>')
@login_required
@super_admin_required
def delete_subscription(subscription_id):
    """Verwijder een abonnement"""
    
    # Haal abonnement op
    subscription = Subscription.query.get(subscription_id)
    if not subscription:
        flash('Abonnement niet gevonden', 'danger')
        return redirect(url_for('admin_mollie_settings'))
    
    # Controleer of het abonnement in gebruik is
    if len(subscription.workspaces) > 0:
        flash(f'Het abonnement "{subscription.name}" is in gebruik door {len(subscription.workspaces)} werkruimte(s) en kan niet worden verwijderd', 'warning')
        return redirect(url_for('admin_mollie_settings'))
    
    try:
        db.session.delete(subscription)
        db.session.commit()
        flash(f'Abonnement "{subscription.name}" verwijderd', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij verwijderen abonnement: {str(e)}")
        flash('Er is een fout opgetreden bij het verwijderen van het abonnement', 'danger')
    
    return redirect(url_for('admin_mollie_settings'))

@app.route('/admin/check-payment/<int:payment_id>')
@login_required
@super_admin_required
def check_payment(payment_id):
    """Controleer de status van een betaling"""
    
    status = mollie_service.check_payment_status(payment_id)
    
    if status:
        if status['is_paid']:
            flash(f'Betaling {status["mollie_payment_id"]} is betaald', 'success')
        else:
            flash(f'Betaling {status["mollie_payment_id"]} heeft status: {status["status"]}', 'info')
    else:
        flash('Kan de betaling niet controleren', 'danger')
    
    return redirect(url_for('admin_mollie_settings'))

@app.route('/admin/create-example-subscriptions')
@login_required
@super_admin_required
def create_example_subscriptions():
    """Maak voorbeeld abonnementen aan"""
    
    # Controleer of er al abonnementen zijn
    existing_count = Subscription.query.count()
    if existing_count > 0:
        flash(f'Er zijn al {existing_count} abonnementen. Deze functie is alleen beschikbaar als er nog geen abonnementen zijn.', 'warning')
        return redirect(url_for('admin_mollie_settings'))
    
    try:
        # Maak 3 basis abonnementen
        starter = Subscription(
            name="Starter",
            description="Perfect voor zzp'ers en kleine bedrijven",
            price_monthly=9.95,
            price_yearly=99.50,
            max_users=1,
            max_invoices_per_month=50,
            price_per_extra_user=5.00,
            is_active=True,
            features=json.dumps([
                "1 gebruiker",
                "50 facturen per maand",
                "Onbeperkte klanten",
                "E-mailfacturen",
                "Basisrapportages",
                "BTW-aangifte"
            ])
        )
        
        business = Subscription(
            name="Business",
            description="Ideaal voor groeiende bedrijven",
            price_monthly=24.95,
            price_yearly=249.50,
            max_users=3,
            max_invoices_per_month=200,
            price_per_extra_user=4.00,
            is_active=True,
            features=json.dumps([
                "3 gebruikers",
                "200 facturen per maand",
                "Onbeperkte klanten",
                "E-mailfacturen",
                "Uitgebreide rapportages",
                "BTW-aangifte",
                "API-toegang",
                "Factuurtemplates",
                "Klantenportaal"
            ])
        )
        
        professional = Subscription(
            name="Professional",
            description="Complete oplossing voor grotere bedrijven",
            price_monthly=49.95,
            price_yearly=499.50,
            max_users=10,
            max_invoices_per_month=1000,
            price_per_extra_user=2.00,
            is_active=True,
            features=json.dumps([
                "10 gebruikers",
                "1000 facturen per maand",
                "Onbeperkte klanten",
                "E-mailfacturen",
                "Uitgebreide rapportages",
                "BTW-aangifte",
                "API-toegang",
                "Factuurtemplates",
                "Klantenportaal",
                "Prioriteitsondersteuning",
                "Multi-valuta ondersteuning",
                "Geavanceerde boekhouding",
                "Projectmanagement"
            ])
        )
        
        db.session.add_all([starter, business, professional])
        db.session.commit()
        
        flash('Voorbeeld abonnementen aangemaakt', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Fout bij aanmaken voorbeeld abonnementen: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van voorbeeld abonnementen', 'danger')
    
    return redirect(url_for('admin_mollie_settings'))