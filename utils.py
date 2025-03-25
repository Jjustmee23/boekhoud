import os
import pandas as pd
from datetime import datetime
from decimal import Decimal
from flask import render_template
import tempfile
import uuid
from werkzeug.utils import secure_filename
from weasyprint import HTML

def format_currency(value):
    """Format a value as a Euro currency string"""
    if value is None:
        return "€0.00"
    return f"€{float(value):,.2f}"

def format_decimal(value, decimal_places=2):
    """Format a decimal number with specified decimal places"""
    if value is None:
        return "0.00"
    return f"{float(value):,.{decimal_places}f}"

def generate_pdf_invoice(invoice, customer):
    """Generate a PDF invoice from HTML template"""
    # Create a temporary file to store the PDF
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    
    # Render the invoice template
    html_content = render_template(
        'invoice_template.html', 
        invoice=invoice, 
        customer=customer,
        format_currency=format_currency,
        now=datetime.now()
    )
    
    # Generate PDF and save to temp file
    HTML(string=html_content).write_pdf(temp_file.name)
    
    return temp_file.name

def export_to_excel(data, filename, columns=None):
    """Export data to Excel format"""
    df = pd.DataFrame(data)
    
    # Filter columns if specified
    if columns:
        df = df[columns]
    
    # Create a temporary file to store the Excel file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
    
    # Save to Excel
    df.to_excel(temp_file.name, index=False)
    
    return temp_file.name

def export_to_csv(data, filename, columns=None):
    """Export data to CSV format"""
    df = pd.DataFrame(data)
    
    # Filter columns if specified
    if columns:
        df = df[columns]
    
    # Create a temporary file to store the CSV file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    
    # Save to CSV
    df.to_csv(temp_file.name, index=False)
    
    return temp_file.name

def get_vat_rates():
    """Return the available Belgian VAT rates"""
    return [
        {'rate': 0, 'label': '0%'},
        {'rate': 6, 'label': '6%'},
        {'rate': 12, 'label': '12%'},
        {'rate': 21, 'label': '21%'}
    ]

def date_to_quarter(date):
    """Convert a date to its quarter (1-4)"""
    if isinstance(date, str):
        date = datetime.strptime(date, '%Y-%m-%d')
    return ((date.month - 1) // 3) + 1

def get_quarters():
    """Return the quarters for selection"""
    return [
        {'id': 1, 'name': 'Q1 (Jan-Mar)'},
        {'id': 2, 'name': 'Q2 (Apr-Jun)'},
        {'id': 3, 'name': 'Q3 (Jul-Sep)'},
        {'id': 4, 'name': 'Q4 (Oct-Dec)'}
    ]

def get_months():
    """Return the months for selection"""
    return [
        {'id': 1, 'name': 'January'},
        {'id': 2, 'name': 'February'},
        {'id': 3, 'name': 'March'},
        {'id': 4, 'name': 'April'},
        {'id': 5, 'name': 'May'},
        {'id': 6, 'name': 'June'},
        {'id': 7, 'name': 'July'},
        {'id': 8, 'name': 'August'},
        {'id': 9, 'name': 'September'},
        {'id': 10, 'name': 'October'},
        {'id': 11, 'name': 'November'},
        {'id': 12, 'name': 'December'}
    ]

def get_years():
    """Return a list of years for reporting, from 5 years ago to 5 years in the future"""
    current_year = datetime.now().year
    return list(range(current_year - 5, current_year + 6))

def save_uploaded_file(file, prefix="invoice"):
    """
    Save an uploaded file to the uploads directory with a unique name
    
    Args:
        file: The FileStorage object from request.files
        prefix: Prefix for the filename (default: "invoice")
        
    Returns:
        str: Path to the saved file relative to the static directory
    """
    # Make sure the upload directory exists
    upload_folder = os.path.join('static', 'uploads')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    if not file:
        return None
        
    # Make sure the filename is safe
    filename = secure_filename(file.filename)
    
    # Generate a unique filename to prevent overwriting
    unique_filename = f"{prefix}_{uuid.uuid4()}_{filename}"
    
    # Create the upload path (relative to the static directory)
    upload_path = os.path.join('uploads', unique_filename)
    
    # Create the full file path
    full_path = os.path.join('static', upload_path)
    
    # Save the file
    file.save(full_path)
    
    # Return the path relative to the static directory
    return upload_path

def allowed_file(filename, allowed_extensions=None):
    """
    Check if the file has an allowed extension
    
    Args:
        filename: The filename to check
        allowed_extensions: Set of allowed extensions (default: pdf, png, jpg, jpeg)
        
    Returns:
        bool: True if file is allowed, False otherwise
    """
    if allowed_extensions is None:
        allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg'}
        
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions
