from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
import os
import logging
from document_processor import DocumentProcessor
from utils import save_uploaded_file, allowed_file
from models import get_customers, get_invoices

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
document_bp = Blueprint('document', __name__)

# Create document processor
document_processor = DocumentProcessor(confidence_threshold=0.9)

# Function to automatically process high-confidence documents
def auto_process_document(document_data, file_path):
    """
    Automatically process a document with high confidence
    
    Returns:
        tuple: (success, message)
    """
    try:
        document_type = document_data.get('document_type')
        
        if document_type == 'invoice':
            # Get invoice data
            invoice_number = document_data.get('invoice_number')
            invoice_date = document_data.get('date')
            customer_id = document_data.get('customer_id')
            invoice_type = document_data.get('invoice_type', 'expense')
            amount_incl_vat = document_data.get('amount_incl_vat')
            vat_rate = document_data.get('vat_rate', 21)
            
            # Validate required fields
            if not customer_id or not invoice_date or not amount_incl_vat:
                return False, 'Onvoldoende gegevens voor automatische verwerking'
            
            # Convert amount to float if needed
            if isinstance(amount_incl_vat, str):
                amount_incl_vat = float(amount_incl_vat.replace(',', '.'))
            
            if isinstance(vat_rate, str):
                vat_rate = float(vat_rate.replace(',', '.'))
            
            # Create invoice
            from models import add_invoice
            invoice, message, is_duplicate = add_invoice(
                customer_id=customer_id,
                date=invoice_date,
                invoice_type=invoice_type,
                amount_incl_vat=amount_incl_vat,
                vat_rate=vat_rate,
                invoice_number=invoice_number,
                file_path=file_path,
                check_duplicate=True
            )
            
            if invoice:
                return True, f'Factuur succesvol aangemaakt: {invoice_number}'
            else:
                return False, f'Fout bij aanmaken factuur: {message}'
                
        elif document_type == 'bank_statement':
            # Process bank statement (placeholder for now)
            return True, 'Bankafschrift verwerkt'
        
        return False, 'Onbekend documenttype'
        
    except Exception as e:
        logger.error(f'Error auto-processing document: {str(e)}')
        return False, f'Fout bij automatische verwerking: {str(e)}'

@document_bp.route('/document/upload', methods=['GET', 'POST'])
def upload_documents():
    """Handle document upload and processing"""
    if request.method == 'POST':
        # Check if customer_id was provided
        customer_id = request.form.get('customer_id')
        
        # Check if files were uploaded
        if 'files[]' not in request.files:
            flash('Geen bestanden geselecteerd', 'danger')
            return redirect(request.url)
        
        files = request.files.getlist('files[]')
        
        # Check if any valid files were provided
        if not files or files[0].filename == '':
            flash('Geen bestanden geselecteerd', 'danger')
            return redirect(request.url)
        
        # Save and process files
        processed_files = []
        duplicate_files = []
        manual_review_files = []
        
        for file in files:
            if file and allowed_file(file.filename):
                # Save file
                file_path = save_uploaded_file(file)
                
                if file_path:
                    # Process document
                    result = document_processor.process_document(file_path)
                    
                    # Handle based on result
                    if 'error' in result:
                        # Error processing file
                        manual_review_files.append({
                            'file_path': file_path,
                            'file_name': os.path.basename(file_path),
                            'reason': result['error']
                        })
                    elif result.get('document_type') == 'invoice':
                        # Check if it's a duplicate
                        if result.get('is_duplicate'):
                            duplicate_files.append({
                                'file_path': file_path,
                                'file_name': os.path.basename(file_path),
                                'invoice_data': result,
                                'existing_invoice_id': result.get('existing_invoice_id'),
                                'options': ['link', 'delete']
                            })
                        # Check if it needs review
                        elif result.get('needs_review', True):
                            manual_review_files.append({
                                'file_path': file_path,
                                'file_name': os.path.basename(file_path),
                                'document_data': result,
                                'reason': 'Needs manual review',
                                'confidence': result.get('matching_confidence', 0)
                            })
                        else:
                            # Auto-processed successfully
                            processed_files.append({
                                'file_path': file_path,
                                'file_name': os.path.basename(file_path),
                                'document_data': result
                            })
                    elif result.get('document_type') == 'bank_statement':
                        # Bank statements always need review for now
                        manual_review_files.append({
                            'file_path': file_path,
                            'file_name': os.path.basename(file_path),
                            'document_data': result,
                            'reason': 'Bank statement needs manual review'
                        })
                    else:
                        # Unknown document type
                        manual_review_files.append({
                            'file_path': file_path,
                            'file_name': os.path.basename(file_path),
                            'document_data': result,
                            'reason': 'Unknown document type'
                        })
            else:
                # Invalid file type
                flash(f'Ongeldig bestandstype: {file.filename}', 'danger')
        
        # Save results to session for review page
        session['processed_files'] = processed_files
        session['duplicate_files'] = duplicate_files
        session['manual_review_files'] = manual_review_files
        
        # Redirect to review page
        return redirect(url_for('document.review_documents'))
    
    # GET request - show upload form
    customers = get_customers()
    from datetime import datetime
    return render_template('document_upload.html', customers=customers, now=datetime.now())

@document_bp.route('/document/review', methods=['GET'])
def review_documents():
    """Show document processing results for review"""
    # Get results from session
    processed_files = session.get('processed_files', [])
    duplicate_files = session.get('duplicate_files', [])
    manual_review_files = session.get('manual_review_files', [])
    
    # Auto-process documents that don't need review
    auto_processed = []
    remaining_processed = []
    
    # Auto-process files with high confidence scores (>= 90%)
    for doc in processed_files:
        file_path = doc.get('file_path')
        document_data = doc.get('document_data')
        
        if document_data and file_path:
            # Try to auto-process this document
            success, message = auto_process_document(document_data, file_path)
            
            if success:
                auto_processed.append({
                    'file_name': os.path.basename(file_path),
                    'message': message,
                    'document_type': document_data.get('document_type')
                })
            else:
                # If auto-processing failed, add to manual review instead
                manual_review_files.append({
                    'file_path': file_path,
                    'file_name': os.path.basename(file_path),
                    'document_data': document_data,
                    'reason': message,
                    'confidence': document_data.get('matching_confidence', 0)
                })
        else:
            # Missing data, keep for manual view
            remaining_processed.append(doc)
    
    # Clear auto-processed files from session and update
    session['processed_files'] = remaining_processed
    session['duplicate_files'] = duplicate_files
    session['manual_review_files'] = manual_review_files
    
    # Get customers and invoices for reference
    customers = get_customers()
    invoices = get_invoices()
    
    # If any files were auto-processed, show a success message
    if auto_processed:
        invoice_count = sum(1 for doc in auto_processed if doc.get('document_type') == 'invoice')
        bank_count = sum(1 for doc in auto_processed if doc.get('document_type') == 'bank_statement')
        
        if invoice_count > 0 or bank_count > 0:
            message = f"Automatisch verwerkt: {len(auto_processed)} document(en): "
            if invoice_count > 0:
                message += f"{invoice_count} facturen"
            if bank_count > 0:
                if invoice_count > 0:
                    message += " en "
                message += f"{bank_count} bankafschriften"
            flash(message, 'success')
    
    from datetime import datetime
    return render_template(
        'document_review.html',
        processed_files=remaining_processed,
        duplicate_files=duplicate_files,
        manual_review_files=manual_review_files,
        auto_processed=auto_processed,
        customers=customers,
        invoices=invoices,
        now=datetime.now()
    )

@document_bp.route('/document/process', methods=['POST'])
def process_document():
    """Process a document after review"""
    # Get form data
    document_type = request.form.get('document_type')
    file_path = request.form.get('file_path')
    customer_id = request.form.get('customer_id')
    
    if not file_path or not os.path.exists(file_path):
        flash('Ongeldig bestand', 'danger')
        return redirect(url_for('document.review_documents'))
    
    if document_type == 'invoice':
        # Get invoice data
        invoice_number = request.form.get('invoice_number')
        invoice_date = request.form.get('invoice_date')
        invoice_type = request.form.get('invoice_type', 'expense')
        amount_incl_vat = request.form.get('amount_incl_vat')
        vat_rate = request.form.get('vat_rate', 21)
        
        # Validate required fields
        if not customer_id or not invoice_date or not amount_incl_vat:
            flash('Verplichte velden ontbreken', 'danger')
            return redirect(url_for('document.review_documents'))
        
        try:
            # Convert amount to float
            amount_incl_vat = float(amount_incl_vat)
            vat_rate = float(vat_rate)
            
            # Create invoice
            from models import add_invoice
            invoice, message, _ = add_invoice(
                customer_id=customer_id,
                date=invoice_date,
                invoice_type=invoice_type,
                amount_incl_vat=amount_incl_vat,
                vat_rate=vat_rate,
                invoice_number=invoice_number,
                file_path=file_path
            )
            
            if invoice:
                flash(f'Factuur succesvol aangemaakt: {invoice_number}', 'success')
            else:
                flash(f'Fout bij aanmaken factuur: {message}', 'danger')
                
        except Exception as e:
            flash(f'Fout bij aanmaken factuur: {str(e)}', 'danger')
            
    elif document_type == 'bank_statement':
        # Process bank statement (not implemented yet)
        flash('Bank statement processing not implemented yet', 'warning')
    
    # Return to review page
    return redirect(url_for('document.review_documents'))

@document_bp.route('/document/handle_duplicate', methods=['POST'])
def handle_duplicate():
    """Handle a duplicate document"""
    action = request.form.get('action')
    file_path = request.form.get('file_path')
    existing_invoice_id = request.form.get('existing_invoice_id')
    
    if not file_path or not action or not existing_invoice_id:
        flash('Verplichte velden ontbreken', 'danger')
        return redirect(url_for('document.review_documents'))
    
    if action == 'link':
        # Link the file to the existing invoice
        try:
            from models import update_invoice
            invoice = update_invoice(
                invoice_id=existing_invoice_id,
                file_path=file_path
            )
            
            if invoice:
                flash(f'Bestand gekoppeld aan bestaande factuur: {invoice.get("invoice_number")}', 'success')
            else:
                flash('Kan bestand niet koppelen aan factuur', 'danger')
                
        except Exception as e:
            flash(f'Fout bij koppelen bestand: {str(e)}', 'danger')
            
    elif action == 'delete':
        # Delete the duplicate file
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                flash('Duplicaat bestand verwijderd', 'success')
            else:
                flash('Bestand niet gevonden', 'danger')
                
        except Exception as e:
            flash(f'Fout bij verwijderen bestand: {str(e)}', 'danger')
    
    # Return to review page
    return redirect(url_for('document.review_documents'))