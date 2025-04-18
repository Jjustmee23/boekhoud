import os
import logging
import uuid
import json
import traceback
from datetime import datetime, date, timedelta
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify, session, abort, g
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from email_service import EmailService, EmailServiceHelper
from email_service_oauth import EmailServiceOAuth, EmailServiceOAuthHelper

# Logger voor deze module
logger = logging.getLogger(__name__)
from models import (
    Customer, Invoice, User, UserPermission, Workspace, EmailSettings, EmailMessage, get_next_invoice_number, check_duplicate_invoice, add_invoice,
    calculate_vat_report, get_monthly_summary, get_quarterly_summary, get_customer_summary,
    get_users, get_user, create_user, update_user, delete_user
)
from utils import (
    format_currency, format_decimal, generate_pdf_invoice, export_to_excel, export_to_csv,
    get_vat_rates, date_to_quarter, get_quarters, get_months, get_years,
    save_uploaded_file, allowed_file, permission_required, check_permission
)
from file_processor import FileProcessor
from token_helper import token_helper

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Check if there are any workspaces in the database
    workspaces = Workspace.query.all()
    workspaces_exist = len(workspaces) > 0
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        password = request.form.get('password')
        workspace_name = request.form.get('workspace_name')
        workspace_id = request.form.get('workspace_id')  # Fallback voor backward compatibility
        remember = request.form.get('remember', 'false') == 'true'
        
        # Special case: if no workspaces exist yet, allow login with admin/admin123
        if not workspaces_exist and username == 'admin' and password == 'admin123':
            # Create a new super admin user on first login if no workspaces exist
            new_admin = User.query.filter_by(username='admin', is_super_admin=True).first()
            if not new_admin:
                new_admin = User(
                    username='admin',
                    email='admin@example.com',
                    is_admin=True,
                    is_super_admin=True,
                    password_change_required=True
                )
                new_admin.set_password('admin123')
                db.session.add(new_admin)
                db.session.commit()
                flash('Eerste admin-account aangemaakt. Wijzig alstublieft het wachtwoord.', 'success')
            login_user(new_admin, remember=remember)
            return redirect(url_for('dashboard'))
        
        # Initialize user variable to avoid "possibly unbound" error
        user = None
        
        # Regular login flow for when workspaces exist
        if workspaces_exist:
            # log alle loginpogingen
            app.logger.info(f"Login poging voor gebruiker: {username}, werkruimte: {workspace_name}, werkruimte ID: {workspace_id}")
            
            # Controleer eerst of dit een admin-login is, die kan zonder werkruimte inloggen
            super_admin = User.query.filter_by(username=username, is_super_admin=True).first()
            if super_admin:
                app.logger.info(f"Super admin {username} gevonden, controleer wachtwoord")
                if super_admin.check_password(password):
                    app.logger.info(f"Wachtwoord correct voor super admin {username}")
                    user = super_admin
                else:
                    app.logger.info(f"Wachtwoord incorrect voor super admin {username}")
            else:
                # Voor normale gebruikers is werkruimte wel verplicht
                if not username or not password or (not workspace_name and not workspace_id):
                    flash('Gebruikersnaam, wachtwoord en werkruimte zijn verplicht', 'danger')
                    return render_template('login.html', workspaces=workspaces, no_workspaces=not workspaces_exist, now=datetime.now())
                
                # Als werkruimtenaam wordt gebruikt, zoek de bijbehorende workspace_id
                if workspace_name and not workspace_id:
                    workspace = Workspace.query.filter_by(name=workspace_name.strip()).first()
                    if workspace:
                        workspace_id = workspace.id
                        app.logger.info(f"Werkruimte gevonden: {workspace_name} met id {workspace_id}")
                    else:
                        app.logger.info(f"Werkruimte niet gevonden: {workspace_name}")
                        flash(f'Werkruimte "{workspace_name}" niet gevonden', 'danger')
                        return render_template('login.html', workspaces=workspaces, no_workspaces=not workspaces_exist, now=datetime.now())
                
                # Find user by username in the selected workspace
                user = User.query.filter_by(username=username, workspace_id=workspace_id).first()
                app.logger.info(f"Gebruiker zoeken in werkruimte {workspace_id}: {'gevonden' if user else 'niet gevonden'}")
        
        # Check if user exists and password is correct
        if user and user.check_password(password):
            # Log in user
            login_user(user, remember=remember)
            flash(f'Welkom terug, {user.username}!', 'success')
            
            # Check if password change is required (e.g., first login)
            if user.password_change_required:
                flash('Je moet je wachtwoord wijzigen voordat je verder kunt gaan.', 'warning')
                return redirect(url_for('profile'))
            
            # Redirect to requested page or dashboard
            # Als de gebruiker een superadmin is zonder workspace, stuur naar systeemoverzicht
            if user.is_super_admin and not user.workspace_id:
                return redirect(url_for('system_overview'))
            
            # Anders, check next parameter of ga naar gewone dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Ongeldige gebruikersnaam, wachtwoord of werkruimte', 'danger')
            return render_template('login.html', workspaces=Workspace.query.all(), now=datetime.now())
    
    # GET request - show login form with workspaces
    workspaces = Workspace.query.all()
    return render_template('login.html', workspaces=workspaces, now=datetime.now())

@app.route('/register', methods=['GET', 'POST'])
def register():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        workspace_option = request.form.get('workspace_option')
        
        # Validate input
        if not all([username, email, password, confirm_password, workspace_option]):
            flash('Alle velden zijn verplicht', 'danger')
            return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
        
        if password != confirm_password:
            flash('Wachtwoorden komen niet overeen', 'danger')
            return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
        
        # Determine workspace
        workspace_id = None
        if workspace_option == 'join':
            workspace_id = request.form.get('workspace_id')
            if not workspace_id:
                flash('Selecteer een werkruimte om bij aan te sluiten', 'danger')
                return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
        elif workspace_option == 'create':
            workspace_name = request.form.get('workspace_name')
            workspace_description = request.form.get('workspace_description')
            if not workspace_name:
                flash('Werkruimte naam is verplicht', 'danger')
                return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
            
            # Check if workspace name already exists
            existing_workspace = Workspace.query.filter_by(name=workspace_name).first()
            if existing_workspace:
                flash('Deze werkruimte naam is al in gebruik', 'danger')
                return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
            
            # Create new workspace
            new_workspace = Workspace(name=workspace_name, description=workspace_description)
            db.session.add(new_workspace)
            db.session.flush()  # This assigns an ID to new_workspace without committing
            workspace_id = new_workspace.id
        
        # Check if username or email already exists in the selected workspace
        existing_user = User.query.filter(
            (User.username == username) & (User.workspace_id == workspace_id) | 
            (User.email == email) & (User.workspace_id == workspace_id)
        ).first()
        
        if existing_user:
            if existing_user.username == username:
                flash('Deze gebruikersnaam is al in gebruik binnen deze werkruimte', 'danger')
            else:
                flash('Dit e-mailadres is al in gebruik binnen deze werkruimte', 'danger')
            return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
        
        # Create new user
        new_user = User(username=username, email=email, workspace_id=workspace_id)
        new_user.set_password(password)
        
        # Set first user of a workspace as admin
        if User.query.filter_by(workspace_id=workspace_id).count() == 0:
            new_user.is_admin = True
            # Password change required on first login
            new_user.password_change_required = True
        
        # Save to database
        try:
            db.session.add(new_user)
            db.session.commit()
            flash('Account succesvol aangemaakt! Je kunt nu inloggen.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating user: {str(e)}")
            flash('Er is een fout opgetreden bij het aanmaken van je account.', 'danger')
            return render_template('register.html', workspaces=Workspace.query.all(), now=datetime.now())
    
    # GET request - show registration form with workspaces
    workspaces = Workspace.query.all()
    return render_template('register.html', workspaces=workspaces, now=datetime.now())

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Je bent uitgelogd', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Get form data
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Update email if provided
        if email and email != current_user.email:
            # Check if email already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user and existing_user.id != current_user.id:
                flash('Dit e-mailadres is al in gebruik', 'danger')
                return render_template('profile.html', now=datetime.now())
            
            current_user.email = email
            db.session.add(current_user)
            flash('E-mailadres bijgewerkt', 'success')
        
        # Update password if provided
        if current_password and new_password and confirm_password:
            # Check if current password is correct
            if not current_user.check_password(current_password):
                flash('Huidig wachtwoord is onjuist', 'danger')
                return render_template('profile.html', now=datetime.now())
            
            # Check if new passwords match
            if new_password != confirm_password:
                flash('Nieuwe wachtwoorden komen niet overeen', 'danger')
                return render_template('profile.html', now=datetime.now())
            
            # Update password
            current_user.set_password(new_password)
            
            # Reset password_change_required flag if set
            if current_user.password_change_required:
                current_user.password_change_required = False
                flash('Wachtwoord bijgewerkt. Je kunt nu het systeem gebruiken.', 'success')
            else:
                flash('Wachtwoord bijgewerkt', 'success')
                
            db.session.add(current_user)
        
        # Commit changes
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating profile: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van je profiel.', 'danger')
        
        return redirect(url_for('profile'))
    
    # GET request - show profile form
    return render_template('profile.html', now=datetime.now())

# Hulpfunctie voor het bijwerken van het .env bestand
def _update_env_file(env_vars):
    """
    Update het .env bestand met de opgegeven omgevingsvariabelen.
    
    Args:
        env_vars: Dictionary met omgevingsvariabelen en hun waarden
    """
    env_path = '.env'
    
    try:
        # Lees het huidige .env bestand
        with open(env_path, 'r') as file:
            lines = file.readlines()
        
        # Update bestaande variabelen of voeg nieuwe toe
        updated_vars = set()
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('#'):
                for var_name, var_value in env_vars.items():
                    if line.startswith(f"{var_name}="):
                        lines[i] = f"{var_name}={var_value}\n"
                        updated_vars.add(var_name)
        
        # Voeg ontbrekende variabelen toe
        for var_name, var_value in env_vars.items():
            if var_name not in updated_vars:
                lines.append(f"{var_name}={var_value}\n")
        
        # Schrijf de bijgewerkte inhoud terug naar het .env bestand
        with open(env_path, 'w') as file:
            file.writelines(lines)
            
        return True
    except Exception as e:
        logging.error(f"Fout bij het bijwerken van .env bestand: {str(e)}")
        return False

@app.route('/return-to-super-admin', methods=['POST'])
@login_required
def return_to_super_admin():
    """Route om terug te keren naar super admin account na toegang tot een werkruimte"""
    # Controleer of er een super_admin_id in de sessie staat
    super_admin_id = session.get('super_admin_id')
    if not super_admin_id:
        flash('Er is geen super admin sessie actief', 'danger')
        return redirect(url_for('profile'))
    
    # Vind de super admin gebruiker
    super_admin = User.query.get(super_admin_id)
    if not super_admin or not super_admin.is_super_admin:
        flash('Super admin account niet gevonden', 'danger')
        session.pop('super_admin_id', None)  # Verwijder de ongeldige sessie data
        return redirect(url_for('dashboard'))
    
    # Log uit huidige gebruiker en log in als super admin
    logout_user()
    login_user(super_admin)
    
    # Verwijder super_admin_id uit sessie
    session.pop('super_admin_id', None)
    
    flash('Je bent teruggekeerd naar je super admin account', 'success')
    return redirect(url_for('system_overview'))

# Dashboard routes
@app.route('/')
@login_required
def dashboard():
    # Get current year
    current_year = datetime.now().year
    
    # Controleer of het een superadmin is zonder actieve workspace sessie
    # Super admins hebben geen workspace_id of hebben een actieve workspace sessie (via session['super_admin_id'])
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        # Stuur superadmins zonder workspace naar het systeem overzicht
        return redirect(url_for('system_overview'))
    
    # Voor normale gebruikers en super admins die ingelogd zijn in een werkruimte
    # Bepaal werkruimte ID (None voor super admin zonder workspace sessie)
    workspace_id = current_user.workspace_id
    
    # Get summaries for the workspace
    monthly_summary = get_monthly_summary(current_year, workspace_id)
    quarterly_summary = get_quarterly_summary(current_year, workspace_id)
    customer_summary = get_customer_summary(workspace_id)
    
    # Calculate totals for the year
    year_income = sum(month['income'] for month in monthly_summary)
    year_expenses = sum(month['expenses'] for month in monthly_summary)
    year_profit = year_income - year_expenses
    
    # Calculate VAT totals
    vat_collected = sum(month['vat_collected'] for month in monthly_summary)
    vat_paid = sum(month['vat_paid'] for month in monthly_summary)
    vat_balance = vat_collected - vat_paid
    
    # Get recent invoices (5 most recent) for the workspace
    recent_invoices_query = Invoice.query.filter_by(workspace_id=workspace_id)
    recent_invoices_query = recent_invoices_query.order_by(Invoice.date.desc()).limit(5)
    
    # Convert to dictionary format for the template
    recent_invoices = []
    for invoice in recent_invoices_query:
        invoice_dict = invoice.to_dict()
        customer = Customer.query.get(invoice.customer_id)
        invoice_dict['customer_name'] = customer.name if customer else 'Onbekende Klant'
        recent_invoices.append(invoice_dict)
    
    return render_template(
        'dashboard.html',
        monthly_summary=monthly_summary,
        quarterly_summary=quarterly_summary,
        customer_summary=customer_summary,
        year_income=year_income,
        year_expenses=year_expenses,
        year_profit=year_profit,
        vat_collected=vat_collected,
        vat_paid=vat_paid,
        vat_balance=vat_balance,
        recent_invoices=recent_invoices,
        current_year=current_year,
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/dashboard/api/monthly-data/<int:year>')
def api_monthly_data(year):
    """API endpoint for monthly chart data"""
    # Super admins zonder actieve workspace sessie krijgen lege data
    if current_user.is_super_admin and not session.get('super_admin_id'):
        return jsonify({
            'labels': [],
            'income': [],
            'expenses': [],
            'profit': []
        })
    
    # Voor werkruimte gebruikers en super admins in een werkruimte
    workspace_id = current_user.workspace_id
    monthly_data = get_monthly_summary(year, workspace_id)
    
    # Format data for Chart.js
    labels = [month['month_name'] for month in monthly_data]
    income_data = [float(month['income']) for month in monthly_data]
    expense_data = [float(month['expenses']) for month in monthly_data]
    profit_data = [float(month['profit']) for month in monthly_data]
    
    return jsonify({
        'labels': labels,
        'income': income_data,
        'expenses': expense_data,
        'profit': profit_data
    })

@app.route('/dashboard/api/quarterly-data/<int:year>')
def api_quarterly_data(year):
    """API endpoint for quarterly chart data"""
    # Super admins zonder actieve workspace sessie krijgen lege data
    if current_user.is_super_admin and not session.get('super_admin_id'):
        return jsonify({
            'labels': [],
            'income': [],
            'expenses': [],
            'profit': []
        })
    
    # Voor werkruimte gebruikers en super admins in een werkruimte
    workspace_id = current_user.workspace_id
    quarterly_data = get_quarterly_summary(year, workspace_id)
    
    # Format data for Chart.js
    labels = [f"Q{quarter['quarter']}" for quarter in quarterly_data]
    income_data = [float(quarter['income']) for quarter in quarterly_data]
    expense_data = [float(quarter['expenses']) for quarter in quarterly_data]
    profit_data = [float(quarter['profit']) for quarter in quarterly_data]
    
    return jsonify({
        'labels': labels,
        'income': income_data,
        'expenses': expense_data,
        'profit': profit_data
    })

# Invoice management routes
@app.route('/invoices')
@login_required
@permission_required('can_view_invoices')
def invoices_list():
    # Super admin zonder actieve workspace sessie kan geen facturen zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om facturen te bekijken', 'warning')
        return redirect(url_for('dashboard'))
    
    # Get filter parameters
    customer_id = request.args.get('customer_id')
    invoice_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query with filters
    query = Invoice.query
    
    # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
    workspace_id = current_user.workspace_id
    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)
    
    if customer_id:
        # Convert string to UUID if needed
        if isinstance(customer_id, str):
            try:
                customer_id = uuid.UUID(customer_id)
            except ValueError:
                flash('Ongeldige klant-ID', 'danger')
                # Continue with no filter if invalid
        query = query.filter(Invoice.customer_id == customer_id)
    
    if invoice_type:
        query = query.filter(Invoice.invoice_type == invoice_type)
    
    if start_date:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(Invoice.date >= start_date)
    
    if end_date:
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(Invoice.date <= end_date)
    
    # Order by date, newest first
    query = query.order_by(Invoice.date.desc())
    
    # Execute query
    invoices_query = query.all()
    
    # Convert to dictionary format for the template
    invoices_data = []
    for invoice in invoices_query:
        invoice_dict = invoice.to_dict()
        customer = Customer.query.get(invoice.customer_id)
        invoice_dict['customer_name'] = customer.name if customer else 'Onbekende Klant'
        invoices_data.append(invoice_dict)
    
    # Get customers for filter dropdown (alleen van huidige werkruimte)
    customers_query = Customer.query
    if workspace_id:
        customers_query = customers_query.filter_by(workspace_id=workspace_id)
    customers_data = [customer.to_dict() for customer in customers_query.all()]
    
    return render_template(
        'invoices.html',
        invoices=invoices_data,
        customers=customers_data,
        filter_customer_id=customer_id,
        filter_type=invoice_type,
        filter_start_date=start_date,
        filter_end_date=end_date,
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/invoices/new', methods=['GET', 'POST'])
@login_required
@permission_required('can_add_invoices')
def new_invoice():
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        date_str = request.form.get('date')
        invoice_type = request.form.get('type')
        amount_incl_vat = request.form.get('amount_incl_vat')
        vat_rate = request.form.get('vat_rate')
        invoice_number = request.form.get('invoice_number')  # Optional
        
        # Validate data
        if not all([customer_id, date_str, invoice_type, amount_incl_vat, vat_rate]):
            flash('Alle velden zijn verplicht', 'danger')
            customers_query = Customer.query.all()
            customers_data = [customer.to_dict() for customer in customers_query]
            return render_template(
                'invoice_form.html',
                customers=customers_data,
                vat_rates=get_vat_rates(),
                invoice={'date': datetime.now().strftime('%Y-%m-%d'), 'type': 'income'},
                now=datetime.now()
            )
        
        try:
            # Convert customer_id to UUID
            if isinstance(customer_id, str):
                customer_id = uuid.UUID(customer_id)
                
            # Convert date string to date object
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Parse amounts
            amount_incl_vat_float = float(amount_incl_vat)
            vat_rate_float = float(vat_rate)
            
            # Calculate amounts
            amount_incl_vat_decimal = Decimal(str(amount_incl_vat_float))
            vat_rate_decimal = Decimal(str(vat_rate_float))
            vat_amount = amount_incl_vat_decimal - (amount_incl_vat_decimal / (1 + vat_rate_decimal / 100))
            amount_excl_vat = amount_incl_vat_decimal - vat_amount
            
            # Handle file upload
            file_path = None
            if 'invoice_file' in request.files:
                file = request.files['invoice_file']
                if file and file.filename and allowed_file(file.filename):
                    file_path = save_uploaded_file(file)
                    if not file_path:
                        flash('Bestand uploaden mislukt', 'warning')
                elif file and file.filename:
                    flash('Alleen PDF, PNG, JPG en JPEG bestanden zijn toegestaan', 'warning')
            
            # Check for duplicate invoice number
            if invoice_number:
                existing_invoice = Invoice.query.filter_by(invoice_number=invoice_number).first()
                if existing_invoice:
                    duplicate_id = existing_invoice.id
                    flash(f'Factuur met dit nummer bestaat al. <a href="{url_for("view_invoice", invoice_id=duplicate_id)}">Bekijk dubbele factuur</a>', 'warning')
                    customers_query = Customer.query.all()
                    customers_data = [customer.to_dict() for customer in customers_query]
                    return render_template(
                        'invoice_form.html',
                        customers=customers_data,
                        vat_rates=get_vat_rates(),
                        invoice=request.form,
                        now=datetime.now()
                    )
            else:
                # Generate new invoice number
                invoice_number = get_next_invoice_number()
            
            # Check if customer exists
            customer = Customer.query.get(customer_id)
            if not customer:
                flash('Klant niet gevonden', 'danger')
                customers_query = Customer.query.all()
                customers_data = [customer.to_dict() for customer in customers_query]
                return render_template(
                    'invoice_form.html',
                    customers=customers_data,
                    vat_rates=get_vat_rates(),
                    invoice=request.form,
                    now=datetime.now()
                )
            
            # Create new invoice
            invoice = Invoice(
                invoice_number=invoice_number,
                customer_id=customer_id,
                date=date,
                invoice_type=invoice_type,
                amount_excl_vat=float(amount_excl_vat),
                amount_incl_vat=amount_incl_vat_float,
                vat_rate=vat_rate_float,
                vat_amount=float(vat_amount),
                file_path=file_path,
                workspace_id=current_user.workspace_id
            )
            
            # Save to database
            db.session.add(invoice)
            db.session.commit()
            
            flash('Factuur succesvol toegevoegd', 'success')
            return redirect(url_for('invoices_list'))
            
        except ValueError as e:
            flash(f'Ongeldige invoer: {str(e)}', 'danger')
            logging.error(f"Error adding invoice: {str(e)}")
        except Exception as e:
            db.session.rollback()
            flash(f'Fout bij het toevoegen van de factuur: {str(e)}', 'danger')
            logging.error(f"Error adding invoice: {str(e)}")
        
        # If we get here, there was an error
        customers_query = Customer.query.all()
        customers_data = [customer.to_dict() for customer in customers_query]
        return render_template(
            'invoice_form.html',
            customers=customers_data,
            vat_rates=get_vat_rates(),
            invoice=request.form,
            now=datetime.now()
        )
    
    # GET request - show the form
    # Filter customers by workspace for regular users
    query = Customer.query
    if not current_user.is_super_admin:
        query = query.filter_by(workspace_id=current_user.workspace_id)
    customers_query = query.all()
    customers_data = [customer.to_dict() for customer in customers_query]
    
    # Als een klant_id is opgegeven in de query parameter, zorg ervoor dat deze wordt vooringevuld
    customer_id = request.args.get('customer_id')
    invoice_data = {'date': datetime.now().strftime('%Y-%m-%d'), 'type': 'income'}
    
    if customer_id:
        try:
            # Zet de string om naar UUID
            if isinstance(customer_id, str):
                customer_id = uuid.UUID(customer_id)
            
            # Haal de klantgegevens op
            customer = Customer.query.get(customer_id)
            if customer:
                invoice_data['customer_id'] = str(customer.id)
                
                # Neem het BTW-tarief over van de klant indien beschikbaar
                if customer.default_vat_rate is not None:
                    invoice_data['vat_rate'] = customer.default_vat_rate
        except (ValueError, Exception) as e:
            logging.error(f"Error getting customer for pre-filled invoice: {str(e)}")
            # Ga verder zonder voorinvulling als er een fout optreedt
    
    return render_template(
        'invoice_form.html',
        customers=customers_data,
        vat_rates=get_vat_rates(),
        invoice=invoice_data,
        now=datetime.now()
    )

@app.route('/invoices/<invoice_id>')
@login_required
@permission_required('can_view_invoices')
def view_invoice(invoice_id):
    try:
        # Convert invoice_id from string to UUID if needed
        if isinstance(invoice_id, str):
            invoice_id = uuid.UUID(invoice_id)
            
        # Query the invoice from the database
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            flash('Factuur niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        # Get the associated customer
        customer = Customer.query.get(invoice.customer_id)
        if not customer:
            flash('Klant niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        # Convert to dictionary format for the template
        invoice_dict = invoice.to_dict()
        customer_dict = customer.to_dict()
        
        return render_template(
            'invoice_detail.html',
            invoice=invoice_dict,
            customer=customer_dict,
            format_currency=format_currency,
            now=datetime.now()
        )
    except ValueError:
        flash('Ongeldige factuur-ID', 'danger')
        return redirect(url_for('invoices_list'))

@app.route('/invoices/<invoice_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_invoices')
def edit_invoice(invoice_id):
    try:
        # Convert invoice_id from string to UUID if needed
        if isinstance(invoice_id, str):
            invoice_id = uuid.UUID(invoice_id)
            
        # Query the invoice from the database
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            flash('Factuur niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        if request.method == 'POST':
            # Get form data
            customer_id = request.form.get('customer_id')
            date_str = request.form.get('date')
            invoice_type = request.form.get('type')
            amount_incl_vat = request.form.get('amount_incl_vat')
            vat_rate = request.form.get('vat_rate')
            invoice_number = request.form.get('invoice_number')  # Optional
            
            # Validate data
            if not all([customer_id, date_str, invoice_type, amount_incl_vat, vat_rate]):
                flash('Alle velden zijn verplicht', 'danger')
                customers_query = Customer.query.all()
                customers_data = [customer.to_dict() for customer in customers_query]
                return render_template(
                    'invoice_form.html',
                    invoice=invoice.to_dict(),
                    customers=customers_data,
                    vat_rates=get_vat_rates(),
                    edit_mode=True,
                    now=datetime.now()
                )
            
            try:
                # Convert customer_id to UUID
                if isinstance(customer_id, str):
                    customer_id = uuid.UUID(customer_id)
                    
                # Convert date string to date object
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Parse amounts
                amount_incl_vat_float = float(amount_incl_vat)
                vat_rate_float = float(vat_rate)
                
                # Calculate amounts
                amount_incl_vat_decimal = Decimal(str(amount_incl_vat_float))
                vat_rate_decimal = Decimal(str(vat_rate_float))
                vat_amount = amount_incl_vat_decimal - (amount_incl_vat_decimal / (1 + vat_rate_decimal / 100))
                amount_excl_vat = amount_incl_vat_decimal - vat_amount
                
                # Handle file upload
                file_path = invoice.file_path  # Keep existing file path by default
                if 'invoice_file' in request.files:
                    file = request.files['invoice_file']
                    if file and file.filename and allowed_file(file.filename):
                        # Replace the old file with the new one
                        new_file_path = save_uploaded_file(file)
                        if new_file_path:
                            file_path = new_file_path
                        else:
                            flash('Bestand uploaden mislukt', 'warning')
                    elif file and file.filename:
                        flash('Alleen PDF, PNG, JPG en JPEG bestanden zijn toegestaan', 'warning')
                
                # Check for duplicate invoice number if changed
                if invoice_number and invoice_number != invoice.invoice_number:
                    existing_invoice = Invoice.query.filter_by(invoice_number=invoice_number).first()
                    if existing_invoice and existing_invoice.id != invoice_id:
                        duplicate_id = existing_invoice.id
                        flash(f'Factuur met dit nummer bestaat al. <a href="{url_for("view_invoice", invoice_id=duplicate_id)}">Bekijk dubbele factuur</a>', 'warning')
                        customers_query = Customer.query.all()
                        customers_data = [customer.to_dict() for customer in customers_query]
                        return render_template(
                            'invoice_form.html',
                            invoice=invoice.to_dict(),
                            customers=customers_data,
                            vat_rates=get_vat_rates(),
                            edit_mode=True,
                            now=datetime.now()
                        )
                
                # Check if customer exists
                customer = Customer.query.get(customer_id)
                if not customer:
                    flash('Klant niet gevonden', 'danger')
                    customers_query = Customer.query.all()
                    customers_data = [customer.to_dict() for customer in customers_query]
                    return render_template(
                        'invoice_form.html',
                        invoice=invoice.to_dict(),
                        customers=customers_data,
                        vat_rates=get_vat_rates(),
                        edit_mode=True,
                        now=datetime.now()
                    )
                
                # Update invoice attributes
                invoice.invoice_number = invoice_number
                invoice.customer_id = customer_id
                invoice.date = date
                invoice.invoice_type = invoice_type
                invoice.amount_excl_vat = float(amount_excl_vat)
                invoice.amount_incl_vat = amount_incl_vat_float
                invoice.vat_rate = vat_rate_float
                invoice.vat_amount = float(vat_amount)
                
                # Haal mark_as_processed op uit het formulier (voor "Mark as Processed" checkbox)
                mark_as_processed = 'mark_as_processed' in request.form
                
                # Als de factuur onbewerkt was of het vinkje voor 'verwerkt' aanstaat, markeer als verwerkt
                if invoice.status == 'unprocessed' or mark_as_processed:
                    invoice.status = 'processed'
                invoice.file_path = file_path
                
                # Save changes to database
                db.session.commit()
                
                flash('Factuur succesvol bijgewerkt', 'success')
                return redirect(url_for('view_invoice', invoice_id=invoice_id))
                
            except ValueError as e:
                db.session.rollback()
                flash(f'Ongeldige invoer: {str(e)}', 'danger')
                logging.error(f"Error updating invoice: {str(e)}")
            except Exception as e:
                db.session.rollback()
                flash(f'Fout bij het bijwerken van de factuur: {str(e)}', 'danger')
                logging.error(f"Error updating invoice: {str(e)}")
            
            # If we get here, there was an error
            customers_query = Customer.query.all()
            customers_data = [customer.to_dict() for customer in customers_query]
            return render_template(
                'invoice_form.html',
                invoice=request.form,
                customers=customers_data,
                vat_rates=get_vat_rates(),
                edit_mode=True,
                now=datetime.now()
            )
        
        # GET request - show the form
        # Filter customers by workspace for regular users
        query = Customer.query
        if not current_user.is_super_admin:
            query = query.filter_by(workspace_id=current_user.workspace_id)
        customers_query = query.all()
        customers_data = [customer.to_dict() for customer in customers_query]
        
        # Convert invoice to dictionary for template
        invoice_dict = invoice.to_dict()
        
        return render_template(
            'invoice_form.html',
            invoice=invoice_dict,
            customers=customers_data,
            vat_rates=get_vat_rates(),
            edit_mode=True,
            now=datetime.now()
        )
    except ValueError:
        flash('Ongeldige factuur-ID', 'danger')
        return redirect(url_for('invoices_list'))

@app.route('/invoices/<invoice_id>/delete', methods=['POST'])
@login_required
@permission_required('can_delete_invoices')
def delete_invoice_route(invoice_id):
    try:
        # Convert invoice_id from string to UUID if needed
        if isinstance(invoice_id, str):
            invoice_id = uuid.UUID(invoice_id)
            
        # Query the invoice from the database
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            flash('Factuur niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        # Delete the invoice from the database
        db.session.delete(invoice)
        db.session.commit()
        
        flash('Factuur succesvol verwijderd', 'success')
    except ValueError:
        flash('Ongeldige factuur-ID', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Fout bij het verwijderen van de factuur: {str(e)}', 'danger')
        logging.error(f"Error deleting invoice: {str(e)}")
    
    return redirect(url_for('invoices_list'))

@app.route('/invoices/<invoice_id>/pdf')
@login_required
@permission_required('can_view_invoices')
def generate_invoice_pdf(invoice_id):
    try:
        # Convert invoice_id from string to UUID if needed
        if isinstance(invoice_id, str):
            invoice_id = uuid.UUID(invoice_id)
            
        # Query the invoice from the database
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            flash('Factuur niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        # Get the associated customer
        customer = Customer.query.get(invoice.customer_id)
        if not customer:
            flash('Klant niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        # Convert to dictionary format for the PDF generation
        invoice_dict = invoice.to_dict()
        customer_dict = customer.to_dict()
        
        # Generate PDF
        pdf_path = generate_pdf_invoice(invoice_dict, customer_dict)
        
        # Filename for download
        filename = f"Factuur-{invoice.invoice_number}.pdf"
        
        # Send file and then delete it after sending
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except ValueError:
        flash('Ongeldige factuur-ID', 'danger')
        return redirect(url_for('invoices_list'))
    except Exception as e:
        flash(f'Fout bij het genereren van PDF: {str(e)}', 'danger')
        logging.error(f"Error generating PDF invoice: {str(e)}")
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

@app.route('/invoices/<invoice_id>/attachment')
@login_required
@permission_required('can_view_invoices')
def view_invoice_attachment(invoice_id):
    try:
        # Convert invoice_id from string to UUID if needed
        if isinstance(invoice_id, str):
            invoice_id = uuid.UUID(invoice_id)
            
        # Query the invoice from the database
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            flash('Factuur niet gevonden', 'danger')
            return redirect(url_for('invoices_list'))
        
        # Check if invoice has a file attached
        if not invoice.file_path:
            flash('Deze factuur heeft geen bijlage', 'warning')
            return redirect(url_for('view_invoice', invoice_id=invoice_id))
        
        # Get the file extension to determine mime type
        file_ext = os.path.splitext(invoice.file_path)[1].lower()
        
        # Set mime type based on extension
        if file_ext in ['.jpg', '.jpeg']:
            mime_type = 'image/jpeg'
        elif file_ext == '.png':
            mime_type = 'image/png'
        elif file_ext == '.pdf':
            mime_type = 'application/pdf'
        else:
            mime_type = 'application/octet-stream'  # Generic binary
        
        # Create the full file path
        full_file_path = os.path.join('static', invoice.file_path)
        
        # Check if file exists
        if not os.path.exists(full_file_path):
            flash('Het bijgevoegde bestand kon niet worden gevonden', 'danger')
            return redirect(url_for('view_invoice', invoice_id=invoice_id))
        
        # Get filename for download
        filename = os.path.basename(invoice.file_path)
        
        # Send the file for viewing or download
        download = request.args.get('download', '0') == '1'
        return send_file(
            full_file_path,
            as_attachment=download,
            download_name=filename,
            mimetype=mime_type
        )
    except ValueError:
        flash('Ongeldige factuur-ID', 'danger')
        return redirect(url_for('invoices_list'))
    except Exception as e:
        flash(f'Fout bij het weergeven van de bijlage: {str(e)}', 'danger')
        logging.error(f"Error viewing invoice attachment: {str(e)}")
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

# Customer management routes
@app.route('/customers')
@login_required
@permission_required('can_view_customers')
def customers_list():
    # Super admin zonder actieve workspace sessie kan geen klanten zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om klanten te bekijken', 'warning')
        return redirect(url_for('dashboard'))
    
    # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
    workspace_id = current_user.workspace_id
    query = Customer.query
    if workspace_id:
        query = query.filter_by(workspace_id=workspace_id)
    
    # Get customers from the database
    customers_query = query.all()
    
    # Convert to dictionary format for the template and add counts/totals
    customers_data = []
    for customer in customers_query:
        customer_dict = customer.to_dict()
        
        # Query invoices for this customer (alleen van huidige werkruimte)
        invoice_query = Invoice.query.filter_by(customer_id=customer.id)
        if workspace_id:
            invoice_query = invoice_query.filter_by(workspace_id=workspace_id)
        customer_invoices_query = invoice_query.all()
        
        # Add additional data
        customer_dict['invoice_count'] = len(customer_invoices_query)
        customer_dict['total_amount'] = sum(
            inv.amount_incl_vat 
            for inv in customer_invoices_query 
            if inv.invoice_type == 'income'
        )
        
        customers_data.append(customer_dict)
    
    return render_template(
        'customers.html',
        customers=customers_data,
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/customers/new', methods=['GET', 'POST'])
@login_required
@permission_required('can_add_customers')
def new_customer():
    if request.method == 'POST':
        # Check if request is coming from an AJAX call
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'json' in request.headers.get('Accept', '')
        
        # Get form data
        company_name = request.form.get('company_name')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        vat_number = request.form.get('vat_number')
        email = request.form.get('email')
        phone = request.form.get('phone')
        street = request.form.get('street')
        house_number = request.form.get('house_number')
        postal_code = request.form.get('postal_code')
        city = request.form.get('city')
        country = request.form.get('country')
        customer_type = request.form.get('customer_type')
        default_vat_rate = request.form.get('default_vat_rate')
        
        # Validate data
        if not all([company_name, email, street, house_number, postal_code, city]):
            if is_ajax:
                return jsonify({'success': False, 'message': 'Bedrijfsnaam, e-mail en adresgegevens zijn verplicht'})
            else:
                flash('Bedrijfsnaam, e-mail en adresgegevens zijn verplicht', 'danger')
                return render_template(
                    'customer_form.html',
                    customer=request.form,
                    now=datetime.now()
                )
                
        # Controleer of BTW-nummer ingevuld is voor bedrijven en leveranciers
        if (customer_type in ['business', 'supplier']) and not vat_number:
            if is_ajax:
                return jsonify({'success': False, 'message': 'BTW-nummer is verplicht voor bedrijven en leveranciers'})
            else:
                flash('BTW-nummer is verplicht voor bedrijven en leveranciers', 'danger')
                return render_template(
                    'customer_form.html',
                    customer=request.form,
                    now=datetime.now()
                )
                
        # Valideer BTW-nummer formaat indien ingevuld
        if vat_number and not vat_number.startswith('BE') and len(vat_number) != 12:
            if is_ajax:
                return jsonify({'success': False, 'message': 'BTW-nummer moet in het formaat BE0123456789 zijn'})
            else:
                flash('BTW-nummer moet in het formaat BE0123456789 zijn', 'danger')
                return render_template(
                    'customer_form.html',
                    customer=request.form,
                    now=datetime.now()
                )
        
        # Add customer
        try:
            # Create a new customer object
            customer = Customer(
                company_name=company_name,
                first_name=first_name,
                last_name=last_name,
                vat_number=vat_number,
                email=email,
                phone=phone,
                street=street,
                house_number=house_number,
                postal_code=postal_code,
                city=city,
                country=country or 'België',
                customer_type=customer_type or 'business',
                workspace_id=current_user.workspace_id
            )
            
            # Set default VAT rate if provided
            if default_vat_rate:
                customer.default_vat_rate = float(default_vat_rate)
                
            # Add to database
            db.session.add(customer)
            db.session.commit()
            
            if is_ajax:
                return jsonify({
                    'success': True, 
                    'customer': {
                        'id': str(customer.id),
                        'name': customer.name  # Uses the property we defined
                    }
                })
            else:
                flash('Klant is succesvol toegevoegd', 'success')
                return redirect(url_for('customers_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding customer: {str(e)}")
            if is_ajax:
                return jsonify({'success': False, 'message': f'Fout: {str(e)}'})
            else:
                flash(f'Fout: {str(e)}', 'danger')
                
        # If we get here, there was an error
        if not is_ajax:
            return render_template(
                'customer_form.html',
                customer=request.form,
                now=datetime.now()
            )
        # For AJAX request, error responses are already handled above
    
    # GET request - show the form
    return render_template(
        'customer_form.html',
        customer={},
        now=datetime.now()
    )

@app.route('/customers/<customer_id>')
@login_required
@permission_required('can_view_customers')
def view_customer(customer_id):
    try:
        # Convert customer_id from string to UUID if needed
        if isinstance(customer_id, str):
            customer_id = uuid.UUID(customer_id)
            
        # Query the customer from the database
        customer = Customer.query.get(customer_id)
        if not customer:
            flash('Klant niet gevonden', 'danger')
            return redirect(url_for('customers_list'))
        
        # Query customer invoices - all and separate processed/unprocessed
        invoice_query = Invoice.query.filter_by(customer_id=customer.id)
        # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
        workspace_id = current_user.workspace_id
        if workspace_id:
            invoice_query = invoice_query.filter_by(workspace_id=workspace_id)
        customer_invoices_query = invoice_query.all()
        
        # Filter processed and unprocessed invoices
        processed_invoices = [invoice.to_dict() for invoice in customer_invoices_query 
                              if invoice.status == 'processed' or invoice.status is None]
        unprocessed_invoices = [invoice.to_dict() for invoice in customer_invoices_query 
                               if invoice.status == 'unprocessed']
        
        # Convert to dictionary format for the template
        customer_data = customer.to_dict()
        
        # Calculate total income and expense
        total_income = sum(
            inv.amount_incl_vat 
            for inv in customer_invoices_query 
            if inv.invoice_type == 'income'
        )
        total_expense = sum(
            inv.amount_incl_vat 
            for inv in customer_invoices_query 
            if inv.invoice_type == 'expense'
        )
        
        return render_template(
            'customer_detail.html',
            customer=customer_data,
            invoices=processed_invoices,
            unprocessed_invoices=unprocessed_invoices,
            total_income=total_income,
            total_expense=total_expense,
            format_currency=format_currency,
            now=datetime.now()
        )
    except ValueError:
        flash('Ongeldige klant-ID', 'danger')
        return redirect(url_for('customers_list'))

@app.route('/customers/<customer_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_customers')
def edit_customer(customer_id):
    try:
        # Convert customer_id from string to UUID if needed
        if isinstance(customer_id, str):
            customer_id = uuid.UUID(customer_id)
            
        # Query the customer from the database
        customer = Customer.query.get(customer_id)
        if not customer:
            flash('Klant niet gevonden', 'danger')
            return redirect(url_for('customers_list'))
        
        if request.method == 'POST':
            # Get form data 
            company_name = request.form.get('company_name')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            vat_number = request.form.get('vat_number')
            email = request.form.get('email')
            phone = request.form.get('phone')
            street = request.form.get('street')
            house_number = request.form.get('house_number')
            postal_code = request.form.get('postal_code')
            city = request.form.get('city')
            country = request.form.get('country')
            customer_type = request.form.get('customer_type')
            default_vat_rate = request.form.get('default_vat_rate')
            
            # Validate data
            if not all([company_name, email, street, house_number, postal_code, city]):
                flash('Bedrijfsnaam, e-mail en adresgegevens zijn verplicht', 'danger')
                return render_template(
                    'customer_form.html',
                    customer=request.form,
                    edit_mode=True,
                    now=datetime.now()
                )
                
            # Controleer of BTW-nummer ingevuld is voor bedrijven en leveranciers
            if (customer_type in ['business', 'supplier']) and not vat_number:
                flash('BTW-nummer is verplicht voor bedrijven en leveranciers', 'danger')
                return render_template(
                    'customer_form.html',
                    customer=request.form,
                    edit_mode=True,
                    now=datetime.now()
                )
                
            # Valideer BTW-nummer formaat indien ingevuld
            if vat_number and not vat_number.startswith('BE') and len(vat_number) != 12:
                flash('BTW-nummer moet in het formaat BE0123456789 zijn', 'danger')
                return render_template(
                    'customer_form.html',
                    customer=request.form,
                    edit_mode=True,
                    now=datetime.now()
                )
            
            # Update customer
            try:
                # Update customer attributes
                customer.company_name = company_name
                customer.first_name = first_name
                customer.last_name = last_name
                customer.vat_number = vat_number
                customer.email = email
                customer.phone = phone
                customer.street = street
                customer.house_number = house_number
                customer.postal_code = postal_code
                customer.city = city
                customer.country = country or 'België'
                customer.customer_type = customer_type or 'business'
                
                # Set default VAT rate if provided
                if default_vat_rate:
                    customer.default_vat_rate = float(default_vat_rate)
                
                # Save changes
                db.session.commit()
                
                flash('Klant succesvol bijgewerkt', 'success')
                return redirect(url_for('view_customer', customer_id=customer_id))
            except Exception as e:
                db.session.rollback()
                flash(f'Fout bij het bijwerken van de klant: {str(e)}', 'danger')
                logging.error(f"Error updating customer: {str(e)}")
            
            # If we get here, there was an error
            return render_template(
                'customer_form.html',
                customer=request.form,
                edit_mode=True,
                now=datetime.now()
            )
        
        # GET request - show the form with current data
        return render_template(
            'customer_form.html',
            customer=customer.to_dict(),
            edit_mode=True,
            now=datetime.now()
        )
    except ValueError:
        flash('Ongeldige klant-ID', 'danger')
        return redirect(url_for('customers_list'))

@app.route('/customers/bulk-action', methods=['POST'])
@login_required
@permission_required('can_delete_customers')
def bulk_action_customers():
    """Process bulk actions for selected customers"""
    selected_ids = request.form.getlist('selected_ids[]')
    bulk_action = request.form.get('bulk_action')
    
    if not selected_ids:
        flash('Geen klanten geselecteerd', 'warning')
        return redirect(url_for('customers_list'))
    
    if bulk_action == 'delete':
        # Delete selected customers
        delete_count = 0
        error_count = 0
        
        for customer_id in selected_ids:
            try:
                # Convert string to UUID if needed
                if isinstance(customer_id, str):
                    customer_id = uuid.UUID(customer_id)
                
                customer = Customer.query.get(customer_id)
                
                if customer:
                    # Check if customer has invoices
                    invoice_count = Invoice.query.filter_by(customer_id=customer.id).count()
                    
                    if invoice_count > 0:
                        flash(f'Klant "{customer.name}" heeft nog {invoice_count} facturen en kan niet worden verwijderd', 'warning')
                        error_count += 1
                    else:
                        db.session.delete(customer)
                        delete_count += 1
            except Exception as e:
                flash(f'Fout bij verwijderen klant: {str(e)}', 'danger')
                error_count += 1
        
        if delete_count > 0:
            db.session.commit()
            flash(f'{delete_count} klanten succesvol verwijderd', 'success')
        
        if error_count > 0:
            flash(f'{error_count} klanten konden niet worden verwijderd', 'warning')
        
    elif bulk_action == 'export_excel':
        try:
            # Get all selected customers
            customers_data = []
            for customer_id in selected_ids:
                if isinstance(customer_id, str):
                    customer_id = uuid.UUID(customer_id)
                
                customer = Customer.query.get(customer_id)
                if customer:
                    # Count invoices
                    invoice_count = Invoice.query.filter_by(customer_id=customer.id).count()
                    
                    # Calculate total amounts
                    income_invoices = Invoice.query.filter_by(customer_id=customer.id, invoice_type='income').all()
                    expense_invoices = Invoice.query.filter_by(customer_id=customer.id, invoice_type='expense').all()
                    
                    total_income = sum(invoice.amount_incl_vat for invoice in income_invoices)
                    total_expense = sum(invoice.amount_incl_vat for invoice in expense_invoices)
                    
                    customer_dict = customer.to_dict()
                    customer_dict['invoice_count'] = invoice_count
                    customer_dict['total_income'] = total_income
                    customer_dict['total_expense'] = total_expense
                    customers_data.append(customer_dict)
            
            if customers_data:
                # Generate Excel file with customer data
                excel_file = export_to_excel(
                    customers_data, 
                    'klanten_export.xlsx',
                    columns=[
                        'company_name', 'first_name', 'last_name', 'vat_number', 
                        'email', 'phone', 'street', 'house_number', 
                        'postal_code', 'city', 'country', 'customer_type',
                        'invoice_count', 'total_income', 'total_expense'
                    ]
                )
                
                # Return Excel file as download
                return send_file(
                    excel_file,
                    as_attachment=True,
                    download_name='klanten_export.xlsx',
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            else:
                flash('Geen klantgegevens beschikbaar voor export', 'warning')
        except Exception as e:
            flash(f'Fout bij exporteren: {str(e)}', 'danger')
    
    elif bulk_action == 'change_type':
        # Change customer type
        new_type = request.form.get('new_type')
        if not new_type or new_type not in ['business', 'individual', 'supplier']:
            flash('Ongeldig klanttype geselecteerd', 'warning')
            return redirect(url_for('customers_list'))
        
        updated_count = 0
        for customer_id in selected_ids:
            try:
                if isinstance(customer_id, str):
                    customer_id = uuid.UUID(customer_id)
                
                customer = Customer.query.get(customer_id)
                if customer:
                    customer.customer_type = new_type
                    updated_count += 1
            except Exception as e:
                flash(f'Fout bij het wijzigen van klanttype: {str(e)}', 'danger')
        
        if updated_count > 0:
            db.session.commit()
            flash(f'Type van {updated_count} klanten succesvol gewijzigd naar {new_type}', 'success')
    
    else:
        flash('Ongeldige bulk actie', 'warning')
    
    return redirect(url_for('customers_list'))

@app.route('/customers/<customer_id>/delete', methods=['POST'])
@login_required
@permission_required('can_delete_customers')
def delete_customer_route(customer_id):
    try:
        # Convert customer_id from string to UUID if needed
        if isinstance(customer_id, str):
            customer_id = uuid.UUID(customer_id)
            
        # Query the customer from the database
        customer = Customer.query.get(customer_id)
        if not customer:
            flash('Klant niet gevonden', 'danger')
            return redirect(url_for('customers_list'))
        
        # Check if customer has invoices
        has_invoices = Invoice.query.filter_by(customer_id=customer.id).first() is not None
        if has_invoices:
            flash('Kan klant niet verwijderen omdat er nog facturen aan gekoppeld zijn', 'danger')
            return redirect(url_for('customers_list'))
        
        # Delete the customer
        try:
            db.session.delete(customer)
            db.session.commit()
            flash('Klant succesvol verwijderd', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Fout bij het verwijderen van de klant: {str(e)}', 'danger')
            logging.error(f"Error deleting customer: {str(e)}")
        
        return redirect(url_for('customers_list'))
    except ValueError:
        flash('Ongeldige klant-ID', 'danger')
        return redirect(url_for('customers_list'))

# Reports routes
@app.route('/reports')
@login_required
@permission_required('can_view_reports')
def reports():
    # Get the current year and quarter
    current_year = datetime.now().year
    current_quarter = date_to_quarter(datetime.now())
    
    return render_template(
        'reports.html',
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        current_year=current_year,
        current_quarter=current_quarter,
        now=datetime.now()
    )

@app.route('/reports/monthly/<int:year>', methods=['GET'])
@login_required
@permission_required('can_view_reports')
def monthly_report(year):
    # Super admin zonder actieve workspace sessie kan geen rapporten zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om rapporten te bekijken', 'warning')
        return redirect(url_for('dashboard'))
    
    # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
    workspace_id = current_user.workspace_id
    monthly_data = get_monthly_summary(year, workspace_id)
    
    # Get export format
    export_format = request.args.get('format')
    if export_format:
        if export_format == 'excel':
            temp_file = export_to_excel(
                monthly_data, 
                f'Monthly_Report_{year}.xlsx',
                columns=['month_name', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Monthly_Report_{year}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            temp_file = export_to_csv(
                monthly_data, 
                f'Monthly_Report_{year}.csv',
                columns=['month_name', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Monthly_Report_{year}.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'reports.html',
        report_type='monthly',
        report_data=monthly_data,
        year=year,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/reports/quarterly/<int:year>', methods=['GET'])
@login_required
@permission_required('can_view_reports')
def quarterly_report(year):
    # Super admin zonder actieve workspace sessie kan geen rapporten zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om rapporten te bekijken', 'warning')
        return redirect(url_for('dashboard'))
    
    # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
    workspace_id = current_user.workspace_id
    quarterly_data = get_quarterly_summary(year, workspace_id)
    
    # Get export format
    export_format = request.args.get('format')
    if export_format:
        if export_format == 'excel':
            temp_file = export_to_excel(
                quarterly_data, 
                f'Quarterly_Report_{year}.xlsx',
                columns=['quarter', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Quarterly_Report_{year}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            temp_file = export_to_csv(
                quarterly_data, 
                f'Quarterly_Report_{year}.csv',
                columns=['quarter', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Quarterly_Report_{year}.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'reports.html',
        report_type='quarterly',
        report_data=quarterly_data,
        year=year,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/reports/customers', methods=['GET'])
@login_required
@permission_required('can_view_reports')
def customer_report():
    # Super admin zonder actieve workspace sessie kan geen rapporten zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om rapporten te bekijken', 'warning')
        return redirect(url_for('dashboard'))
    
    # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
    workspace_id = current_user.workspace_id
    customer_data = get_customer_summary(workspace_id)
    
    # Get export format
    export_format = request.args.get('format')
    if export_format:
        if export_format == 'excel':
            temp_file = export_to_excel(
                customer_data, 
                'Customer_Report.xlsx',
                columns=['customer_name', 'income', 'vat_collected', 'invoice_count']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name='Customer_Report.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            temp_file = export_to_csv(
                customer_data, 
                'Customer_Report.csv',
                columns=['customer_name', 'income', 'vat_collected', 'invoice_count']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name='Customer_Report.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'reports.html',
        report_type='customers',
        report_data=customer_data,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency,
        now=datetime.now()
    )

# VAT report routes
@app.route('/vat-report')
@login_required
@permission_required('can_view_vat_reports')
def vat_report_form():
    # Super admin zonder actieve workspace sessie kan geen BTW-rapport zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om BTW-rapporten te bekijken', 'warning')
        return redirect(url_for('dashboard'))
        
    current_year = datetime.now().year
    return render_template(
        'vat_report.html',
        years=get_years(start_year=current_year-3, end_year=current_year),
        quarters=get_quarters(),
        months=get_months(),
        current_year=current_year,
        current_quarter=date_to_quarter(datetime.now()),
        now=datetime.now()
    )

@app.route('/vat-report/generate', methods=['POST'])
@login_required
@permission_required('can_view_vat_reports')
def generate_vat_report():
    # Super admin zonder actieve workspace sessie kan geen rapporten zien
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om BTW-rapporten te genereren', 'warning')
        return redirect(url_for('dashboard'))
    
    # Get form data
    year = int(request.form.get('year'))
    report_type = request.form.get('report_type')  # 'quarterly' or 'monthly'
    
    # Alle gebruikers (inclusief super admins in workspace mode) krijgen alleen hun eigen workspace data
    workspace_id = current_user.workspace_id
    
    if report_type == 'quarterly':
        quarter = int(request.form.get('quarter'))
        month = None
        report = calculate_vat_report(year=year, quarter=quarter, workspace_id=workspace_id)
        period_name = f"Q{quarter} {year}"
    else:  # monthly
        month = int(request.form.get('month'))
        quarter = None
        report = calculate_vat_report(year=year, month=month, workspace_id=workspace_id)
        month_name = datetime(year, month, 1).strftime('%B')
        period_name = f"{month_name} {year}"
    
    # Get export format
    export_format = request.form.get('export_format')
    if export_format:
        if export_format == 'excel':
            # Prepare data for export
            export_data = [{
                'Period': period_name,
                'Grid 03 (Sales excl. VAT)': report['grid_03'],
                'Grid 54 (Output VAT)': report['grid_54'],
                'Grid 59 (Input VAT)': report['grid_59'],
                'Grid 71 (VAT Balance)': report['grid_71']
            }]
            
            temp_file = export_to_excel(
                export_data, 
                f'VAT_Report_{period_name}.xlsx'
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'VAT_Report_{period_name}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            # Prepare data for export
            export_data = [{
                'Period': period_name,
                'Grid 03 (Sales excl. VAT)': report['grid_03'],
                'Grid 54 (Output VAT)': report['grid_54'],
                'Grid 59 (Input VAT)': report['grid_59'],
                'Grid 71 (VAT Balance)': report['grid_71']
            }]
            
            temp_file = export_to_csv(
                export_data, 
                f'VAT_Report_{period_name}.csv'
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'VAT_Report_{period_name}.csv',
                mimetype='text/csv'
            )
    
    # Get customer information for invoices
    # Print debug information about invoices to understand their structure
    app.logger.debug(f"Invoices in report: {len(report.get('invoices', []))}")
    if report.get('invoices'):
        app.logger.debug(f"First invoice keys: {list(report.get('invoices', [])[0].keys())}")
    
    # Convert any ID objects to strings for consistent lookup
    customer_ids = []
    for invoice in report.get('invoices', []):
        # Check if customer_id exists in invoice
        if 'customer_id' in invoice:
            customer_id = invoice['customer_id']
            # Convert to string if it exists and is not None
            if customer_id is not None:
                customer_ids.append(str(customer_id))
        # Log warning if no customer_id
        else:
            app.logger.warning(f"Invoice {invoice.get('id')} has no customer_id")
    
    # Get unique customer IDs
    unique_customer_ids = list(set(customer_ids))
    app.logger.debug(f"Unique customer IDs: {unique_customer_ids}")
    
    # Query customers
    customers_query = Customer.query.filter(Customer.id.in_(unique_customer_ids) if unique_customer_ids else False)
    
    # Create dictionary of customers by ID for easy lookup in template
    # Make sure all IDs are converted to strings for consistent lookup
    customers = {str(customer.id): customer.to_dict() for customer in customers_query}
    app.logger.debug(f"Customers dictionary has {len(customers)} entries")
    
    # Regular HTML response
    return render_template(
        'vat_report.html',
        report=report,
        period_name=period_name,
        customers=customers,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency,
        now=datetime.now()
    )

# Bulk upload routes
@app.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
@permission_required('can_upload_invoices')
def bulk_upload():
    # Super admin zonder actieve workspace sessie kan geen bulk upload doen
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id:
        flash('U moet eerst een werkruimte kiezen om bulk uploads te doen', 'warning')
        return redirect(url_for('dashboard'))
    
    # Get optional customer_id from URL parameter (for GET)
    url_customer_id = request.args.get('customer_id')
    
    if request.method == 'POST':
        # Get optional customer_id if specified
        customer_id = request.form.get('customer_id')
        
        # Check if any files were uploaded
        if 'files[]' not in request.files:
            flash('Geen bestanden geselecteerd', 'danger')
            customers_data = [customer.to_dict() for customer in Customer.query.all()]
            return render_template(
                'bulk_upload.html',
                customers=customers_data,
                now=datetime.now()
            )
        
        files = request.files.getlist('files[]')
        if not files or all(not f.filename for f in files):
            flash('Geen bestanden geselecteerd', 'danger')
            customers_data = [customer.to_dict() for customer in Customer.query.all()]
            return render_template(
                'bulk_upload.html',
                customers=customers_data,
                now=datetime.now()
            )
        
        # Alleen bestanden opslaan, niet verwerken
        processor = FileProcessor()
        saved_paths = processor.save_files(files)
        
        # Voorinformatieformulieren voorbereiden
        file_previews = []
        customers_data = [customer.to_dict() for customer in Customer.query.all()]
        
        for file_path in saved_paths:
            # Basisinfo uit bestandsnaam halen (eenvoudige implementatie)
            file_name = os.path.basename(file_path)
            
            # Voorlopige analyse
            invoice_type = "expense"  # Standaard uitgaven
            if "income" in file_name.lower() or "inkomst" in file_name.lower() or "sales" in file_name.lower():
                invoice_type = "income"
                
            # Datum extraheren of huidige datum gebruiken
            date_obj = datetime.now()
            
            # Maak een voorbeeldformulier voor dit bestand
            preview = {
                'file_path': file_path,
                'file_name': file_name,
                'invoice_date': date_obj.strftime('%Y-%m-%d'),
                'invoice_type': invoice_type,
                'invoice_number': '',
                'amount_incl_vat': '',
                'vat_rate': '21',  # Standaard BTW-tarief
                'customer_id': customer_id if customer_id else ''
            }
            
            file_previews.append(preview)
        
        if file_previews:
            # Bewaar de previews in de sessie
            session['file_previews'] = file_previews
            
            # Ga naar het reviewformulier
            return render_template(
                'bulk_upload_review.html',
                file_previews=file_previews,
                customers=customers_data,
                vat_rates=get_vat_rates(),
                now=datetime.now()
            )
        else:
            flash('Geen bestanden werden geüpload', 'warning')
            customers_data = [customer.to_dict() for customer in Customer.query.all()]
            return render_template(
                'bulk_upload.html',
                customers=customers_data,
                now=datetime.now()
            )
    
    # GET request - show the form
    customers_data = [customer.to_dict() for customer in Customer.query.all()]
    selected_customer = None
    
    # Set pre-selected customer if specified in URL
    if url_customer_id:
        selected_customer = url_customer_id
        # Try to get customer name for displaying
        for customer in customers_data:
            if str(customer['id']) == url_customer_id:
                flash(f"Bestanden worden geüpload voor klant: {customer['name']}", 'info')
                break
    
    return render_template(
        'bulk_upload.html',
        customers=customers_data,
        selected_customer=selected_customer,
        now=datetime.now()
    )

@app.route('/invoices/bulk-action', methods=['POST'])
@login_required
@permission_required('can_manage_invoices')
def bulk_action_invoices():
    """Process bulk actions for selected invoices"""
    selected_ids = request.form.getlist('selected_ids[]')
    bulk_action = request.form.get('bulk_action')
    
    if not selected_ids:
        flash('Geen facturen geselecteerd', 'warning')
        return redirect(url_for('invoices_list'))
    
    if bulk_action == 'delete':
        # Delete selected invoices
        delete_count = 0
        for invoice_id in selected_ids:
            try:
                # Convert string to UUID if needed
                if isinstance(invoice_id, str):
                    invoice_id = uuid.UUID(invoice_id)
                
                invoice = Invoice.query.get(invoice_id)
                if invoice:
                    db.session.delete(invoice)
                    delete_count += 1
            except Exception as e:
                flash(f'Fout bij verwijderen factuur: {str(e)}', 'danger')
        
        if delete_count > 0:
            db.session.commit()
            flash(f'{delete_count} facturen succesvol verwijderd', 'success')
        
    elif bulk_action == 'export_pdf':
        # Not implemented yet - would create a ZIP file with multiple PDFs
        flash('PDF bulk export nog niet geïmplementeerd', 'info')
        
    elif bulk_action == 'change_status':
        # Change the status of selected invoices (processed/unprocessed)
        status_count = 0
        new_status = request.form.get('new_status', 'processed')
        
        for invoice_id in selected_ids:
            try:
                if isinstance(invoice_id, str):
                    invoice_id = uuid.UUID(invoice_id)
                
                invoice = Invoice.query.get(invoice_id)
                if invoice:
                    invoice.status = new_status
                    status_count += 1
            except Exception as e:
                flash(f'Fout bij het wijzigen van status: {str(e)}', 'danger')
        
        if status_count > 0:
            db.session.commit()
            flash(f'Status van {status_count} facturen succesvol gewijzigd', 'success')
            
    else:
        flash('Ongeldige bulk actie', 'warning')
        
    return redirect(url_for('invoices_list'))


@app.route('/customers/<customer_id>/invoices/bulk-action', methods=['POST'])
@login_required
@permission_required('can_manage_invoices')
def bulk_action_customer_invoices(customer_id):
    """Process bulk actions for selected invoices on the customer detail page"""
    selected_ids = request.form.getlist('selected_ids[]')
    bulk_action = request.form.get('bulk_action')
    invoice_status = request.form.get('invoice_status', 'processed')
    
    if not selected_ids:
        flash('Geen facturen geselecteerd', 'warning')
        return redirect(url_for('view_customer', customer_id=customer_id))
    
    try:
        # Convert customer_id from string to UUID if needed
        if isinstance(customer_id, str):
            customer_id = uuid.UUID(customer_id)
            
        # Verify customer exists
        customer = Customer.query.get(customer_id)
        if not customer:
            flash('Klant niet gevonden', 'danger')
            return redirect(url_for('customers_list'))
    except ValueError:
        flash('Ongeldige klant-ID', 'danger')
        return redirect(url_for('customers_list'))
    
    if bulk_action == 'delete':
        # Delete selected invoices
        delete_count = 0
        for invoice_id in selected_ids:
            try:
                # Convert string to UUID if needed
                if isinstance(invoice_id, str):
                    invoice_id = uuid.UUID(invoice_id)
                
                invoice = Invoice.query.get(invoice_id)
                if invoice and invoice.customer_id == customer_id:
                    db.session.delete(invoice)
                    delete_count += 1
            except Exception as e:
                flash(f'Fout bij verwijderen factuur: {str(e)}', 'danger')
        
        if delete_count > 0:
            db.session.commit()
            flash(f'{delete_count} facturen succesvol verwijderd', 'success')
        
    elif bulk_action == 'export_pdf':
        # Not implemented yet - would create a ZIP file with multiple PDFs
        flash('PDF bulk export nog niet geïmplementeerd', 'info')
        
    elif bulk_action == 'mark_processed':
        # Mark selected invoices as processed
        status_count = 0
        for invoice_id in selected_ids:
            try:
                if isinstance(invoice_id, str):
                    invoice_id = uuid.UUID(invoice_id)
                
                invoice = Invoice.query.get(invoice_id)
                if invoice and invoice.customer_id == customer_id:
                    invoice.status = 'processed'
                    status_count += 1
            except Exception as e:
                flash(f'Fout bij het wijzigen van status: {str(e)}', 'danger')
        
        if status_count > 0:
            db.session.commit()
            flash(f'{status_count} facturen gemarkeerd als verwerkt', 'success')
            
    elif bulk_action == 'mark_unprocessed':
        # Mark selected invoices as unprocessed
        status_count = 0
        for invoice_id in selected_ids:
            try:
                if isinstance(invoice_id, str):
                    invoice_id = uuid.UUID(invoice_id)
                
                invoice = Invoice.query.get(invoice_id)
                if invoice and invoice.customer_id == customer_id:
                    invoice.status = 'unprocessed'
                    status_count += 1
            except Exception as e:
                flash(f'Fout bij het wijzigen van status: {str(e)}', 'danger')
        
        if status_count > 0:
            db.session.commit()
            flash(f'{status_count} facturen gemarkeerd als onverwerkt', 'success')
            
    else:
        flash('Ongeldige bulk actie', 'warning')
        
    return redirect(url_for('view_customer', customer_id=customer_id))

@app.route('/bulk-upload/process', methods=['POST'])
@login_required
@permission_required('can_upload_invoices')
def bulk_upload_process():
    # Haal de ingevulde formuliergegevens op
    file_data = []
    
    # Bepaal hoeveel bestanden er zijn
    file_count = int(request.form.get('file_count', 0))
    
    # Bepaal welke actie gekozen is
    action = request.form.get('action', 'process')
    
    # Verwerk ieder bestand
    for i in range(file_count):
        file_info = {
            'file_path': request.form.get(f'file_path_{i}'),
            'file_name': request.form.get(f'file_name_{i}'),
            'invoice_date': request.form.get(f'invoice_date_{i}'),
            'invoice_type': request.form.get(f'invoice_type_{i}'),
            'invoice_number': request.form.get(f'invoice_number_{i}'),
            'amount_incl_vat': request.form.get(f'amount_incl_vat_{i}'),
            'vat_rate': request.form.get(f'vat_rate_{i}'),
            'customer_id': request.form.get(f'customer_id_{i}')
        }
        
        # Voeg bestanden toe aan de lijst
        # Voor 'naar klantportaal' alleen filter op file_path en customer_id
        if action == 'to_customer_portal':
            if file_info['file_path'] and file_info['customer_id']:
                file_data.append(file_info)
        # Voor normale verwerking, alleen als er ook een bedrag is
        else:
            if file_info['file_path'] and file_info['amount_incl_vat']:
                file_data.append(file_info)
                
    # Als de actie is om naar klantportaal te sturen
    if action == 'to_customer_portal':
        return process_to_customer_portal(file_data)
    
    # Resultaten voorbereiden
    results = {
        'saved_files': [],
        'recognized_invoices': [],
        'new_customers': [],
        'manual_review': [],
        'errors': []
    }
    
    # Invoices aanmaken op basis van de ingevulde gegevens
    for data in file_data:
        try:
            # Basisvalidatie
            if not data['customer_id'] or not data['amount_incl_vat'] or not data['invoice_date']:
                results['manual_review'].append({
                    'file_path': data['file_path'],
                    'reason': 'Onvolledige gegevens',
                    'metadata': {'document_type': 'invoice'}
                })
                continue
                
            # Converteer datums en bedragen
            invoice_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
            amount_incl_vat = float(data['amount_incl_vat'].replace(',', '.'))
            vat_rate = float(data['vat_rate'])
            
            # Maak een factuur aan
            invoice_number = data['invoice_number']
            if not invoice_number:
                invoice_number = get_next_invoice_number()
                
            # Controleer of de factuur een duplicaat is
            is_duplicate, duplicate_id = check_duplicate_invoice(
                invoice_number=invoice_number,
                customer_id=data['customer_id'],
                date=invoice_date,
                amount_incl_vat=amount_incl_vat
            )
            
            if is_duplicate:
                results['manual_review'].append({
                    'file_path': data['file_path'],
                    'reason': 'Mogelijk duplicaat',
                    'duplicate_id': duplicate_id,
                    'metadata': {'document_type': 'invoice'}
                })
                continue
                
            # Maak een nieuwe factuur aan
            new_invoice_obj = Invoice(
                invoice_number=invoice_number,
                customer_id=uuid.UUID(data['customer_id']),
                date=invoice_date,
                invoice_type=data['invoice_type'],
                amount_incl_vat=amount_incl_vat,
                vat_rate=vat_rate,
                amount_excl_vat=amount_incl_vat / (1 + (vat_rate / 100)),
                vat_amount=amount_incl_vat - (amount_incl_vat / (1 + (vat_rate / 100))),
                file_path=data['file_path'],
                status='unprocessed'  # Markeer als onbewerkt
            )
            
            db.session.add(new_invoice_obj)
            db.session.commit()
            
            # Gebruik de aangemaakte factuur
            new_invoice = new_invoice_obj
            
            # Voeg toe aan resultaten
            customer = Customer.query.get(data['customer_id'])
            
            invoice_dict = {
                'id': str(new_invoice.id),
                'invoice_number': new_invoice.invoice_number,
                'customer_id': str(new_invoice.customer_id),
                'customer_name': customer.name if customer else 'Onbekende klant',
                'date': new_invoice.date.strftime('%Y-%m-%d'),
                'invoice_type': new_invoice.invoice_type,
                'amount_incl_vat': new_invoice.amount_incl_vat
            }
            
            results['recognized_invoices'].append(invoice_dict)
            results['saved_files'].append(data['file_path'])
            
        except Exception as e:
            results['errors'].append({
                'file_path': data['file_path'],
                'error': str(e)
            })
    
    # Bewaar resultaten in sessie
    session['bulk_upload_results'] = results
    
    # Bereid samenvatting voor
    summary = {
        'total_files': len(file_data),
        'processed_invoices': len(results['recognized_invoices']),
        'new_customers': len(results['new_customers']),
        'manual_review': len(results['manual_review']),
        'errors': len(results['errors'])
    }
    
    # Toon geschikte melding
    if summary['processed_invoices'] > 0:
        flash(f"Verwerkt: {summary['processed_invoices']} facturen aangemaakt, "
              f"{summary['manual_review']} bestanden voor handmatige controle", 'success')
    elif summary['errors'] > 0:
        flash('Er zijn fouten opgetreden bij het verwerken van de bestanden', 'danger')
    else:
        flash('Er zijn geen facturen aangemaakt', 'warning')
    
    return redirect(url_for('bulk_upload_results'))

def process_to_customer_portal(file_data):
    """
    Verwerk bestanden door ze naar het klantportaal te sturen als onbewerkte facturen
    
    Args:
        file_data: lijst met bestandsgegevens uit het uploadformulier
    """
    results = {
        'processed_count': 0,
        'error_count': 0,
        'customer_id': None
    }
    
    for data in file_data:
        try:
            # Check of er een klant is geselecteerd
            if not data['customer_id']:
                continue
                
            # Bepaal standaardwaarden voor ontbrekende velden
            invoice_date = datetime.now().date()
            if data['invoice_date']:
                try:
                    invoice_date = datetime.strptime(data['invoice_date'], '%Y-%m-%d').date()
                except ValueError:
                    pass
                    
            # Probeer bedrag te converteren, default naar 0 als niet opgegeven
            amount_incl_vat = 0.0
            if data['amount_incl_vat']:
                try:
                    amount_incl_vat = float(data['amount_incl_vat'].replace(',', '.'))
                except ValueError:
                    pass
                    
            # BTW-tarief, default naar 21%
            vat_rate = 21.0
            if data['vat_rate']:
                try:
                    vat_rate = float(data['vat_rate'])
                except ValueError:
                    pass
            
            # Maak de factuur aan, expliciet gemarkeerd als 'unprocessed'
            invoice_number = data['invoice_number']
            if not invoice_number:
                invoice_number = get_next_invoice_number()
                
            new_invoice = Invoice(
                invoice_number=invoice_number,
                customer_id=uuid.UUID(data['customer_id']),
                date=invoice_date,
                invoice_type=data['invoice_type'] or 'income',
                amount_excl_vat=amount_incl_vat / (1 + (vat_rate / 100)),
                amount_incl_vat=amount_incl_vat,
                vat_rate=vat_rate,
                vat_amount=amount_incl_vat - (amount_incl_vat / (1 + (vat_rate / 100))),
                file_path=data['file_path'],
                status='unprocessed'  # Hier markeren we de factuur expliciet als onbewerkt
            )
            
            db.session.add(new_invoice)
            db.session.commit()
            
            results['processed_count'] += 1
            results['customer_id'] = data['customer_id']  # Onthoud customer_id voor redirect
            
        except Exception as e:
            results['error_count'] += 1
    
    # Toon feedback
    if results['processed_count'] > 0:
        flash(f"{results['processed_count']} document(en) naar klantportaal gestuurd", 'success')
        
        # Redirect naar de klantpagina als er een customer_id is
        if results['customer_id']:
            return redirect(url_for('view_customer', customer_id=results['customer_id']))
    else:
        flash('Er zijn geen documenten naar het klantportaal gestuurd', 'warning')
    
    # Als geen klant gevonden of geen succes, dan terug naar de klantenlijst
    return redirect(url_for('customers_list'))

@app.route('/bulk-upload/results')
@login_required
@permission_required('can_upload_invoices')
def bulk_upload_results():
    # Get results from session
    results = session.get('bulk_upload_results', {
        'saved_files': [],
        'recognized_invoices': [],
        'new_customers': [],
        'manual_review': [],
        'errors': []
    })
    
    # Create a more detailed summary
    summary = {
        'total_files': len(results['saved_files']),
        'processed_invoices': len(results['recognized_invoices']),
        'new_customers': len(results['new_customers']),
        'manual_review': len(results['manual_review']),
        'errors': len(results['errors'])
    }
    
    # Get customers for displaying names instead of IDs
    customers_dict = {c['id']: c for c in [customer.to_dict() for customer in Customer.query.all()]}
    
    # Enrich invoice data with customer names
    for invoice in results.get('recognized_invoices', []):
        if invoice.get('customer_id') in customers_dict:
            invoice['customer_name'] = customers_dict[invoice['customer_id']]['name']
        else:
            invoice['customer_name'] = 'Unknown Customer'
    
    return render_template(
        'bulk_upload_results.html',
        results=results,
        summary=summary,
        customers_dict=customers_dict,
        format_currency=format_currency,
        now=datetime.now()
    )

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 Pagina niet gevonden: {request.path}")
    return render_template('404.html', now=datetime.now()), 404

@app.errorhandler(403)
def forbidden_error(error):
    logger.warning(f"403 Toegang geweigerd: {request.path} door gebruiker {current_user.username if current_user.is_authenticated else 'onbekend'}")
    return render_template('403.html', now=datetime.now()), 403

@app.errorhandler(500)
def internal_error(error):
    # Log de fout met traceback voor betere debugging
    logger.error(f"500 Server error: {str(error)}\n{traceback.format_exc()}")
    return render_template('500.html', now=datetime.now()), 500

# Admin routes
@app.route('/admin')
@login_required
def admin():
    # Only admins and super admins can access admin panel
    if not current_user.is_admin and not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Super admins without workspace context are redirected to system overview
    # BUT ONLY if there's no override parameter
    if current_user.is_super_admin and not session.get('super_admin_id') and not current_user.workspace_id and not request.args.get('settings'):
        return redirect(url_for('system_overview'))
    
    # Regular admins are redirected to workspace admin page
    if current_user.is_admin and not current_user.is_super_admin:
        return redirect(url_for('workspace_admin'))
    
    from models import get_users, EmailSettings
    
    # Filter users based on workspace for regular admins
    # Abonnement informatie ophalen uit de database
    subscription = None
    workspace = None
    users = []
    workspaces = []
    customer_count = 0
    invoice_count = 0
    email_settings = None
    
    # Initialize email-related variables
    ms_graph_client_id = ''
    ms_graph_tenant_id = ''
    ms_graph_client_secret = ''
    ms_graph_sender_email = ''
    ms_graph_shared_mailbox = ''
    ms_graph_use_shared_mailbox = False
    smtp_server = ''
    smtp_port = ''
    smtp_username = ''
    smtp_password = ''
    email_from = ''
    email_from_name = ''
    default_sender_name = ''
    reply_to = ''
    smtp_use_ssl = True
    smtp_use_tls = False
    use_ms_graph = True
    
    if current_user.is_super_admin:
        # Super admins can see all users
        users = get_users()
        # Get all workspaces for super admin
        workspaces = Workspace.query.all()
        # Get counts across all workspaces
        customer_count = Customer.query.count()
        invoice_count = Invoice.query.count()
        
        # Voor super_admin gebruikers, zorg dat we altijd de workspace variabele vullen
        # Dit is nodig om de werkruimte-gebaseerde secties in de template weer te geven
        if current_user.workspace_id:
            # Gebruik de eigen werkruimte van de super admin als deze er één heeft
            workspace = Workspace.query.get(current_user.workspace_id)
        elif workspaces:
            # Anders gebruik de eerste beschikbare werkruimte
            workspace = workspaces[0]
        
        # Haal huidige e-mailinstellingen op uit de database of fallback naar omgevingsvariabelen
        system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
    else:
        # Initialiseer system_settings als None voor andere gebruikers
        system_settings = None
        users = []  # Initialiseer users als lege lijst voor andere gebruikers
        # Voor niet-superadmins hoeven we geen werkruimtes op te halen
        # Belangrijk: behoud de werkruimtes die in een eerdere stap zijn opgehaald
        # workspaces = []  # Dit overschrijft workspaces-lijst, dus commentaren we dit uit
        customer_count = 0
        invoice_count = 0
        
    # Deze code is voor alle super admins, ongeacht of ze een workspace_id hebben
    if current_user.is_super_admin:
        # Vul ze in met gegevens uit system_settings als die beschikbaar is
        if system_settings:
            # Gebruik instellingen uit database
            ms_graph_client_id = system_settings.ms_graph_client_id or ''
            ms_graph_tenant_id = system_settings.ms_graph_tenant_id or ''
            ms_graph_client_secret = '********' if system_settings.ms_graph_client_secret else ''  # Beveiliging: altijd sterretjes tonen
            ms_graph_sender_email = system_settings.ms_graph_sender_email or ''
            # Nieuwe velden voor gedeelde mailbox
            ms_graph_shared_mailbox = system_settings.ms_graph_shared_mailbox if hasattr(system_settings, 'ms_graph_shared_mailbox') else ''
            ms_graph_use_shared_mailbox = system_settings.ms_graph_use_shared_mailbox if hasattr(system_settings, 'ms_graph_use_shared_mailbox') else False
            
            smtp_server = system_settings.smtp_server or ''
            smtp_port = str(system_settings.smtp_port) if system_settings.smtp_port else ''
            smtp_username = system_settings.smtp_username or ''
            smtp_password = '********' if system_settings.smtp_password else ''  # Beveiliging: altijd sterretjes tonen
            email_from = system_settings.email_from or ''
            email_from_name = system_settings.email_from_name or ''
            
            # Nieuwe velden voor e-mailinstellingen
            default_sender_name = system_settings.default_sender_name or ''
            reply_to = system_settings.reply_to or ''
            smtp_use_ssl = system_settings.smtp_use_ssl
            smtp_use_tls = system_settings.smtp_use_tls
            
            # Provider selectie
            use_ms_graph = system_settings.use_ms_graph
        else:
            # Fallback naar omgevingsvariabelen voor compatibiliteit
            ms_graph_client_id = os.environ.get('MS_GRAPH_CLIENT_ID', '')
            ms_graph_tenant_id = os.environ.get('MS_GRAPH_TENANT_ID', '')
            ms_graph_client_secret = os.environ.get('MS_GRAPH_CLIENT_SECRET', '')
            ms_graph_sender_email = os.environ.get('MS_GRAPH_SENDER_EMAIL', '')
            
            smtp_server = os.environ.get('SMTP_SERVER', '')
            smtp_port = os.environ.get('SMTP_PORT', '')
            smtp_username = os.environ.get('SMTP_USERNAME', '')
            smtp_password = os.environ.get('SMTP_PASSWORD', '')
            email_from = os.environ.get('EMAIL_FROM', '')
            email_from_name = os.environ.get('EMAIL_FROM_NAME', '')
            
            # Standaard waarden voor nieuwe velden
            default_sender_name = os.environ.get('EMAIL_FROM_NAME', 'MidaWeb')
            reply_to = os.environ.get('EMAIL_REPLY_TO', '')
            smtp_use_ssl = True  # Standaard SSL gebruiken
            smtp_use_tls = False  # Standaard geen TLS
            
            # Standaard provider selectie
            use_ms_graph = True  # Default naar MS Graph als er geen instellingen zijn
    else:
        # Controleren of dit een super_admin is met een workspace_id (speciale situatie)
        if current_user.is_super_admin:
            # Super admin blijft toegang houden tot alle werkruimtes, ook al heeft deze een workspace_id
            users = get_users()
            # Get all workspaces for super admin
            workspaces = Workspace.query.all()
            # Get counts across all workspaces
            customer_count = Customer.query.count()
            invoice_count = Invoice.query.count()
        else:
            # Regular admins can only see users in their workspace
            users = User.query.filter_by(workspace_id=current_user.workspace_id).all()
            # Only their workspace
            workspaces = [current_user.workspace] if current_user.workspace else []
            # Get counts for their workspace only
            customer_count = Customer.query.filter_by(workspace_id=current_user.workspace_id).count()
            invoice_count = Invoice.query.filter_by(workspace_id=current_user.workspace_id).count()
        
        # Voor normale admins geen e-mailinstellingen
        ms_graph_client_id = ms_graph_tenant_id = ms_graph_client_secret = ms_graph_sender_email = ''
        smtp_server = smtp_port = smtp_username = smtp_password = email_from = email_from_name = ''
        default_sender_name = reply_to = ''
        smtp_use_ssl = True
        smtp_use_tls = False
        use_ms_graph = True  # Default voor normale admins
    
    return render_template('admin.html', 
                           users=users, 
                           workspaces=workspaces,
                           customer_count=customer_count, 
                           invoice_count=invoice_count, 
                           now=datetime.now(),
                           # Abonnement informatie voor werkruimte beheerders
                           workspace=workspace,
                           subscription=subscription,
                           format_currency=format_currency,
                           # E-mailinstellingen voor het template
                           email_settings=email_settings,
                           # E-mail instellingen voor template
                           ms_graph_client_id=ms_graph_client_id if 'ms_graph_client_id' in locals() else '',
                           ms_graph_tenant_id=ms_graph_tenant_id if 'ms_graph_tenant_id' in locals() else '',
                           ms_graph_client_secret=ms_graph_client_secret if 'ms_graph_client_secret' in locals() else '',
                           ms_graph_sender_email=ms_graph_sender_email if 'ms_graph_sender_email' in locals() else '',
                           # Nieuwe velden voor gedeelde mailbox
                           ms_graph_shared_mailbox=ms_graph_shared_mailbox if 'ms_graph_shared_mailbox' in locals() else '',
                           ms_graph_use_shared_mailbox=ms_graph_use_shared_mailbox if 'ms_graph_use_shared_mailbox' in locals() else False,
                           # SMTP instellingen
                           smtp_server=smtp_server if 'smtp_server' in locals() else '',
                           smtp_port=smtp_port if 'smtp_port' in locals() else '',
                           smtp_username=smtp_username if 'smtp_username' in locals() else '',
                           smtp_password=smtp_password if 'smtp_password' in locals() else '',
                           email_from=email_from if 'email_from' in locals() else '',
                           email_from_name=email_from_name if 'email_from_name' in locals() else '',
                           # Nieuwe velden voor e-mailinstellingen
                           default_sender_name=default_sender_name if 'default_sender_name' in locals() else '',
                           reply_to=reply_to if 'reply_to' in locals() else '',
                           smtp_use_ssl=smtp_use_ssl if 'smtp_use_ssl' in locals() else True,
                           smtp_use_tls=smtp_use_tls if 'smtp_use_tls' in locals() else False,
                           # Provider selectie
                           use_ms_graph=use_ms_graph if 'use_ms_graph' in locals() else True)

@app.route('/system-overview')
@login_required
def system_overview():
    """Systeem overzicht pagina voor super admins"""
    # Alleen super admins hebben toegang tot het systeem overzicht
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Get current year
    current_year = datetime.now().year
    
    # Super admin dashboard zonder specifieke workspace data
    # Haal alleen systeemstatistieken op
    workspaces = Workspace.query.all()
    workspace_count = len(workspaces)
    
    user_count = User.query.count()
    customer_count = Customer.query.count()
    invoice_count = Invoice.query.count()
    
    # Haal de werkruimtes met de meeste gebruikers op
    top_workspaces = []
    for workspace in workspaces:
        users_count = User.query.filter_by(workspace_id=workspace.id).count()
        customers_count = Customer.query.filter_by(workspace_id=workspace.id).count()
        invoices_count = Invoice.query.filter_by(workspace_id=workspace.id).count()
        
        # Bereken totaal inkomen en uitgaven per werkruimte
        workspace_invoices = Invoice.query.filter_by(workspace_id=workspace.id).all()
        income = sum(inv.amount_incl_vat for inv in workspace_invoices if inv.invoice_type == 'income')
        expenses = sum(inv.amount_incl_vat for inv in workspace_invoices if inv.invoice_type == 'expense')
        
        top_workspaces.append({
            'id': workspace.id,
            'name': workspace.name,
            'users_count': users_count,
            'customers_count': customers_count,
            'invoices_count': invoices_count,
            'created_at': workspace.created_at,
            'income': income,
            'expenses': expenses,
            'profit': income - expenses
        })
    
    # Sorteer op aantal gebruikers (van hoog naar laag)
    top_workspaces = sorted(top_workspaces, key=lambda x: x['users_count'], reverse=True)[:5]
    
    # Recente gebruikers en klanten
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_workspaces = Workspace.query.order_by(Workspace.created_at.desc()).limit(5).all()
    
    # Maandelijks overzicht van nieuwe gebruikers en klanten
    monthly_signups = {}
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Initialiseer voor de laatste 6 maanden
    for i in range(6):
        month = current_month - i
        year = current_year
        if month <= 0:
            month += 12
            year -= 1
        month_name = datetime(year, month, 1).strftime('%B')
        monthly_signups[month_name] = {
            'users': 0,
            'workspaces': 0,
            'customers': 0
        }
    
    # Verzamel data van de laatste 6 maanden
    six_months_ago = datetime.now() - timedelta(days=180)
    
    # Gebruikers per maand
    users_by_month = User.query.filter(User.created_at >= six_months_ago).all()
    for user in users_by_month:
        month_name = user.created_at.strftime('%B')
        if month_name in monthly_signups:
            monthly_signups[month_name]['users'] += 1
    
    # Werkruimtes per maand
    workspaces_by_month = Workspace.query.filter(Workspace.created_at >= six_months_ago).all()
    for workspace in workspaces_by_month:
        month_name = workspace.created_at.strftime('%B')
        if month_name in monthly_signups:
            monthly_signups[month_name]['workspaces'] += 1
    
    # Klanten per maand
    customers_by_month = Customer.query.filter(Customer.created_at >= six_months_ago).all()
    for customer in customers_by_month:
        month_name = customer.created_at.strftime('%B')
        if month_name in monthly_signups:
            monthly_signups[month_name]['customers'] += 1
    
    # Maak arrays voor grafiekdata
    chart_months = list(monthly_signups.keys())
    chart_months.reverse()  # Oudste maand eerst
    chart_users = [monthly_signups[month]['users'] for month in chart_months]
    chart_workspaces = [monthly_signups[month]['workspaces'] for month in chart_months]
    chart_customers = [monthly_signups[month]['customers'] for month in chart_months]
    
    return render_template(
        'admin_dashboard.html',
        current_year=current_year,
        is_super_admin_dashboard=True,
        workspace_count=workspace_count,
        user_count=user_count,
        customer_count=customer_count,
        invoice_count=invoice_count,
        top_workspaces=top_workspaces,
        recent_users=recent_users,
        recent_workspaces=recent_workspaces,
        chart_months=json.dumps(chart_months),
        chart_users=json.dumps(chart_users),
        chart_workspaces=json.dumps(chart_workspaces),
        chart_customers=json.dumps(chart_customers),
        format_currency=format_currency,
        now=datetime.now()
    )

@app.route('/admin/user/create', methods=['POST'])
@login_required
def admin_create_user():
    # Only admins can create users
    if not current_user.is_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Check if request is from super admin for super admin creation
    can_create_super_admin = current_user.is_super_admin
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = 'is_admin' in request.form
    is_super_admin = 'is_super_admin' in request.form and can_create_super_admin
    
    # Validate input
    if not all([username, email, password]):
        flash('Alle velden zijn verplicht', 'danger')
        return redirect(url_for('admin'))
    
    # Check if username or email already exists
    if User.query.filter((User.username == username) | (User.email == email)).first():
        flash('Gebruikersnaam of e-mailadres is al in gebruik', 'danger')
        return redirect(url_for('admin'))
    
    # Handle workspace assignment
    workspace_id = None
    if current_user.is_super_admin:
        # Super admins can assign to any workspace or none (for other super admins)
        workspace_id_input = request.form.get('workspace_id', '')
        if workspace_id_input and workspace_id_input.strip():
            try:
                workspace_id = int(workspace_id_input)
            except ValueError:
                # Als de waarde geen geldige integer is, gebruik None
                workspace_id = None
        # Expliciete leeg waarde behandelen ('' of None)
        elif workspace_id_input == '':
            # Lege string expliciet omzetten in None voor de database
            workspace_id = None
    else:
        # Regular admins can only create users in their workspace
        workspace_id = current_user.workspace_id
    
    # Required password change
    password_change_required = 'password_change_required' in request.form
    
    # Create user
    try:
        from models import create_user
        user = create_user(username, email, password, is_admin, is_super_admin)
        
        # Update workspace and password change flag
        if user:
            user.workspace_id = workspace_id
            user.password_change_required = password_change_required
            db.session.commit()
            
        flash(f'Gebruiker {username} is aangemaakt', 'success')
    except Exception as e:
        logging.error(f"Error creating user: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van de gebruiker', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/edit-permissions/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_permissions(user_id):
    """Beheer rechten van een gebruiker"""
    # Alleen admins mogen rechten bewerken
    if not current_user.is_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de gebruiker op
    user = User.query.get(user_id)
    if not user:
        flash('Gebruiker niet gevonden', 'danger')
        return redirect(url_for('admin'))
    
    # Admins mogen geen rechten van super admins bewerken
    if user.is_super_admin and not current_user.is_super_admin:
        flash('U heeft geen toegang om rechten van super admins te bewerken', 'danger')
        return redirect(url_for('admin'))
    
    # Super admins hebben altijd alle rechten, eigen rechten kunnen niet worden bewerkt
    if user.is_super_admin or user.id == current_user.id:
        flash('Super admins hebben automatisch alle rechten en eigen rechten kunnen niet worden bewerkt', 'warning')
        return redirect(url_for('edit_user', user_id=user_id))
    
    # Haal huidige permissions op of maak een nieuw permissions object aan
    permissions = user.permissions
    if not permissions:
        permissions = UserPermission(user_id=user.id)
        db.session.add(permissions)
    
    # Bij POST verwerken we het formulier
    if request.method == 'POST':
        # Klanten rechten
        permissions.can_view_customers = 'can_view_customers' in request.form
        permissions.can_add_customers = 'can_add_customers' in request.form
        permissions.can_edit_customers = 'can_edit_customers' in request.form
        permissions.can_delete_customers = 'can_delete_customers' in request.form
        
        # Facturen rechten
        permissions.can_view_invoices = 'can_view_invoices' in request.form
        permissions.can_add_invoices = 'can_add_invoices' in request.form
        permissions.can_edit_invoices = 'can_edit_invoices' in request.form
        permissions.can_delete_invoices = 'can_delete_invoices' in request.form
        permissions.can_upload_invoices = 'can_upload_invoices' in request.form
        
        # Rapporten rechten
        permissions.can_view_reports = 'can_view_reports' in request.form
        permissions.can_export_reports = 'can_export_reports' in request.form
        permissions.can_generate_vat_report = 'can_generate_vat_report' in request.form
        
        # Andere rechten
        permissions.can_view_dashboard = 'can_view_dashboard' in request.form
        permissions.can_manage_settings = 'can_manage_settings' in request.form
        
        # Opslaan in database
        try:
            db.session.commit()
            flash('Gebruikersrechten zijn bijgewerkt', 'success')
            return redirect(url_for('edit_permissions', user_id=user_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating user permissions: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de rechten', 'danger')
    
    # Toon formulier met huidige rechten
    return render_template('edit_permissions.html', user=user, permissions=permissions, now=datetime.now())

@app.route('/update-permissions/<int:user_id>', methods=['POST'])
@login_required
def update_permissions(user_id):
    """Update de rechten van een gebruiker"""
    return redirect(url_for('edit_permissions', user_id=user_id))

@app.route('/admin/user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    # Only admins can edit users
    if not current_user.is_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    from models import get_user, update_user
    user = get_user(user_id)
    if not user:
        flash('Gebruiker niet gevonden', 'danger')
        return redirect(url_for('admin'))
    
    # Regular admins cannot edit super admins
    if user.is_super_admin and not current_user.is_super_admin:
        flash('U heeft geen toegang om super admins te bewerken', 'danger')
        return redirect(url_for('admin'))
    
    # Handle form submission
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Check permissions for admin status changes
        can_change_admin = current_user.is_super_admin or not user.is_super_admin
        can_change_super_admin = current_user.is_super_admin and user_id != current_user.id
        
        is_admin = 'is_admin' in request.form if can_change_admin else user.is_admin
        is_super_admin = 'is_super_admin' in request.form if can_change_super_admin else user.is_super_admin
        
        # Validate password if changing
        if new_password:
            if new_password != confirm_password:
                flash('Wachtwoorden komen niet overeen', 'danger')
                # Get workspaces for dropdown
                workspaces = []
                if current_user.is_super_admin:
                    workspaces = Workspace.query.all()
                return render_template('edit_user.html', user=user, workspaces=workspaces, now=datetime.now())
        
        # Process workspace assignment for super admins
        workspace_id = None
        if current_user.is_super_admin:
            workspace_id_input = request.form.get('workspace_id', '')
            if workspace_id_input and workspace_id_input.strip():
                try:
                    workspace_id = int(workspace_id_input)
                except ValueError:
                    # Als de waarde geen geldige integer is, gebruik None
                    workspace_id = None
            # Expliciete leeg waarde behandelen ('' of None)
            elif workspace_id_input == '':
                # Lege string expliciet omzetten in None voor de database
                workspace_id = None
        
        # Update user
        try:
            update_user(user_id, email, new_password if new_password else None, is_admin, is_super_admin, workspace_id)
            flash(f'Gebruiker {user.username} is bijgewerkt', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            logging.error(f"Error updating user: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de gebruiker', 'danger')
    
    # Get workspaces for dropdown
    workspaces = []
    if current_user.is_super_admin:
        workspaces = Workspace.query.all()
    
    return render_template('edit_user.html', user=user, workspaces=workspaces, now=datetime.now())

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    # Only admins can delete users
    if not current_user.is_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Cannot delete yourself
    if user_id == current_user.id:
        flash('U kunt uw eigen account niet verwijderen', 'danger')
        return redirect(url_for('admin'))
    
    from models import get_user, delete_user as delete_user_model
    user = get_user(user_id)
    if not user:
        flash('Gebruiker niet gevonden', 'danger')
        return redirect(url_for('admin'))
    
    # Regular admins cannot delete super admins
    if user.is_super_admin and not current_user.is_super_admin:
        flash('U heeft geen toegang om super admins te verwijderen', 'danger')
        return redirect(url_for('admin'))
    
    # Delete user
    if delete_user_model(user_id):
        flash(f'Gebruiker {user.username} is verwijderd', 'success')
    else:
        flash('Kan de gebruiker niet verwijderen. Er moet minimaal één super admin behouden blijven.', 'danger')
    
    return redirect(url_for('admin'))

# Workspace management routes
@app.route('/admin/workspace/create', methods=['POST'])
@login_required
def create_workspace():
    # Only super admins can create workspaces
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    # Validate input
    if not name:
        flash('Werkruimte naam is verplicht', 'danger')
        return redirect(url_for('admin'))
    
    # Check if workspace name already exists
    existing_workspace = Workspace.query.filter_by(name=name).first()
    if existing_workspace:
        flash('Een werkruimte met deze naam bestaat al', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # Create new workspace
        workspace = Workspace(name=name, description=description)
        db.session.add(workspace)
        db.session.commit()
        flash(f'Werkruimte "{name}" is aangemaakt', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating workspace: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van de werkruimte', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/workspace/<int:workspace_id>/edit', methods=['POST'])
@login_required
def edit_workspace(workspace_id):
    # Only super admins can edit workspaces
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('admin'))
    
    name = request.form.get('name')
    description = request.form.get('description', '')
    
    # Validate input
    if not name:
        flash('Werkruimte naam is verplicht', 'danger')
        return redirect(url_for('admin'))
    
    # Check if new name already exists (if name changed)
    if name != workspace.name:
        existing_workspace = Workspace.query.filter_by(name=name).first()
        if existing_workspace:
            flash('Een werkruimte met deze naam bestaat al', 'danger')
            return redirect(url_for('admin'))
    
    try:
        # Update workspace
        workspace.name = name
        workspace.description = description
        db.session.commit()
        flash(f'Werkruimte "{name}" is bijgewerkt', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating workspace: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de werkruimte', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/workspace/<int:workspace_id>/delete', methods=['POST'])
@login_required
def delete_workspace(workspace_id):
    # Only super admins can delete workspaces
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden', 'danger')
        return redirect(url_for('admin'))
    
    # Check if workspace has users
    if User.query.filter_by(workspace_id=workspace_id).count() > 0:
        flash('Deze werkruimte kan niet worden verwijderd omdat er nog gebruikers aan gekoppeld zijn', 'danger')
        return redirect(url_for('admin'))
    
    # Check if workspace has customers or invoices
    if Customer.query.filter_by(workspace_id=workspace_id).count() > 0 or Invoice.query.filter_by(workspace_id=workspace_id).count() > 0:
        flash('Deze werkruimte kan niet worden verwijderd omdat er nog klanten of facturen aan gekoppeld zijn', 'danger')
        return redirect(url_for('admin'))
    
    try:
        # Delete workspace
        db.session.delete(workspace)
        db.session.commit()
        flash(f'Werkruimte "{workspace.name}" is verwijderd', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting workspace: {str(e)}")
        flash('Er is een fout opgetreden bij het verwijderen van de werkruimte', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/user/<int:user_id>/assign-workspace', methods=['POST'])
@login_required
def assign_workspace_to_user(user_id):
    # Only super admins can assign users to workspaces
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get(user_id)
    if not user:
        flash('Gebruiker niet gevonden', 'danger')
        return redirect(url_for('admin'))
    
    workspace_id_input = request.form.get('workspace_id', '')
    workspace = None
    
    if workspace_id_input and workspace_id_input.strip():
        try:
            workspace_id = int(workspace_id_input)
            workspace = Workspace.query.get(workspace_id)
            if not workspace:
                flash('Werkruimte niet gevonden', 'danger')
                return redirect(url_for('admin'))
        except ValueError:
            # Als de waarde geen geldige integer is, gebruik None
            workspace_id = None
    else:
        # Setting to None for super admins
        workspace_id = None
    
    try:
        # Assign user to workspace
        user.workspace_id = workspace_id
        db.session.commit()
        
        # Get workspace name for the flash message
        if workspace_id and workspace:
            workspace_name = workspace.name
        else:
            workspace_name = "Geen (Super Admin)"
            
        flash(f'Gebruiker {user.username} is toegewezen aan werkruimte: {workspace_name}', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error assigning workspace to user: {str(e)}")
        flash('Er is een fout opgetreden bij het toewijzen van de werkruimte', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/workspace/<int:workspace_id>/access', methods=['GET'])
@login_required
def access_workspace(workspace_id):
    """Access a workspace as an admin (super admin only)"""
    # Check if user is super admin
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze functie.', 'danger')
        return redirect(url_for('dashboard'))
    
    # Find workspace
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        flash('Werkruimte niet gevonden.', 'danger')
        return redirect(url_for('admin'))
    
    # Store the original user ID in the session so we can restore it later
    session['super_admin_id'] = current_user.id
    
    # Find an admin user in this workspace or the first user if no admins
    admin_user = User.query.filter_by(workspace_id=workspace_id, is_admin=True).first()
    if not admin_user:
        admin_user = User.query.filter_by(workspace_id=workspace_id).first()
        
    if not admin_user:
        flash('Er zijn geen gebruikers in deze werkruimte om als in te loggen.', 'warning')
        return redirect(url_for('admin'))
    
    # Login as the workspace admin
    logout_user()
    login_user(admin_user)
    
    flash(f'Je bent nu ingelogd als "{admin_user.username}" in werkruimte "{workspace.name}". Je kunt terugkeren naar je super admin account via het profielmenu.', 'info')
    return redirect(url_for('dashboard'))

# Client/Workspace onboarding routes
@app.route("/admin/client/create", methods=["GET", "POST"])
@login_required
def create_client():
    """
    Super admin route voor het aanmaken van een nieuwe klant (customer) en werkruimte
    De functie stuurt ook een uitnodigingsmail naar de klant
    """
    # Only super admins can create clients/workspaces
    if not current_user.is_super_admin:
        flash("U heeft geen toegang tot deze pagina", "danger")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        # Get form data
        company_name = request.form.get("company_name")
        vat_number = request.form.get("vat_number")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        street = request.form.get("street")
        house_number = request.form.get("house_number")
        postal_code = request.form.get("postal_code")
        city = request.form.get("city")
        country = request.form.get("country", "België")
        workspace_name = request.form.get("workspace_name")
        
        # Validate required fields
        if not all([company_name, email, workspace_name]):
            flash("Bedrijfsnaam, e-mailadres en werkruimtenaam zijn verplicht", "danger")
            return render_template("create_client.html", now=datetime.now())
        
        # Check if workspace name already exists
        existing_workspace = Workspace.query.filter_by(name=workspace_name).first()
        if existing_workspace:
            flash("Een werkruimte met deze naam bestaat al", "danger")
            return render_template("create_client.html", now=datetime.now())
        
        try:
            # Create new workspace
            workspace = Workspace(name=workspace_name, description=f"Werkruimte voor {company_name}")
            db.session.add(workspace)
            db.session.flush()  # Get workspace ID without committing
            
            # Create new customer in this workspace
            customer = Customer(
                company_name=company_name,
                vat_number=vat_number,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                street=street,
                house_number=house_number,
                postal_code=postal_code,
                city=city,
                country=country,
                customer_type="business",
                workspace_id=workspace.id
            )
            db.session.add(customer)
            db.session.commit()
            
            # Generate invitation token
            activation_token = token_helper.generate_workspace_invitation_token(
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                customer_email=email
            )
            
            # Send invitation email
            customer_name = f"{first_name} {last_name}" if first_name and last_name else None
            email_service = EmailService()
            email_sent = email_service.send_workspace_invitation(
                recipient_email=email,
                workspace_name=workspace_name,
                activation_token=activation_token,
                customer_name=customer_name
            )
            
            if email_sent:
                flash(f"Klant \"{company_name}\" en werkruimte \"{workspace_name}\" aangemaakt. Uitnodiging verzonden naar {email}.", "success")
            else:
                flash(f"Klant \"{company_name}\" en werkruimte \"{workspace_name}\" aangemaakt, maar de uitnodiging kon niet worden verzonden.", "warning")
            
            return redirect(url_for("admin", settings=True))
        
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating client and workspace: {str(e)}")
            flash("Er is een fout opgetreden bij het aanmaken van de klant en werkruimte", "danger")
            return render_template("create_client.html", now=datetime.now())
    
    # GET request - show client creation form
    return render_template("create_client.html", now=datetime.now())

@app.route("/activate/workspace/", methods=["GET"])
def activate_workspace_missing_token():
    """
    Route voor wanneer een gebruiker de werkruimte-activatie-URL zonder token probeert te gebruiken
    """
    flash("Ongeldige activatie-URL. Er ontbreekt een activatiecode in de link.", "danger")
    return redirect(url_for("login"))

@app.route("/activate/workspace/<token>", methods=["GET", "POST"])
def activate_workspace(token):
    """
    Route voor het activeren van een werkruimte door een klant
    De klant maakt de eerste gebruiker aan (admin) en wordt automatisch ingelogd
    """
    # Verifieer token
    token_data = token_helper.verify_token(token)
    
    if not token_data or token_data.get("type") != "workspace_invitation":
        flash("Ongeldige of verlopen activatiecode", "danger")
        return redirect(url_for("login"))
    
    workspace_id = token_data.get("workspace_id")
    workspace_name = token_data.get("workspace_name")
    email = token_data.get("email")
    
    # Controleer of werkruimte bestaat
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        flash("De werkruimte bestaat niet meer", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        # Get form data
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        # Validate input
        if not all([username, password, confirm_password]):
            flash("Alle velden zijn verplicht", "danger")
            return render_template(
                "activate_workspace.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
        
        if password != confirm_password:
            flash("Wachtwoorden komen niet overeen", "danger")
            return render_template(
                "activate_workspace.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
        
        # Check if username already exists in this workspace
        existing_user = User.query.filter_by(username=username, workspace_id=workspace_id).first()
        if existing_user:
            flash("Deze gebruikersnaam is al in gebruik binnen deze werkruimte", "danger")
            return render_template(
                "activate_workspace.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
            
        try:
            # Create new admin user for this workspace
            user = User(
                username=username,
                email=email,
                workspace_id=workspace_id,
                is_admin=True,  # Eerste gebruiker is altijd admin
                password_change_required=False  # Wachtwoord is al zelf ingesteld
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Log gebruiker automatisch in
            login_user(user)
            
            flash(f"Welkom bij {workspace_name}! Je account is geactiveerd en je bent nu ingelogd als beheerder.", "success")
            return redirect(url_for("dashboard"))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating workspace admin user: {str(e)}")
            flash("Er is een fout opgetreden bij het aanmaken van je account", "danger")
            return render_template(
                "activate_workspace.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
    
    # GET request - show activation form
    return render_template(
        "activate_workspace.html", 
        workspace_name=workspace_name,
        email=email,
        token=token,
        now=datetime.now()
    )

@app.route('/admin/email/provider', methods=['POST'])
@login_required
def update_email_provider():
    """Update de e-mail provider (Microsoft Graph API of SMTP)"""
    # Alleen super-admins kunnen e-mailinstellingen wijzigen
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de selected provider op (1 = MS Graph, 0 = SMTP)
    use_ms_graph = request.form.get('use_ms_graph') == '1'
    
    # Zoek de system-wide email settings
    from models import EmailSettings
    email_settings = EmailSettings.query.filter_by(workspace_id=None).first()
    
    if not email_settings:
        # Als er nog geen systeem-instellingen zijn, maak ze aan
        email_settings = EmailSettings(workspace_id=None)
        db.session.add(email_settings)
    
    # Update de provider selectie
    email_settings.use_ms_graph = use_ms_graph
    
    # Sla de wijzigingen op
    db.session.commit()
    
    # Log de wijziging
    app.logger.info(f"Email provider gewijzigd naar {'Microsoft Graph API' if use_ms_graph else 'SMTP'} door gebruiker {current_user.username}")
    
    # Toon een bevestiging aan de gebruiker
    flash(f"E-mail verzendmethode is gewijzigd naar {'Microsoft Graph API' if use_ms_graph else 'SMTP Server'}", 'success')
    
    # Ga terug naar admin pagina
    return redirect(url_for('admin'))

# Route for sending a test email
@app.route('/admin/test-email/<provider>', methods=['GET'])
@login_required
def send_test_email(provider):
    # Only super admins can send test emails
    if not current_user.is_super_admin:
        flash('Alleen super admins kunnen test e-mails verzenden', 'danger')
        return redirect(url_for('admin'))
    
    # Get the system email settings
    email_settings = EmailSettings.query.filter_by(workspace_id=None).first()
    
    if not email_settings:
        flash('E-mailinstellingen zijn niet geconfigureerd', 'danger')
        return redirect(url_for('admin'))
    
    # Create an email service based on the provider
    if provider == 'oauth':
        # Gebruik de nieuwe OAuth implementatie
        from email_service_oauth import EmailServiceOAuth
        email_service = EmailServiceOAuth(email_settings)
    else:
        # Gebruik de bestaande email service
        email_service = EmailService(email_settings)
    
    # Determine the subject and content based on provider
    provider_name = {
        'msgraph': 'Microsoft Graph API',
        'smtp': 'SMTP',
        'oauth': 'Microsoft 365 OAuth'
    }.get(provider, provider)
    
    subject = f"Test e-mail van MidaWeb via {provider_name}"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px;">
        <h2 style="color: #4a6ee0;">Test E-mail</h2>
        <p>Dit is een test e-mail verzonden via {provider_name} provider.</p>
        <p>Als u deze e-mail ontvangt, zijn uw e-mailinstellingen correct geconfigureerd.</p>
        <p>Verzonden op: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}</p>
        <p style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666;">
            Dit bericht is automatisch gegenereerd. U kunt niet reageren op dit e-mailadres.
        </p>
    </div>
    """
    
    # Force the appropriate provider based on the route parameter for the standard email service
    from email_service_oauth import EmailServiceOAuth
    if provider == 'msgraph' and not isinstance(email_service, EmailServiceOAuth):
        email_settings.use_ms_graph = True
    elif provider == 'smtp' and not isinstance(email_service, EmailServiceOAuth):
        email_settings.use_ms_graph = False
    elif provider not in ['msgraph', 'smtp', 'oauth']:
        flash('Ongeldige e-mail provider', 'danger')
        return redirect(url_for('admin'))
    
    # Send the test email to the current user
    success = email_service.send_email(
        recipient=current_user.email,
        subject=subject,
        body_html=body_html
    )
    
    if success:
        flash(f'Test e-mail succesvol verzonden naar {current_user.email} via {provider} provider', 'success')
    else:
        flash(f'Fout bij het verzenden van test e-mail via {provider} provider. Controleer de instellingen en probeer het opnieuw.', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/email/ms-oauth', methods=['GET'])
@login_required
def ms_oauth_settings():
    """Pagina voor Microsoft 365 OAuth instellingen"""
    # Alleen super-admins kunnen e-mailinstellingen wijzigen
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de huidige e-mail-instellingen op
    from models import EmailSettings
    email_settings = EmailSettings.query.filter_by(workspace_id=None).first()
    
    # Geef de template weer met de huidige instellingen
    return render_template('admin_email_oauth.html', email_settings=email_settings, now=datetime.now())

@app.route('/admin/email/ms-graph', methods=['POST'])
@login_required
def update_ms_graph_settings():
    """Update Microsoft Graph API instellingen voor e-mail"""
    # Alleen super-admins kunnen e-mailinstellingen wijzigen
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de instellingen uit het formulier
    client_id = request.form.get('ms_graph_client_id', '')
    tenant_id = request.form.get('ms_graph_tenant_id', '')
    client_secret = request.form.get('ms_graph_client_secret', '')
    sender_email = request.form.get('ms_graph_sender_email', '')
    default_sender_name = request.form.get('default_sender_name', 'MidaWeb')
    reply_to = request.form.get('reply_to', '')
    # Nieuwe velden voor gedeelde mailbox
    shared_mailbox = request.form.get('ms_graph_shared_mailbox', '')
    use_shared_mailbox = request.form.get('ms_graph_use_shared_mailbox') == 'on'
    
    # Valideer invoer
    if not all([client_id, tenant_id, client_secret, sender_email]):
        flash('Alle verplichte velden zijn nodig voor Microsoft Graph API configuratie', 'danger')
        return redirect(url_for('admin'))
    
    try:
        from models import EmailSettings, db
        
        # Zoek bestaande systeeminstellingen of maak nieuwe aan
        system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
        if not system_settings:
            system_settings = EmailSettings(workspace_id=None)
            db.session.add(system_settings)
        
        # Werk de instellingen bij
        system_settings.ms_graph_client_id = client_id
        system_settings.ms_graph_tenant_id = tenant_id
        system_settings.ms_graph_client_secret = EmailSettings.encrypt_secret(client_secret)
        system_settings.ms_graph_sender_email = sender_email
        system_settings.default_sender_name = default_sender_name
        system_settings.reply_to = reply_to
        system_settings.use_ms_graph = True
        
        # Nieuwe velden voor gedeelde mailbox
        system_settings.ms_graph_shared_mailbox = shared_mailbox
        system_settings.ms_graph_use_shared_mailbox = use_shared_mailbox
        
        # Sla de wijzigingen op in de database
        db.session.commit()
        
        # Update omgevingsvariabelen (belangrijk voor huidige sessie)
        os.environ['MS_GRAPH_CLIENT_ID'] = client_id
        os.environ['MS_GRAPH_TENANT_ID'] = tenant_id
        os.environ['MS_GRAPH_CLIENT_SECRET'] = client_secret
        os.environ['MS_GRAPH_SENDER_EMAIL'] = sender_email

        # Update ook het .env bestand voor persistentie na herstart
        try:
            _update_env_file({
                'MS_GRAPH_CLIENT_ID': client_id,
                'MS_GRAPH_CLIENT_SECRET': client_secret,
                'MS_GRAPH_TENANT_ID': tenant_id,
                'MS_GRAPH_SENDER_EMAIL': sender_email
            })
            logging.info("MS Graph instellingen bijgewerkt in .env bestand")
        except Exception as e:
            logging.warning(f"Kon .env bestand niet bijwerken: {str(e)}")
        
        # Bevestigingsmelding
        flash('Microsoft Graph API instellingen zijn bijgewerkt en beveiligd opgeslagen', 'success')
        logging.info("MS Graph API instellingen bijgewerkt door gebruiker %s", current_user.username)
    except Exception as e:
        logging.error(f"Fout bij bijwerken van MS Graph instellingen: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de instellingen', 'danger')
    
    return redirect(url_for('admin', settings=True))

# Deze functie is vervangen door de functie bovenaan,
# dit commentaar staat hier om de code te behouden voor referentie
# @app.route('/admin/email/ms-oauth', methods=['GET', 'POST'])
# @login_required
# def ms_oauth_settings_duplicate():
#     """Pagina voor Microsoft 365 OAuth instellingen"""
#     # Alleen super-admins kunnen e-mailinstellingen wijzigen
#     if not current_user.is_super_admin:
#         flash('U heeft geen toegang tot deze pagina', 'danger')
#         return redirect(url_for('dashboard'))
#     
#     # Als het een POST-verzoek is, verwijs naar de update-functie
#     if request.method == 'POST':
#         return update_ms_oauth_settings()
#     
#     # Haal de huidige e-mail-instellingen op
#     from models import EmailSettings
#     email_settings = EmailSettings.query.filter_by(workspace_id=None).first()
#     
#     # Geef de template weer met de huidige instellingen
#     return render_template('admin_email_oauth.html', email_settings=email_settings, now=datetime.now())

@app.route('/admin/email/ms-oauth/update', methods=['POST'])
@login_required
def update_ms_oauth_settings():
    """Update Microsoft 365 OAuth instellingen voor e-mail"""
    # Alleen super-admins kunnen e-mailinstellingen wijzigen
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de instellingen uit het formulier
    client_id = request.form.get('ms_graph_client_id', '')
    tenant_id = request.form.get('ms_graph_tenant_id', '')
    client_secret = request.form.get('ms_graph_client_secret', '')
    sender_email = request.form.get('ms_graph_sender_email', '')
    default_sender_name = request.form.get('default_sender_name', 'MidaWeb')
    
    # Valideer invoer
    if not all([client_id, tenant_id, client_secret, sender_email]):
        flash('Alle verplichte velden zijn nodig voor Microsoft 365 OAuth configuratie', 'danger')
        return redirect(url_for('admin', settings=True))
    
    try:
        from models import EmailSettings, db
        
        # Zoek bestaande systeeminstellingen of maak nieuwe aan
        system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
        if not system_settings:
            system_settings = EmailSettings(workspace_id=None)
            db.session.add(system_settings)
        
        # Werk de instellingen bij
        system_settings.ms_graph_client_id = client_id
        system_settings.ms_graph_tenant_id = tenant_id
        system_settings.ms_graph_client_secret = EmailSettings.encrypt_secret(client_secret)
        system_settings.ms_graph_sender_email = sender_email
        system_settings.default_sender_name = default_sender_name
        system_settings.use_ms_graph = True  # We gebruiken de MS Graph settings voor OAuth ook
        
        # Sla de wijzigingen op in de database
        db.session.commit()
        
        # Update omgevingsvariabelen (belangrijk voor huidige sessie)
        os.environ['MS_GRAPH_CLIENT_ID'] = client_id
        os.environ['MS_GRAPH_TENANT_ID'] = tenant_id
        os.environ['MS_GRAPH_CLIENT_SECRET'] = client_secret
        os.environ['MS_GRAPH_SENDER_EMAIL'] = sender_email
        
        # Update ook het .env bestand voor persistentie na herstart
        try:
            _update_env_file({
                'MS_GRAPH_CLIENT_ID': client_id,
                'MS_GRAPH_CLIENT_SECRET': client_secret,
                'MS_GRAPH_TENANT_ID': tenant_id,
                'MS_GRAPH_SENDER_EMAIL': sender_email
            })
            logging.info("MS OAuth instellingen bijgewerkt in .env bestand")
        except Exception as e:
            logging.warning(f"Kon .env bestand niet bijwerken: {str(e)}")
        
        # Test de OAuth configuratie
        from microsoft_365_oauth import Microsoft365OAuth
        ms_oauth = Microsoft365OAuth(system_settings)
        
        # Probeer token te verkrijgen
        token = ms_oauth.get_oauth_token()
        if token:
            logging.info("OAuth token succesvol verkregen voor %s", sender_email)
            flash('Microsoft 365 OAuth instellingen zijn bijgewerkt en werken correct', 'success')
        else:
            logging.warning("OAuth token kon niet worden verkregen voor %s", sender_email)
            flash('Microsoft 365 OAuth instellingen zijn bijgewerkt, maar het verkrijgen van een token is mislukt. Controleer de instellingen.', 'warning')
        
        logging.info("Microsoft 365 OAuth instellingen bijgewerkt door gebruiker %s", current_user.username)
    except Exception as e:
        logging.error(f"Fout bij bijwerken van Microsoft 365 OAuth instellingen: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de instellingen', 'danger')
    
    return redirect(url_for('admin', settings=True))

@app.route('/admin/email/smtp', methods=['POST'])
@login_required
def update_smtp_settings():
    """Update SMTP instellingen voor e-mail"""
    # Alleen super-admins kunnen e-mailinstellingen wijzigen
    if not current_user.is_super_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    # Haal de instellingen uit het formulier
    smtp_server = request.form.get('smtp_server', '')
    smtp_port = request.form.get('smtp_port', '')
    smtp_username = request.form.get('smtp_username', '')
    smtp_password = request.form.get('smtp_password', '')
    email_from = request.form.get('email_from', '')
    email_from_name = request.form.get('email_from_name', '')
    default_sender_name = request.form.get('default_sender_name', '')
    reply_to = request.form.get('reply_to', '')
    smtp_use_ssl = request.form.get('smtp_use_ssl') == 'true'
    smtp_use_tls = request.form.get('smtp_use_tls') == 'true'
    
    # Valideer de essentiële velden als de gebruiker SMTP wil gebruiken
    if any([smtp_server, smtp_port, smtp_username, smtp_password, email_from]) and not all([smtp_server, smtp_port, smtp_username, smtp_password, email_from]):
        flash('Alle verplichte SMTP velden moeten worden ingevuld (server, poort, gebruikersnaam, wachtwoord, e-mail van)', 'warning')
        return redirect(url_for('admin', settings=True))
    
    try:
        from models import EmailSettings, db
        
        # Zoek bestaande systeeminstellingen of maak nieuwe aan
        system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
        if not system_settings:
            system_settings = EmailSettings(workspace_id=None)
            db.session.add(system_settings)
        
        # Werk de instellingen bij als ze zijn opgegeven
        if all([smtp_server, smtp_port, smtp_username, smtp_password, email_from]):
            system_settings.smtp_server = smtp_server
            system_settings.smtp_port = int(smtp_port) if smtp_port.isdigit() else None
            system_settings.smtp_username = smtp_username
            system_settings.smtp_password = EmailSettings.encrypt_secret(smtp_password)
            system_settings.email_from = email_from
            system_settings.email_from_name = email_from_name
            system_settings.default_sender_name = default_sender_name or email_from_name
            system_settings.reply_to = reply_to
            system_settings.smtp_use_ssl = smtp_use_ssl
            system_settings.smtp_use_tls = smtp_use_tls
            system_settings.use_ms_graph = False
            
            # Sla de wijzigingen op in de database
            db.session.commit()
        
        # Update omgevingsvariabelen (belangrijk voor huidige sessie)
        if smtp_server:
            os.environ['SMTP_SERVER'] = smtp_server
        if smtp_port:
            os.environ['SMTP_PORT'] = smtp_port
        if smtp_username:
            os.environ['SMTP_USERNAME'] = smtp_username
        if smtp_password:
            os.environ['SMTP_PASSWORD'] = smtp_password
        if email_from:
            os.environ['EMAIL_FROM'] = email_from
        if email_from_name:
            os.environ['EMAIL_FROM_NAME'] = email_from_name
        
        # Update ook het .env bestand voor persistentie na herstart
        try:
            env_vars = {}
            if smtp_server:
                env_vars['SMTP_SERVER'] = smtp_server
            if smtp_port:
                env_vars['SMTP_PORT'] = smtp_port
            if smtp_username:
                env_vars['SMTP_USERNAME'] = smtp_username
            if smtp_password:
                env_vars['SMTP_PASSWORD'] = smtp_password
            if email_from:
                env_vars['EMAIL_FROM'] = email_from
            if email_from_name:
                env_vars['EMAIL_FROM_NAME'] = email_from_name
            
            _update_env_file(env_vars)
            logging.info("SMTP instellingen bijgewerkt in .env bestand")
        except Exception as e:
            logging.warning(f"Kon .env bestand niet bijwerken: {str(e)}")
        
        # Bevestigingsmelding
        flash('SMTP instellingen zijn bijgewerkt en beveiligd opgeslagen', 'success')
        logging.info("SMTP instellingen bijgewerkt door gebruiker %s", current_user.username)
    except Exception as e:
        logging.error(f"Fout bij bijwerken van SMTP instellingen: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de instellingen', 'danger')
    
    return redirect(url_for('admin', settings=True))

@app.route("/admin/user/invite", methods=["GET", "POST"])
@login_required
def invite_user():
    """
    Route voor het uitnodigen van een nieuwe gebruiker voor een werkruimte
    Enkel workspaceadmins of superadmins kunnen gebruikers uitnodigen
    """
    # Controleer of de gebruiker admin rechten heeft
    if not current_user.is_admin and not current_user.is_super_admin:
        flash("U heeft geen toegang tot deze pagina", "danger")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        # Get form data
        email = request.form.get("email")
        is_admin = request.form.get("is_admin") == "true"
        workspace_id = request.form.get("workspace_id")
        
        # Validate input
        if not email:
            flash("E-mailadres is verplicht", "danger")
            return redirect(url_for("admin"))
        
        # Als superadmin, controleer of werkruimte is geselecteerd
        if current_user.is_super_admin and not workspace_id:
            flash("Selecteer een werkruimte", "danger")
            return redirect(url_for("admin"))
        
        # Bepaal de juiste werkruimte
        if current_user.is_super_admin:
            workspace = Workspace.query.get_or_404(workspace_id)
        else:
            # Normale admin kan alleen binnen eigen werkruimte uitnodigen
            workspace = Workspace.query.get_or_404(current_user.workspace_id)
            
        try:
            # Genereer uitnodigingstoken
            activation_token = token_helper.generate_user_invitation_token(
                workspace_id=workspace.id,
                workspace_name=workspace.name,
                email=email,
                is_admin=is_admin
            )
            
            # Verzend uitnodigingsmail
            email_service = EmailService()
            email_sent = email_service.send_user_invitation(
                recipient_email=email,
                workspace_name=workspace.name,
                activation_token=activation_token,
                inviter_name=current_user.username
            )
            
            if email_sent:
                flash(f"Uitnodiging verzonden naar {email} voor werkruimte {workspace.name}.", "success")
            else:
                flash(f"De uitnodiging kon niet worden verzonden naar {email}.", "warning")
            
            return redirect(url_for("admin"))
            
        except Exception as e:
            logging.error(f"Error inviting user: {str(e)}")
            flash("Er is een fout opgetreden bij het versturen van de uitnodiging", "danger")
            return redirect(url_for("admin"))
    
    # GET request - show user invitation form
    workspaces = []
    if current_user.is_super_admin:
        workspaces = Workspace.query.all()
    
    return render_template("invite_user.html", workspaces=workspaces, now=datetime.now())

@app.route("/activate/user/", methods=["GET"])
def activate_user_missing_token():
    """
    Route voor wanneer een gebruiker de activatie-URL zonder token probeert te gebruiken
    """
    flash("Ongeldige activatie-URL. Er ontbreekt een activatiecode in de link.", "danger")
    return redirect(url_for("login"))

@app.route("/activate/user/<token>", methods=["GET", "POST"])
def activate_user(token):
    """
    Route voor het activeren van een gebruikersaccount na uitnodiging
    """
    # Verifieer token
    token_data = token_helper.verify_token(token)
    
    if not token_data or token_data.get("type") != "user_invitation":
        flash("Ongeldige of verlopen activatiecode", "danger")
        return redirect(url_for("login"))
    
    workspace_id = token_data.get("workspace_id")
    workspace_name = token_data.get("workspace_name")
    email = token_data.get("email")
    is_admin = token_data.get("is_admin", False)
    
    # Controleer of werkruimte bestaat
    workspace = Workspace.query.get(workspace_id)
    if not workspace:
        flash("De werkruimte bestaat niet meer", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        # Get form data
        username = request.form.get("username")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        # Validate input
        if not all([username, password, confirm_password]):
            flash("Alle velden zijn verplicht", "danger")
            return render_template(
                "activate_user.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
        
        if password != confirm_password:
            flash("Wachtwoorden komen niet overeen", "danger")
            return render_template(
                "activate_user.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
        
        # Check if username already exists in this workspace
        existing_user = User.query.filter_by(username=username, workspace_id=workspace_id).first()
        if existing_user:
            flash("Deze gebruikersnaam is al in gebruik binnen deze werkruimte", "danger")
            return render_template(
                "activate_user.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
            
        try:
            # Create new user for this workspace
            user = User(
                username=username,
                email=email,
                workspace_id=workspace_id,
                is_admin=is_admin,
                password_change_required=False  # Wachtwoord is al zelf ingesteld
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Log gebruiker automatisch in
            login_user(user)
            
            flash(f"Welkom bij {workspace_name}! Je account is geactiveerd en je bent nu ingelogd.", "success")
            return redirect(url_for("dashboard"))
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating user: {str(e)}")
            flash("Er is een fout opgetreden bij het aanmaken van je account", "danger")
            return render_template(
                "activate_user.html", 
                workspace_name=workspace_name,
                email=email,
                token=token,
                now=datetime.now()
            )
    
    # GET request - show activation form
    return render_template(
        "activate_user.html", 
        workspace_name=workspace_name,
        email=email,
        token=token,
        now=datetime.now()
    )


@app.route('/terms-of-service')
@app.route('/terms-of-service/<lang>')
def terms_of_service(lang='nl'):
    """
    Route voor het tonen van de gebruiksrechtovereenkomst in verschillende talen
    """
    # Valideer de taalcode
    if lang not in ['nl', 'en', 'fr']:
        lang = 'nl'
        
    return render_template('terms_of_service.html', lang=lang, now=datetime.now())


@app.route('/privacy-policy')
@app.route('/privacy-policy/<lang>')
def privacy_policy(lang='nl'):
    """
    Route voor het tonen van de privacyverklaring in verschillende talen
    """
    # Valideer de taalcode
    if lang not in ['nl', 'en', 'fr']:
        lang = 'nl'
        
    return render_template('privacy_policy.html', lang=lang, now=datetime.now())


# Taal ondersteuning routes en functies
@app.before_request
def load_user_language():
    """Laad taalvoorkeuren van de gebruiker en globale variabelen voorafgaand aan elk verzoek"""
    # Standaardtaal is Nederlands
    g.language = session.get('language', 'nl')
    
    # Laad vertalingen voor de huidige taal
    try:
        translation_file = os.path.join(app.root_path, 'static', 'translations', f'{g.language}.json')
        if os.path.exists(translation_file):
            with open(translation_file, 'r', encoding='utf-8') as f:
                g.translations = json.load(f)
        else:
            # Fallback naar Nederlands als het vertaalbestand niet bestaat
            fallback_file = os.path.join(app.root_path, 'static', 'translations', 'nl.json')
            if os.path.exists(fallback_file):
                with open(fallback_file, 'r', encoding='utf-8') as f:
                    g.translations = json.load(f)
                    g.language = 'nl'  # Reset naar standaard
            else:
                g.translations = {}  # Leeg dict als fallback
    except Exception as e:
        app.logger.error(f"Fout bij laden van vertalingen: {e}")
        g.translations = {}  # Leeg dict als fallback
        
    # Stel datetime in voor templates
    g.now = datetime.now()
    
    # Voor super admins, laad de lijst met werkruimtes voor de dropdown in de navigatiebalk
    if current_user.is_authenticated and current_user.is_super_admin:
        try:
            workspaces = Workspace.query.all()
            app.logger.info(f"Werkruimtes opgehaald: {len(workspaces)} gevonden")
            g.workspaces = workspaces
        except Exception as e:
            app.logger.error(f"Fout bij ophalen werkruimtes: {e}")
            g.workspaces = []
    else:
        g.workspaces = []

@app.route('/set-language/<language_code>')
def set_language(language_code):
    """Stel de taalvoorkeur van de gebruiker in"""
    # Alleen geldige taalcodes toestaan
    valid_languages = ['nl', 'en', 'fr']
    
    if language_code in valid_languages:
        session['language'] = language_code
        # Vlaganimatie wordt door JavaScript toegepast
        flash(f'Taal gewijzigd naar {language_code.upper()}', 'success')
    else:
        flash(f'Ongeldige taalcode: {language_code}', 'danger')
    
    # Redirect terug naar de verwijzende pagina of dashboard
    referrer = request.referrer or url_for('dashboard')
    return redirect(referrer)


# Test routes voor debugging
@app.route('/test/workspaces')
def test_workspaces():
    """Test route om werkruimtes weer te geven voor debugging"""
    try:
        workspaces = Workspace.query.all()
        result = [{'id': w.id, 'name': w.name} for w in workspaces]
        app.logger.info(f"Test workspaces: {len(workspaces)} gevonden")
        return jsonify({
            'success': True,
            'workspaces': result,
            'count': len(result)
        })
    except Exception as e:
        app.logger.error(f"Fout bij test_workspaces: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/test/users')
def test_users():
    """Test route om gebruikers en hun werkruimtes te tonen"""
    try:
        users = User.query.all()
        result = []
        for user in users:
            workspace_name = user.workspace.name if user.workspace else "Geen werkruimte"
            result.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_admin': user.is_admin,
                'is_super_admin': user.is_super_admin,
                'workspace_id': user.workspace_id,
                'workspace_name': workspace_name
            })
        app.logger.info(f"Test users: {len(users)} gevonden")
        return jsonify({
            'success': True,
            'users': result,
            'count': len(result)
        })
    except Exception as e:
        app.logger.error(f"Fout bij test_users: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# Error handling en monitoring routes
@app.route('/admin/error-test')
@login_required
def error_test():
    """Test route om fouten te genereren voor het testen van het logsysteem"""
    if not current_user.is_admin and not current_user.is_super_admin:
        abort(403)  # Forbidden voor niet-admins
    
    error_type = request.args.get('type', 'info')
    
    # Log verschillende soorten berichten op basis van de 'type' parameter
    if error_type == 'debug':
        logger.debug("Dit is een test DEBUG bericht")
        flash("DEBUG bericht gelogd", "info")
    elif error_type == 'info':
        logger.info("Dit is een test INFO bericht")
        flash("INFO bericht gelogd", "info")
    elif error_type == 'warning':
        logger.warning("Dit is een test WARNING bericht")
        flash("WARNING bericht gelogd", "warning")
    elif error_type == 'error':
        logger.error("Dit is een test ERROR bericht")
        flash("ERROR bericht gelogd", "danger")
    elif error_type == 'critical':
        logger.critical("Dit is een test CRITICAL bericht")
        flash("CRITICAL bericht gelogd", "danger")
    elif error_type == 'exception':
        try:
            # Opzettelijk een fout genereren
            1/0
        except Exception as e:
            logger.exception("Dit is een test exception")
            flash(f"Exception gelogd: {str(e)}", "danger")
    elif error_type == 'unhandled':
        # Genereer een onbehandelde fout
        non_existent_variable = undefined_variable  # Genereert een NameError
    else:
        flash("Onbekend fouttype", "danger")
    
    return redirect(url_for('logs.logs_dashboard'))

# Globale errorhandler voor 404 fouten
@app.errorhandler(404)
def page_not_found(error):
    logger.warning(f"404 Pagina niet gevonden: {request.path}")
    return render_template('404.html', now=datetime.now()), 404

# Globale errorhandler voor 403 fouten
@app.errorhandler(403)
def forbidden(error):
    logger.warning(f"403 Verboden toegang: {request.path} door gebruiker {current_user.username if current_user.is_authenticated else 'onbekend'}")
    return render_template('403.html', now=datetime.now()), 403

# Globale errorhandler voor 500 fouten
@app.errorhandler(500)
def internal_error(error):
    # Log de error met traceback
    logger.error(f"500 Server error: {str(error)}\n{traceback.format_exc()}")
    return render_template('500.html', now=datetime.now()), 500

