"""
Routes voor facturen en klantengegevens
"""
import os
import logging
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_required, current_user
from app import app, db
from models import Customer, Invoice, get_next_invoice_number, check_duplicate_invoice, add_invoice
from utils import format_currency, format_decimal, generate_pdf_invoice, export_to_excel, export_to_csv, save_uploaded_file, allowed_file

# Klanten routes
@app.route('/customers')
@login_required
def customers_list():
    """Toon lijst van klanten"""
    # Bepaal werkruimte ID (alleen facturen van huidige werkruimte)
    workspace_id = current_user.workspace_id
    
    customers = Customer.query.filter_by(workspace_id=workspace_id).order_by(Customer.name).all()
    return render_template('customers.html', customers=customers, now=datetime.now())

@app.route('/customers/create', methods=['GET', 'POST'])
@login_required
def create_customer():
    """Maak een nieuwe klant aan"""
    if request.method == 'POST':
        # Get form data
        company_name = request.form.get('company_name', '')
        contact_name = request.form.get('contact_name', '')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        vat_number = request.form.get('vat_number', '')
        street = request.form.get('street', '')
        house_number = request.form.get('house_number', '')
        postal_code = request.form.get('postal_code', '')
        city = request.form.get('city', '')
        country = request.form.get('country', '')
        
        # Validate required fields
        if not company_name:
            flash('Bedrijfsnaam is verplicht', 'danger')
            return render_template('customer_form.html', customer=None, now=datetime.now())
        
        # Create customer
        customer = Customer(
            name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            vat_number=vat_number,
            street=street,
            house_number=house_number,
            postal_code=postal_code,
            city=city,
            country=country,
            workspace_id=current_user.workspace_id
        )
        
        # Save to database
        try:
            db.session.add(customer)
            db.session.commit()
            flash('Klant succesvol aangemaakt', 'success')
            return redirect(url_for('customers_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating customer: {str(e)}")
            flash('Er is een fout opgetreden bij het aanmaken van de klant', 'danger')
    
    # GET request
    return render_template('customer_form.html', customer=None, now=datetime.now())

@app.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    """Bewerk een bestaande klant"""
    # Get customer
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if customer belongs to user's workspace
    if customer.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze klant', 'danger')
        return redirect(url_for('customers_list'))
    
    if request.method == 'POST':
        # Get form data
        customer.name = request.form.get('company_name', '')
        customer.contact_name = request.form.get('contact_name', '')
        customer.email = request.form.get('email', '')
        customer.phone = request.form.get('phone', '')
        customer.vat_number = request.form.get('vat_number', '')
        customer.street = request.form.get('street', '')
        customer.house_number = request.form.get('house_number', '')
        customer.postal_code = request.form.get('postal_code', '')
        customer.city = request.form.get('city', '')
        customer.country = request.form.get('country', '')
        
        # Validate required fields
        if not customer.name:
            flash('Bedrijfsnaam is verplicht', 'danger')
            return render_template('customer_form.html', customer=customer, now=datetime.now())
        
        # Save to database
        try:
            db.session.commit()
            flash('Klant succesvol bijgewerkt', 'success')
            return redirect(url_for('customers_list'))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating customer: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de klant', 'danger')
    
    # GET request
    return render_template('customer_form.html', customer=customer, now=datetime.now())

@app.route('/customers/<int:customer_id>/delete', methods=['POST'])
@login_required
def delete_customer(customer_id):
    """Verwijder een klant"""
    # Get customer
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if customer belongs to user's workspace
    if customer.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze klant', 'danger')
        return redirect(url_for('customers_list'))
    
    # Check if customer has invoices
    invoices = Invoice.query.filter_by(customer_id=customer_id).count()
    if invoices > 0:
        flash('Deze klant heeft nog facturen en kan niet verwijderd worden', 'danger')
        return redirect(url_for('customers_list'))
    
    # Delete customer
    try:
        db.session.delete(customer)
        db.session.commit()
        flash('Klant succesvol verwijderd', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting customer: {str(e)}")
        flash('Er is een fout opgetreden bij het verwijderen van de klant', 'danger')
    
    return redirect(url_for('customers_list'))

@app.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    """Toon klantdetails en bijbehorende facturen"""
    # Get customer
    customer = Customer.query.get_or_404(customer_id)
    
    # Check if customer belongs to user's workspace
    if customer.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze klant', 'danger')
        return redirect(url_for('customers_list'))
    
    # Get invoices for this customer
    invoices = Invoice.query.filter_by(customer_id=customer_id).order_by(Invoice.date.desc()).all()
    
    return render_template('customer_detail.html', customer=customer, invoices=invoices, 
                           format_currency=format_currency, now=datetime.now())

# Facturen routes
@app.route('/invoices')
@login_required
def invoices_list():
    """Toon lijst van facturen"""
    # Bepaal werkruimte ID (alleen facturen van huidige werkruimte)
    workspace_id = current_user.workspace_id
    
    # Haal alle facturen op
    invoices_query = Invoice.query.filter_by(workspace_id=workspace_id)
    
    # Sorteer op datum (nieuwste eerst)
    invoices_query = invoices_query.order_by(Invoice.date.desc())
    
    # Voer de query uit
    invoices = invoices_query.all()
    
    # Haal klanten op voor de dropdown
    customers = Customer.query.filter_by(workspace_id=workspace_id).order_by(Customer.name).all()
    
    # Voeg klantnamen toe aan facturen voor weergave
    for invoice in invoices:
        customer = Customer.query.get(invoice.customer_id)
        invoice.customer_name = customer.name if customer else 'Onbekende Klant'
    
    return render_template('invoices.html', invoices=invoices, customers=customers, 
                           format_currency=format_currency, now=datetime.now())

@app.route('/invoices/create', methods=['GET', 'POST'])
@login_required
def create_invoice():
    """Maak een nieuwe factuur aan"""
    # Bepaal werkruimte ID
    workspace_id = current_user.workspace_id
    
    # Haal klanten op voor de dropdown
    customers = Customer.query.filter_by(workspace_id=workspace_id).order_by(Customer.name).all()
    
    if len(customers) == 0:
        flash('Je moet eerst een klant aanmaken voordat je een factuur kunt maken', 'warning')
        return redirect(url_for('create_customer'))
    
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        invoice_number = request.form.get('invoice_number')
        invoice_date = request.form.get('invoice_date')
        due_date = request.form.get('due_date')
        description = request.form.get('description')
        
        # Validate required fields
        if not all([customer_id, invoice_number, invoice_date]):
            flash('Klant, factuurnummer en factuurdatum zijn verplicht', 'danger')
            return render_template('invoice_form.html', customers=customers, 
                                   invoice=None, next_invoice_number=get_next_invoice_number(workspace_id),
                                   now=datetime.now())
        
        # Check if invoice number already exists
        if check_duplicate_invoice(invoice_number, workspace_id):
            flash('Dit factuurnummer bestaat al', 'danger')
            return render_template('invoice_form.html', customers=customers, 
                                   invoice=None, next_invoice_number=get_next_invoice_number(workspace_id),
                                   now=datetime.now())
        
        # Parse dates
        try:
            invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
        except ValueError:
            flash('Ongeldige datum', 'danger')
            return render_template('invoice_form.html', customers=customers, 
                                   invoice=None, next_invoice_number=get_next_invoice_number(workspace_id),
                                   now=datetime.now())
        
        # Create invoice items from form data
        items = []
        for i in range(10):  # Max 10 items
            quantity = request.form.get(f'quantity_{i}')
            description = request.form.get(f'item_description_{i}')
            unit_price = request.form.get(f'unit_price_{i}')
            vat_rate = request.form.get(f'vat_rate_{i}')
            
            if quantity and description and unit_price:
                try:
                    quantity = float(quantity.replace(',', '.'))
                    unit_price = float(unit_price.replace(',', '.'))
                    vat_rate = float(vat_rate.replace(',', '.')) if vat_rate else 0
                    
                    items.append({
                        'quantity': quantity,
                        'description': description,
                        'unit_price': unit_price,
                        'vat_rate': vat_rate
                    })
                except ValueError:
                    flash('Ongeldige getallen in factuurregel '+str(i+1), 'danger')
                    return render_template('invoice_form.html', customers=customers, 
                                        invoice=None, next_invoice_number=get_next_invoice_number(workspace_id),
                                        now=datetime.now())
        
        if not items:
            flash('Voeg minstens één factuurregel toe', 'danger')
            return render_template('invoice_form.html', customers=customers, 
                                   invoice=None, next_invoice_number=get_next_invoice_number(workspace_id),
                                   now=datetime.now())
        
        # Add invoice to database
        try:
            invoice = add_invoice(
                workspace_id=workspace_id,
                customer_id=customer_id,
                invoice_number=invoice_number,
                date=invoice_date,
                due_date=due_date,
                description=description,
                items=items
            )
            
            flash('Factuur succesvol aangemaakt', 'success')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating invoice: {str(e)}")
            flash('Er is een fout opgetreden bij het aanmaken van de factuur', 'danger')
    
    # GET request
    return render_template('invoice_form.html', 
                          customers=customers, 
                          invoice=None, 
                          next_invoice_number=get_next_invoice_number(workspace_id),
                          now=datetime.now())

@app.route('/invoices/<int:invoice_id>')
@login_required
def invoice_detail(invoice_id):
    """Toon factuurdetails"""
    # Get invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if invoice belongs to user's workspace
    if invoice.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze factuur', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Get customer
    customer = Customer.query.get(invoice.customer_id)
    
    return render_template('invoice_detail.html', 
                          invoice=invoice, 
                          customer=customer, 
                          format_currency=format_currency, 
                          format_decimal=format_decimal,
                          now=datetime.now())

@app.route('/invoices/<int:invoice_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_invoice(invoice_id):
    """Bewerk een bestaande factuur"""
    # Get invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if invoice belongs to user's workspace
    if invoice.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze factuur', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Get customers for dropdown
    customers = Customer.query.filter_by(workspace_id=current_user.workspace_id).order_by(Customer.name).all()
    
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        invoice_number = request.form.get('invoice_number')
        invoice_date = request.form.get('invoice_date')
        due_date = request.form.get('due_date')
        description = request.form.get('description')
        
        # Validate required fields
        if not all([customer_id, invoice_number, invoice_date]):
            flash('Klant, factuurnummer en factuurdatum zijn verplicht', 'danger')
            return render_template('invoice_form.html', customers=customers, invoice=invoice, now=datetime.now())
        
        # Check if invoice number already exists (if changed)
        if invoice_number != invoice.invoice_number and check_duplicate_invoice(invoice_number, current_user.workspace_id):
            flash('Dit factuurnummer bestaat al', 'danger')
            return render_template('invoice_form.html', customers=customers, invoice=invoice, now=datetime.now())
        
        # Parse dates
        try:
            invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
            due_date = datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None
        except ValueError:
            flash('Ongeldige datum', 'danger')
            return render_template('invoice_form.html', customers=customers, invoice=invoice, now=datetime.now())
        
        # Update invoice
        invoice.customer_id = customer_id
        invoice.invoice_number = invoice_number
        invoice.date = invoice_date
        invoice.due_date = due_date
        invoice.description = description
        
        # Create invoice items from form data
        invoice.items = []  # Clear existing items
        
        for i in range(10):  # Max 10 items
            quantity = request.form.get(f'quantity_{i}')
            description = request.form.get(f'item_description_{i}')
            unit_price = request.form.get(f'unit_price_{i}')
            vat_rate = request.form.get(f'vat_rate_{i}')
            
            if quantity and description and unit_price:
                try:
                    quantity = float(quantity.replace(',', '.'))
                    unit_price = float(unit_price.replace(',', '.'))
                    vat_rate = float(vat_rate.replace(',', '.')) if vat_rate else 0
                    
                    invoice.add_item(
                        quantity=quantity,
                        description=description,
                        unit_price=unit_price,
                        vat_rate=vat_rate
                    )
                except ValueError:
                    flash('Ongeldige getallen in factuurregel '+str(i+1), 'danger')
                    return render_template('invoice_form.html', customers=customers, invoice=invoice, now=datetime.now())
        
        if not invoice.items:
            flash('Voeg minstens één factuurregel toe', 'danger')
            return render_template('invoice_form.html', customers=customers, invoice=invoice, now=datetime.now())
        
        # Save to database
        try:
            db.session.commit()
            flash('Factuur succesvol bijgewerkt', 'success')
            return redirect(url_for('invoice_detail', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating invoice: {str(e)}")
            flash('Er is een fout opgetreden bij het bijwerken van de factuur', 'danger')
    
    # GET request
    # Format date for HTML input (YYYY-MM-DD)
    if invoice.date:
        invoice.date_html = invoice.date.strftime('%Y-%m-%d')
    if invoice.due_date:
        invoice.due_date_html = invoice.due_date.strftime('%Y-%m-%d')
    
    return render_template('invoice_form.html', 
                          customers=customers, 
                          invoice=invoice, 
                          now=datetime.now())

@app.route('/invoices/<int:invoice_id>/delete', methods=['POST'])
@login_required
def delete_invoice(invoice_id):
    """Verwijder een factuur"""
    # Get invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if invoice belongs to user's workspace
    if invoice.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze factuur', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Delete invoice
    try:
        db.session.delete(invoice)
        db.session.commit()
        flash('Factuur succesvol verwijderd', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting invoice: {str(e)}")
        flash('Er is een fout opgetreden bij het verwijderen van de factuur', 'danger')
    
    return redirect(url_for('invoices_list'))

@app.route('/invoices/<int:invoice_id>/generate-pdf')
@login_required
def generate_invoice_pdf(invoice_id):
    """Genereer een PDF van de factuur"""
    # Get invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if invoice belongs to user's workspace
    if invoice.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze factuur', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Get customer
    customer = Customer.query.get(invoice.customer_id)
    
    # Generate PDF
    try:
        pdf_file = generate_pdf_invoice(invoice, customer)
        return send_file(
            pdf_file,
            download_name=f'Factuur-{invoice.invoice_number}.pdf',
            as_attachment=True,
            mimetype='application/pdf'
        )
    except Exception as e:
        logging.error(f"Error generating PDF: {str(e)}")
        flash('Er is een fout opgetreden bij het genereren van de PDF', 'danger')
        return redirect(url_for('invoice_detail', invoice_id=invoice.id))

@app.route('/invoices/<int:invoice_id>/mark-paid', methods=['POST'])
@login_required
def mark_invoice_paid(invoice_id):
    """Markeer een factuur als betaald"""
    # Get invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if invoice belongs to user's workspace
    if invoice.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze factuur', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Update status
    invoice.is_paid = True
    invoice.payment_date = datetime.now().date()
    
    # Save to database
    try:
        db.session.commit()
        flash('Factuur gemarkeerd als betaald', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking invoice as paid: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de factuur', 'danger')
    
    return redirect(url_for('invoice_detail', invoice_id=invoice.id))

@app.route('/invoices/<int:invoice_id>/mark-unpaid', methods=['POST'])
@login_required
def mark_invoice_unpaid(invoice_id):
    """Markeer een factuur als onbetaald"""
    # Get invoice
    invoice = Invoice.query.get_or_404(invoice_id)
    
    # Check if invoice belongs to user's workspace
    if invoice.workspace_id != current_user.workspace_id:
        flash('Je hebt geen toegang tot deze factuur', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Update status
    invoice.is_paid = False
    invoice.payment_date = None
    
    # Save to database
    try:
        db.session.commit()
        flash('Factuur gemarkeerd als onbetaald', 'success')
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error marking invoice as unpaid: {str(e)}")
        flash('Er is een fout opgetreden bij het bijwerken van de factuur', 'danger')
    
    return redirect(url_for('invoice_detail', invoice_id=invoice.id))

# Bulkupload routes
@app.route('/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload():
    """Bulkupload van facturen"""
    # Bepaal werkruimte ID
    workspace_id = current_user.workspace_id
    
    if request.method == 'POST':
        # Check if files were submitted
        if 'files[]' not in request.files:
            flash('Geen bestanden gevonden', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        
        # Check if any files were selected
        if not files or files[0].filename == '':
            flash('Geen bestanden geselecteerd', 'danger')
            return redirect(request.url)
        
        # Process files
        saved_files = []
        for file in files:
            if file and allowed_file(file.filename):
                # Generate unique filename
                ext = os.path.splitext(file.filename)[1]
                unique_id = str(uuid.uuid4())
                filename = f"invoice_{unique_id}_{file.filename}"
                
                # Save file
                filepath = save_uploaded_file(file, filename)
                if filepath:
                    saved_files.append({
                        'original_name': file.filename,
                        'saved_name': filename,
                        'path': filepath
                    })
                else:
                    flash(f'Fout bij opslaan bestand: {file.filename}', 'danger')
            else:
                flash(f'Ongeldig bestandstype: {file.filename}', 'danger')
        
        # If no files were saved, redirect back
        if not saved_files:
            flash('Geen geldige bestanden geüpload', 'danger')
            return redirect(request.url)
        
        # Store saved files in session for next step
        session['uploaded_files'] = saved_files
        
        return redirect(url_for('bulk_upload_review'))
    
    # GET request
    return render_template('bulk_upload.html', now=datetime.now())

@app.route('/bulk-upload/review', methods=['GET', 'POST'])
@login_required
def bulk_upload_review():
    """Review en verwerking van geüploade bestanden"""
    # Check if any files were uploaded
    uploaded_files = session.get('uploaded_files', [])
    if not uploaded_files:
        flash('Geen bestanden gevonden om te verwerken', 'danger')
        return redirect(url_for('bulk_upload'))
    
    if request.method == 'POST':
        # Process files with AI/OCR
        from file_processor import FileProcessor
        
        # Initialize file processor
        processor = FileProcessor()
        
        # Get list of customers for matching
        workspace_id = current_user.workspace_id
        customers = Customer.query.filter_by(workspace_id=workspace_id).all()
        
        # Process each file
        results = []
        for file_info in uploaded_files:
            # Process file
            file_path = file_info['path']
            result = processor.process_file(file_path, customers)
            result['original_name'] = file_info['original_name']
            result['saved_name'] = file_info['saved_name']
            result['file_path'] = file_path
            
            results.append(result)
        
        # Store results in session for next step
        session['processing_results'] = results
        
        # Clear uploaded files from session
        session.pop('uploaded_files', None)
        
        return redirect(url_for('bulk_upload_results'))
    
    # GET request - show files that will be processed
    return render_template('bulk_upload_review.html', files=uploaded_files, now=datetime.now())

@app.route('/bulk-upload/results', methods=['GET', 'POST'])
@login_required
def bulk_upload_results():
    """Toon resultaten van bulkupload en verwerk facturen"""
    # Check if any results exist
    results = session.get('processing_results', [])
    if not results:
        flash('Geen verwerkingsresultaten gevonden', 'danger')
        return redirect(url_for('bulk_upload'))
    
    # Get customers for dropdown (for manual selection)
    customers = Customer.query.filter_by(workspace_id=current_user.workspace_id).order_by(Customer.name).all()
    
    if request.method == 'POST':
        # Import confirmed invoices
        successful_imports = 0
        failed_imports = 0
        
        for i, result in enumerate(results):
            try:
                # Get form data for this invoice
                import_this = request.form.get(f'import_{i}') == 'on'
                
                if import_this:
                    # Get corrected data from form
                    customer_id = request.form.get(f'customer_id_{i}')
                    invoice_number = request.form.get(f'invoice_number_{i}')
                    invoice_date = request.form.get(f'invoice_date_{i}')
                    amount = request.form.get(f'amount_{i}')
                    
                    # Validate required fields
                    if not all([customer_id, invoice_number, invoice_date, amount]):
                        flash(f'Ontbrekende vereiste velden voor bestand: {result["original_name"]}', 'danger')
                        failed_imports += 1
                        continue
                    
                    # Parse date
                    try:
                        invoice_date = datetime.strptime(invoice_date, '%Y-%m-%d').date()
                    except ValueError:
                        flash(f'Ongeldige datum voor bestand: {result["original_name"]}', 'danger')
                        failed_imports += 1
                        continue
                    
                    # Parse amount
                    try:
                        amount = float(amount.replace(',', '.'))
                    except ValueError:
                        flash(f'Ongeldig bedrag voor bestand: {result["original_name"]}', 'danger')
                        failed_imports += 1
                        continue
                    
                    # Check if invoice number already exists
                    if check_duplicate_invoice(invoice_number, current_user.workspace_id):
                        flash(f'Factuurnummer bestaat al: {invoice_number}', 'danger')
                        failed_imports += 1
                        continue
                    
                    # Create invoice with single item
                    invoice = add_invoice(
                        workspace_id=current_user.workspace_id,
                        customer_id=customer_id,
                        invoice_number=invoice_number,
                        date=invoice_date,
                        description=f"Geïmporteerd bestand: {result['original_name']}",
                        items=[{
                            'quantity': 1,
                            'description': f"Geïmporteerd bestand: {result['original_name']}",
                            'unit_price': amount,
                            'vat_rate': 0  # Default to 0% VAT, user can edit later
                        }]
                    )
                    
                    # Update invoice with file attachment
                    invoice.attachment_path = result['file_path']
                    db.session.commit()
                    
                    successful_imports += 1
            except Exception as e:
                logging.error(f"Error importing invoice: {str(e)}")
                failed_imports += 1
        
        # Report success/failure
        if successful_imports > 0:
            flash(f'{successful_imports} facturen succesvol geïmporteerd', 'success')
        if failed_imports > 0:
            flash(f'{failed_imports} facturen konden niet worden geïmporteerd', 'danger')
        
        # Clear results from session
        session.pop('processing_results', None)
        
        # Redirect to invoices list
        return redirect(url_for('invoices_list'))
    
    # GET request - show processing results and let user confirm/correct
    return render_template('bulk_upload_results.html', 
                          results=results, 
                          customers=customers,
                          now=datetime.now())