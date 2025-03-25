from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, session
import os
import logging
import json
from werkzeug.utils import secure_filename

from ai_document_processor import AIDocumentProcessor
from models import add_customer, add_invoice
from utils import allowed_file, save_uploaded_file

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
ai_bp = Blueprint('ai', __name__)

# Initialize the AI processor
ai_processor = AIDocumentProcessor()

from datetime import datetime

@ai_bp.route('/ai/analyze', methods=['GET', 'POST'])
def ai_analyze_document():
    """Render the AI document analysis page and handle uploads"""
    if request.method == 'POST':
        # Check if files were uploaded
        if 'files[]' not in request.files:
            flash('Geen bestanden geselecteerd', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        
        # If no selected files
        if not files or files[0].filename == '':
            flash('Geen bestanden geselecteerd', 'danger')
            return redirect(request.url)
        
        results = []
        for file in files:
            if file and allowed_file(file.filename, {'pdf', 'png', 'jpg', 'jpeg'}):
                # Save the file
                file_path = save_uploaded_file(file)
                
                if not file_path:
                    flash(f'Fout bij opslaan van bestand {file.filename}', 'danger')
                    continue
                
                # Analyze the document
                try:
                    analysis_result = ai_processor.analyze_document(file_path)
                    
                    # Store the result in the session for processing
                    results.append({
                        'filename': file.filename,
                        'file_path': file_path,
                        'analysis': analysis_result
                    })
                    
                    # If high confidence and it's an invoice, create automatically
                    if (analysis_result.get('document_type') == 'invoice' and 
                            analysis_result.get('confidence', 0) > 0.85 and
                            not analysis_result.get('error')):
                        process_result = process_invoice_result(analysis_result)
                        if process_result['success']:
                            flash(f'Factuur {analysis_result.get("invoice_number")} werd automatisch aangemaakt', 'success')
                        
                except Exception as e:
                    logger.error(f"Error analyzing {file.filename}: {str(e)}")
                    results.append({
                        'filename': file.filename,
                        'file_path': file_path,
                        'error': str(e)
                    })
            else:
                flash(f'Ongeldig bestandstype voor {file.filename}', 'warning')
        
        # Store results in session
        session['ai_analysis_results'] = results
        
        return redirect(url_for('ai.ai_analysis_results'))
    
    return render_template('ai_analyze.html', now=datetime.now())

@ai_bp.route('/ai/results')
def ai_analysis_results():
    """Display the results of AI analysis"""
    results = session.get('ai_analysis_results', [])
    return render_template('ai_results.html', results=results)

@ai_bp.route('/ai/process/<path:file_path>', methods=['POST'])
def ai_process_document(file_path):
    """Process a document after analysis"""
    results = session.get('ai_analysis_results', [])
    
    # Find the document analysis in results
    document_result = None
    for result in results:
        if result.get('file_path') == file_path:
            document_result = result.get('analysis')
            break
    
    if not document_result:
        flash('Document niet gevonden', 'danger')
        return redirect(url_for('ai.ai_analysis_results'))
    
    # Process based on document type
    if document_result.get('document_type') == 'invoice':
        process_result = process_invoice_result(document_result)
        if process_result['success']:
            flash(f'Factuur {document_result.get("invoice_number")} verwerkt', 'success')
        else:
            flash(f'Fout bij verwerken factuur: {process_result.get("error")}', 'danger')
    else:
        flash('Onbekend documenttype', 'warning')
    
    return redirect(url_for('ai.ai_analysis_results'))

def process_invoice_result(invoice_data):
    """Process invoice analysis result to create customer and invoice"""
    try:
        # Extract customer data from seller or buyer based on invoice type
        invoice_type = invoice_data.get('invoice_type', 'expense')
        
        if invoice_type == 'expense':
            # For expenses, the seller is the one we need to record
            customer_data = invoice_data.get('seller', {})
        else:
            # For income invoices, the buyer is our customer
            customer_data = invoice_data.get('buyer', {})
        
        # Create or find customer
        customer = add_customer(
            name=customer_data.get('name', 'Auto-detected Customer'),
            address=customer_data.get('address', ''),
            vat_number=customer_data.get('vat_number', ''),
            email=customer_data.get('email', '')
        )
        
        if not customer:
            return {'success': False, 'error': 'Fout bij aanmaken klant'}
        
        # Compute VAT amounts if needed
        amount_incl_vat = invoice_data.get('amount_incl_vat')
        amount_excl_vat = invoice_data.get('amount_excl_vat')
        vat_amount = invoice_data.get('vat_amount')
        vat_rate = invoice_data.get('vat_rate', 21)
        
        # If we only have incl VAT amount, calculate the rest
        if amount_incl_vat and not amount_excl_vat and not vat_amount:
            amount_excl_vat = amount_incl_vat / (1 + vat_rate/100)
            vat_amount = amount_incl_vat - amount_excl_vat
        
        # If we only have excl VAT amount, calculate the rest
        elif amount_excl_vat and not amount_incl_vat and not vat_amount:
            vat_amount = amount_excl_vat * (vat_rate/100)
            amount_incl_vat = amount_excl_vat + vat_amount
        
        # Create invoice
        invoice, message, _ = add_invoice(
            customer_id=customer['id'],
            date=invoice_data.get('date', ''),
            invoice_type=invoice_type,
            amount_incl_vat=amount_incl_vat or 0,
            vat_rate=vat_rate,
            invoice_number=invoice_data.get('invoice_number', ''),
            file_path=invoice_data.get('file_path', '')
        )
        
        if not invoice:
            return {'success': False, 'error': message}
        
        return {'success': True, 'invoice': invoice, 'customer': customer}
    
    except Exception as e:
        logger.error(f"Error processing invoice: {str(e)}")
        return {'success': False, 'error': str(e)}