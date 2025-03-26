import os
import uuid
import logging
import re
import io
import tempfile
from datetime import datetime
from werkzeug.utils import secure_filename
from utils import save_uploaded_file, allowed_file
from models import (
    add_customer, get_customer, add_invoice, check_duplicate_invoice,
    get_customers, get_invoices
)

# Import libraries for PDF and text extraction
from pypdf import PdfReader
import pytesseract
from PIL import Image
import trafilatura

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
                # Extract data first from file content (OCR)
                file_info = self.extract_document_data(file_path)
                
                # If we couldn't extract needed info, fallback to filename analysis
                if not (file_info.get('is_invoice', False) or file_info.get('is_bank_statement', False)):
                    filename_info = self._extract_info_from_filename(filename)
                    # Merge the extracted data, preferring file content over filename data
                    for key, value in filename_info.items():
                        if key not in file_info:
                            file_info[key] = value
                
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
        statement_data = document.get_statement_data()
        
        # For now, we'll just record that we processed a bank statement
        # and mark it for manual review since matching it to invoices
        # requires more complex logic
        
        # Add to bank statements list
        results['bank_statements'].append({
            'file_path': document.file_path,
            'date': statement_data.get('date'),
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
    
    def extract_text_from_pdf(self, file_path):
        """Extract text from PDF file using PyPDF."""
        try:
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    text += pdf_reader.pages[page_num].extract_text()
            return text
        except Exception as e:
            logger.warning(f"Failed to extract text from PDF: {str(e)}")
            return ""
            
    def extract_text_from_image(self, file_path):
        """Extract text from image file using pytesseract OCR."""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang='nld+eng')
            return text
        except Exception as e:
            logger.warning(f"Failed to extract text from image: {str(e)}")
            return ""
    
    def extract_document_data(self, file_path):
        """
        Extract information from document using OCR/text extraction.
        """
        # Determine file type
        file_extension = os.path.splitext(file_path)[1].lower()
        extracted_text = ""
        
        try:
            if file_extension == '.pdf':
                extracted_text = self.extract_text_from_pdf(file_path)
            elif file_extension in ['.jpg', '.jpeg', '.png']:
                extracted_text = self.extract_text_from_image(file_path)
            else:
                # Unsupported file type
                logger.warning(f"Unsupported file type for OCR: {file_extension}")
        except Exception as e:
            logger.error(f"Error extracting text from document: {str(e)}")
        
        # Process the extracted text to find invoice details
        logger.info(f"Extracted text length: {len(extracted_text)}")
        # Debug: Log the extracted text to see what we're working with
        logger.debug(f"Extracted text: {extracted_text[:500]}...")  # Log first 500 chars
        
        # Extract data from the text
        info = self.analyze_document_text(extracted_text)
        
        return info
        
    def analyze_document_text(self, text):
        """
        Analyze text from document to extract invoice information.
        """
        # Initialize extracted data
        info = {}
        
        if not text:
            return info
        
        # Determine document type (invoice vs. bank statement)
        lower_text = text.lower()
        is_invoice = any(keyword in lower_text for keyword in [
            'factuur', 'invoice', 'rekening', 'bill', 'nota', 'bon', 
            'btw', 'vat', 'tva', 'facture'
        ])
        
        is_bank_statement = any(keyword in lower_text for keyword in [
            'rekeningafschrift', 'bank statement', 'statement of account', 'account statement', 
            'transaction overview', 'transactieoverzicht'
        ])
        
        # Add document classification to info
        info['is_invoice'] = is_invoice
        info['is_bank_statement'] = is_bank_statement
        
        # For invoices, extract detailed information
        if is_invoice:
            # Special case for Hostio Solutions
            if 'Hostio Solutions' in text and 'Invoice #' in text:
                # Extract invoice number
                invoice_num_parts = text.split('Invoice #')
                if len(invoice_num_parts) > 1:
                    invoice_num = invoice_num_parts[1].strip().split('\n')[0]
                    info['invoice_number'] = invoice_num
                    
                    # Extract date if possible
                    if 'Invoice Date:' in text:
                        date_parts = text.split('Invoice Date:')
                        if len(date_parts) > 1:
                            date_str = date_parts[1].strip().split('\n')[0]
                            info['date'] = self._normalize_date(date_str)
                            
                    # Extract amount if in EUR format
                    amount_pattern = r'€(\d+\.\d+)\s*EUR'
                    amount_match = re.search(amount_pattern, text)
                    if amount_match:
                        try:
                            amount = float(amount_match.group(1))
                            info['amount_incl_vat'] = amount
                        except:
                            pass
                    
                    # Set default VAT rate for Belgium
                    info['vat_rate'] = 21.0
                    
                    # Invoice is expense (buying from Hostio)
                    info['invoice_type'] = 'expense'
                    
                    # Extract customer info (the one receiving the invoice)
                    if 'Invoiced To' in text:
                        customer_parts = text.split('Invoiced To')
                        if len(customer_parts) > 1:
                            customer_text = customer_parts[1].strip()
                            lines = customer_text.split('\n')
                            if lines:
                                info['customer_name'] = lines[0].strip()
                                # Extract VAT number if present
                                for line in lines:
                                    if 'VAT Number:' in line or 'BTW' in line:
                                        vat_parts = line.split(':')
                                        if len(vat_parts) > 1:
                                            info['customer_vat_number'] = vat_parts[1].strip()
                                            break
                
                return info  # Return early if it's a Hostio invoice
            
            # For other invoices - general pattern matching
            invoice_number_patterns = [
                r'invoice\s*#(\d{4}-[A-Za-z]{2}-\d+)',  # Format like #2024-HS-1430
                r'invoice\s*#\s*([A-Za-z0-9\-\_\/\.]+)',
                r'factuurnr\.?\s*[:.\-]\s*([A-Za-z0-9\-\_\/\.]+)',
                r'factuurnummer\s*[:.\-]\s*([A-Za-z0-9\-\_\/\.]+)',
                r'invoice\s*number\s*[:.\-]\s*([A-Za-z0-9\-\_\/\.]+)',
                r'invoice\s*no\.?\s*[:.\-]?\s*([A-Za-z0-9\-\_\/\.]+)',
                r'factuur\s*#\s*([A-Za-z0-9\-\_\/\.]+)',
                r'factuurnummer\s*(\d+)',
                r'factuurnr\s*(\d+)',
                r'f-?[\d]+',  # Simple pattern like F-12345 or F12345
                r'INV-?[\d]+' # Simple pattern like INV-12345 or INV12345
            ]
            
            invoice_number = None
            for pattern in invoice_number_patterns:
                match = re.search(pattern, lower_text, re.IGNORECASE)
                if match:
                    invoice_number = match.group(1).strip()
                    break
                    
            if invoice_number:
                info['invoice_number'] = invoice_number
                
            # Extract date
            date_patterns = [
                r'invoice\s*date:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
                r'factuurdatum:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
                r'datum:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
                r'date:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
                r'invoice\s*date:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
                r'factuurdatum:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
                r'datum:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
                r'date:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
                r'due\s*date:?\s*\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4}.*?invoice\s*date:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
                r'invoice\s*date:?\s*(\d{2}-\d{2}-\d{4})',  # Specifiek voor 18-10-2024 formaat
                r'invoice\s*date[^0-9]*(\d{2}-\d{2}-\d{4})' # Nog specifieker voor 18-10-2024
            ]
            
            invoice_date = None
            for pattern in date_patterns:
                match = re.search(pattern, lower_text, re.IGNORECASE)
                if match:
                    date_str = match.group(1).strip()
                    try:
                        # Try to convert to standard format (will implement properly in real app)
                        info['date'] = date_str
                        break
                    except:
                        pass
                        
            # Extract amount
            amount_patterns = [
                r'total\s*(?:incl\.?\s*vat)?\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'totaal\s*(?:incl\.?\s*btw)?\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'te\s*betalen\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'amount\s*due\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'totaal\s*bedrag\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'total\s*amount\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'eindtotaal\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
                r'€\s*([0-9.,]+)\s*(?:eur|euro)?',
                r'([0-9.]+,[0-9]{2})\s*(?:eur|euro)',
                r'([0-9]+\.[0-9]{2})\s*(?:eur|euro)',
                r'sub\s*total\s*[:,.\-€]*\s*([0-9.,]+)\s*(?:eur|euro)?',  # For Hostio invoice format
                r'total\s*[:,.\-€]*\s*([0-9.,]+)\s*(?:eur|euro)?',        # General total format
                r'credit\s*[:,.\-€]*\s*([0-9.,]+)\s*(?:eur|euro)?'        # Handle credit lines
            ]
            
            amount_incl_vat = None
            for pattern in amount_patterns:
                match = re.search(pattern, lower_text, re.IGNORECASE)
                if match:
                    amount_str = match.group(1).strip().replace('€', '').replace('.', '').replace(',', '.')
                    try:
                        amount_incl_vat = float(amount_str)
                        info['amount_incl_vat'] = amount_incl_vat
                        break
                    except:
                        pass
                        
            # Extract VAT rate
            vat_patterns = [
                r'btw\s*(?:percentage|tarief|rate)?\s*[:.\-]\s*(\d{1,2})[.,]?(\d{0,2})?\s*%',
                r'vat\s*(?:percentage|rate)?\s*[:.\-]\s*(\d{1,2})[.,]?(\d{0,2})?\s*%',
                r'btw\s*\((\d{1,2})[.,]?(\d{0,2})?\s*%\)',
                r'vat\s*\((\d{1,2})[.,]?(\d{0,2})?\s*%\)',
                r'(\d{1,2})[.,]?(\d{0,2})?\s*%\s*btw',
                r'(\d{1,2})[.,]?(\d{0,2})?\s*%\s*vat',
                r'tarief\s*(\d{1,2})[.,]?(\d{0,2})?\s*%'
            ]
            
            vat_rate = 21.0  # Default rate for Belgium
            for pattern in vat_patterns:
                match = re.search(pattern, lower_text, re.IGNORECASE)
                if match:
                    try:
                        whole_part = match.group(1)
                        decimal_part = match.group(2) if len(match.groups()) > 1 and match.group(2) else '0'
                        vat_rate = float(f"{whole_part}.{decimal_part}")
                        info['vat_rate'] = vat_rate
                        break
                    except:
                        pass
            
            # Determine invoice type (income or expense)
            # Typical markers for income invoices
            income_markers = [
                'uw klantnummer', 'your customer number', 
                'klantnummer', 'customer number',
                'client number', 'clientnummer'
            ]
            
            # Check if any income markers are present
            is_income = any(marker in lower_text for marker in income_markers)
            info['invoice_type'] = 'income' if is_income else 'expense'
            
            # Extract customer info
            # For expense invoices, look for supplier details
            # For income invoices, look for client details
            if info['invoice_type'] == 'expense':
                # Look for "from" or supplier section
                name_patterns = [
                    r'(?:van|from|sender|afzender)[:.\-]\s*([^\n]+)',
                    r'(?:supplier|leverancier|verkoper|seller)[:.\-]\s*([^\n]+)'
                ]
                
                vat_patterns = [
                    r'(?:btw|vat|tva)(?:-|\s)(?:nummer|number|no)[:.\-]\s*([A-Za-z0-9\s]+)',
                    r'(?:ondernemingsnummer|company\s*number)[:.\-]\s*([A-Za-z0-9\s]+)'
                ]
            else:
                # Look for "to" or client section
                name_patterns = [
                    r'(?:aan|to|recipient|ontvanger)[:.\-]\s*([^\n]+)',
                    r'(?:customer|klant|koper|buyer)[:.\-]\s*([^\n]+)'
                ]
                
                vat_patterns = [
                    r'(?:btw|vat|tva)(?:-|\s)(?:nummer|number|no)[:.\-]\s*([A-Za-z0-9\s]+)',
                    r'(?:ondernemingsnummer|company\s*number)[:.\-]\s*([A-Za-z0-9\s]+)'
                ]
            
            # Extract customer name
            customer_name = None
            for pattern in name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    customer_name = match.group(1).strip()
                    info['customer_name'] = customer_name
                    break
                    
            # Special case: Look for "Invoiced To" section which is common in invoices
            if not customer_name:
                invoiced_to_match = re.search(r'invoiced\s+to\s*\n(.*?)(?:\n\n|\n[A-Z])', text, re.IGNORECASE | re.DOTALL)
                if invoiced_to_match:
                    customer_info = invoiced_to_match.group(1).strip()
                    # The first line is usually the customer name
                    lines = customer_info.split('\n')
                    if lines:
                        info['customer_name'] = lines[0].strip()
                        # If there are more lines, use them as address
                        if len(lines) > 1:
                            info['customer_address'] = '\n'.join(lines[1:]).strip()
                            
            # Special case for Hostio Solutions as seen in the example invoice
            if 'Hostio' in text and 'Solutions' in text and not info.get('customer_name'):
                info['customer_name'] = 'Hostio Solutions'
                # Find VAT number pattern
                vat_text = None
                if 'VAT Number:' in text:
                    vat_parts = text.split('VAT Number:')
                    if len(vat_parts) > 1:
                        vat_text = vat_parts[1].strip().split()[0]
                if vat_text:
                    info['customer_vat_number'] = vat_text
                            
            # Also try matching customer name from the "Invoiced To" line more generically
            if not info.get('customer_name'):
                business_name_match = re.search(r'invoiced\s+to\s*\n\s*([^\n]+)', text, re.IGNORECASE)
                if business_name_match:
                    info['customer_name'] = business_name_match.group(1).strip()
                    
            # Extract VAT number
            customer_vat = None
            for pattern in vat_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    customer_vat = match.group(1).strip().replace(' ', '')
                    info['customer_vat_number'] = customer_vat
                    break
        
        return info
    
    def _extract_info_from_filename(self, filename):
        """
        Analyzes filename to extract document information.
        This is a fallback method that will be used if OCR extraction fails.
        """
        # This is a placeholder implementation
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
        
        # Generate a customer name based on the filename
        possible_customer_name = re.sub(r'[._-]', ' ', os.path.splitext(filename)[0])
        possible_customer_name = re.sub(r'(?:invoice|factuur|bank|statement|afschrift|expense|uitgave|income|inkomst).*', '', possible_customer_name, flags=re.IGNORECASE)
        possible_customer_name = possible_customer_name.strip()
        
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
                
            # Create a sanitized email from the customer name (removing special chars)
            sanitized_name = ''.join(c for c in possible_customer_name.lower() if c.isalnum())
            info['customer_email'] = f"info@{sanitized_name}.com"
            
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
    
