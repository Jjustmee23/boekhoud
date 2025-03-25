import os
import uuid
import logging
import re
from datetime import datetime
from werkzeug.utils import secure_filename
from utils import save_uploaded_file, allowed_file
from models import (
    add_customer, get_customer, add_invoice, check_duplicate_invoice,
    get_customers, get_invoices
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Document Class to store document data and metadata
class Document:
    """Base class for all document types."""
    def __init__(self, file_path, file_info=None):
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.file_info = file_info or {}
        self.document_type = "unknown"
        self.extract_date = self._extract_date_from_filename()
    
    def _extract_date_from_filename(self):
        """Extract date from filename if possible."""
        # Look for patterns like YYYY-MM-DD, DD-MM-YYYY, etc.
        patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}-\d{2}-\d{4})',  # DD-MM-YYYY
            r'(\d{2}/\d{2}/\d{4})',  # DD/MM/YYYY
            r'(\d{4}/\d{2}/\d{2})'   # YYYY/MM/DD
        ]
        
        for pattern in patterns:
            match = re.search(pattern, self.file_name)
            if match:
                date_str = match.group(1)
                try:
                    if '-' in date_str:
                        parts = date_str.split('-')
                    else:
                        parts = date_str.split('/')
                        
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        date_obj = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                    else:  # DD-MM-YYYY
                        date_obj = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                    
                    return date_obj.strftime('%Y-%m-%d')
                except (ValueError, IndexError):
                    pass
        
        # Default to current date if no date found
        return datetime.now().strftime('%Y-%m-%d')
    
    def get_metadata(self):
        """Return document metadata."""
        return {
            'file_path': self.file_path,
            'file_name': self.file_name,
            'document_type': self.document_type,
            'date': self.extract_date,
            **self.file_info
        }

class InvoiceDocument(Document):
    """Class for invoice documents."""
    def __init__(self, file_path, file_info=None):
        super().__init__(file_path, file_info)
        self.document_type = "invoice"
        self.invoice_type = file_info.get('invoice_type', 'expense')
        self.invoice_number = file_info.get('invoice_number', '')
        self.amount_incl_vat = file_info.get('amount_incl_vat', 0.0)
        self.vat_rate = file_info.get('vat_rate', 21.0)
        self.customer_info = {
            'name': file_info.get('customer_name', ''),
            'address': file_info.get('customer_address', ''),
            'vat_number': file_info.get('customer_vat_number', ''),
            'email': file_info.get('customer_email', '')
        }
    
    def get_invoice_data(self):
        """Return invoice data for creating an invoice."""
        return {
            'invoice_number': self.invoice_number,
            'date': self.extract_date,
            'invoice_type': self.invoice_type,
            'amount_incl_vat': self.amount_incl_vat,
            'vat_rate': self.vat_rate,
            'file_path': self.file_path
        }
    
    def get_customer_data(self):
        """Return customer data for creating a customer."""
        return self.customer_info

class BankStatementDocument(Document):
    """Class for bank statement documents."""
    def __init__(self, file_path, file_info=None):
        super().__init__(file_path, file_info)
        self.document_type = "bank_statement"
        self.statement_date = file_info.get('date', self.extract_date)
        self.transactions = file_info.get('transactions', [])
    
    def get_statement_data(self):
        """Return bank statement data."""
        return {
            'date': self.statement_date,
            'file_path': self.file_path,
            'transactions': self.transactions
        }

class FileProcessor:
    """Class for processing uploaded files and extracting information"""
    
    def __init__(self, upload_folder='static/uploads'):
        self.upload_folder = upload_folder
        # Ensure the upload folder exists
        os.makedirs(self.upload_folder, exist_ok=True)
    
    def save_files(self, files):
        """
        Save multiple uploaded files
        
        Args:
            files: list of FileStorage objects from request.files
            
        Returns:
            list: Paths to the saved files
        """
        saved_paths = []
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                file_path = save_uploaded_file(file)
                if file_path:
                    saved_paths.append(file_path)
                    logger.info(f"Saved file: {file_path}")
                else:
                    logger.warning(f"Failed to save file: {file.filename}")
            elif file and file.filename:
                logger.warning(f"Disallowed file type: {file.filename}")
        
        return saved_paths
    
    def process_files(self, files, customer_id=None):
        """
        Process multiple files, extracting information and associating with customers/invoices
        
        Args:
            files: list of FileStorage objects from request.files
            customer_id: Optional customer ID to associate with files
            
        Returns:
            dict: Results of processing with counts and lists of processed items
        """
        results = {
            'saved_files': [],  # List of saved file paths
            'recognized_invoices': [],  # Successfully created invoices
            'new_customers': [],  # Newly created customers
            'manual_review': [],  # Files needing manual review
            'errors': [],  # Processing errors
            'bank_statements': []  # Processed bank statements
        }
        
        # First save all files
        saved_paths = self.save_files(files)
        results['saved_files'] = saved_paths
        
        # Then process each saved file
        for file_path in saved_paths:
            try:
                # In a real implementation, you would use OCR, ML, or specific parsing
                # to extract data from the file. For now, we'll just use the filename
                # for demonstration.
                
                # Extract data from filename as placeholder for real extraction
                filename = os.path.basename(file_path)
                file_info = self._extract_info_from_filename(filename)
                
                # Create appropriate document object based on detected type
                if file_info.get('is_invoice', False):
                    # Create an invoice document
                    document = InvoiceDocument(file_path, file_info)
                    
                    # Process the invoice
                    self._process_invoice_document(document, customer_id, results)
                    
                elif file_info.get('is_bank_statement', False):
                    # Create a bank statement document
                    document = BankStatementDocument(file_path, file_info)
                    
                    # Process the bank statement
                    self._process_bank_statement_document(document, results)
                    
                else:
                    # Unknown file type, create a generic document for manual review
                    document = Document(file_path, file_info)
                    
                    # Add to manual review list
                    results['manual_review'].append({
                        'file_path': file_path,
                        'reason': 'Unknown document type',
                        'metadata': document.get_metadata()
                    })
                    
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                results['errors'].append({
                    'file_path': file_path,
                    'error': str(e)
                })
                results['manual_review'].append({
                    'file_path': file_path,
                    'reason': f'Processing error: {str(e)}'
                })
        
        return results

    def _process_invoice_document(self, document, customer_id, results):
        """Process an invoice document"""
        # Extract data from document
        invoice_data = document.get_invoice_data()
        customer_data = document.get_customer_data()
        file_path = document.file_path
        
        # Use provided customer_id or try to find/create one
        if not customer_id:
            # Try to find an existing customer by VAT number
            customers = get_customers()
            matching_customer = None
            
            # First try to match by VAT number if available
            if customer_data.get('vat_number'):
                for c in customers:
                    if c.get('vat_number') == customer_data.get('vat_number'):
                        matching_customer = c
                        break
            
            # If no match by VAT, try to match by name with basic fuzzy matching
            if not matching_customer and customer_data.get('name'):
                customer_name = customer_data.get('name').lower()
                for c in customers:
                    if customer_name in c.get('name', '').lower() or c.get('name', '').lower() in customer_name:
                        # Found potential name match
                        matching_customer = c
                        break
            
            if matching_customer:
                # Use the existing customer
                customer_id = matching_customer['id']
                logger.info(f"Matched invoice to existing customer: {matching_customer['name']}")
            else:
                # Create a new customer
                new_customer = add_customer(
                    name=customer_data.get('name', 'Auto-detected Customer'),
                    address=customer_data.get('address', 'Automatisch gedetecteerd'),
                    vat_number=customer_data.get('vat_number', ''),
                    email=customer_data.get('email', f"info@{re.sub(r'[^a-z0-9]', '', customer_data.get('name', 'autodetect').lower())}.com")
                )
                
                if new_customer:
                    customer_id = new_customer['id']
                    results['new_customers'].append(new_customer)
                    logger.info(f"Created new customer: {new_customer['name']}")
                else:
                    # Failed to create customer
                    results['manual_review'].append({
                        'file_path': file_path,
                        'reason': 'Failed to create customer',
                        'metadata': document.get_metadata()
                    })
                    return
        
        # Check for duplicate invoice
        is_duplicate, duplicate_id = check_duplicate_invoice(
            invoice_number=invoice_data.get('invoice_number'),
            customer_id=customer_id,
            date=invoice_data.get('date'),
            amount_incl_vat=invoice_data.get('amount_incl_vat')
        )
        
        if is_duplicate:
            results['manual_review'].append({
                'file_path': file_path,
                'reason': 'Possible duplicate invoice',
                'duplicate_id': duplicate_id,
                'metadata': document.get_metadata()
            })
            return
        
        # Create the invoice
        invoice, message, _ = add_invoice(
            customer_id=customer_id,
            date=invoice_data.get('date'),
            invoice_type=invoice_data.get('invoice_type', 'expense'),
            amount_incl_vat=invoice_data.get('amount_incl_vat', 0),
            vat_rate=invoice_data.get('vat_rate', 21),
            invoice_number=invoice_data.get('invoice_number'),
            file_path=file_path,
            check_duplicate=False  # We already checked
        )
        
        if invoice:
            results['recognized_invoices'].append(invoice)
            logger.info(f"Successfully created invoice {invoice['invoice_number']}")
        else:
            results['manual_review'].append({
                'file_path': file_path,
                'reason': f'Failed to create invoice: {message}',
                'metadata': document.get_metadata()
            })

    def _process_bank_statement_document(self, document, results):
        """Process a bank statement document"""
        # Extract data from document
        statement_data = document.get_statement_data()
        
        # For now, we'll just record that we processed a bank statement
        # and mark it for manual review since matching it to invoices
        # requires more complex logic
        
        # Add to bank statements list
        results['bank_statements'].append({
            'file_path': document.file_path,
            'date': statement_data.get('date', datetime.now().strftime('%Y-%m-%d')),
            'transactions': statement_data.get('transactions', []),
            'metadata': document.get_metadata()
        })
        
        # Also add to manual review to show in the UI
        results['manual_review'].append({
            'file_path': document.file_path,
            'reason': 'Bank statement requires manual matching to invoices',
            'metadata': document.get_metadata()
        })
        
        logger.info(f"Processed bank statement dated {statement_data.get('date')}")
        
        # In a real implementation, you would:
        # 1. Match transactions to existing invoices based on amount, date, etc.
        # 2. Update the invoice payment status
        # 3. Create a proper bank statement record in the database
    
    def _extract_info_from_filename(self, filename):
        """
        Analyzes filename to extract document information.
        In a real implementation, this would use OCR/ML to extract info from the file content.
        
        For demo purposes, we're using filename patterns to simulate document analysis.
        """
        # This is a placeholder implementation
        # In real life, you'd use OCR tools like pytesseract, or ML services
        info = {}
        
        # Basic classification based on filename keywords
        lower_filename = filename.lower()
        
        # Extract possible amounts from filename (e.g., 100eur, 50.99euro, etc.)
        amount_match = re.search(r'(\d+[.,]?\d*)(?:eur|euro)', lower_filename)
        amount = 100.0  # Default amount
        if amount_match:
            try:
                amount_str = amount_match.group(1).replace(',', '.')
                amount = float(amount_str)
            except ValueError:
                pass
        
        # Extract possible VAT rates (e.g., 21%, 6pct, etc.)
        vat_match = re.search(r'(\d+)(?:%|pct|percent)', lower_filename)
        vat_rate = 21.0  # Default VAT rate in Belgium
        if vat_match:
            try:
                vat_rate = float(vat_match.group(1))
            except ValueError:
                pass
        
        # Generate a customer name based on the filename - improved algorithm
        customer_parts = []
        
        # First, look for known name patterns: klant_*_factuur.pdf or company-name_invoice_*.pdf
        name_pattern = re.match(r'^([^_\.]+)[_\.-]', os.path.splitext(filename)[0])
        if name_pattern:
            customer_parts.append(name_pattern.group(1))
            
        # If nothing matched with first pattern, try another approach
        if not customer_parts:
            parts = re.split(r'[_\.-]', os.path.splitext(filename)[0])
            for part in parts:
                lower_part = part.lower()
                # Skip common terms that aren't part of a company name
                if not any(term in lower_part for term in ['invoice', 'factuur', 'bank', 'statement', 
                                                        'afschrift', 'expense', 'uitgave', 'income', 
                                                        'inkomst', 'detail', 'datum', 'date']):
                    # Only add if it's not just numbers
                    if not re.match(r'^\d+$', part):
                        customer_parts.append(part)
                    # Stop once we have a plausible name
                    if len(customer_parts) == 1 and len(part) > 3:
                        break
        
        possible_customer_name = ' '.join(customer_parts).strip()
        
        # Provide default if we couldn't extract anything meaningful
        if len(possible_customer_name) < 3:  # Too short to be a real name
            possible_customer_name = "Auto-detected Customer"
        
        # Check if it looks like an invoice
        if 'invoice' in lower_filename or 'factuur' in lower_filename:
            info['is_invoice'] = True
            
            # Try to determine if it's income or expense
            if 'income' in lower_filename or 'inkomst' in lower_filename:
                info['invoice_type'] = 'income'
            elif 'expense' in lower_filename or 'uitgave' in lower_filename:
                info['invoice_type'] = 'expense'
            else:
                # Default type
                info['invoice_type'] = 'expense'
            
            # Extract a placeholder invoice number from the filename or generate one
            invoice_num_match = re.search(r'([A-Za-z0-9]{2,10}[-/][0-9]{2,8})', filename)
            if invoice_num_match:
                info['invoice_number'] = invoice_num_match.group(1)
            else:
                info['invoice_number'] = f"AUTO-{uuid.uuid4().hex[:8].upper()}"
            
            # Set amount and VAT rate
            info['amount_incl_vat'] = amount
            info['vat_rate'] = vat_rate
            
            # Extract date or use current
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})', filename)
            if date_match:
                info['date'] = self._normalize_date(date_match.group(1))
            else:
                info['date'] = datetime.now().strftime('%Y-%m-%d')
            
            # Set customer info
            info['customer_name'] = possible_customer_name.title()
            info['customer_address'] = "Automatisch gedetecteerd"
            
            # Look for potential VAT number (Belgian format: BE0123456789)
            vat_number_match = re.search(r'(BE\d{10}|BE \d{4}\.\d{3}\.\d{3})', filename, re.IGNORECASE)
            if vat_number_match:
                info['customer_vat_number'] = vat_number_match.group(1).upper().replace(' ', '').replace('.', '')
            else:
                info['customer_vat_number'] = ""
                
            info['customer_email'] = f"info@{re.sub(r'[^a-z0-9]', '', possible_customer_name.lower())}.com"
            
        # Check if it looks like a bank statement
        elif 'bank' in lower_filename or 'statement' in lower_filename or 'afschrift' in lower_filename:
            info['is_bank_statement'] = True
            
            # Extract date or use current
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})', filename)
            if date_match:
                info['date'] = self._normalize_date(date_match.group(1))
            else:
                info['date'] = datetime.now().strftime('%Y-%m-%d')
                
            # Simulate a few transactions for demo purposes
            info['transactions'] = [
                {'date': info['date'], 'description': 'Demo transaction 1', 'amount': 125.50},
                {'date': info['date'], 'description': 'Demo transaction 2', 'amount': -45.20},
                {'date': info['date'], 'description': 'Demo transaction 3', 'amount': 67.00}
            ]
        
        return info
    
    def _normalize_date(self, date_str):
        """Convert different date formats to YYYY-MM-DD."""
        if '-' not in date_str:
            return date_str
            
        parts = date_str.split('-')
        if len(parts[0]) == 4:  # YYYY-MM-DD
            return date_str
        else:  # DD-MM-YYYY
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    
