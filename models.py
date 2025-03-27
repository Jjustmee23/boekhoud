from datetime import datetime, date, timedelta
import uuid
import json
import os
from decimal import Decimal
from app import db
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Legacy in-memory storage (will be deprecated)
customers = {}  # id -> customer
invoices = {}   # id -> invoice

# Database models
class Customer(db.Model):
    __tablename__ = 'customers'
    
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
    invoice_type = db.Column(db.String(10), nullable=False)  # income, expense
    amount_excl_vat = db.Column(db.Float, nullable=False)
    amount_incl_vat = db.Column(db.Float, nullable=False)
    vat_rate = db.Column(db.Float, nullable=False)
    vat_amount = db.Column(db.Float, nullable=False)
    file_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default='processed')  # processed, unprocessed
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Workspace relationship
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'))
    workspace = db.relationship('Workspace', back_populates='invoices')
    
    # Relationship to customer
    customer = db.relationship('Customer', back_populates='invoices')
    
    # Make invoice_number unique per workspace
    __table_args__ = (
        sa.UniqueConstraint('invoice_number', 'workspace_id', name='uix_invoice_number_workspace'),
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
class UserOAuthToken(db.Model):
    """
    Model voor het opslaan van OAuth tokens per gebruiker en werkruimte.
    Dit stelt gebruikers in staat om hun eigen e-mailaccount te gebruiken om namens hen e-mails te versturen.
    """
    __tablename__ = 'user_oauth_tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
    provider = db.Column(db.String(20), nullable=False)  # 'microsoft', 'google', etc.
    
    # OAuth gegevens
    access_token = db.Column(db.String(2048))  # Versleuteld opgeslagen
    refresh_token = db.Column(db.String(2048))  # Versleuteld opgeslagen
    token_expiry = db.Column(db.DateTime)
    email = db.Column(db.String(120))  # E-mailadres dat geautoriseerd is
    display_name = db.Column(db.String(120))  # Weergavenaam voor de gebruiker
    
    # Bijhouden wanneer tokens zijn gewijzigd
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, onupdate=datetime.now)
    
    # Relaties
    user = db.relationship('User', back_populates='oauth_tokens')
    workspace = db.relationship('Workspace', back_populates='oauth_tokens')
    
    # Maak combinatie van user_id, workspace_id en provider uniek
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'workspace_id', 'provider', name='uix_user_workspace_provider'),
    )
    
    @property
    def is_valid(self):
        """Controleert of het token nog geldig is (niet verlopen)"""
        if not self.token_expiry:
            return False
        return datetime.now() < self.token_expiry
        
    def to_dict(self):
        """Token in dictionary formaat"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'provider': self.provider,
            'email': self.email,
            'display_name': self.display_name,
            'token_expiry': self.token_expiry,
            'is_valid': self.is_valid,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @property
    def is_valid(self):
        """Controleert of het token nog geldig is (niet verlopen)"""
        if not self.token_expiry:
            return False
        return self.token_expiry > datetime.now()
    
    @staticmethod
    def encrypt_token(token):
        """
        Versleutel een token voor opslag.
        
        Deze implementatie slaat nu het token direct op zonder versleuteling om problemen
        met de authenticatie te voorkomen.
        """
        if not token:
            return None
        
        # Retourneer het token ongewijzigd
        return token
    
    @staticmethod
    def decrypt_token(encrypted_token):
        """
        Ontsleutel een opgeslagen token.
        
        Omdat we het token direct opslaan, retourneren we het ongewijzigd.
        """
        if not encrypted_token:
            return None
            
        # Retourneer het token ongewijzigd
        return encrypted_token
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workspace_id': self.workspace_id,
            'provider': self.provider,
            'email': self.email,
            'display_name': self.display_name,
            'token_expiry': self.token_expiry,
            'is_valid': self.is_valid,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


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
    
    # OAuth gebruikersmodus instellingen
    use_user_oauth = db.Column(db.Boolean, default=False)  # Indien true, gebruik OAuth tokens van gebruikers
    allow_microsoft_oauth = db.Column(db.Boolean, default=True)  # Sta Microsoft OAuth toe
    allow_google_oauth = db.Column(db.Boolean, default=False)  # Sta Google OAuth toe (toekomstige functionaliteit)
    oauth_scopes = db.Column(db.String(1024), default="mail.send")  # Benodigde permissions voor OAuth
    
    # Relatie met Workspace (nullable voor systeem-instellingen)
    workspace = db.relationship('Workspace', back_populates='email_settings')
    
    @staticmethod
    def encrypt_secret(secret):
        """
        Versleutel een geheim voor opslag.
        
        Deze implementatie slaat nu het geheim direct op zonder versleuteling om problemen
        met de authenticatie te voorkomen.
        """
        if not secret:
            return None
        
        # Retourneer het geheim ongewijzigd
        return secret
    
    @staticmethod
    def decrypt_secret(encrypted_secret):
        """
        Ontsleutel een opgeslagen geheim.
        
        Omdat we het geheim direct opslaan, retourneren we het ongewijzigd.
        """
        if not encrypted_secret:
            return None
            
        # Retourneer het geheim ongewijzigd
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
            'use_user_oauth': self.use_user_oauth if hasattr(self, 'use_user_oauth') else False,
            'allow_microsoft_oauth': self.allow_microsoft_oauth if hasattr(self, 'allow_microsoft_oauth') else True,
            'allow_google_oauth': self.allow_google_oauth if hasattr(self, 'allow_google_oauth') else False,
            'oauth_scopes': self.oauth_scopes if hasattr(self, 'oauth_scopes') else "mail.send",
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


class Workspace(db.Model):
    __tablename__ = 'workspaces'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Relationships
    users = db.relationship('User', back_populates='workspace')
    customers = db.relationship('Customer', back_populates='workspace')
    invoices = db.relationship('Invoice', back_populates='workspace')
    email_settings = db.relationship('EmailSettings', uselist=False, back_populates='workspace', cascade='all, delete-orphan')
    email_templates = db.relationship('EmailTemplate', back_populates='workspace', cascade='all, delete-orphan')
    email_messages = db.relationship('EmailMessage', back_populates='workspace', cascade='all, delete-orphan')
    oauth_tokens = db.relationship('UserOAuthToken', back_populates='workspace', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Workspace {self.name}>'

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
    
    # Workspace relationship (nullable for super_admin users who can access all workspaces)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspaces.id'), nullable=True)
    workspace = db.relationship('Workspace', back_populates='users')
    
    # OAuth token relationship
    oauth_tokens = db.relationship('UserOAuthToken', back_populates='user', cascade='all, delete-orphan')
    
    # Make username and email unique per workspace
    __table_args__ = (
        sa.UniqueConstraint('username', 'workspace_id', name='uix_user_username_workspace'),
        sa.UniqueConstraint('email', 'workspace_id', name='uix_user_email_workspace'),
    )
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_oauth_token(self, workspace_id=None, provider='microsoft'):
        """
        Haal een OAuth token op voor een specifieke provider en workspace
        
        Args:
            workspace_id: ID van de werkruimte, als None wordt de huidige werkruimte gebruikt
            provider: Naam van de provider ('microsoft', 'google', etc.)
            
        Returns:
            UserOAuthToken object of None als er geen is gevonden
        """
        if workspace_id is None and self.workspace_id is not None:
            workspace_id = self.workspace_id
        
        if workspace_id is None:
            return None
        
        return UserOAuthToken.query.filter_by(
            user_id=self.id,
            workspace_id=workspace_id,
            provider=provider
        ).first()
        
    def has_valid_oauth_token(self, workspace_id=None, provider='microsoft'):
        """Controleert of de gebruiker een geldig OAuth token heeft voor een specifieke provider en werkruimte"""
        token = self.get_oauth_token(workspace_id, provider)
        return token is not None and token.is_valid
    
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
