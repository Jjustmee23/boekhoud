import os
import json
import logging
import subprocess
import base64
from typing import Dict, Any, List, Tuple
import re
from pathlib import Path
import io

import anthropic
from anthropic import Anthropic
import pytesseract
from PIL import Image
from pdf2image import convert_from_path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIDocumentProcessor:
    """
    Uses AI (Claude) and OCR to extract information from documents
    """
    
    def __init__(self):
        """Initialize the AI document processor with Claude API"""
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.anthropic_key:
            logger.warning("ANTHROPIC_API_KEY not found in environment variables")
        
        if self.anthropic_key:
            self.client = Anthropic(api_key=self.anthropic_key)
            # the newest Anthropic model is "claude-3-5-sonnet-20241022" which was released October 22, 2024
            self.model = "claude-3-5-sonnet-20241022"
        else:
            self.client = None
            self.model = None
            logger.info("Using rule-based document analysis as fallback (no Claude API key available)")
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF using OCR"""
        try:
            # Convert PDF to images
            pages = convert_from_path(pdf_path, 300)
            
            # Extract text from each page
            text_content = ""
            for i, page in enumerate(pages):
                text = pytesseract.image_to_string(page, lang='eng+nld')
                text_content += f"\n--- Page {i+1} ---\n{text}\n"
            
            return text_content
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise Exception(f"PDF text extraction failed: {str(e)}")
    
    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR"""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='eng+nld')
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image: {str(e)}")
            raise Exception(f"Image text extraction failed: {str(e)}")
    
    def analyze_document(self, file_path: str) -> Dict[str, Any]:
        """
        Extract text from document and analyze with Claude
        Returns structured data based on document type
        """
        try:
            logger.info(f"Analyzing document: {file_path}")
            # Check if file exists
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return {
                    'error': f"File does not exist: {file_path}",
                    'file_path': file_path
                }
                
            # Extract text based on file type
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                text_content = self.extract_text_from_pdf(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg']:
                text_content = self.extract_text_from_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_ext}")
            
            # First identify document type
            document_type = self._identify_document_type(text_content)
            
            # Now analyze based on document type
            if document_type == 'invoice':
                result = self._analyze_invoice(text_content, file_path)
            elif document_type == 'bank_statement':
                result = self._analyze_bank_statement(text_content, file_path)
            else:
                result = {
                    'document_type': 'unknown',
                    'confidence': 0.0,
                    'error': 'Document type not recognized',
                    'text_content': text_content[:500] + '...' if len(text_content) > 500 else text_content
                }
            
            # Add file path to result
            result['file_path'] = file_path
            
            return result
        except Exception as e:
            logger.error(f"Error analyzing document: {str(e)}")
            return {
                'error': str(e),
                'file_path': file_path
            }
    
    def _identify_document_type(self, text_content: str) -> str:
        """Identify document type using Claude or rule-based fallback"""
        # Fallback rule-based document identification (when Claude API is unavailable)
        def identify_by_rules(text):
            # Convert to lowercase for case-insensitive matching
            text_lower = text.lower()
            
            # Invoice detection keywords
            invoice_keywords = [
                'invoice', 'factuur', 'facture', 'rechnung', 'bill', 
                'amount due', 'bedrag verschuldigd', 'payment due', 'betaling verschuldigd',
                'tax', 'btw', 'vat', 'subtotal', 'total', 'totaal',
                'customer', 'klant', 'client', 'purchase', 'order'
            ]
            invoice_count = sum(1 for keyword in invoice_keywords if keyword in text_lower)
            
            # Bank statement detection keywords
            bank_keywords = [
                'bank statement', 'rekeningafschrift', 'account statement', 'transactie', 'transaction',
                'opening balance', 'closing balance', 'beginsaldo', 'eindsaldo',
                'withdrawal', 'opname', 'deposit', 'storting', 'credit', 'debit',
                'interest', 'rente', 'banking', 'bank', 'rekeningnummer', 'account number'
            ]
            bank_count = sum(1 for keyword in bank_keywords if keyword in text_lower)
            
            # Determine document type based on keyword counts
            if invoice_count > bank_count and invoice_count >= 3:
                return 'invoice'
            elif bank_count > invoice_count and bank_count >= 3:
                return 'bank_statement'
            else:
                # Check for specific strong indicators
                if re.search(r'invoice\s+number|invoice\s+#|factuurnummer', text_lower):
                    return 'invoice'
                elif re.search(r'bank\s+statement|statement\s+date|afschrift\s+datum', text_lower):
                    return 'bank_statement'
                
                # Default when uncertain
                return 'unknown'
        
        # First try Claude API
        try:
            if not self.anthropic_key:
                logger.warning("No Anthropic API key provided, using rule-based identification")
                return identify_by_rules(text_content)
                
            # Create prompt for document type identification
            prompt = f"""
            You are a document analyst. Analyze the following document text and identify what type of document it is.
            
            Document types:
            - invoice: A bill requesting payment from a customer, containing items, prices, tax rates, etc.
            - bank_statement: A document from a bank showing account activity, transactions, balances, etc.
            - unknown: Any other document type
            
            Document text:
            ---
            {text_content[:8000]}  # Limit content to avoid exceeding context window
            ---
            
            Respond in JSON format with:
            {{
                "document_type": "invoice|bank_statement|unknown",
                "confidence": 0.0-1.0,  # Your confidence in the identification
                "reasoning": "brief explanation"
            }}
            """
            
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0,
                system="You are a document analysis assistant that identifies document types accurately and responds in valid JSON format.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract and parse JSON from response
            content = response.content[0].text
            # Find JSON object in the response
            matches = re.search(r'({.*})', content, re.DOTALL)
            if matches:
                json_str = matches.group(1)
                result = json.loads(json_str)
                return result.get('document_type', 'unknown')
            else:
                logger.error("No JSON found in Claude's response")
                return identify_by_rules(text_content)
                
        except Exception as e:
            logger.error(f"Error identifying document type: {str(e)}")
            logger.info("Falling back to rule-based document identification")
            return identify_by_rules(text_content)
    
    def _analyze_invoice(self, text_content: str, file_path: str) -> Dict[str, Any]:
        """Extract invoice information using Claude or basic regex fallback"""
        # Fallback method for invoice extraction when Claude API is unavailable
        def extract_invoice_info_from_text(text):
            text_lower = text.lower()
            lines = text.splitlines()
            
            # Initialize result with default values
            result = {
                'document_type': 'invoice',
                'confidence': 0.5,  # Medium confidence for rule-based extraction
                'invoice_number': None,
                'date': None,
                'amount_excl_vat': None,
                'amount_incl_vat': None,
                'vat_amount': None,
                'vat_rate': 21,  # Default Belgian VAT rate
                'invoice_type': 'expense',  # Default to expense
                'seller': {
                    'name': None,
                    'address': None,
                    'vat_number': None,
                    'email': None
                },
                'buyer': {
                    'name': None,
                    'address': None,
                    'vat_number': None,
                    'email': None
                }
            }
            
            # Try to extract invoice number
            invoice_patterns = [
                r'(?:invoice|factuur)\s*(?:[-#:;]|number|nr\.?|nummer|no\.?)?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'(?:invoice|factuur)(?:[-#:;]|number|nr\.?|nummer|no\.?)?\s*[:;. ]*\s*#\s*([A-Za-z0-9\-_/\.]+)',
                r'(?:invoice|factuur)(?:[-#:;]|number|nr\.?|nummer|no\.?)?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'(?:facture|rekening|bill)\s*(?:[-#:;]|number|nr\.?|nummer|no\.?)?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'factuurnr\.?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'factuurnummer\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'nummer\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'klantnummer\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'(?<!\w)nr\.?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'(?<!\w)no\.?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'facture\s*n[o°]?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'rechnung\s*(?:nr|nummer)?\s*[:;. ]*\s*([A-Za-z0-9\-_/\.]+)',
                r'invoice\s+(?:date|datum).{1,30}((?:VF|HS)[-\s]*\d+)', # VirtFusion format
                r'((?:VF|HS)[-\s]*\d+)' # VirtFusion/HostingSolutions format as standalone
            ]
            
            # First check in header area
            header_text = '\n'.join(lines[:min(10, len(lines))])
            header_text_lower = header_text.lower()
            
            for pattern in invoice_patterns:
                match = re.search(pattern, header_text_lower)
                if match:
                    result['invoice_number'] = match.group(1).strip()
                    break
            
            # Then check in full text if not found
            if not result['invoice_number']:
                for pattern in invoice_patterns:
                    match = re.search(pattern, text_lower)
                    if match:
                        result['invoice_number'] = match.group(1).strip()
                        break
                    
            # Try to extract date
            date_patterns = [
                r'(?:invoice|facture|fact\.|factuur|factuurdatum)\s*(?:date|datum)\s*[:;. ]*\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:date|datum)(?:\s+of\s+invoice|\s+van\s+factuur)?\s*[:;. ]*\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:date|datum)(?:\s+of\s+invoice|\s+van\s+factuur)?\s*[:;. ]*\s*(\d{1,2}\s+[a-z]{3,}\s+\d{2,4})',
                r'(?:invoice|factuur)\s*(?:date|datum)\s*[:;. ]*\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:invoice|factuur)\s*(?:date|datum)\s*[:;. ]*\s*(\d{1,2}\s+[a-z]{3,}\s+\d{2,4})',
                r'(?:invoice|factuur|bill|rekening)\s*[:;.]\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:issued|issued\s+date|uitgegeven|uitgegeven\s+op)\s*[:;. ]*\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:issued|issued\s+date|uitgegeven|uitgegeven\s+op)\s*[:;. ]*\s*(\d{1,2}\s+[a-z]{3,}\s+\d{2,4})',
                # Month names in Dutch and English
                r'(\d{1,2}\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december|january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2,4})',
                # Standard date formats
                r'\b(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})\b'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Try to convert to YYYY-MM-DD format
                    date_str = match.group(1).strip()
                    # Very basic conversion - in real app would need more robust date parsing
                    if re.match(r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}', date_str):
                        parts = re.split(r'[-/\.]', date_str)
                        if len(parts) == 3:
                            # Assuming day-month-year format
                            day, month, year = parts
                            if len(year) == 2:
                                year = '20' + year
                            result['date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            break
            
            # Try to extract amounts using regex
            amount_patterns = [
                # For amount_excl_vat (bedrag exclusief BTW)
                (r'(?:total|totaal|subtotal|subtotaal|sub-totaal|total amount|net amount|net|netto)\s*(?:excl\.?|excluding|zonder|excl|ex)[.\s]*(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_excl_vat'),
                (r'(?:subtotal|subtotaal|sub-totaal)\s*[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_excl_vat'),
                (r'(?:amount|bedrag)(?:\s+excl\.?|\s+excluding|\s+zonder|\s+excl|\s+ex)[.\s]*(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_excl_vat'),
                (r'(?:excl\.?|excluding|zonder|excl|ex)[.\s]*(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_excl_vat'),
                (r'(?:netto\s+)?(?:bedrag|amount)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)\s*(?:excl\.?|excluding|zonder|excl|ex)[.\s]*(?:vat|btw)', 'amount_excl_vat'),
                
                # For amount_incl_vat (bedrag inclusief BTW)
                (r'(?:total|totaal|eindtotaal|te\s+betalen|to\s+pay|amount\s+due|grand\s+total)\s*(?:incl\.?|including|inclusief|met|incl)[.\s]*(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_incl_vat'),
                (r'(?:amount|bedrag)(?:\s+incl\.?|\s+including|\s+met|\s+inclusief|\s+incl)[.\s]*(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_incl_vat'),
                (r'(?:incl\.?|including|inclusief|met|incl)[.\s]*(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_incl_vat'),
                (r'(?:to\s+pay|te\s+betalen|balance\s+due|amount\s+due|grand\s+total|eindtotaal)\s*[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_incl_vat'),
                (r'(?:bruto\s+)?(?:bedrag|amount)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)\s*(?:incl\.?|including|inclusief|met|incl)[.\s]*(?:vat|btw)', 'amount_incl_vat'),
                
                # Last resort - total without qualification (usually incl_vat)
                (r'(?:total|totaal|total amount|totaalbedrag)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'amount_incl_vat'),
                
                # For VAT amount
                (r'(?:vat|btw)(?:\s+amount|\s+bedrag)?[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'vat_amount'),
                (r'(?:vat|btw)[.\s:]*\s*(?:[€$£]|\beur\b)?\s*(\d+[.,]\d+)', 'vat_amount'),
                
                # For VAT rate
                (r'(?:vat|btw)(?:\s+rate|\s+tarief|\s+percentage|\s+%)?[.\s:%]*\s*(\d+)[.,]?(\d*)\s*%?', 'vat_rate'),
                (r'(?:rate|tarief|percentage)[.\s:%]*\s*(\d+)[.,]?(\d*)\s*%', 'vat_rate')
            ]
            
            for pattern, field in amount_patterns:
                match = re.search(pattern, text_lower)
                if match and field != 'vat_rate':
                    # Convert string amount to float
                    amount_str = match.group(1).replace(',', '.')
                    try:
                        result[field] = float(amount_str)
                    except ValueError:
                        pass
                elif match and field == 'vat_rate':
                    # Extract VAT rate percentage
                    rate = match.group(1)
                    if match.group(2):
                        rate += '.' + match.group(2)
                    try:
                        result['vat_rate'] = float(rate)
                    except ValueError:
                        pass
            
            # Extract seller and buyer info
            company_patterns = [
                (r'(?:from|van|seller|verkoper|company|bedrijf)[.\s:]*\s*([A-Za-z0-9\s]+(?:B\.?V\.?|N\.?V\.?|S\.?A\.?|Ltd\.?|Inc\.?|GmbH)?)', 'seller'),
                (r'(?:bill to|aan|buyer|koper|client|klant)[.\s:]*\s*([A-Za-z0-9\s]+(?:B\.?V\.?|N\.?V\.?|S\.?A\.?|Ltd\.?|Inc\.?|GmbH)?)', 'buyer')
            ]
            
            # Advanced company name detection
            # First 5-10 lines often have company info
            header_text = '\n'.join(lines[:min(10, len(lines))])
            header_text_lower = header_text.lower()
            
            # Try to find company names directly in document
            for pattern, entity_type in company_patterns:
                match = re.search(pattern, header_text_lower)
                if match and entity_type == 'seller' and not result['seller']['name']:
                    result['seller']['name'] = match.group(1).strip()
                elif match and entity_type == 'buyer' and not result['buyer']['name']:
                    result['buyer']['name'] = match.group(1).strip()
            
            # For invoices with specific formats
            # VirtFusion and similar hosted service invoices typically have seller at top left
            if not result['seller']['name'] and len(lines) > 5:
                # Try first line if it looks like a company name
                if re.match(r'^[A-Za-z0-9\s]+(?:B\.?V\.?|N\.?V\.?|S\.?A\.?|Ltd\.?|Inc\.?|GmbH)?$', lines[0].strip()):
                    result['seller']['name'] = lines[0].strip()
                # Or look for logo labels that might be company names
                elif re.search(r'VirtFusion|Virtfusion|virtfusion', text):
                    result['seller']['name'] = "VirtFusion"
            
            # Try to find company names in text structure
            seller_found = result['seller']['name'] is not None
            buyer_found = result['buyer']['name'] is not None
            
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                # Look for invoice or buyer/seller indicators
                if not seller_found and any(x in line_lower for x in ['from:', 'van:', 'seller:', 'verkoper:', 'invoice from:', 'factuur van:']):
                    # Next line might be the company name
                    if i+1 < len(lines) and lines[i+1].strip():
                        result['seller']['name'] = lines[i+1].strip()
                        seller_found = True
                        # Next few lines might be address
                        address_lines = []
                        for j in range(i+2, min(i+5, len(lines))):
                            if lines[j].strip() and not any(x in lines[j].lower() for x in ['vat', 'btw', 'email', 'tel']):
                                address_lines.append(lines[j].strip())
                            else:
                                break
                        if address_lines:
                            result['seller']['address'] = ' '.join(address_lines)
                
                if not buyer_found and any(x in line_lower for x in ['to:', 'aan:', 'buyer:', 'koper:', 'bill to:', 'invoice to:', 'factuur aan:']):
                    # Next line might be the company name
                    if i+1 < len(lines) and lines[i+1].strip():
                        result['buyer']['name'] = lines[i+1].strip()
                        buyer_found = True
                        # Next few lines might be address
                        address_lines = []
                        for j in range(i+2, min(i+5, len(lines))):
                            if lines[j].strip() and not any(x in lines[j].lower() for x in ['vat', 'btw', 'email', 'tel']):
                                address_lines.append(lines[j].strip())
                            else:
                                break
                        if address_lines:
                            result['buyer']['address'] = ' '.join(address_lines)
                            
                # For invoices with specific layouts
                # Look for "Customer:" or "Klant:" followed by name
                if not buyer_found:
                    customer_match = re.search(r'(?:customer|klant)[:\s]+([A-Za-z0-9\s]+)', line_lower)
                    if customer_match:
                        result['buyer']['name'] = customer_match.group(1).strip().title()
                        buyer_found = True
                        
                # Generic company name detection for first few lines
                if i < 5 and not seller_found and len(line) > 3 and len(line) < 40:
                    # If a line looks like it could be a company name at the top of the invoice
                    # and doesn't contain common header words
                    common_header_words = ['invoice', 'factuur', 'date', 'datum', 'number', 'nummer', 'page', 'pagina']
                    if not any(word in line_lower for word in common_header_words):
                        if re.match(r'^[A-Za-z0-9\s\.,-]+$', line):
                            result['seller']['name'] = line.strip()
                            seller_found = True
                            
                # Look for common patterns in specific invoice types
                if 'virtfusion' in line_lower and not seller_found:
                    result['seller']['name'] = "VirtFusion"
                    seller_found = True
            
            # Extract VAT numbers
            vat_patterns = [
                # Standard VAT patterns with label
                (r'(?:vat|btw|tva|vatin|tax\s+id)(?:\s*id|\s*number|\s*nr|\s*nummer)?[.\s:]*\s*((?:[A-Za-z]{2})?[0-9]{8,12})', 'vat_number'),
                (r'(?:vat|btw|tva|vatin|tax\s+id)(?:\s*id|\s*number|\s*nr|\s*nummer)?[.\s:]*\s*([A-Za-z]{2}\s*[0-9]{8,12})', 'vat_number'),
                # Country-specific VAT patterns
                (r'be\s*0?[0-9]{9}', 'vat_number'),  # Belgian
                (r'nl\s*[0-9]{9}B[0-9]{2}', 'vat_number'),  # Dutch
                (r'lu\s*[0-9]{8}', 'vat_number'),  # Luxembourg
                (r'fr\s*[0-9A-Z]{2}\s*[0-9]{9}', 'vat_number'),  # French
                (r'de\s*[0-9]{9}', 'vat_number'),  # German
                (r'gb\s*[0-9]{9}', 'vat_number'),  # UK (GB)
                (r'gb\s*[0-9]{12}', 'vat_number'),  # UK (GB)
                # Random formats that appear in invoices
                (r'ondernemingnummer[.\s:]*\s*([0-9]{4}\.[0-9]{3}\.[0-9]{3})', 'vat_number'),  # Belgian enterprise number
                (r'ondernemingsnummer[.\s:]*\s*([0-9]{4}\.[0-9]{3}\.[0-9]{3})', 'vat_number'),  # Belgian enterprise number
                (r'btw[.\s:]*\s*([A-Za-z]{2}[0-9]{4}\.[0-9]{3}\.[0-9]{3})', 'vat_number'),  # Belgian VAT with dots
                (r'btw[.\s:]*\s*([A-Za-z]{2}[0-9]{4}[0-9]{3}[0-9]{3})', 'vat_number'),  # Belgian VAT without dots
                # Direct patterns without labels (careful to avoid false positives)
                (r'\b([A-Za-z]{2}[0-9]{9,12})\b', 'vat_number'),  # General EU VAT pattern
                (r'\b(BE0[0-9]{9})\b', 'vat_number'),  # Specific Belgian pattern
                (r'\b(BE\s+0[0-9]{3}\s+[0-9]{3}\s+[0-9]{3})\b', 'vat_number')  # Belgian with spaces
            ]
            
            for i, line in enumerate(lines):
                line_lower = line.lower().strip()
                
                # Check if line contains VAT number
                for pattern, field in vat_patterns:
                    match = re.search(pattern, line_lower)
                    if match:
                        vat_num = match.group(1).strip()
                        # Normalize VAT number format
                        if vat_num:
                            # Add BE prefix if missing and looks like Belgian VAT
                            if not vat_num.upper().startswith('BE') and re.match(r'0?[0-9]{9}', vat_num):
                                vat_num = 'BE' + vat_num.zfill(10)
                            # Remove spaces
                            vat_num = vat_num.replace(' ', '')
                            
                            # Assign to seller or buyer based on context
                            if any(x in line_lower for x in ['seller', 'verkoper', 'from']):
                                result['seller']['vat_number'] = vat_num.upper()
                            elif any(x in line_lower for x in ['buyer', 'koper', 'to', 'client']):
                                result['buyer']['vat_number'] = vat_num.upper()
                            else:
                                # If no clear indicator, assign to seller by default
                                result['seller']['vat_number'] = vat_num.upper()
            
            # Extract email addresses
            email_pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+'
            for i, line in enumerate(lines):
                match = re.search(email_pattern, line)
                if match:
                    email = match.group(0)
                    # Determine if seller or buyer based on context
                    if i > 0 and any(x in lines[i-1].lower() for x in ['seller', 'verkoper', 'from']):
                        result['seller']['email'] = email
                    elif i > 0 and any(x in lines[i-1].lower() for x in ['buyer', 'koper', 'to', 'client']):
                        result['buyer']['email'] = email
                    else:
                        # If no clear indicator, assign to seller by default
                        result['seller']['email'] = email
            
            # Determine if income or expense
            # This is a simplistic approach - in real implementation would need more logic
            if 'income' in text_lower or 'omzet' in text_lower:
                result['invoice_type'] = 'income'
            
            # Calculate missing amounts if possible
            if result['amount_incl_vat'] is not None and result['amount_excl_vat'] is None and result['vat_rate'] is not None:
                result['amount_excl_vat'] = result['amount_incl_vat'] / (1 + result['vat_rate']/100)
                result['vat_amount'] = result['amount_incl_vat'] - result['amount_excl_vat']
            elif result['amount_excl_vat'] is not None and result['amount_incl_vat'] is None and result['vat_rate'] is not None:
                result['vat_amount'] = result['amount_excl_vat'] * (result['vat_rate']/100)
                result['amount_incl_vat'] = result['amount_excl_vat'] + result['vat_amount']
            
            return result
        
        # First try Claude API if available
        if not self.anthropic_key:
            logger.warning("No Anthropic API key provided, using rule-based invoice extraction")
            return extract_invoice_info_from_text(text_content)
            
        prompt = f"""
        You are a financial document analyst. Analyze the following invoice text and extract key information.
        
        Invoice text:
        ---
        {text_content[:8000]}  # Limit content to avoid exceeding context window
        ---
        
        Respond in JSON format with:
        {{
            "document_type": "invoice",
            "confidence": 0.0-1.0,  # Your confidence in the extraction
            "invoice_number": "string",
            "date": "YYYY-MM-DD",
            "amount_excl_vat": float or null,
            "amount_incl_vat": float or null,
            "vat_amount": float or null,
            "vat_rate": float (percentage) or null,
            "invoice_type": "income|expense",
            "seller": {{
                "name": "string",
                "address": "string",
                "vat_number": "string",
                "email": "string"
            }},
            "buyer": {{
                "name": "string",
                "address": "string",
                "vat_number": "string",
                "email": "string"
            }},
            "line_items": [
                {{
                    "description": "string",
                    "quantity": float or null,
                    "unit_price": float or null,
                    "amount": float or null
                }}
            ]
        }}
        
        For VAT numbers, normalize them to standard format. For example, Belgian VAT numbers should be in the format "BE0123456789".
        Include confidence level based on how clearly the information is presented in the document.
        """
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                system="You are a financial document analysis assistant that extracts information from invoices accurately and responds in valid JSON format. Belgian VAT numbers should be formatted as BE0123456789.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract and parse JSON from response
            content = response.content[0].text
            # Find JSON object in the response
            matches = re.search(r'({.*})', content, re.DOTALL)
            if matches:
                json_str = matches.group(1)
                result = json.loads(json_str)
                return result
            else:
                logger.error("No JSON found in Claude's response")
                return extract_invoice_info_from_text(text_content)
                
        except Exception as e:
            logger.error(f"Error analyzing invoice: {str(e)}")
            logger.info("Falling back to rule-based invoice extraction")
            return extract_invoice_info_from_text(text_content)
    
    def _analyze_bank_statement(self, text_content: str, file_path: str) -> Dict[str, Any]:
        """Extract bank statement information using Claude or basic regex fallback"""
        # Fallback method for bank statement extraction when Claude API is unavailable
        def extract_bank_statement_info_from_text(text):
            text_lower = text.lower()
            lines = text.splitlines()
            
            # Initialize result with default values
            result = {
                'document_type': 'bank_statement',
                'confidence': 0.5,  # Medium confidence for rule-based extraction
                'bank_name': None,
                'account_number': None,
                'statement_date': None,
                'statement_period': None,
                'opening_balance': None,
                'closing_balance': None,
                'currency': '€',  # Default to Euro
                'transactions': []
            }
            
            # Try to extract bank name
            bank_name_patterns = [
                r'(ing\s+bank)',
                r'(bnp\s+paribas\s+fortis)',
                r'(kbc\s+bank)',
                r'(belfius\s+bank)',
                r'(argenta\s+bank)',
                r'(axa\s+bank)',
                r'(deutsche\s+bank)',
                r'(beobank)',
                r'(crelan)',
                r'(rabobank)'
            ]
            
            for pattern in bank_name_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    result['bank_name'] = match.group(1).strip().title()
                    break
                    
            if not result['bank_name']:
                # Try to find any word followed by "Bank"
                bank_match = re.search(r'(\w+)\s+bank', text_lower)
                if bank_match:
                    result['bank_name'] = bank_match.group(0).strip().title()
            
            # Try to extract account number
            account_patterns = [
                r'(?:account(?:\s+number)?|rekening(?:\s*nummer)?|no\.?|nr\.?)[:;. ]\s*([A-Z]{2}\d{2}[\s-]?[A-Z0-9]{4}[\s-]?[A-Z0-9]{4}[\s-]?[A-Z0-9]{4})',
                r'(?:iban)[:;. ]\s*([A-Z]{2}\d{2}[\s-]?[A-Z0-9]{4}[\s-]?[A-Z0-9]{4}[\s-]?[A-Z0-9]{4})',
                r'([A-Z]{2}\d{2}[\s-]?[A-Z0-9]{4}[\s-]?[A-Z0-9]{4}[\s-]?[A-Z0-9]{4})'
            ]
            
            for pattern in account_patterns:
                match = re.search(pattern, text)
                if match:
                    # Normalize account number format (remove spaces)
                    result['account_number'] = match.group(1).replace(' ', '').replace('-', '')
                    break
            
            # Try to extract date
            date_patterns = [
                r'(?:statement|afschrift)(?:\s+date|\s+datum)[:;. ]\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:date|datum)[:;. ]\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(?:date|datum)[:;. ]\s*(\d{1,2}\s+[a-z]{3,}\s+\d{2,4})'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Try to convert to YYYY-MM-DD format
                    date_str = match.group(1).strip()
                    # Very basic conversion - in real app would need more robust date parsing
                    if re.match(r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}', date_str):
                        parts = re.split(r'[-/\.]', date_str)
                        if len(parts) == 3:
                            # Assuming day-month-year format
                            day, month, year = parts
                            if len(year) == 2:
                                year = '20' + year
                            result['statement_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            break
            
            # Try to extract statement period
            period_patterns = [
                r'(?:period|periode)[:;. ]\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})\s*(?:to|tot|[-/\.])\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})',
                r'(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})\s*(?:to|tot|[-/\.])\s*(\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4})'
            ]
            
            for pattern in period_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Simplistic approach - just use the raw match
                    result['statement_period'] = f"{match.group(1)} to {match.group(2)}"
                    break
            
            # Try to extract balances
            balance_patterns = [
                (r'(?:opening|begin)(?:\s+balance|\s+saldo)[:;. ]\s*(?:[€$£]|\beur\b)?\s*([+-]?\d+[.,]\d+)', 'opening_balance'),
                (r'(?:closing|eind)(?:\s+balance|\s+saldo)[:;. ]\s*(?:[€$£]|\beur\b)?\s*([+-]?\d+[.,]\d+)', 'closing_balance'),
                (r'(?:balance|saldo)(?:\s+brought\s+forward|\s+opening|\s+begin)[:;. ]\s*(?:[€$£]|\beur\b)?\s*([+-]?\d+[.,]\d+)', 'opening_balance'),
                (r'(?:balance|saldo)(?:\s+carried\s+forward|\s+closing|\s+eind)[:;. ]\s*(?:[€$£]|\beur\b)?\s*([+-]?\d+[.,]\d+)', 'closing_balance')
            ]
            
            for pattern, field in balance_patterns:
                match = re.search(pattern, text_lower)
                if match:
                    # Convert string amount to float
                    amount_str = match.group(1).replace(',', '.')
                    try:
                        result[field] = float(amount_str)
                    except ValueError:
                        pass
            
            # Try to extract transactions
            # This is a very simplistic approach - in a real implementation would need more robust parsing
            transaction_date_pattern = r'\b(\d{1,2}[-/\.]\d{1,2}(?:[-/\.]\d{2,4})?)\b'
            transaction_amount_pattern = r'\b([+-]?\d+[.,]\d+)\b'
            
            # Look for transaction sections in the document
            transaction_section = False
            current_transaction = {}
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this might be a transaction line
                date_match = re.search(transaction_date_pattern, line)
                amount_match = re.search(transaction_amount_pattern, line)
                
                if date_match and amount_match:
                    # This looks like a transaction line
                    transaction_section = True
                    
                    # Get the date
                    date_str = date_match.group(1)
                    # Simple date conversion (not robust)
                    if re.match(r'\d{1,2}[-/\.]\d{1,2}[-/\.]\d{2,4}', date_str):
                        parts = re.split(r'[-/\.]', date_str)
                        if len(parts) == 3:
                            day, month, year = parts
                            if len(year) == 2:
                                year = '20' + year
                            date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        else:
                            date = date_str
                    else:
                        date = date_str
                    
                    # Get the amount
                    amount_str = amount_match.group(1).replace(',', '.')
                    try:
                        amount = float(amount_str)
                        # Determine transaction type
                        if amount < 0:
                            ttype = 'debit'
                        else:
                            ttype = 'credit'
                        
                        # Extract description (everything except date and amount)
                        description = line
                        # Remove date
                        description = re.sub(transaction_date_pattern, '', description)
                        # Remove amount
                        description = re.sub(transaction_amount_pattern, '', description)
                        # Clean up
                        description = re.sub(r'\s+', ' ', description).strip()
                        
                        # Add transaction
                        result['transactions'].append({
                            'date': date,
                            'description': description,
                            'amount': abs(amount),  # Store absolute value
                            'type': ttype
                        })
                    except ValueError:
                        pass
            
            # Extract currency
            currency_match = re.search(r'(?:currency|valuta|munt)[:;. ]\s*([A-Z]{3})', text)
            if currency_match:
                result['currency'] = currency_match.group(1)
            else:
                # Look for currency symbols
                if '€' in text:
                    result['currency'] = '€'
                elif '$' in text:
                    result['currency'] = '$'
                elif '£' in text:
                    result['currency'] = '£'
                
            return result
        
        # First try Claude API if available
        if not self.anthropic_key:
            logger.warning("No Anthropic API key provided, using rule-based bank statement extraction")
            return extract_bank_statement_info_from_text(text_content)
            
        prompt = f"""
        You are a financial document analyst. Analyze the following bank statement text and extract key information.
        
        Bank Statement text:
        ---
        {text_content[:8000]}  # Limit content to avoid exceeding context window
        ---
        
        Respond in JSON format with:
        {{
            "document_type": "bank_statement",
            "confidence": 0.0-1.0,  # Your confidence in the extraction
            "bank_name": "string",
            "account_number": "string",
            "statement_date": "YYYY-MM-DD",
            "statement_period": "string",
            "opening_balance": float or null,
            "closing_balance": float or null,
            "currency": "string",
            "transactions": [
                {{
                    "date": "YYYY-MM-DD",
                    "description": "string",
                    "amount": float,
                    "type": "credit|debit"
                }}
            ]
        }}
        
        Include confidence level based on how clearly the information is presented in the document.
        """
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0,
                system="You are a financial document analysis assistant that extracts information from bank statements accurately and responds in valid JSON format.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract and parse JSON from response
            content = response.content[0].text
            # Find JSON object in the response
            matches = re.search(r'({.*})', content, re.DOTALL)
            if matches:
                json_str = matches.group(1)
                result = json.loads(json_str)
                return result
            else:
                logger.error("No JSON found in Claude's response")
                return extract_bank_statement_info_from_text(text_content)
                
        except Exception as e:
            logger.error(f"Error analyzing bank statement: {str(e)}")
            logger.info("Falling back to rule-based bank statement extraction")
            return extract_bank_statement_info_from_text(text_content)