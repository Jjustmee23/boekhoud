from datetime import datetime, date, timedelta
import uuid
import json
import os
import logging
from decimal import Decimal
from database import db
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Legacy in-memory storage (will be deprecated)
customers = {}  # id -> customer
invoices = {}   # id -> invoice

# Database models

class InvoiceItem(db.Model):
    """Invoice item model for detailed invoice lines"""
    __tablename__ = 'invoice_items'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = db.Column(UUID(as_uuid=True), db.ForeignKey('invoices.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Float, default=1.0, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    vat_rate = db.Column(db.Float, nullable=False, default=21.0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relationship to invoice
    invoice = db.relationship('Invoice', back_populates='items')
    
    def to_dict(self):
        """Convert item to dictionary for serialization"""
        return {
            'id': str(self.id),
            'invoice_id': str(self.invoice_id),
            'description': self.description,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'vat_rate': self.vat_rate,
            'total_without_vat': self.quantity * self.unit_price,
            'total_with_vat': self.quantity * self.unit_price * (1 + self.vat_rate / 100)
        }
class Customer(db.Model):
    __tablename__ = 'customers'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name = db.Column(db.String(100), nullable=False)
    vat_number = db.Column(db.String(20))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    street = db.Column(db.String(100))
    house_number = db.Column(db.String(10))
    postal_code = db.Column(db.String(10))
    city = db.Column(db.String(50))
    country = db.Column(db.String(50), default='België')
    customer_type = db.Column(db.String(20), default='business')  # business, individual, supplier
    
    # WHMCS integratie
    whmcs_client_id = db.Column(db.Integer, nullable=True)
    synced_from_whmcs = db.Column(db.Boolean, default=False)
    whmcs_last_sync = db.Column(db.DateTime, nullable=True)
    
    # Workspace relationship
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'))
    workspace = db.relationship('Workspace', back_populates='customers')
    default_vat_rate = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relationship to invoices
    invoices = db.relationship('Invoice', back_populates='customer', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'company_name': self.company_name,
            'vat_number': self.vat_number,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'street': self.street,
            'house_number': self.house_number,
            'postal_code': self.postal_code,
            'city': self.city,
            'country': self.country,
            'customer_type': self.customer_type,
            'default_vat_rate': self.default_vat_rate,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'name': self.name,
            'address': self.address
        }
        
    @property
    def name(self):
        """For compatibility with existing code"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.company_name
        
    @property
    def address(self):
        """For compatibility with existing code"""
        address_parts = []
        if self.street and self.house_number:
            address_parts.append(f"{self.street} {self.house_number}")
        if self.postal_code and self.city:
            address_parts.append(f"{self.postal_code} {self.city}")
        if self.country:
            address_parts.append(self.country)
        return ", ".join(address_parts)

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number = db.Column(db.String(20), nullable=False)
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    invoice_type = db.Column(db.String(10), nullable=False)  # income, expense
    amount_excl_vat = db.Column(db.Float, nullable=False)
    amount_incl_vat = db.Column(db.Float, nullable=False)
    vat_rate = db.Column(db.Float, nullable=False)
    vat_amount = db.Column(db.Float, nullable=False)
    file_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='processed')  # processed, unprocessed, paid, overdue, cancelled
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # WHMCS integratie
    whmcs_invoice_id = db.Column(db.Integer, nullable=True)
    synced_from_whmcs = db.Column(db.Boolean, default=False)
    whmcs_last_sync = db.Column(db.DateTime, nullable=True)
    
    # Workspace relationship
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'))
    workspace = db.relationship('Workspace', back_populates='invoices')
    
    # Relationship to customer
    customer = db.relationship('Customer', back_populates='invoices')
    
    # Relationship to invoice items
    items = db.relationship('InvoiceItem', back_populates='invoice', cascade='all, delete-orphan')
    
    # Make invoice_number unique per workspace
    __table_args__ = (
        sa.UniqueConstraint('invoice_number', 'workspace_id', name='uix_invoice_number_workspace'),
        {'extend_existing': True}  # Hiermee dwingen we SQLAlchemy om de tabel te updaten, zelfs als deze al bestaat
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'invoice_number': self.invoice_number,
            'customer_id': str(self.customer_id),
            'date': self.date.strftime('%Y-%m-%d') if isinstance(self.date, date) else self.date,
            'invoice_type': self.invoice_type,
            'amount_excl_vat': self.amount_excl_vat,
            'amount_incl_vat': self.amount_incl_vat,
            'vat_rate': self.vat_rate,
            'vat_amount': self.vat_amount,
            'file_path': self.file_path,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

# Helper function to generate next invoice number
def get_next_invoice_number():
    """Generate the next invoice number in format INV-YYYY-XXXX"""
    year = datetime.now().year
    # Count invoices for this year
    count = Invoice.query.filter(Invoice.invoice_number.like(f"INV-{year}-%")).count()
    return f"INV-{year}-{(count + 1):04d}"

# Customer Management
def add_customer(name, address, vat_number, email):
    """Add a new customer and return the customer object"""
    customer_id = str(uuid.uuid4())
    customer = {
        'id': customer_id,
        'name': name,
        'address': address,
        'vat_number': vat_number,
        'email': email,
        'created_at': datetime.now()
    }
    customers[customer_id] = customer
    return customer

def update_customer(customer_id, name, address, vat_number, email):
    """Update an existing customer"""
    if customer_id not in customers:
        return None
    
    customer = customers[customer_id]
    customer['name'] = name
    customer['address'] = address
    customer['vat_number'] = vat_number
    customer['email'] = email
    customer['updated_at'] = datetime.now()
    
    return customer

def delete_customer(customer_id):
    """Delete a customer by ID"""
    if customer_id in customers:
        # Check if customer has invoices
        has_invoices = any(inv['customer_id'] == customer_id for inv in invoices.values())
        if has_invoices:
            return False, "Cannot delete customer with existing invoices"
        
        del customers[customer_id]
        return True, "Customer deleted successfully"
    return False, "Customer not found"

def get_customer(customer_id):
    """Get a customer by ID"""
    return customers.get(customer_id)

def get_customers():
    """Get all customers"""
    return list(customers.values())

# Invoice Management
def check_duplicate_invoice(invoice_number=None, customer_id=None, date=None, amount_incl_vat=None):
    """
    Check if an invoice might be a duplicate based on multiple criteria
    
    Returns:
        tuple: (is_duplicate, existing_invoice_id)
    """
    if invoice_number:
        # Direct check for exact invoice number match
        for inv_id, inv in invoices.items():
            if inv.get('invoice_number') == invoice_number:
                return True, inv_id
    
    # If other criteria provided, check for likely duplicates
    if customer_id and date and amount_incl_vat:
        amount_incl_vat = Decimal(str(amount_incl_vat))
        for inv_id, inv in invoices.items():
            if (inv['customer_id'] == customer_id and 
                inv['date'] == date and 
                abs(Decimal(str(inv['amount_incl_vat'])) - amount_incl_vat) < Decimal('0.01')):
                return True, inv_id
    
    # No duplicate found
    return False, None

def add_invoice(customer_id, date, invoice_type, amount_incl_vat, vat_rate, invoice_number=None, file_path=None, check_duplicate=True):
    """Add a new invoice"""
    if customer_id not in customers:
        return None
    
    # Convert to Decimal for accurate calculations
    amount_incl_vat = Decimal(str(amount_incl_vat))
    vat_rate = Decimal(str(vat_rate))
    
    # Check for duplicates if requested
    if check_duplicate:
        is_duplicate, duplicate_id = check_duplicate_invoice(
            invoice_number=invoice_number,
            customer_id=customer_id,
            date=date,
            amount_incl_vat=amount_incl_vat
        )
        if is_duplicate:
            return None, "Duplicate invoice detected", duplicate_id
    
    invoice_id = str(uuid.uuid4())
    
    # Calculate amounts
    vat_amount = amount_incl_vat - (amount_incl_vat / (1 + vat_rate / 100))
    amount_excl_vat = amount_incl_vat - vat_amount
    
    invoice = {
        'id': invoice_id,
        'invoice_number': invoice_number if invoice_number else get_next_invoice_number(),
        'customer_id': customer_id,
        'date': date,
        'invoice_type': invoice_type,  # 'income' or 'expense'
        'amount_incl_vat': float(amount_incl_vat),
        'amount_excl_vat': float(amount_excl_vat),
        'vat_rate': float(vat_rate),
        'vat_amount': float(vat_amount),
        'file_path': file_path,
        'created_at': datetime.now()
    }
    
    invoices[invoice_id] = invoice
    return invoice, "Invoice added successfully", None

def update_invoice(invoice_id, customer_id, date, invoice_type, amount_incl_vat, vat_rate, invoice_number=None, file_path=None):
    """Update an existing invoice"""
    if invoice_id not in invoices or customer_id not in customers:
        return None, "Invoice or customer not found", None
    
    # Convert to Decimal for accurate calculations
    amount_incl_vat = Decimal(str(amount_incl_vat))
    vat_rate = Decimal(str(vat_rate))
    
    # Calculate amounts
    vat_amount = amount_incl_vat - (amount_incl_vat / (1 + vat_rate / 100))
    amount_excl_vat = amount_incl_vat - vat_amount
    
    invoice = invoices[invoice_id]
    
    # Check if invoice number is being changed, and if so, check for duplicates
    if invoice_number and invoice_number != invoice['invoice_number']:
        is_duplicate, duplicate_id = check_duplicate_invoice(invoice_number=invoice_number)
        if is_duplicate and duplicate_id != invoice_id:
            return None, "Duplicate invoice number detected", duplicate_id
    
    invoice['customer_id'] = customer_id
    invoice['date'] = date
    invoice['invoice_type'] = invoice_type
    invoice['amount_incl_vat'] = float(amount_incl_vat)
    invoice['amount_excl_vat'] = float(amount_excl_vat)
    invoice['vat_rate'] = float(vat_rate)
    invoice['vat_amount'] = float(vat_amount)
    
    # Only update these fields if provided
    if invoice_number:
        invoice['invoice_number'] = invoice_number
        
    if file_path:
        invoice['file_path'] = file_path
        
    invoice['updated_at'] = datetime.now()
    
    return invoice, "Invoice updated successfully", None

def delete_invoice(invoice_id):
    """Delete an invoice by ID"""
    if invoice_id in invoices:
        del invoices[invoice_id]
        return True, "Invoice deleted successfully"
    return False, "Invoice not found"

def get_invoice(invoice_id):
    """Get an invoice by ID"""
    return invoices.get(invoice_id)

def get_invoices(customer_id=None, invoice_type=None, start_date=None, end_date=None):
    """
    Get invoices with optional filtering
    
    Args:
        customer_id: Filter by customer
        invoice_type: 'income' or 'expense'
        start_date: Start date for filtering
        end_date: End date for filtering
    """
    result = list(invoices.values())
    
    if customer_id:
        result = [inv for inv in result if inv['customer_id'] == customer_id]
    
    if invoice_type:
        result = [inv for inv in result if inv['invoice_type'] == invoice_type]
    
    if start_date:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        result = [inv for inv in result if datetime.strptime(inv['date'], '%Y-%m-%d') >= start_date]
    
    if end_date:
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        result = [inv for inv in result if datetime.strptime(inv['date'], '%Y-%m-%d') <= end_date]
    
    # Sort by date, newest first
    result.sort(key=lambda x: x['date'], reverse=True)
    
    return result

# VAT Calculations for Belgian reporting
def calculate_vat_report(year, quarter=None, month=None, workspace_id=None):
    """
    Calculate VAT report for Belgian reporting
    
    Args:
        year: Year to report
        quarter: Quarter (1-4) if reporting quarterly
        month: Month (1-12) if reporting monthly
        workspace_id: Optional workspace ID to filter by
    
    Returns:
        Dictionary with VAT grids:
        - Grid 03: Sales excluding VAT
        - Grid 54: Output VAT (VAT on sales)
        - Grid 59: Input VAT (VAT on purchases)
        - Grid 71: VAT balance (54-59)
    """
    # Start with base query for the year
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    query = Invoice.query.filter(
        Invoice.date >= start_date,
        Invoice.date <= end_date
    )
    
    # Apply workspace filter if provided
    if workspace_id is not None:
        query = query.filter_by(workspace_id=workspace_id)
    
    # Apply additional filters if specified
    if quarter:
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        
        quarter_start = date(year, start_month, 1)
        if end_month == 12:
            quarter_end = date(year, end_month, 31)
        else:
            quarter_end = date(year, end_month + 1, 1) - timedelta(days=1)
            
        query = query.filter(
            Invoice.date >= quarter_start,
            Invoice.date <= quarter_end
        )
    
    if month:
        month_start = date(year, month, 1)
        if month == 12:
            month_end = date(year, month, 31)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)
            
        query = query.filter(
            Invoice.date >= month_start,
            Invoice.date <= month_end
        )
    
    # Execute query and get results
    filtered_invoices = query.all()
    
    # Convert DB objects to dictionaries for easier handling in templates
    invoice_dicts = [inv.to_dict() for inv in filtered_invoices]
    
    # Ensure customer_id is properly saved as a string
    for invoice_dict in invoice_dicts:
        if 'customer' in invoice_dict and isinstance(invoice_dict['customer'], dict):
            invoice_dict['customer_id'] = str(invoice_dict['customer']['id'])
        # Ensure invoice_dict has a customer_id key even if it doesn't have a customer
        elif 'customer_id' not in invoice_dict:
            invoice_dict['customer_id'] = None
    
    # Calculate VAT grids
    grid_03 = sum(inv.amount_excl_vat for inv in filtered_invoices if inv.invoice_type == 'income')
    grid_54 = sum(inv.vat_amount for inv in filtered_invoices if inv.invoice_type == 'income')
    grid_59 = sum(inv.vat_amount for inv in filtered_invoices if inv.invoice_type == 'expense')
    grid_71 = grid_54 - grid_59
    
    return {
        'grid_03': float(grid_03),
        'grid_54': float(grid_54),
        'grid_59': float(grid_59),
        'grid_71': float(grid_71),
        'year': year,
        'quarter': quarter,
        'month': month,
        'invoices': invoice_dicts
    }

# User Model
class EmailSettings(db.Model):
    """
    Model voor e-mailinstellingen per werkruimte of systeembrede instellingen.
    Als workspace_id NULL is, zijn het systeembrede instellingen die worden gebruikt
    wanneer een werkruimte geen eigen instellingen heeft.
    """
    __tablename__ = 'email_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    # NULL voor systeeminstellingen, anders specifiek voor een workspace
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=True, unique=True)
    
    # SMTP instellingen
    smtp_server = db.Column(db.String(100))
    smtp_port = db.Column(db.Integer)
    smtp_username = db.Column(db.String(100))
    smtp_password = db.Column(db.String(255))  # Versleuteld opgeslagen
    smtp_use_ssl = db.Column(db.Boolean, default=True)
    smtp_use_tls = db.Column(db.Boolean, default=False)
    
    # Algemene e-mailinstellingen
    email_from = db.Column(db.String(100))
    email_from_name = db.Column(db.String(100))
    default_sender_name = db.Column(db.String(100), default="MidaWeb")
    reply_to = db.Column(db.String(100))
    
    # Bijhouden wanneer instellingen zijn gewijzigd
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Microsoft Graph API (Office 365) instellingen
    use_ms_graph = db.Column(db.Boolean, default=False)
    ms_graph_client_id = db.Column(db.String(100))
    ms_graph_client_secret = db.Column(db.String(255))  # Versleuteld opgeslagen
    ms_graph_tenant_id = db.Column(db.String(100))
    ms_graph_sender_email = db.Column(db.String(100))
    ms_graph_shared_mailbox = db.Column(db.String(100))  # E-mailadres van gedeelde mailbox
    ms_graph_use_shared_mailbox = db.Column(db.Boolean, default=False)  # Indien true, gebruik gedeelde mailbox
    
    # Relatie met Workspace (nullable voor systeem-instellingen)
    workspace = db.relationship('Workspace', back_populates='email_settings')
    
    @staticmethod
    def encrypt_secret(secret):
        """
        Versleutel een geheim voor opslag.
        
        Deze implementatie gebruikt base64 encoding om ervoor te zorgen dat speciale tekens
        correct worden opgeslagen.
        """
        if not secret:
            return None
        
        try:
            import base64
            import logging
            logger = logging.getLogger(__name__)
            
            # Converteer naar bytes en dan naar base64
            secret_bytes = secret.encode('utf-8')
            base64_secret = base64.b64encode(secret_bytes).decode('utf-8')
            
            # Voeg een prefix toe zodat we weten dat het een base64-gecodeerd geheim is
            encoded_secret = f"b64:{base64_secret}"
            logger.info(f"Secret succesvol gecodeerd met base64")
            
            return encoded_secret
        except Exception as e:
            logger.error(f"Fout bij het coderen van secret: {str(e)}")
            # Als er een fout optreedt, sla het geheim dan ongecodeerd op
            return secret
    
    @staticmethod
    def decrypt_secret(encrypted_secret):
        """
        Ontsleutel een opgeslagen geheim.
        
        Deze implementatie detecteert of het geheim base64-gecodeerd is en decodeert het indien nodig.
        """
        if not encrypted_secret:
            return None
            
        try:
            import base64
            import logging
            logger = logging.getLogger(__name__)
            
            # Controleer of het een base64-gecodeerd geheim is
            if encrypted_secret.startswith("b64:"):
                # Verwijder het prefix en decodeer
                base64_part = encrypted_secret[4:]  # Verwijder "b64:"
                decoded_bytes = base64.b64decode(base64_part)
                decoded_secret = decoded_bytes.decode('utf-8')
                logger.info(f"Secret succesvol gedecodeerd van base64")
                return decoded_secret
            else:
                # Als het niet base64-gecodeerd is, retourneer ongewijzigd
                return encrypted_secret
        except Exception as e:
            logger.error(f"Fout bij het decoderen van secret: {str(e)}")
            # Bij fouten, retourneer het originele geheim
            return encrypted_secret
    
    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'smtp_server': self.smtp_server,
            'smtp_port': self.smtp_port,
            'smtp_username': self.smtp_username,
            'smtp_use_ssl': self.smtp_use_ssl,
            'smtp_use_tls': self.smtp_use_tls,
            'email_from': self.email_from,
            'email_from_name': self.email_from_name,
            'default_sender_name': self.default_sender_name,
            'reply_to': self.reply_to,
            'use_ms_graph': self.use_ms_graph,
            'ms_graph_client_id': self.ms_graph_client_id,
            'ms_graph_sender_email': self.ms_graph_sender_email,
            'ms_graph_tenant_id': self.ms_graph_tenant_id,
            'ms_graph_shared_mailbox': self.ms_graph_shared_mailbox if hasattr(self, 'ms_graph_shared_mailbox') else None,
            'ms_graph_use_shared_mailbox': self.ms_graph_use_shared_mailbox if hasattr(self, 'ms_graph_use_shared_mailbox') else False,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class EmailMessage(db.Model):
    """
    Model voor ontvangen en verzonden e-mailberichten.
    Deze worden gebruikt om e-mails te traceren en zorgen voor automatische verwerking.
    """
    __tablename__ = 'email_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'))
    message_id = db.Column(db.String(255), unique=True)  # Unieke e-mail ID
    subject = db.Column(db.String(255))
    sender = db.Column(db.String(255))
    recipient = db.Column(db.String(255))
    body_text = db.Column(db.Text)
    body_html = db.Column(db.Text)
    received_date = db.Column(db.DateTime)
    is_processed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='received')  # received, processed, error
    
    # Als de e-mail aan een klant is gekoppeld
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=True)
    
    # Bijlagen (JSON opgeslagen)
    attachments = db.Column(db.Text)  # JSON met bestandspaden
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relaties
    workspace = db.relationship('Workspace', back_populates='email_messages')
    customer = db.relationship('Customer', backref=db.backref('email_messages', lazy=True))
    
    def get_attachments(self):
        """Haal bijlagen op als lijst"""
        if not self.attachments:
            return []
        try:
            return json.loads(self.attachments)
        except:
            return []
    
    def set_attachments(self, attachment_list):
        """Sla bijlagen op als JSON"""
        if not attachment_list:
            self.attachments = None
        else:
            self.attachments = json.dumps(attachment_list)
    
    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'message_id': self.message_id,
            'subject': self.subject,
            'sender': self.sender,
            'recipient': self.recipient,
            'received_date': self.received_date,
            'is_processed': self.is_processed,
            'status': self.status,
            'customer_id': str(self.customer_id) if self.customer_id else None,
            'attachments': self.get_attachments(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class EmailTemplate(db.Model):
    """
    Model voor e-mailtemplates
    Deze templates kunnen worden gebruikt voor het versturen van gestandaardiseerde e-mails
    """
    __tablename__ = 'email_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'))
    name = db.Column(db.String(100))
    subject = db.Column(db.String(255))
    body_html = db.Column(db.Text)
    is_default = db.Column(db.Boolean, default=False)
    template_type = db.Column(db.String(50))  # invoice, reminder, welcome, etc.
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relatie met Workspace
    workspace = db.relationship('Workspace', back_populates='email_templates')
    
    def to_dict(self):
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'name': self.name,
            'subject': self.subject,
            'body_html': self.body_html,
            'is_default': self.is_default,
            'template_type': self.template_type,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class Subscription(db.Model):
    """Model voor abonnementen die beschikbaar zijn in het systeem"""
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price_monthly = db.Column(db.Float, nullable=False)
    price_yearly = db.Column(db.Float, nullable=False)
    max_users = db.Column(db.Integer, nullable=False, default=1)
    max_invoices_per_month = db.Column(db.Integer, nullable=False, default=50)
    price_per_extra_user = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    features = db.Column(db.Text)  # JSON string met features
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relatie
    workspaces = db.relationship('Workspace', back_populates='subscription')
    
    @property
    def features_list(self):
        """Retourneert de features als een lijst (voor gebruik in templates)"""
        try:
            if self.features:
                # Probeer eerst als JSON object/dict te parsen
                features_data = json.loads(self.features)
                # Als het een dict is, gebruik de regels uit de oude code 
                if isinstance(features_data, dict):
                    return [
                        f"{v} gebruiker{'s' if v > 1 else ''}" if k == 'max_users' else
                        f"{v} facturen per maand" if k == 'max_invoices_per_month' else k
                        for k, v in features_data.items() if v
                    ]
                # Anders als het een array is, gebruik direct die lijst    
                elif isinstance(features_data, list):
                    return features_data
            # Fallback: als leeg of geen geldig JSON
            return []
        except:
            # In geval van error, retourneer lege lijst
            return []
    
    def to_dict(self):
        """Converteer naar dictionary voor JSON serialisatie"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price_monthly': self.price_monthly,
            'price_yearly': self.price_yearly,
            'max_users': self.max_users,
            'max_invoices_per_month': self.max_invoices_per_month,
            'price_per_extra_user': self.price_per_extra_user,
            'is_active': self.is_active,
            'features': json.loads(self.features) if self.features else {},
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class MollieSettings(db.Model):
    """Model voor Mollie betalingsinstellingen"""
    __tablename__ = 'mollie_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    api_key_live = db.Column(db.String(255))
    api_key_test = db.Column(db.String(255))
    is_test_mode = db.Column(db.Boolean, default=True)
    webhook_url = db.Column(db.String(255))
    redirect_url = db.Column(db.String(255))
    is_system_default = db.Column(db.Boolean, default=False)
    
    @property
    def api_key(self):
        """Geeft de juiste API key terug op basis van de test mode instelling"""
        return self.api_key_test if self.is_test_mode else self.api_key_live
    
    @api_key.setter
    def api_key(self, value):
        """Stelt de juiste API key in op basis van de test mode instelling"""
        if self.is_test_mode:
            self.api_key_test = value
        else:
            self.api_key_live = value
    
    # Workspace relatie
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'))
    workspace = db.relationship('Workspace', back_populates='mollie_settings')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<MollieSettings id={self.id} workspace_id={self.workspace_id}>"

class Payment(db.Model):
    """Model voor betalingen"""
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    mollie_payment_id = db.Column(db.String(255), unique=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='EUR')
    period = db.Column(db.String(20))  # 'monthly' of 'yearly'
    status = db.Column(db.String(50))  # 'pending', 'paid', 'failed', etc.
    payment_method = db.Column(db.String(50))  # 'ideal', 'creditcard', etc.
    payment_url = db.Column(db.String(255))
    expiry_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relaties
    workspace = db.relationship('Workspace', back_populates='payments')
    subscription = db.relationship('Subscription')
    
    def to_dict(self):
        """Converteer naar dictionary voor JSON serialisatie"""
        return {
            'id': self.id,
            'mollie_payment_id': self.mollie_payment_id,
            'workspace_id': self.workspace_id,
            'subscription_id': self.subscription_id,
            'amount': self.amount,
            'currency': self.currency,
            'period': self.period,
            'status': self.status,
            'payment_method': self.payment_method,
            'payment_url': self.payment_url,
            'expiry_date': self.expiry_date,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class SystemSettings(db.Model):
    """
    Model voor systeeminstellingen, waaronder WHMCS-integratie-instellingen.
    """
    __tablename__ = 'system_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text, nullable=True)
    
    # WHMCS API instellingen
    whmcs_api_url = db.Column(db.String(255), nullable=True)
    whmcs_api_identifier = db.Column(db.String(255), nullable=True)
    whmcs_api_secret = db.Column(db.String(255), nullable=True)
    whmcs_auto_sync = db.Column(db.Boolean, default=False)
    whmcs_last_sync = db.Column(db.DateTime, nullable=True)
    
    # Versie en systeeminformatie
    system_version = db.Column(db.String(20), default='1.0.0')
    last_backup = db.Column(db.DateTime, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    @staticmethod
    def get_setting(key, default=None):
        """Haal een systeeminstelling op volgens sleutel"""
        setting = SystemSettings.query.filter_by(key=key).first()
        if setting and setting.value is not None:
            return setting.value
        return default
    
    @staticmethod
    def set_setting(key, value):
        """Stel een systeeminstelling in volgens sleutel"""
        setting = SystemSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = SystemSettings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
        return setting


class Workspace(db.Model):
    __tablename__ = 'workspaces'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(200))
    domain = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    
    # Abonnement gegevens
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    subscription_start_date = db.Column(db.DateTime)
    subscription_end_date = db.Column(db.DateTime)
    extra_users = db.Column(db.Integer, default=0)
    billing_cycle = db.Column(db.String(20), default='monthly')  # 'monthly' of 'yearly'
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relationships
    users = db.relationship('User', back_populates='workspace')
    customers = db.relationship('Customer', back_populates='workspace')
    invoices = db.relationship('Invoice', back_populates='workspace')
    email_settings = db.relationship('EmailSettings', uselist=False, back_populates='workspace', cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='workspace')
    subscription = db.relationship('Subscription', back_populates='workspaces')
    email_templates = db.relationship('EmailTemplate', back_populates='workspace', cascade='all, delete-orphan')
    email_messages = db.relationship('EmailMessage', back_populates='workspace', cascade='all, delete-orphan')
    mollie_settings = db.relationship('MollieSettings', uselist=False, back_populates='workspace', cascade='all, delete-orphan')
    backup_settings = db.relationship('BackupSettings', uselist=False, back_populates='workspace', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Workspace {self.name}>'
        
    def to_dict(self):
        """Converteer naar dictionary voor JSON serialisatie"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'domain': self.domain,
            'is_active': self.is_active,
            'subscription_id': self.subscription_id,
            'subscription_start_date': self.subscription_start_date,
            'subscription_end_date': self.subscription_end_date,
            'extra_users': self.extra_users,
            'billing_cycle': self.billing_cycle,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
    def is_subscription_active(self):
        """Controleer of het abonnement nog actief is"""
        if not self.subscription_end_date:
            return False
        return datetime.now() <= self.subscription_end_date
        
    def get_monthly_cost(self):
        """Bereken maandelijkse kosten op basis van abonnement en extra gebruikers"""
        if not self.subscription:
            return 0
            
        base_price = self.subscription.price_monthly if self.billing_cycle == 'monthly' else self.subscription.price_yearly / 12
        extra_users_cost = self.extra_users * self.subscription.price_per_extra_user
        
        return base_price + extra_users_cost

# Forward reference voor circulaire relatie
class UserPermission(db.Model):
    """Model voor gebruikersrechten - de verschillende functies die een gebruiker mag uitvoeren"""
    __tablename__ = 'user_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # Klanten rechten
    can_view_customers = db.Column(db.Boolean, default=True)
    can_add_customers = db.Column(db.Boolean, default=False)
    can_edit_customers = db.Column(db.Boolean, default=False)
    can_delete_customers = db.Column(db.Boolean, default=False)
    
    # Facturen rechten
    can_view_invoices = db.Column(db.Boolean, default=True)
    can_add_invoices = db.Column(db.Boolean, default=False)
    can_edit_invoices = db.Column(db.Boolean, default=False)
    can_delete_invoices = db.Column(db.Boolean, default=False)
    can_upload_invoices = db.Column(db.Boolean, default=False)
    
    # Rapporten rechten
    can_view_reports = db.Column(db.Boolean, default=True)
    can_export_reports = db.Column(db.Boolean, default=False)
    can_generate_vat_report = db.Column(db.Boolean, default=False)
    
    # Andere rechten
    can_view_dashboard = db.Column(db.Boolean, default=True)
    can_manage_settings = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relationship met gebruiker - gebruik string reference om circulaire import te vermijden
    user = db.relationship('User', back_populates='permissions')
    
    def to_dict(self):
        """Converteer naar dictionary voor JSON serialisatie"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'can_view_customers': self.can_view_customers,
            'can_add_customers': self.can_add_customers,
            'can_edit_customers': self.can_edit_customers,
            'can_delete_customers': self.can_delete_customers,
            'can_view_invoices': self.can_view_invoices,
            'can_add_invoices': self.can_add_invoices,
            'can_edit_invoices': self.can_edit_invoices,
            'can_delete_invoices': self.can_delete_invoices,
            'can_upload_invoices': self.can_upload_invoices,
            'can_view_reports': self.can_view_reports,
            'can_export_reports': self.can_export_reports,
            'can_generate_vat_report': self.can_generate_vat_report,
            'can_view_dashboard': self.can_view_dashboard,
            'can_manage_settings': self.can_manage_settings,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    password_change_required = db.Column(db.Boolean, default=False)
    is_new_user = db.Column(db.Boolean, default=True)
    
    # Workspace relationship (nullable for super_admin users who can access all workspaces)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    workspace = db.relationship('Workspace', back_populates='users')
    
    # User permissions
    permissions = db.relationship('UserPermission', back_populates='user', cascade='all, delete-orphan', uselist=False)
    
    # Make username and email unique per workspace
    __table_args__ = (
        sa.UniqueConstraint('username', 'workspace_id', name='uix_user_username_workspace'),
        sa.UniqueConstraint('email', 'workspace_id', name='uix_user_email_workspace'),
        {'extend_existing': True}
    )
    
    def has_permission(self, permission_name):
        """Controleert of de gebruiker een specifieke permissie heeft"""
        # Super admins en workspace admins hebben altijd alle rechten
        if self.is_super_admin or self.is_admin:
            return True
        
        # Controleer specifieke permissies voor normale gebruikers
        if self.permissions:
            return getattr(self.permissions, permission_name, False)
        
        return False
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
        
# Financial Summary functions
def get_monthly_summary(year, workspace_id=None):
    """
    Get monthly financial summary for a year
    
    Args:
        year: Year to get summary for
        workspace_id: Optional workspace ID to filter by
    """
    monthly_data = []
    
    for month in range(1, 13):
        # Create date range for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Query all invoices for this month
        query = Invoice.query.filter(
            Invoice.date >= start_date,
            Invoice.date <= end_date
        )
        
        # Apply workspace filter if provided
        if workspace_id is not None:
            query = query.filter_by(workspace_id=workspace_id)
            
        month_invoices = query.all()
        
        income = sum(inv.amount_excl_vat for inv in month_invoices if inv.invoice_type == 'income')
        expenses = sum(inv.amount_excl_vat for inv in month_invoices if inv.invoice_type == 'expense')
        vat_collected = sum(inv.vat_amount for inv in month_invoices if inv.invoice_type == 'income')
        vat_paid = sum(inv.vat_amount for inv in month_invoices if inv.invoice_type == 'expense')
        
        monthly_data.append({
            'month': month,
            'month_name': datetime(year, month, 1).strftime('%B'),
            'income': float(income),
            'expenses': float(expenses),
            'profit': float(income - expenses),
            'vat_collected': float(vat_collected),
            'vat_paid': float(vat_paid),
            'vat_balance': float(vat_collected - vat_paid)
        })
    
    return monthly_data

def get_quarterly_summary(year, workspace_id=None):
    """
    Get quarterly financial summary for a year
    
    Args:
        year: Year to get summary for
        workspace_id: Optional workspace ID to filter by
    """
    quarterly_data = []
    
    for quarter in range(1, 5):
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        
        # Define date range for the quarter
        start_date = date(year, start_month, 1)
        if end_month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, end_month + 1, 1) - timedelta(days=1)
        
        # Query invoices for this quarter
        query = Invoice.query.filter(
            Invoice.date >= start_date,
            Invoice.date <= end_date
        )
        
        # Apply workspace filter if provided
        if workspace_id is not None:
            query = query.filter_by(workspace_id=workspace_id)
            
        quarter_invoices = query.all()
        
        income = sum(inv.amount_excl_vat for inv in quarter_invoices if inv.invoice_type == 'income')
        expenses = sum(inv.amount_excl_vat for inv in quarter_invoices if inv.invoice_type == 'expense')
        vat_collected = sum(inv.vat_amount for inv in quarter_invoices if inv.invoice_type == 'income')
        vat_paid = sum(inv.vat_amount for inv in quarter_invoices if inv.invoice_type == 'expense')
        
        quarterly_data.append({
            'quarter': quarter,
            'income': float(income),
            'expenses': float(expenses),
            'profit': float(income - expenses),
            'vat_collected': float(vat_collected),
            'vat_paid': float(vat_paid),
            'vat_balance': float(vat_collected - vat_paid)
        })
    
    return quarterly_data

def get_customer_summary(workspace_id=None):
    """
    Get financial summary by customer
    
    Args:
        workspace_id: Optional workspace ID to filter by
    """
    customer_data = []
    
    # Get customers filtered by workspace if provided
    customers_query = Customer.query
    if workspace_id is not None:
        customers_query = customers_query.filter_by(workspace_id=workspace_id)
    customers_query = customers_query.all()
    
    for customer in customers_query:
        # Query invoices for this customer, filtered by workspace if provided
        query = Invoice.query.filter_by(customer_id=customer.id)
        if workspace_id is not None:
            query = query.filter_by(workspace_id=workspace_id)
        customer_invoices = query.all()
        
        income = sum(inv.amount_excl_vat for inv in customer_invoices if inv.invoice_type == 'income')
        vat_collected = sum(inv.vat_amount for inv in customer_invoices if inv.invoice_type == 'income')
        invoice_count = len([inv for inv in customer_invoices if inv.invoice_type == 'income'])
        
        customer_data.append({
            'customer_id': str(customer.id),
            'customer_name': customer.name,
            'vat_number': customer.vat_number,
            'income': float(income),
            'vat_collected': float(vat_collected),
            'invoice_count': invoice_count
        })
    
    # Sort by income, highest first
    customer_data.sort(key=lambda x: x['income'], reverse=True)
    
    return customer_data

# User management functions
def get_users():
    """Get all users"""
    return User.query.order_by(User.username).all()

def get_user(user_id):
    """Get user by ID"""
    return User.query.get(user_id)

def create_user(username, email, password, is_admin=False, is_super_admin=False):
    """Create a new user"""
    user = User(username=username, email=email, is_admin=is_admin, is_super_admin=is_super_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user

def update_user(user_id, email=None, password=None, is_admin=None, is_super_admin=None, workspace_id=None):
    """Update user information"""
    user = get_user(user_id)
    if not user:
        return False
    
    if email:
        user.email = email
    
    if password:
        user.set_password(password)
    
    if is_admin is not None:
        user.is_admin = is_admin
    
    if is_super_admin is not None:
        user.is_super_admin = is_super_admin
        # Super admins are always admins
        if is_super_admin:
            user.is_admin = True
        
    # Workspace_id verwerken - moet voorzichtig gebeuren vanwege type conversies
    if workspace_id is not None:
        # Controleer op lege strings (komen uit formulieren) en zet ze om naar None
        if workspace_id == '' or workspace_id == "":
            user.workspace_id = None
        # Controleer op geldige integers of None
        elif isinstance(workspace_id, int) or workspace_id is None:
            user.workspace_id = workspace_id
        # Probeer string om te zetten naar int indien mogelijk
        elif isinstance(workspace_id, str) and workspace_id.isdigit():
            user.workspace_id = int(workspace_id)
        # Anders, zet naar None (veilig)
        else:
            user.workspace_id = None
    
    db.session.commit()
    return user

def delete_user(user_id):
    """Delete a user"""
    user = get_user(user_id)
    if not user:
        return False
    
    # Don't allow deleting the last super admin
    if user.is_super_admin and User.query.filter_by(is_super_admin=True).count() <= 1:
        return False
    
    db.session.delete(user)
    db.session.commit()
    return True

# Backup gerelateerde modellen
class BackupSettings(db.Model):
    """
    Model voor backup instellingen per werkruimte
    """
    __tablename__ = 'backup_settings'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=False)
    
    # Backup plan instellingen
    plan = db.Column(db.String(20), nullable=False, default='free')  # free, basic, premium, enterprise
    plan_start_date = db.Column(db.DateTime, default=datetime.now)
    plan_end_date = db.Column(db.DateTime)
    
    # Backup configuratie
    backup_enabled = db.Column(db.Boolean, default=True)
    include_uploads = db.Column(db.Boolean, default=True)
    auto_backup_enabled = db.Column(db.Boolean, default=False)
    auto_backup_interval = db.Column(db.String(20), default='daily')  # 'hourly', 'daily', 'weekly', 'monthly'
    auto_backup_time = db.Column(db.String(10), default='02:00')
    auto_backup_day = db.Column(db.Integer)  # Dag van de week (1-7) of dag van de maand (1-31)
    last_backup_date = db.Column(db.DateTime)
    retention_days = db.Column(db.Integer, default=7)
    
    # Relaties
    workspace = db.relationship('Workspace', back_populates='backup_settings')
    backup_schedules = db.relationship('BackupSchedule', back_populates='backup_settings', cascade='all, delete-orphan')
    backup_jobs = db.relationship('BackupJob', back_populates='backup_settings', cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<BackupSettings id={self.id} workspace_id={self.workspace_id} plan={self.plan}>"
        
    def to_dict(self):
        """Converteer naar dictionary"""
        return {
            'id': self.id,
            'workspace_id': self.workspace_id,
            'plan': self.plan,
            'plan_start_date': self.plan_start_date,
            'plan_end_date': self.plan_end_date,
            'backup_enabled': self.backup_enabled,
            'include_uploads': self.include_uploads,
            'auto_backup_enabled': self.auto_backup_enabled,
            'auto_backup_interval': self.auto_backup_interval,
            'auto_backup_time': self.auto_backup_time,
            'auto_backup_day': self.auto_backup_day,
            'last_backup_date': self.last_backup_date,
            'retention_days': self.retention_days,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
    def get_plan_limits(self):
        """Haal de limieten op voor het huidige plan"""
        from backup_service import BackupSubscription
        return BackupSubscription.get_plan_limits(self.plan)
        
    def get_plan_description(self):
        """Haal de omschrijving op voor het huidige plan"""
        from backup_service import BackupSubscription
        return BackupSubscription.get_plan_description(self.plan)
        
    def update_plan(self, new_plan, duration_months=12):
        """
        Werk het backup plan bij
        
        Args:
            new_plan: Het nieuwe plan ('free', 'basic', 'premium', 'enterprise')
            duration_months: Aantal maanden dat het abonnement geldig is
        """
        self.plan = new_plan
        self.plan_start_date = datetime.now()
        
        # Bereken de einddatum (standaard 12 maanden)
        if duration_months:
            # Voeg maanden toe en bereken de nieuwe datum
            year = self.plan_start_date.year + (self.plan_start_date.month + duration_months - 1) // 12
            month = (self.plan_start_date.month + duration_months - 1) % 12 + 1
            day = min(self.plan_start_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            self.plan_end_date = datetime(year, month, day)
        else:
            # Geen einddatum voor gratis abonnement
            self.plan_end_date = None
            
        # Bepaal aan de hand van het plan welke backup opties worden ingeschakeld
        plan_limits = self.get_plan_limits()
        if new_plan == 'free':
            self.auto_backup_enabled = False
            self.retention_days = 7
        else:
            self.auto_backup_enabled = plan_limits.get('auto_backup', False)
            self.retention_days = plan_limits.get('retention_days', 7)
            self.include_uploads = plan_limits.get('include_uploads', False)
            
        self.updated_at = datetime.now()
        return self

class BackupSchedule(db.Model):
    """
    Model voor geplande backups
    """
    __tablename__ = 'backup_schedules'
    
    id = db.Column(db.Integer, primary_key=True)
    backup_settings_id = db.Column(db.Integer, db.ForeignKey('backup_settings.id'), nullable=False)
    
    # Backup planning
    interval = db.Column(db.String(20), nullable=False, default='daily')  # 'hourly', 'daily', 'weekly', 'monthly'
    time = db.Column(db.String(10), default='02:00')  # HH:MM formaat
    day = db.Column(db.Integer)  # Dag van de week (1-7) of dag van de maand (1-31)
    
    # Voor backups van specifieke tabellen
    tables = db.Column(db.Text)  # JSON lijst met tabelnamen
    include_uploads = db.Column(db.Boolean, default=True)
    retention_days = db.Column(db.Integer, default=7)
    
    # Status
    is_active = db.Column(db.Boolean, default=True)
    last_run = db.Column(db.DateTime)
    next_run = db.Column(db.DateTime)
    
    # Relaties
    backup_settings = db.relationship('BackupSettings', back_populates='backup_schedules')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<BackupSchedule id={self.id} interval={self.interval}>"
        
    def to_dict(self):
        """Converteer naar dictionary"""
        return {
            'id': self.id,
            'backup_settings_id': self.backup_settings_id,
            'interval': self.interval,
            'time': self.time,
            'day': self.day,
            'tables': json.loads(self.tables) if self.tables else None,
            'include_uploads': self.include_uploads,
            'retention_days': self.retention_days,
            'is_active': self.is_active,
            'last_run': self.last_run,
            'next_run': self.next_run,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
    def calculate_next_run(self):
        """
        Bereken het volgende geplande uitvoermoment op basis van de planning
        
        Returns:
            datetime: Tijdstip van volgende uitvoering
        """
        now = datetime.now()
        time_parts = self.time.split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        
        # Begin met vandaag op het geplande tijdstip
        next_run = datetime(now.year, now.month, now.day, hour, minute)
        
        # Als dat tijdstip al voorbij is, ga naar de volgende interval
        if next_run <= now:
            if self.interval == 'hourly':
                # Volgende uur, zelfde minuut
                next_run = datetime(now.year, now.month, now.day, now.hour + 1, minute)
            elif self.interval == 'daily':
                # Morgen, zelfde uur en minuut
                next_run = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=1)
            elif self.interval == 'weekly':
                # Volgende week, op de gespecificeerde dag (1=maandag, 7=zondag)
                if self.day and 1 <= self.day <= 7:
                    days_ahead = self.day - now.isoweekday()
                    if days_ahead <= 0:  # Als het vandaag of al voorbij is
                        days_ahead += 7  # Ga naar volgende week
                    next_run = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=days_ahead)
                else:
                    # Als geen dag gespecificeerd, volgende week zelfde dag
                    next_run = datetime(now.year, now.month, now.day, hour, minute) + timedelta(days=7)
            elif self.interval == 'monthly':
                # Volgende maand, op de gespecificeerde dag van de maand
                if self.day and 1 <= self.day <= 31:
                    # Bereken de datum voor volgende maand
                    if now.month == 12:
                        year = now.year + 1
                        month = 1
                    else:
                        year = now.year
                        month = now.month + 1
                        
                    # Zorg dat de dag geldig is voor die maand
                    last_day = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
                    day = min(self.day, last_day)
                    
                    next_run = datetime(year, month, day, hour, minute)
                else:
                    # Als geen dag gespecificeerd, volgende maand zelfde dag
                    # Voeg 1 maand toe (let op de juiste logica voor maanden met verschillende lengtes)
                    if now.month == 12:
                        next_run = datetime(now.year + 1, 1, now.day, hour, minute)
                    else:
                        next_month = now.month + 1
                        # Zorg dat de dag geldig is voor die maand
                        last_day = [31, 29 if now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][next_month - 1]
                        day = min(now.day, last_day)
                        next_run = datetime(now.year, next_month, day, hour, minute)
                        
        return next_run

class BackupJob(db.Model):
    """
    Model voor backup jobs (uitgevoerde en geplande backups)
    """
    __tablename__ = 'backup_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    backup_settings_id = db.Column(db.Integer, db.ForeignKey('backup_settings.id'), nullable=False)
    backup_id = db.Column(db.String(50))  # ID van de backup in het systeem
    filename = db.Column(db.String(255))  # Bestandsnaam van de backup
    
    # Backup parameters
    scheduled = db.Column(db.Boolean, default=False)  # Was dit een geplande backup?
    backup_type = db.Column(db.String(20), default='full')  # 'full', 'database', 'uploads'
    status = db.Column(db.String(20), default='pending')  # 'pending', 'running', 'completed', 'failed'
    include_uploads = db.Column(db.Boolean, default=True)
    
    # Metagegevens
    file_size = db.Column(db.BigInteger)  # Grootte in bytes
    tables = db.Column(db.Text)  # JSON lijst met tabellen in de backup
    
    # Tijdstippen
    scheduled_time = db.Column(db.DateTime)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    
    # Resultaten
    result_message = db.Column(db.Text)
    error_details = db.Column(db.Text)
    
    # Relaties
    backup_settings = db.relationship('BackupSettings', back_populates='backup_jobs')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<BackupJob id={self.id} status={self.status}>"
        
    def to_dict(self):
        """Converteer naar dictionary"""
        return {
            'id': self.id,
            'backup_settings_id': self.backup_settings_id,
            'backup_id': self.backup_id,
            'filename': self.filename,
            'scheduled': self.scheduled,
            'backup_type': self.backup_type,
            'status': self.status,
            'include_uploads': self.include_uploads,
            'file_size': self.file_size,
            'tables': json.loads(self.tables) if self.tables else None,
            'scheduled_time': self.scheduled_time,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'result_message': self.result_message,
            'error_details': self.error_details,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


