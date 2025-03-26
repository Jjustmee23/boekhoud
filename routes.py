import os
import logging
import uuid
from datetime import datetime, date
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify, session
from app import app, db
from models import (
    Customer, Invoice, get_next_invoice_number,
    calculate_vat_report, get_monthly_summary, get_quarterly_summary, get_customer_summary
)
from utils import (
    format_currency, format_decimal, generate_pdf_invoice, export_to_excel, export_to_csv,
    get_vat_rates, date_to_quarter, get_quarters, get_months, get_years,
    save_uploaded_file, allowed_file
)
from file_processor import FileProcessor

# Dashboard routes
@app.route('/')
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
        
        # Query customer invoices
        customer_invoices_query = Invoice.query.filter_by(customer_id=customer.id).all()
        
        # Convert to dictionary format for the template
        customer_data = customer.to_dict()
        customer_invoices = [invoice.to_dict() for invoice in customer_invoices_query]
        
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
            invoices=customer_invoices,
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
            flash('No files selected', 'danger')
            customers_data = get_customers()
            return render_template(
                'bulk_upload.html',
                customers=customers_data,
                now=datetime.now()
            )
        
        files = request.files.getlist('files[]')
        if not files or all(not f.filename for f in files):
            flash('No files selected', 'danger')
            customers_data = get_customers()
            return render_template(
                'bulk_upload.html',
                customers=customers_data,
                now=datetime.now()
            )
        
        # Process the uploaded files
        processor = FileProcessor()
        results = processor.process_files(files, customer_id)
        
        # Store results in session for display
        session['bulk_upload_results'] = results
        
        # Create summary counts
        summary = {
            'total_files': len(results['saved_files']),
            'processed_invoices': len(results['recognized_invoices']),
            'new_customers': len(results['new_customers']),
            'manual_review': len(results['manual_review']),
            'errors': len(results['errors'])
        }
        
        # Flash appropriate message
        if summary['total_files'] > 0:
            flash(f"Processed {summary['total_files']} files: "
                  f"{summary['processed_invoices']} invoices created, "
                  f"{summary['new_customers']} new customers, "
                  f"{summary['manual_review']} need review", 'success')
        else:
            flash('No files were processed', 'warning')
        
        # Return to results page
        return redirect(url_for('bulk_upload_results'))
    
    # GET request - show the form
    customers_data = get_customers()
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
    customers_dict = {c['id']: c for c in get_customers()}
    
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
