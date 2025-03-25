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
        
        self.client = Anthropic(api_key=self.anthropic_key)
        # the newest Anthropic model is "claude-3-5-sonnet-20241022" which was released October 22, 2024
        self.model = "claude-3-5-sonnet-20241022"
    
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
        """Identify document type using Claude"""
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
        
        try:
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
                return 'unknown'
                
        except Exception as e:
            logger.error(f"Error identifying document type: {str(e)}")
            return 'unknown'
    
    def _analyze_invoice(self, text_content: str, file_path: str) -> Dict[str, Any]:
        """Extract invoice information using Claude"""
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
                return {
                    'document_type': 'invoice',
                    'confidence': 0.0,
                    'error': "Failed to parse Claude's response"
                }
                
        except Exception as e:
            logger.error(f"Error analyzing invoice: {str(e)}")
            return {
                'document_type': 'invoice',
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _analyze_bank_statement(self, text_content: str, file_path: str) -> Dict[str, Any]:
        """Extract bank statement information using Claude"""
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
                return {
                    'document_type': 'bank_statement',
                    'confidence': 0.0,
                    'error': "Failed to parse Claude's response"
                }
                
        except Exception as e:
            logger.error(f"Error analyzing bank statement: {str(e)}")
            return {
                'document_type': 'bank_statement',
                'confidence': 0.0,
                'error': str(e)
            }