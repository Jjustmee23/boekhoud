"""
Basisroutes voor authenticatie en toegang tot de site
"""
import logging
import sys
import os
from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user, login_user, logout_user
from app import app, db
from models import User, Customer, Invoice, Workspace

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
        workspace_id = request.form.get('workspace_id')
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
            # Validate input
            if not username or not password or not workspace_id:
                flash('Gebruikersnaam, wachtwoord en werkruimte zijn verplicht', 'danger')
                return render_template('login.html', workspaces=workspaces, no_workspaces=not workspaces_exist, now=datetime.now())
            
            # Find user by username in the selected workspace
            user = User.query.filter_by(username=username, workspace_id=workspace_id).first()
            
            # If not found in regular workspace, check if they're a super admin
            if not user:
                super_admin = User.query.filter_by(username=username, is_super_admin=True).first()
                if super_admin and super_admin.check_password(password):
                    user = super_admin
        
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
    from models import get_monthly_summary, get_quarterly_summary, get_customer_summary
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
    
    from utils import format_currency
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