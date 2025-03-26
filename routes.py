import os
import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import (
    Customer, Invoice, User, Workspace, get_next_invoice_number, check_duplicate_invoice, add_invoice,
    calculate_vat_report, get_monthly_summary, get_quarterly_summary, get_customer_summary,
    get_users, get_user, create_user, update_user, delete_user
)
from utils import (
    format_currency, format_decimal, generate_pdf_invoice, export_to_excel, export_to_csv,
    get_vat_rates, date_to_quarter, get_quarters, get_months, get_years,
    save_uploaded_file, allowed_file
)
from file_processor import FileProcessor

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    # If user is already logged in, redirect to dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        password = request.form.get('password')
        workspace_id = request.form.get('workspace_id')
        remember = request.form.get('remember', 'false') == 'true'
        
        # Validate input
        if not username or not password or not workspace_id:
            flash('Gebruikersnaam, wachtwoord en werkruimte zijn verplicht', 'danger')
            return render_template('login.html', workspaces=Workspace.query.all(), now=datetime.now())
        
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
            db.session.add(current_user)
            flash('Wachtwoord bijgewerkt', 'success')
        
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

# Dashboard routes
@app.route('/')
@login_required
def dashboard():
    # Get current year
    current_year = datetime.now().year
    
    # Get summaries
    monthly_summary = get_monthly_summary(current_year)
    quarterly_summary = get_quarterly_summary(current_year)
    customer_summary = get_customer_summary()
    
    # Calculate totals for the year
    year_income = sum(month['income'] for month in monthly_summary)
    year_expenses = sum(month['expenses'] for month in monthly_summary)
    year_profit = year_income - year_expenses
    
    # Calculate VAT totals
    vat_collected = sum(month['vat_collected'] for month in monthly_summary)
    vat_paid = sum(month['vat_paid'] for month in monthly_summary)
    vat_balance = vat_collected - vat_paid
    
    # Get recent invoices (5 most recent)
    recent_invoices_query = Invoice.query.order_by(Invoice.date.desc()).limit(5)
    
    # Convert to dictionary format for the template
    recent_invoices = []
    for invoice in recent_invoices_query:
        invoice_dict = invoice.to_dict()
        customer = Customer.query.get(invoice.customer_id)
        invoice_dict['customer_name'] = customer.name if customer else 'Unknown Customer'
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
    monthly_data = get_monthly_summary(year)
    
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
    quarterly_data = get_quarterly_summary(year)
    
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
def invoices_list():
    # Get filter parameters
    customer_id = request.args.get('customer_id')
    invoice_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Build query with filters
    query = Invoice.query
    
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
    
    # Get all customers for filter dropdown
    customers_query = Customer.query.all()
    customers_data = [customer.to_dict() for customer in customers_query]
    
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
                file_path=file_path
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
    customers_query = Customer.query.all()
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
        customers_query = Customer.query.all()
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
def customers_list():
    # Get all customers from the database
    customers_query = Customer.query.all()
    
    # Convert to dictionary format for the template and add counts/totals
    customers_data = []
    for customer in customers_query:
        customer_dict = customer.to_dict()
        
        # Query invoices for this customer
        customer_invoices_query = Invoice.query.filter_by(customer_id=customer.id).all()
        
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
                customer_type=customer_type or 'business'
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
        customer_invoices_query = Invoice.query.filter_by(customer_id=customer.id).all()
        
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
def monthly_report(year):
    monthly_data = get_monthly_summary(year)
    
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
def quarterly_report(year):
    quarterly_data = get_quarterly_summary(year)
    
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
def customer_report():
    customer_data = get_customer_summary()
    
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
def vat_report_form():
    return render_template(
        'vat_report.html',
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        current_year=datetime.now().year,
        current_quarter=date_to_quarter(datetime.now()),
        now=datetime.now()
    )

@app.route('/vat-report/generate', methods=['POST'])
def generate_vat_report():
    # Get form data
    year = int(request.form.get('year'))
    report_type = request.form.get('report_type')  # 'quarterly' or 'monthly'
    
    if report_type == 'quarterly':
        quarter = int(request.form.get('quarter'))
        month = None
        report = calculate_vat_report(year=year, quarter=quarter)
        period_name = f"Q{quarter} {year}"
    else:  # monthly
        month = int(request.form.get('month'))
        quarter = None
        report = calculate_vat_report(year=year, month=month)
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
    
    # Regular HTML response
    return render_template(
        'vat_report.html',
        report=report,
        period_name=period_name,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency,
        now=datetime.now()
    )

# Bulk upload routes
@app.route('/bulk-upload', methods=['GET', 'POST'])
def bulk_upload():
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
    return render_template('base.html', error='Page not found', now=datetime.now()), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html', error='An internal error occurred', now=datetime.now()), 500

# Admin routes
@app.route('/admin')
@login_required
def admin():
    # Only admins can access admin panel
    if not current_user.is_admin:
        flash('U heeft geen toegang tot deze pagina', 'danger')
        return redirect(url_for('dashboard'))
    
    from models import get_users
    users = get_users()
    customer_count = Customer.query.count()
    invoice_count = Invoice.query.count()
    
    return render_template('admin.html', 
                           users=users, 
                           customer_count=customer_count, 
                           invoice_count=invoice_count, 
                           now=datetime.now())

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
    
    # Create user
    try:
        from models import create_user
        create_user(username, email, password, is_admin, is_super_admin)
        flash(f'Gebruiker {username} is aangemaakt', 'success')
    except Exception as e:
        logging.error(f"Error creating user: {str(e)}")
        flash('Er is een fout opgetreden bij het aanmaken van de gebruiker', 'danger')
    
    return redirect(url_for('admin'))

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
                return render_template('edit_user.html', user=user, now=datetime.now())
        
        # Update user
        try:
            update_user(user_id, email, new_password if new_password else None, is_admin, is_super_admin)
            flash(f'Gebruiker {user.username} is bijgewerkt', 'success')
            return redirect(url_for('admin'))
        except Exception as e:
            logging.error(f"Error updating user: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de gebruiker', 'danger')
    
    return render_template('edit_user.html', user=user, now=datetime.now())

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
