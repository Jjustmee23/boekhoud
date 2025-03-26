import os
import uuid
import logging
import json
import datetime
from datetime import datetime
from werkzeug.utils import secure_filename
import base64
import io
from PIL import Image
from pypdf import PdfReader
import pytesseract
import re
import trafilatura
import numpy as np

# Configure logger for file processor
logger = logging.getLogger('file_processor')

class Document:
    """Base class for all document types."""
    def __init__(self, file_path, file_info=None):
        self.file_path = file_path
        self.file_info = file_info or {}
        self.filename = os.path.basename(file_path)
        self.file_extension = os.path.splitext(file_path)[1].lower()
        self.date = self._extract_date_from_filename()
        
    def _extract_date_from_filename(self):
        """Extract date from filename if possible."""
        date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})', self.filename)
        if date_match:
            date_str = date_match.group(1)
            # Normalize date format to YYYY-MM-DD
            if len(date_str.split('-')[0]) == 4:  # YYYY-MM-DD
                return date_str
            else:  # DD-MM-YYYY
                parts = date_str.split('-')
                return f"{parts[2]}-{parts[1]}-{parts[0]}"
        return datetime.now().strftime('%Y-%m-%d')
        
    def get_metadata(self):
        """Return document metadata."""
        return {
            'filename': self.filename,
            'file_path': self.file_path,
            'file_extension': self.file_extension,
            'date': self.date
        }

class InvoiceDocument(Document):
    """Class for invoice documents."""
    def __init__(self, file_path, file_info=None):
        super().__init__(file_path, file_info)
        self.invoice_data = file_info or {}
        self.is_income = self.invoice_data.get('invoice_type') == 'income'
        
    def get_invoice_data(self):
        """Return invoice data for creating an invoice."""
        # Start with the extracted file info
        invoice_data = {
            'date': self.invoice_data.get('date', self.date),
            'invoice_number': self.invoice_data.get('invoice_number', ''),
            'invoice_type': self.invoice_data.get('invoice_type', 'expense'),
            'amount_incl_vat': self.invoice_data.get('amount_incl_vat', 0.0),
            'vat_rate': self.invoice_data.get('vat_rate', 21.0),
            'file_path': self.file_path
        }
        
        # Add customer ID if present
        if 'customer_id' in self.invoice_data:
            invoice_data['customer_id'] = self.invoice_data['customer_id']
            
        return invoice_data
        
    def get_customer_data(self):
        """Return customer data for creating a customer."""
        # Only return customer data if we find a customer name
        if self.invoice_data.get('customer_name'):
            # Build a complete customer data structure based on all extracted info
            customer_data = {
                'name': self.invoice_data.get('customer_name', ''),
                'group': self.invoice_data.get('customer_group', ''),
                'street': self.invoice_data.get('customer_street', ''),
                'postal_city': self.invoice_data.get('customer_postal_city', ''),
                'country': self.invoice_data.get('customer_country', ''),
                'vat_number': self.invoice_data.get('customer_vat_number', ''),
                'iban': self.invoice_data.get('customer_iban', ''),
                'bic': self.invoice_data.get('customer_bic', ''),
                'email': self.invoice_data.get('customer_email', '')
            }
            
            # For backwards compatibility with existing code
            if 'customer_address' in self.invoice_data:
                # Only use the address if street/postal_city are not set
                if not customer_data['street'] and not customer_data['postal_city']:
                    address_lines = self.invoice_data['customer_address'].split('\n')
                    if len(address_lines) >= 1:
                        customer_data['street'] = address_lines[0]
                    if len(address_lines) >= 2:
                        customer_data['postal_city'] = address_lines[1]
                        
            # Add all fields in a readable address field for display purposes
            address_parts = []
            if customer_data['street']:
                address_parts.append(customer_data['street'])
            if customer_data['postal_city']:
                address_parts.append(customer_data['postal_city'])
            if customer_data['country']:
                address_parts.append(customer_data['country'])
                
            customer_data['address'] = '\n'.join(address_parts)
            
            return customer_data
        return None
        
class BankStatementDocument(Document):
    """Class for bank statement documents."""
    def __init__(self, file_path, file_info=None):
        super().__init__(file_path, file_info)
        self.statement_data = file_info or {}
        
    def get_statement_data(self):
        """Return bank statement data."""
        # Start with the extracted file info
        statement_data = {
            'date': self.statement_data.get('date', self.date),
            'account': self.statement_data.get('account', ''),
            'transactions': self.statement_data.get('transactions', []),
            'file_path': self.file_path
        }
        
        return statement_data

class FileProcessor:
    """Class for processing uploaded files and extracting information"""
    
    def __init__(self, upload_folder='static/uploads'):
        self.upload_folder = upload_folder
        # Create the upload folder if it doesn't exist
        os.makedirs(upload_folder, exist_ok=True)
        
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
            # Skip empty file inputs
            if file.filename == '':
                continue
                
            # Generate a unique filename
            original_filename = secure_filename(file.filename)
            unique_id = str(uuid.uuid4())
            unique_filename = f"invoice_{unique_id[:8]}_{original_filename}"
            
            # Create the path
            file_path = os.path.join(self.upload_folder, unique_filename)
            
            # Save the file
            file.save(file_path)
            logger.info(f"Saved file: {file_path}")
            
            saved_paths.append(file_path)
            
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
            'saved_files': [],
            'recognized_invoices': [],
            'new_customers': [],
            'manual_review': [],
            'errors': []
        }
        
        # First, save all the files
        saved_paths = self.save_files(files)
        results['saved_files'] = saved_paths
        
        # Now process each file
        for file_path in saved_paths:
            try:
                # Extract information from the file
                file_info = self.extract_document_data(file_path)
                
                # Determine document type
                if file_info.get('is_invoice'):
                    # Create an invoice document
                    document = InvoiceDocument(file_path, file_info)
                    
                    # If a customer ID was provided, use it
                    if customer_id:
                        document.invoice_data['customer_id'] = customer_id
                        
                    # Process the invoice
                    self._process_invoice_document(document, customer_id, results)
                
                elif file_info.get('is_bank_statement'):
                    # Create a bank statement document
                    document = BankStatementDocument(file_path, file_info)
                    
                    # Process the bank statement
                    self._process_bank_statement_document(document, results)
                
                else:
                    # Unknown document type, add to manual review
                    logger.warning(f"Unknown document type for file: {file_path}")
                    results['manual_review'].append({
                        'file_path': file_path,
                        'reason': 'Unknown document type'
                    })
            
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                results['errors'].append({
                    'file_path': file_path,
                    'error': str(e)
                })
                
        return results
        
    def _process_invoice_document(self, document, customer_id, results):
        """Process an invoice document"""
        invoice_data = document.get_invoice_data()
        customer_data = document.get_customer_data()
        
        # If no customer ID was provided, try to use customer data from the document
        if not customer_id and customer_data:
            # In a real implementation, you would search for existing customers
            # based on the customer data (name, VAT number, etc.) and create a new one if not found
            # Here we'll just simulate this
            logger.info(f"Created new customer: {customer_data.get('name')}")
            results['new_customers'].append(customer_data)
            # Simulate assigning a customer ID
            invoice_data['customer_id'] = f"{uuid.uuid4().hex[:8]}"
        
        # Add the invoice to the results
        results['recognized_invoices'].append(invoice_data)
        logger.info(f"Successfully created invoice {document.filename[:10]}")
        
    def _process_bank_statement_document(self, document, results):
        """Process a bank statement document"""
        statement_data = document.get_statement_data()
        
        # Add to manual review for now, as we need to match transactions
        # to invoices which requires UI interaction
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
        logger.debug(f"Extracted text: {extracted_text[:100]}...")  # Log first 100 chars
        
        # Extract data from the text
        info = self.analyze_document_text(extracted_text)
        
        return info
        
    def analyze_document_text(self, text):
        """
        Analyze text from document to extract invoice information.
        Supports both Dutch and English language documents.
        """
        # Initialize extracted data
        info = {}
        
        if not text or len(text) < 20:
            logging.warning("Text is too short for analysis")
            return info
        
        # Determine document type (invoice vs. bank statement)
        lower_text = text.lower()
        is_invoice = any(keyword in lower_text for keyword in [
            'factuur', 'invoice', 'rekening', 'bill', 'nota', 'bon', 
            'btw', 'vat', 'tva', 'facture', 'betaling', 'payment'
        ])
        
        is_bank_statement = any(keyword in lower_text for keyword in [
            'rekeningafschrift', 'bank statement', 'statement of account', 'account statement', 
            'transaction overview', 'transactieoverzicht', 'bankafschrift', 'overzicht'
        ])
        
        # Add document classification to info
        info['is_invoice'] = is_invoice
        info['is_bank_statement'] = is_bank_statement
        
        # For invoices, extract detailed information
        if is_invoice:
            # Process common document structures first
            self._extract_dates(text, lower_text, info)
            self._extract_amounts(text, lower_text, info)
            self._extract_vat_rate(text, lower_text, info)
            self._extract_customer_info(text, lower_text, info)
            
            # Apply vendor-specific parsing if we can identify the vendor
            if self._is_hostio_invoice(text):
                self._parse_hostio_invoice(text, info)
                # For Hostio invoices, we always set type to expense as we buy from them
                info['invoice_type'] = 'expense'
            else:
                # Try to determine if this is an income or expense invoice
                self._determine_invoice_type(text, lower_text, info)
                
            # If we still don't have an invoice number, try to extract it
            if not info.get('invoice_number'):
                self._extract_invoice_number(text, lower_text, info)
                
            # Set default VAT rate if not detected
            if not info.get('vat_rate'):
                info['vat_rate'] = 21.0  # Default rate for Belgium
                
        elif is_bank_statement:
            # TODO: Implement bank statement specific parsing
            pass
            
        return info
        
    def _is_hostio_invoice(self, text):
        """Detect if this is a Hostio Solutions invoice"""
        return 'Hostio Solutions' in text and 'Invoice #' in text
        
    def _parse_hostio_invoice(self, text, info):
        """Parse Hostio Solutions specific invoice format"""
        logger.info("Parsing Hostio Solutions invoice...")
        
        # Extract invoice number (format: 2024-HS-1430)
        if 'Invoice #' in text:
            parts = text.split('Invoice #')
            if len(parts) > 1:
                invoice_num = parts[1].strip().split('\n')[0]
                info['invoice_number'] = invoice_num
                logger.info(f"Detected invoice number: {invoice_num}")
                
        # Extract invoice date - try multiple patterns
        date_extracted = False
        
        # Try exact matches first
        if 'Invoice Date:' in text:
            parts = text.split('Invoice Date:')
            if len(parts) > 1:
                date_str = parts[1].strip().split('\n')[0]
                info['date'] = self._normalize_date(date_str)
                date_extracted = True
                logger.info(f"Detected invoice date (method 1): {date_str}")
                
        # If that fails, try regex patterns
        if not date_extracted:
            date_patterns = [
                r'Invoice\s+Date:\s*(\d{1,2}-\d{1,2}-\d{4})',  # 18-10-2024
                r'Due\s+Date:\s*\d{1,2}-\d{1,2}-\d{4}.*?Invoice\s+Date:\s*(\d{1,2}-\d{1,2}-\d{4})'  # Look for invoice date after due date
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    date_str = match.group(1).strip()
                    info['date'] = self._normalize_date(date_str)
                    date_extracted = True
                    logger.info(f"Detected invoice date (method 2): {date_str}")
                    break
        
        # Try scanning line by line if we still don't have a date
        if not date_extracted:
            lines = text.split('\n')
            for line in lines:
                if 'invoice date' in line.lower() and re.search(r'\d{1,2}-\d{1,2}-\d{4}', line):
                    date_match = re.search(r'(\d{1,2}-\d{1,2}-\d{4})', line)
                    if date_match:
                        date_str = date_match.group(1)
                        info['date'] = self._normalize_date(date_str)
                        date_extracted = True
                        logger.info(f"Detected invoice date (method 3): {date_str}")
                        break
        
        # Extract Hostio company information (supplier)
        info['customer_name'] = 'Hostio Solutions'
        
        # Extract group information
        if 'Access2.IT Group B.V.' in text:
            info['customer_group'] = 'Access2.IT Group B.V.'
            logger.info("Detected customer group: Access2.IT Group B.V.")
        
        # Extract address details
        address_extracted = False
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if 'Curaçaostraat 11' in line:
                info['customer_street'] = 'Curaçaostraat 11'
                logger.info("Detected customer street: Curaçaostraat 11")
                
                # Next line likely has the postal code and city
                if i + 1 < len(lines) and '1339KL Almere' in lines[i+1]:
                    info['customer_postal_city'] = '1339KL Almere'
                    logger.info("Detected customer postal code and city: 1339KL Almere")
                    
                # Next line after that likely has the country
                if i + 2 < len(lines) and 'Netherlands' in lines[i+2]:
                    info['customer_country'] = 'Netherlands'
                    logger.info("Detected customer country: Netherlands")
                    
                address_extracted = True
                break
        
        # Extract IBAN information
        for line in lines:
            if 'IBAN:' in line:
                iban_match = re.search(r'IBAN:\s*([\w\s]+)', line)
                if iban_match:
                    info['customer_iban'] = iban_match.group(1).strip()
                    logger.info(f"Detected customer IBAN: {info['customer_iban']}")
        
        # Extract BIC information
        for line in lines:
            if 'BIC/Swift:' in line:
                bic_match = re.search(r'BIC/Swift:\s*(\w+)', line)
                if bic_match:
                    info['customer_bic'] = bic_match.group(1).strip()
                    logger.info(f"Detected customer BIC: {info['customer_bic']}")
        
        # Extract VAT Number
        for line in lines:
            if 'VAT Number:' in line and not 'BE0537' in line:
                vat_match = re.search(r'VAT Number:\s*([A-Za-z0-9]+)', line)
                if vat_match:
                    info['customer_vat_number'] = vat_match.group(1).strip()
                    logger.info(f"Detected customer VAT number: {info['customer_vat_number']}")
        
        # Check if this is an invoice to our company
        if 'nexon solutions' in text.lower() and 'BE0537.664.664' in text:
            logger.info("This is an invoice TO our company FROM Hostio Solutions")
            info['invoice_type'] = 'expense'
            
            # Store our own VAT number if found
            if 'BE0537.664.664' in text or 'BE 0537.664.664' in text:
                logger.info("Found company VAT number: BE0537664664")
                info['own_vat_number'] = 'BE0537664664'
        else:
            logger.info("This is an invoice FROM our company TO another client")
            info['invoice_type'] = 'income'
                
        # Dump the full text for debugging
        logger.debug(f"Full invoice text for amount detection:\n{text}")
        
        # Extract amount (format: €19.00 EUR) - try multiple patterns
        amount_patterns = [
            # Look for Total amount patterns
            r'Total\s+€(\d+\.\d+)\s*EUR',  # Total €19.00 EUR
            r'Total[\s:]+€(\d+\.\d+)',     # Total: €19.00
            r'Total\s+(\d+\.\d+)\s*EUR',   # Total 19.00 EUR
            r'Total\s*:\s*€?(\d+\.\d+)',   # Total: 19.00 or Total: €19.00
            
            # Look for €19.00 EUR pattern anywhere
            r'€(\d+\.\d+)\s*EUR',  # €19.00 EUR
            
            # Try to match more complex patterns
            r'Sub\s+Total\s+€?(\d+\.\d+)', # Sub Total €19.00
            r'Total\s+€?(\d+\.\d+)\s*EUR', # Total €19.00 EUR or Total 19.00 EUR
            
            # Look for line starting with amount
            r'[\n\r]€(\d+\.\d+)', # Line starting with €19.00
            r'Total\s+[\n\r]€(\d+\.\d+)', # Total then line break then €19.00
            
            # Look for Domains pattern as fallback (specific to Hostio invoices)
            r'Domains:.*?€(\d+\.\d+)\s*EUR',  # Domains: 1 x Per 1000 domains €2.00 EUR
            
            # Look for any number in EUR format as last resort
            r'€(\d+\.\d+)'  # €19.00
        ]
        
        for pattern in amount_patterns:
            amount_match = re.search(pattern, text)
            if amount_match:
                try:
                    amount = float(amount_match.group(1))
                    info['amount_incl_vat'] = amount
                    logger.info(f"Detected amount: €{amount} using pattern: {pattern}")
                    
                    # If we find a total amount (containing the word 'total'), favor it over other amounts
                    if 'total' in pattern.lower():
                        logger.info(f"Found a 'total' amount: €{amount}")
                        break
                    
                    # Continue searching for better matches (like totals) if we find the 'Domains' pattern
                    if 'domains' in pattern.lower() and amount < 10:
                        logger.info(f"Found a 'domains' amount (€{amount}), but will continue looking for the total")
                        continue
                        
                    # For all other patterns, break after finding the first match
                    break
                except Exception as e:
                    logger.warning(f"Error parsing amount: {str(e)}")
        
        # Try a different approach by looking for lines with EUR in them
        if 'amount_incl_vat' not in info:
            lines = text.split('\n')
            for line in lines:
                if 'EUR' in line and '€' in line:
                    # Try to extract the number
                    amount_match = re.search(r'€(\d+\.\d+)', line)
                    if amount_match:
                        try:
                            amount = float(amount_match.group(1))
                            info['amount_incl_vat'] = amount
                            logger.info(f"Detected amount (method 2): €{amount}")
                            break
                        except:
                            pass
        
        # Extract customer information
        if 'Invoiced To' in text:
            parts = text.split('Invoiced To')
            if len(parts) > 1:
                customer_text = parts[1].strip()
                lines = customer_text.split('\n')
                if lines:
                    info['customer_name'] = lines[0].strip()
                    
                    # If there are additional lines, use them as address
                    if len(lines) > 1:
                        info['customer_address'] = '\n'.join(lines[1:-1]).strip()
                    
                    # Look for VAT Number in the customer section
                    for line in lines:
                        if 'VAT Number:' in line or 'BTW' in line:
                            vat_parts = line.split(':')
                            if len(vat_parts) > 1:
                                vat_number = vat_parts[1].strip()
                                # Clean up the VAT number
                                vat_number = vat_number.replace(' ', '')
                                info['customer_vat_number'] = vat_number
                                break
                                
    def _extract_dates(self, text, lower_text, info):
        """Extract various date formats from the document text"""
        date_patterns = [
            # Dutch formats
            r'factuurdatum\s*:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
            r'datum\s*:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
            r'datum factuur\s*:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
            # English formats
            r'invoice date\s*:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
            r'date\s*:?\s*(\d{1,2}[-.\/]\d{1,2}[-.\/]\d{2,4})',
            # Various formats with month names
            r'invoice date\s*:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
            r'factuurdatum\s*:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
            r'datum\s*:?\s*([a-zA-Z]+\s+\d{1,2},?\s*\d{4})',
            # Specific format like 18-10-2024
            r'invoice\s*date:?\s*(\d{2}-\d{2}-\d{4})',
            r'invoice\s*date[^0-9]*(\d{2}-\d{2}-\d{4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    info['date'] = self._normalize_date(date_str)
                    break
                except:
                    pass
                    
    def _extract_amounts(self, text, lower_text, info):
        """Extract monetary amounts from the document text"""
        amount_patterns = [
            # Dutch patterns
            r'totaal\s*(?:incl\.?\s*btw)?\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            r'totaalbedrag\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            r'te\s*betalen\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            r'totaal\s*bedrag\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            r'eindtotaal\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            # English patterns
            r'total\s*(?:incl\.?\s*vat)?\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            r'amount\s*due\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            r'total\s*amount\s*[:,.\-€]\s*([0-9.,€]+)\s*(?:eur|euro)?',
            # Generic patterns
            r'€\s*([0-9.,]+)\s*(?:eur|euro)?',
            r'([0-9.]+,[0-9]{2})\s*(?:eur|euro)',
            r'([0-9]+\.[0-9]{2})\s*(?:eur|euro)',
            r'sub\s*total\s*[:,.\-€]*\s*([0-9.,]+)\s*(?:eur|euro)?',  # For Hostio invoice format
            r'total\s*[:,.\-€]*\s*([0-9.,]+)\s*(?:eur|euro)?',        # General total format
            r'credit\s*[:,.\-€]*\s*([0-9.,]+)\s*(?:eur|euro)?'        # Handle credit lines
        ]
        
        for pattern in amount_patterns:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).strip()
                # Clean up the amount string
                amount_str = amount_str.replace('€', '').replace(' ', '')
                # Handle both decimal notations (1.234,56 and 1,234.56)
                if ',' in amount_str and '.' in amount_str:
                    # European format with thousand separators (1.234,56)
                    if amount_str.find('.') < amount_str.find(','):
                        amount_str = amount_str.replace('.', '').replace(',', '.')
                    # American format (1,234.56)
                    else:
                        amount_str = amount_str.replace(',', '')
                elif ',' in amount_str:
                    # Assume European format (123,45)
                    amount_str = amount_str.replace(',', '.')
                
                try:
                    amount_incl_vat = float(amount_str)
                    info['amount_incl_vat'] = amount_incl_vat
                    break
                except:
                    pass
                    
    def _extract_vat_rate(self, text, lower_text, info):
        """Extract VAT rate from the document text"""
        # Default rate for Belgium is 21%
        vat_rate = 21.0
        
        vat_patterns = [
            # Dutch patterns
            r'btw\s*(?:percentage|tarief|rate)?\s*[:.\-]\s*(\d{1,2})[.,]?(\d{0,2})?\s*%',
            r'btw\s*\((\d{1,2})[.,]?(\d{0,2})?\s*%\)',
            r'(\d{1,2})[.,]?(\d{0,2})?\s*%\s*btw',
            r'tarief\s*(\d{1,2})[.,]?(\d{0,2})?\s*%',
            # English patterns
            r'vat\s*(?:percentage|rate)?\s*[:.\-]\s*(\d{1,2})[.,]?(\d{0,2})?\s*%',
            r'vat\s*\((\d{1,2})[.,]?(\d{0,2})?\s*%\)',
            r'(\d{1,2})[.,]?(\d{0,2})?\s*%\s*vat',
            # Match 21%, 6%, etc.
            r'(\d{1,2})[.,]?(\d{0,2})?\s*%'
        ]
        
        for pattern in vat_patterns:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                try:
                    whole_part = match.group(1)
                    decimal_part = match.group(2) if len(match.groups()) > 1 and match.group(2) else '0'
                    vat_rate = float(f"{whole_part}.{decimal_part}")
                    # Only accept common VAT rates to avoid false positives
                    if vat_rate in [0, 6, 9, 12, 21]:
                        info['vat_rate'] = vat_rate
                        break
                except:
                    pass
        
        # If no rate was found, set the default
        if not info.get('vat_rate'):
            info['vat_rate'] = vat_rate
            
    def _determine_invoice_type(self, text, lower_text, info):
        """Determine if invoice is for income or expense"""
        # Typical markers for income invoices (when we are the seller)
        income_markers = [
            # Dutch
            'uw klantnummer', 'klantnummer', 'clientnummer',
            'factuur aan', 'geleverd aan', 'klant',
            # English
            'your customer number', 'customer number', 'client number',
            'billed to', 'invoice to', 'customer'
        ]
        
        # Typical markers for expense invoices (when we are the buyer)
        expense_markers = [
            # Dutch
            'leverancier', 'factuur van', 'geleverd door',
            # English
            'supplier', 'vendor', 'invoice from'
        ]
        
        # Check if any income markers are present
        is_income = any(marker in lower_text for marker in income_markers)
        
        # Check if any expense markers are present
        is_expense = any(marker in lower_text for marker in expense_markers)
        
        # If we have conflicting signals, favor income if it has "customer" related terms
        if is_income and is_expense:
            info['invoice_type'] = 'income' if 'customer' in lower_text else 'expense'
        elif is_income:
            info['invoice_type'] = 'income'
        else:
            # Default is expense for most uploaded invoices
            info['invoice_type'] = 'expense'
            
    def _extract_invoice_number(self, text, lower_text, info):
        """Extract invoice number from the document text"""
        invoice_patterns = [
            # Dutch patterns
            r'factuurnr\.?\s*[:.\-]\s*([A-Za-z0-9\-\_\/\.]+)',
            r'factuurnummer\s*[:.\-]\s*([A-Za-z0-9\-\_\/\.]+)',
            r'factuur\s*#\s*([A-Za-z0-9\-\_\/\.]+)',
            r'factuurnummer\s*(\d+)',
            r'factuurnr\s*(\d+)',
            # English patterns
            r'invoice\s*#\s*([A-Za-z0-9\-\_\/\.]+)',
            r'invoice\s*number\s*[:.\-]\s*([A-Za-z0-9\-\_\/\.]+)',
            r'invoice\s*no\.?\s*[:.\-]?\s*([A-Za-z0-9\-\_\/\.]+)',
            # Special formats
            r'invoice\s*#(\d{4}-[A-Za-z]{2}-\d+)',  # Format like #2024-HS-1430
            r'f-?[\d]+',  # Simple pattern like F-12345 or F12345
            r'INV-?[\d]+' # Simple pattern like INV-12345 or INV12345
        ]
        
        for pattern in invoice_patterns:
            match = re.search(pattern, lower_text, re.IGNORECASE)
            if match:
                invoice_number = match.group(1).strip() if match.groups() else match.group(0).strip()
                info['invoice_number'] = invoice_number
                break
                
        # If no invoice number was found, generate a placeholder
        if not info.get('invoice_number'):
            info['invoice_number'] = f"AUTO-{uuid.uuid4().hex[:8].upper()}"
            
    def _extract_customer_info(self, text, lower_text, info):
        """Extract customer information from the document text"""
        # Look for common customer information patterns
        customer_section_patterns = [
            # Dutch
            r'(?:klant|client|factuur\s+aan|geadresseerde)(?:gegevens)?[\s:]*\n(.*?)(?:\n\n|\n[A-Z]|$)',
            # English
            r'(?:customer|client|bill\s+to|ship\s+to)(?:\s+information)?[\s:]*\n(.*?)(?:\n\n|\n[A-Z]|$)',
            r'invoiced\s+to\s*\n(.*?)(?:\n\n|\n[A-Z]|$)'
        ]
        
        customer_name = None
        customer_address = None
        customer_vat = None
        
        # Try to extract complete customer section
        for pattern in customer_section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                customer_info = match.group(1).strip()
                lines = customer_info.split('\n')
                if lines:
                    # First line is usually the customer name
                    customer_name = lines[0].strip()
                    info['customer_name'] = customer_name
                    
                    # If there are more lines, use them as address
                    if len(lines) > 1:
                        customer_address = '\n'.join(lines[1:]).strip()
                        info['customer_address'] = customer_address
                break
                
        # If no customer name was found, try simpler patterns
        if not customer_name:
            name_patterns = [
                # From/To patterns
                r'(?:van|from|sender|afzender)[:.\-]\s*([^\n]+)',
                r'(?:aan|to|recipient|ontvanger)[:.\-]\s*([^\n]+)',
                # Role patterns
                r'(?:supplier|leverancier|verkoper|seller)[:.\-]\s*([^\n]+)',
                r'(?:customer|klant|koper|buyer)[:.\-]\s*([^\n]+)'
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    customer_name = match.group(1).strip()
                    info['customer_name'] = customer_name
                    break
                    
        # Extract VAT number
        vat_patterns = [
            # Dutch
            r'btw(?:-|\s)(?:nummer|nr)[:.\-]\s*([A-Za-z0-9\s.]+)',
            r'ondernemingsnummer[:.\-]\s*([A-Za-z0-9\s.]+)',
            # English
            r'vat(?:-|\s)(?:number|no|nr)[:.\-]\s*([A-Za-z0-9\s.]+)',
            r'company\s*number[:.\-]\s*([A-Za-z0-9\s.]+)',
            # Generic format for BE VAT numbers
            r'(?:btw|vat|tva)(?:-|\s)?(?:nummer|number|no)?[:.\s]*(BE\s*\d{4}\.\d{3}\.\d{3})',
            r'(?:btw|vat|tva)(?:-|\s)?(?:nummer|number|no)?[:.\s]*(BE\s*\d{10})',
            # Specific VAT Number format with colon
            r'VAT Number:\s*([A-Za-z0-9]+)'
        ]
        
        for pattern in vat_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                customer_vat = match.group(1).strip()
                # Clean up the VAT number (remove spaces and normalize dots)
                customer_vat = customer_vat.replace(' ', '').replace('.', '')
                info['customer_vat_number'] = customer_vat
                break
    
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
    