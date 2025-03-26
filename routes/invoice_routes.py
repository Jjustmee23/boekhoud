import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, send_file
from . import invoice_blueprint
from models import (
    add_invoice, update_invoice, delete_invoice, get_invoice, get_invoices,
    get_customer, get_customers
)
from utils import (
    format_currency, generate_pdf_invoice, get_vat_rates,
    save_uploaded_file, allowed_file
)
from file_processor import FileProcessor, InvoiceDocument

# Invoice management routes
@invoice_blueprint.route('/')
def invoices_list():
    # Get filter parameters
    customer_id = request.args.get('customer_id')
    invoice_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Get invoices with filters
    invoices_data = get_invoices(
        customer_id=customer_id,
        invoice_type=invoice_type,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get all customers for filter dropdown
    customers_data = get_customers()
    
    # Enrich invoices with customer data
    for invoice in invoices_data:
        customer = get_customer(invoice['customer_id'])
        invoice['customer_name'] = customer['name'] if customer else 'Unknown Customer'
    
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

@invoice_blueprint.route('/new', methods=['GET', 'POST'])
def new_invoice():
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        date = request.form.get('date')
        invoice_type = request.form.get('type')
        amount_incl_vat = request.form.get('amount_incl_vat')
        vat_rate = request.form.get('vat_rate')
        invoice_number = request.form.get('invoice_number')  # Optional
        
        # Handle file upload first - so we can extract info if needed
        file_path = None
        extracted_data = {}
        
        if 'invoice_file' in request.files:
            file = request.files['invoice_file']
            if file and file.filename and allowed_file(file.filename):
                # Save the file first
                file_path = save_uploaded_file(file)
                if file_path:
                    # Try to extract data from the file
                    processor = FileProcessor()
                    file_info = processor._extract_info_from_filename(file.filename)
                    
                    # Create document based on file type
                    if file_info.get('document_type') and 'invoice' in file_info.get('document_type').lower():
                        doc = InvoiceDocument(file_path, file_info)
                        extracted_data = doc.get_invoice_data()
                        
                        # Also get customer data if available
                        customer_data = doc.get_customer_data()
                        if customer_data.get('name') and not customer_id:
                            # Try to find customer by name or VAT number
                            found_customer = None
                            customers_list = get_customers()
                            
                            if customer_data.get('vat_number'):
                                # Try to find by VAT number first
                                for c in customers_list:
                                    if c.get('vat_number') == customer_data.get('vat_number'):
                                        found_customer = c
                                        break
                            
                            if not found_customer:
                                # Try to find by name
                                for c in customers_list:
                                    if c.get('name') and customer_data.get('name') and c.get('name').lower() == customer_data.get('name').lower():
                                        found_customer = c
                                        break
                            
                            if found_customer:
                                customer_id = found_customer.get('id')
                                extracted_data['customer_id'] = customer_id
                                flash(f'Klant "{found_customer.get("name")}" automatisch gevonden', 'info')
                else:
                    flash('Failed to upload file', 'warning')
            elif file and file.filename:
                flash('Only PDF, PNG, JPG and JPEG files are allowed', 'warning')
        
        # Use extracted data if form fields are empty
        if not date and extracted_data.get('date'):
            date = extracted_data.get('date')
        
        if not invoice_type and extracted_data.get('invoice_type'):
            invoice_type = extracted_data.get('invoice_type')
        
        if not invoice_number and extracted_data.get('invoice_number'):
            invoice_number = extracted_data.get('invoice_number')
        
        if not amount_incl_vat and extracted_data.get('amount_incl_vat'):
            amount_incl_vat = extracted_data.get('amount_incl_vat')
        
        if not vat_rate and extracted_data.get('vat_rate'):
            vat_rate = extracted_data.get('vat_rate')
        
        if not customer_id and extracted_data.get('customer_id'):
            customer_id = extracted_data.get('customer_id')
            
        # Check if we have extracted data but missing some required fields
        if extracted_data and not all([customer_id, date, invoice_type, amount_incl_vat, vat_rate]):
            flash('Factuurgegevens gedeeltelijk geëxtraheerd uit het bestand. Vul de ontbrekende velden in.', 'info')
            customers_data = get_customers()
            
            # Prepare invoice data with extracted information
            invoice_data = {
                'customer_id': customer_id or '',
                'date': date or datetime.now().strftime('%Y-%m-%d'),
                'type': invoice_type or 'expense',
                'invoice_number': invoice_number or '',
                'amount_incl_vat': amount_incl_vat or '',
                'vat_rate': vat_rate or '21.0',
                'file_path': file_path
            }
            
            return render_template(
                'invoice_form.html',
                customers=customers_data,
                vat_rates=get_vat_rates(),
                invoice=invoice_data,
                now=datetime.now()
            )
            
        # Validate data
        if not all([customer_id, date, invoice_type, amount_incl_vat, vat_rate]):
            flash('Alle verplichte velden moeten worden ingevuld', 'danger')
            customers_data = get_customers()
            return render_template(
                'invoice_form.html',
                customers=customers_data,
                vat_rates=get_vat_rates(),
                invoice={'date': datetime.now().strftime('%Y-%m-%d'), 'type': 'income'},
                now=datetime.now()
            )
        
        # Add invoice
        try:
            invoice, message, duplicate_id = add_invoice(
                customer_id=customer_id,
                date=date,
                invoice_type=invoice_type,
                amount_incl_vat=float(amount_incl_vat) if amount_incl_vat else 0,
                vat_rate=float(vat_rate) if vat_rate else 21,
                invoice_number=invoice_number if invoice_number else None,
                file_path=file_path
            )
            
            if invoice:
                flash(message, 'success')
                return redirect(url_for('invoice.invoices_list'))
            else:
                if duplicate_id:
                    flash(f'{message}. <a href="{url_for("invoice.view_invoice", invoice_id=duplicate_id)}">View duplicate</a>', 'warning')
                else:
                    flash(message, 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        customers_data = get_customers()
        return render_template(
            'invoice_form.html',
            customers=customers_data,
            vat_rates=get_vat_rates(),
            invoice=request.form,
            now=datetime.now()
        )
    
    # GET request - show the form
    customers_data = get_customers()
    return render_template(
        'invoice_form.html',
        customers=customers_data,
        vat_rates=get_vat_rates(),
        invoice={'date': datetime.now().strftime('%Y-%m-%d'), 'type': 'income'},
        now=datetime.now()
    )

@invoice_blueprint.route('/<invoice_id>')
def view_invoice(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoice.invoices_list'))
    
    customer = get_customer(invoice['customer_id'])
    
    return render_template(
        'invoice_detail.html',
        invoice=invoice,
        customer=customer,
        format_currency=format_currency,
        now=datetime.now()
    )

@invoice_blueprint.route('/<invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoice.invoices_list'))
    
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        date = request.form.get('date')
        invoice_type = request.form.get('type')
        amount_incl_vat = request.form.get('amount_incl_vat')
        vat_rate = request.form.get('vat_rate')
        invoice_number = request.form.get('invoice_number')  # Optional
        
        # Validate data
        if not all([customer_id, date, invoice_type, amount_incl_vat, vat_rate]):
            flash('All fields are required', 'danger')
            customers_data = get_customers()
            return render_template(
                'invoice_form.html',
                invoice=invoice,
                customers=customers_data,
                vat_rates=get_vat_rates(),
                edit_mode=True,
                now=datetime.now()
            )
        
        # Handle file upload
        file_path = invoice.get('file_path')  # Keep existing file path by default
        if 'invoice_file' in request.files:
            file = request.files['invoice_file']
            if file and file.filename and allowed_file(file.filename):
                # Replace the old file with the new one
                new_file_path = save_uploaded_file(file)
                if new_file_path:
                    file_path = new_file_path
                else:
                    flash('Failed to upload file', 'warning')
            elif file and file.filename:
                flash('Only PDF, PNG, JPG and JPEG files are allowed', 'warning')
        
        # Update invoice
        try:
            updated_invoice, message, duplicate_id = update_invoice(
                invoice_id=invoice_id,
                customer_id=customer_id,
                date=date,
                invoice_type=invoice_type,
                amount_incl_vat=float(amount_incl_vat) if amount_incl_vat else 0,
                vat_rate=float(vat_rate) if vat_rate else 21,
                invoice_number=invoice_number if invoice_number else None,
                file_path=file_path
            )
            
            if updated_invoice:
                flash(message, 'success')
                return redirect(url_for('invoice.view_invoice', invoice_id=invoice_id))
            else:
                if duplicate_id:
                    flash(f'{message}. <a href="{url_for("invoice.view_invoice", invoice_id=duplicate_id)}">View duplicate</a>', 'warning')
                else:
                    flash(message, 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        customers_data = get_customers()
        return render_template(
            'invoice_form.html',
            invoice=request.form,
            customers=customers_data,
            vat_rates=get_vat_rates(),
            edit_mode=True,
            now=datetime.now()
        )
    
    # GET request - show the form
    customers_data = get_customers()
    return render_template(
        'invoice_form.html',
        invoice=invoice,
        customers=customers_data,
        vat_rates=get_vat_rates(),
        edit_mode=True,
        now=datetime.now()
    )

@invoice_blueprint.route('/<invoice_id>/delete', methods=['POST'])
def delete_invoice_route(invoice_id):
    success, message = delete_invoice(invoice_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('invoice.invoices_list'))

@invoice_blueprint.route('/<invoice_id>/pdf')
def generate_invoice_pdf(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoice.invoices_list'))
    
    customer = get_customer(invoice['customer_id'])
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('invoice.invoices_list'))
    
    # Generate PDF
    pdf_path = generate_pdf_invoice(invoice, customer)
    
    # Filename for download
    filename = f"Invoice-{invoice['invoice_number']}.pdf"
    
    # Send file and then delete it after sending
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

@invoice_blueprint.route('/<invoice_id>/attachment')
def view_invoice_attachment(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoice.invoices_list'))
    
    # Check if invoice has a file attached
    if not invoice.get('file_path'):
        flash('This invoice has no file attached', 'warning')
        return redirect(url_for('invoice.view_invoice', invoice_id=invoice_id))
    
    # Get the file extension to determine mime type
    file_ext = os.path.splitext(invoice['file_path'])[1].lower()
    
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
    full_file_path = os.path.join('static', invoice['file_path'])
    
    # Check if file exists
    if not os.path.exists(full_file_path):
        flash('The attached file could not be found', 'danger')
        return redirect(url_for('invoice.view_invoice', invoice_id=invoice_id))
    
    # Send the file
    try:
        return send_file(
            full_file_path,
            mimetype=mime_type,
            as_attachment=False,
            download_name=os.path.basename(invoice['file_path'])
        )
    except Exception as e:
        flash(f'Error displaying file: {str(e)}', 'danger')
        return redirect(url_for('invoice.view_invoice', invoice_id=invoice_id))