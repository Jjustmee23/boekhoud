from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from . import upload_blueprint
from models import (
    get_customers
)
from utils import (
    format_currency, allowed_file, save_uploaded_file
)
from file_processor import FileProcessor, InvoiceDocument

# Bulk upload routes
@upload_blueprint.route('/bulk', methods=['GET', 'POST'])
def bulk_upload():
    if request.method == 'POST':
        # Check if any files were uploaded
        if 'files' not in request.files:
            flash('No files selected', 'warning')
            return redirect(request.url)
        
        files = request.files.getlist('files')
        
        # Check if files is empty
        if not files or not files[0].filename:
            flash('No files selected', 'warning')
            return redirect(request.url)
        
        # Get customer ID if specified
        customer_id = request.form.get('customer_id')
        
        # Process files
        processor = FileProcessor()
        results = processor.process_files(files, customer_id)
        
        # Store results in session
        session['bulk_upload_results'] = results
        
        # Create summary
        summary = {
            'total_files': len(files),
            'recognized_invoices': len(results.get('recognized_invoices', [])),
            'recognized_statements': len(results.get('recognized_statements', [])),
            'unrecognized_files': len(results.get('unrecognized_files', [])),
            'duplicate_invoices': len(results.get('duplicate_invoices', [])),
            'customers_created': len(results.get('customers_created', [])),
            'total_amount': sum(invoice.get('amount_incl_vat', 0) for invoice in results.get('recognized_invoices', []))
        }
        
        # Store summary in session
        session['bulk_upload_summary'] = summary
        
        # Redirect to results page
        return redirect(url_for('upload.bulk_upload_results'))
    
    # GET request - show upload form
    customers_data = get_customers()
    return render_template(
        'bulk_upload.html',
        customers=customers_data,
        now=datetime.now()
    )

@upload_blueprint.route('/extract-invoice', methods=['POST'])
def extract_invoice_data():
    """API endpoint for extracting data from an uploaded invoice file"""
    # Check if file was uploaded
    if 'invoice_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['invoice_file']
    
    # Check if file is empty
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if file extension is allowed
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Save the file
    file_path = save_uploaded_file(file)
    if not file_path:
        return jsonify({'error': 'Failed to save file'}), 500
    
    # Extract data
    processor = FileProcessor()
    file_info = processor._extract_info_from_filename(file.filename)
    
    # Only extract if it's an invoice
    if file_info.get('document_type') and 'invoice' in file_info.get('document_type').lower():
        doc = InvoiceDocument(file_path, file_info)
        invoice_data = doc.get_invoice_data()
        customer_data = doc.get_customer_data()
        
        # Try to find customer by name or VAT number
        customer_id = None
        customer_name = None
        if customer_data.get('name'):
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
                customer_name = found_customer.get('name')
        
        # Return extracted data
        return jsonify({
            'success': True,
            'file_path': file_path,
            'invoice_data': invoice_data,
            'customer_data': customer_data,
            'customer_id': customer_id,
            'customer_name': customer_name
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Not an invoice document'
        }), 400

@upload_blueprint.route('/bulk/results')
def bulk_upload_results():
    # Get results from session
    results = session.get('bulk_upload_results', {})
    summary = session.get('bulk_upload_summary', {})
    
    # Clear session
    session.pop('bulk_upload_results', None)
    session.pop('bulk_upload_summary', None)
    
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