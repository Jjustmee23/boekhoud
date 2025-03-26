from datetime import datetime
import uuid
import os
from decimal import Decimal
from app import db
from sqlalchemy import and_, extract, func

# Customer / Supplier model
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    vat_number = db.Column(db.String(20))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    street = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    city = db.Column(db.String(50))
    country = db.Column(db.String(50))
    default_vat_rate = db.Column(db.Float, default=21.0)  # Default to 21% (Belgium)
    customer_type = db.Column(db.String(20), default='customer')  # 'customer' or 'supplier'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with invoices
    invoices = db.relationship('Invoice', backref='customer', lazy=True)
    
    def __repr__(self):
        return f'<Customer {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'vat_number': self.vat_number,
            'email': self.email,
            'phone': self.phone,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'street': self.street,
            'postal_code': self.postal_code,
            'city': self.city,
            'country': self.country,
            'default_vat_rate': self.default_vat_rate,
            'customer_type': self.customer_type,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
    @property
    def address(self):
        """Build a formatted address for display purposes"""
        address_parts = []
        if self.street:
            address_parts.append(self.street)
        
        postal_city = []
        if self.postal_code:
            postal_city.append(self.postal_code)
        if self.city:
            postal_city.append(self.city)
        
        if postal_city:
            address_parts.append(' '.join(postal_city))
            
        if self.country:
            address_parts.append(self.country)
            
        return '\n'.join(address_parts)

# Invoice model
class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    invoice_type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    amount_incl_vat = db.Column(db.Float, nullable=False)
    amount_excl_vat = db.Column(db.Float, nullable=False)
    vat_rate = db.Column(db.Float, nullable=False)
    vat_amount = db.Column(db.Float, nullable=False)
    file_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'customer_id': self.customer_id,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'invoice_type': self.invoice_type,
            'amount_incl_vat': self.amount_incl_vat,
            'amount_excl_vat': self.amount_excl_vat,
            'vat_rate': self.vat_rate,
            'vat_amount': self.vat_amount,
            'file_path': self.file_path,
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
def add_customer(name, vat_number=None, email=None, phone=None, first_name=None, 
                last_name=None, street=None, postal_code=None, city=None, country=None, 
                default_vat_rate=21.0, customer_type='customer'):
    """Add a new customer and return the customer object"""
    customer = Customer(
        name=name,
        vat_number=vat_number,
        email=email,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        street=street,
        postal_code=postal_code,
        city=city,
        country=country,
        default_vat_rate=default_vat_rate,
        customer_type=customer_type
    )
    
    db.session.add(customer)
    db.session.commit()
    return customer

def update_customer(customer_id, name=None, vat_number=None, email=None, phone=None, 
                   first_name=None, last_name=None, street=None, postal_code=None, 
                   city=None, country=None, default_vat_rate=None, customer_type=None):
    """Update an existing customer"""
    customer = Customer.query.get(customer_id)
    if not customer:
        return None, "Customer not found"
    
    if name is not None:
        customer.name = name
    if vat_number is not None:
        customer.vat_number = vat_number
    if email is not None:
        customer.email = email
    if phone is not None:
        customer.phone = phone
    if first_name is not None:
        customer.first_name = first_name
    if last_name is not None:
        customer.last_name = last_name
    if street is not None:
        customer.street = street
    if postal_code is not None:
        customer.postal_code = postal_code
    if city is not None:
        customer.city = city
    if country is not None:
        customer.country = country
    if default_vat_rate is not None:
        customer.default_vat_rate = default_vat_rate
    if customer_type is not None:
        customer.customer_type = customer_type
    
    db.session.commit()
    return customer, "Customer updated successfully"

def delete_customer(customer_id):
    """Delete a customer by ID"""
    customer = Customer.query.get(customer_id)
    if not customer:
        return False, "Customer not found"
        
    # Check if customer has invoices
    has_invoices = Invoice.query.filter_by(customer_id=customer_id).first() is not None
    if has_invoices:
        return False, "Cannot delete customer with existing invoices"
    
    db.session.delete(customer)
    db.session.commit()
    return True, "Customer deleted successfully"

def get_customer(customer_id):
    """Get a customer by ID"""
    return Customer.query.get(customer_id)

def get_customers(customer_type=None):
    """Get all customers with optional filtering by type"""
    if customer_type:
        return Customer.query.filter_by(customer_type=customer_type).all()
    return Customer.query.all()

def search_customers(term):
    """Search customers by name, VAT number, or email"""
    search_term = f"%{term}%"
    return Customer.query.filter(
        db.or_(
            Customer.name.ilike(search_term),
            Customer.vat_number.ilike(search_term),
            Customer.email.ilike(search_term)
        )
    ).all()

# Invoice Management
def check_duplicate_invoice(invoice_number=None, customer_id=None, date=None, amount_incl_vat=None):
    """
    Check if an invoice might be a duplicate based on multiple criteria
    
    Returns:
        tuple: (is_duplicate, existing_invoice_id)
    """
    if invoice_number:
        # Direct check for exact invoice number match
        existing = Invoice.query.filter_by(invoice_number=invoice_number).first()
        if existing:
            return True, existing.id
    
    # If other criteria provided, check for likely duplicates
    if customer_id and date and amount_incl_vat:
        amount_incl_vat = Decimal(str(amount_incl_vat))
        
        # Find any invoice with same customer and date
        existing = Invoice.query.filter_by(
            customer_id=customer_id,
            date=date
        ).all()
        
        for inv in existing:
            # Check if amounts are very close (accounting for rounding)
            if abs(Decimal(str(inv.amount_incl_vat)) - amount_incl_vat) < Decimal('0.01'):
                return True, inv.id
    
    # No duplicate found
    return False, None

def add_invoice(customer_id, date, invoice_type, amount_incl_vat, vat_rate, invoice_number=None, file_path=None, check_duplicate=True):
    """Add a new invoice"""
    # Check if customer exists
    customer = Customer.query.get(customer_id)
    if not customer:
        return None, "Customer not found", None
    
    # Convert to Decimal for accurate calculations
    amount_incl_vat = Decimal(str(amount_incl_vat))
    vat_rate = Decimal(str(vat_rate))
    
    # Convert date string to date object if needed
    if isinstance(date, str):
        try:
            date = datetime.strptime(date, '%Y-%m-%d').date()
        except ValueError:
            return None, "Invalid date format. Expected YYYY-MM-DD", None
    
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
    
    # Calculate amounts
    vat_amount = amount_incl_vat - (amount_incl_vat / (1 + vat_rate / 100))
    amount_excl_vat = amount_incl_vat - vat_amount
    
    # Create new invoice with auto-generated invoice number if not provided
    invoice = Invoice(
        invoice_number=invoice_number if invoice_number else get_next_invoice_number(),
        customer_id=customer_id,
        date=date,
        invoice_type=invoice_type,
        amount_incl_vat=float(amount_incl_vat),
        amount_excl_vat=float(amount_excl_vat),
        vat_rate=float(vat_rate),
        vat_amount=float(vat_amount),
        file_path=file_path
    )
    
    db.session.add(invoice)
    db.session.commit()
    
    return invoice, "Invoice added successfully", None

def update_invoice(invoice_id, customer_id=None, date=None, invoice_type=None, 
                  amount_incl_vat=None, vat_rate=None, invoice_number=None, file_path=None):
    """Update an existing invoice"""
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return None, "Invoice not found", None
    
    # If customer_id is being changed, verify the new customer exists
    if customer_id is not None and customer_id != invoice.customer_id:
        customer = Customer.query.get(customer_id)
        if not customer:
            return None, "Customer not found", None
        invoice.customer_id = customer_id
    
    # Only recalculate amounts if amount_incl_vat or vat_rate is being changed
    if amount_incl_vat is not None or vat_rate is not None:
        # Use existing values for params not provided
        calc_amount = amount_incl_vat if amount_incl_vat is not None else invoice.amount_incl_vat
        calc_rate = vat_rate if vat_rate is not None else invoice.vat_rate
        
        # Convert to Decimal for accurate calculations
        calc_amount = Decimal(str(calc_amount))
        calc_rate = Decimal(str(calc_rate))
        
        # Calculate amounts
        vat_amount = calc_amount - (calc_amount / (1 + calc_rate / 100))
        amount_excl_vat = calc_amount - vat_amount
        
        # Update invoice amounts
        if amount_incl_vat is not None:
            invoice.amount_incl_vat = float(calc_amount)
        if vat_rate is not None:
            invoice.vat_rate = float(calc_rate)
        
        invoice.amount_excl_vat = float(amount_excl_vat)
        invoice.vat_amount = float(vat_amount)
    
    # Update other fields if provided
    if date is not None:
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return None, "Invalid date format. Expected YYYY-MM-DD", None
        invoice.date = date
    
    if invoice_type is not None:
        invoice.invoice_type = invoice_type
    
    # Check for duplicate invoice number if changing it
    if invoice_number is not None and invoice_number != invoice.invoice_number:
        is_duplicate, duplicate_id = check_duplicate_invoice(invoice_number=invoice_number)
        if is_duplicate and duplicate_id != invoice_id:
            return None, "Duplicate invoice number detected", duplicate_id
        invoice.invoice_number = invoice_number
    
    if file_path is not None:
        invoice.file_path = file_path
    
    db.session.commit()
    return invoice, "Invoice updated successfully", None

def delete_invoice(invoice_id):
    """Delete an invoice by ID"""
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return False, "Invoice not found"
    
    # Remove the file if it exists
    if invoice.file_path and os.path.exists(invoice.file_path):
        try:
            os.remove(invoice.file_path)
        except OSError:
            # Just log the error but proceed with deletion
            pass
    
    db.session.delete(invoice)
    db.session.commit()
    return True, "Invoice deleted successfully"

def get_invoice(invoice_id):
    """Get an invoice by ID"""
    return Invoice.query.get(invoice_id)

def get_invoices(customer_id=None, invoice_type=None, start_date=None, end_date=None):
    """
    Get invoices with optional filtering
    
    Args:
        customer_id: Filter by customer
        invoice_type: 'income' or 'expense'
        start_date: Start date for filtering
        end_date: End date for filtering
    """
    query = Invoice.query
    
    # Apply filters
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    
    if invoice_type:
        query = query.filter_by(invoice_type=invoice_type)
    
    if start_date:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        query = query.filter(Invoice.date >= start_date)
    
    if end_date:
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        query = query.filter(Invoice.date <= end_date)
    
    # Sort by date (newest first)
    query = query.order_by(Invoice.date.desc())
    
    return query.all()

# VAT Calculations for Belgian reporting
def calculate_vat_report(year, quarter=None, month=None):
    """
    Calculate VAT report for Belgian reporting
    
    Args:
        year: Year to report
        quarter: Quarter (1-4) if reporting quarterly
        month: Month (1-12) if reporting monthly
    
    Returns:
        Dictionary with VAT grids:
        - Grid 03: Sales excluding VAT
        - Grid 54: Output VAT (VAT on sales)
        - Grid 59: Input VAT (VAT on purchases)
        - Grid 71: VAT balance (54-59)
    """
    # Start with base query for the year
    query = Invoice.query.filter(extract('year', Invoice.date) == year)
    
    # Apply quarter or month filter if specified
    if quarter:
        # Calculate the quarter based on month
        query = query.filter((extract('month', Invoice.date) - 1) // 3 + 1 == quarter)
    
    if month:
        query = query.filter(extract('month', Invoice.date) == month)
    
    # Get all the filtered invoices
    filtered_invoices = query.all()
    
    # Calculate VAT grids
    income_invoices = [inv for inv in filtered_invoices if inv.invoice_type == 'income']
    expense_invoices = [inv for inv in filtered_invoices if inv.invoice_type == 'expense']
    
    grid_03 = sum(inv.amount_excl_vat for inv in income_invoices)
    grid_54 = sum(inv.vat_amount for inv in income_invoices)
    grid_59 = sum(inv.vat_amount for inv in expense_invoices)
    grid_71 = grid_54 - grid_59
    
    return {
        'grid_03': grid_03,
        'grid_54': grid_54,
        'grid_59': grid_59,
        'grid_71': grid_71,
        'year': year,
        'quarter': quarter,
        'month': month,
        'invoices': filtered_invoices
    }

# Financial Summary functions
def get_monthly_summary(year):
    """Get monthly financial summary for a year"""
    monthly_data = []
    
    for month in range(1, 13):
        # Query for this month
        month_query = Invoice.query.filter(
            extract('year', Invoice.date) == year,
            extract('month', Invoice.date) == month
        )
        
        # Get income invoices and expense invoices
        income_invoices = month_query.filter_by(invoice_type='income').all()
        expense_invoices = month_query.filter_by(invoice_type='expense').all()
        
        # Calculate sums
        income = sum(inv.amount_excl_vat for inv in income_invoices)
        expenses = sum(inv.amount_excl_vat for inv in expense_invoices)
        vat_collected = sum(inv.vat_amount for inv in income_invoices)
        vat_paid = sum(inv.vat_amount for inv in expense_invoices)
        
        monthly_data.append({
            'month': month,
            'month_name': datetime(year, month, 1).strftime('%B'),
            'income': income,
            'expenses': expenses,
            'profit': income - expenses,
            'vat_collected': vat_collected,
            'vat_paid': vat_paid,
            'vat_balance': vat_collected - vat_paid
        })
    
    return monthly_data

def get_quarterly_summary(year):
    """Get quarterly financial summary for a year"""
    quarterly_data = []
    
    for quarter in range(1, 5):
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        
        # Query for this quarter using month range
        quarter_query = Invoice.query.filter(
            extract('year', Invoice.date) == year,
            extract('month', Invoice.date) >= start_month,
            extract('month', Invoice.date) <= end_month
        )
        
        # Get income invoices and expense invoices
        income_invoices = quarter_query.filter_by(invoice_type='income').all()
        expense_invoices = quarter_query.filter_by(invoice_type='expense').all()
        
        # Calculate sums
        income = sum(inv.amount_excl_vat for inv in income_invoices)
        expenses = sum(inv.amount_excl_vat for inv in expense_invoices)
        vat_collected = sum(inv.vat_amount for inv in income_invoices)
        vat_paid = sum(inv.vat_amount for inv in expense_invoices)
        
        quarterly_data.append({
            'quarter': quarter,
            'income': income,
            'expenses': expenses,
            'profit': income - expenses,
            'vat_collected': vat_collected,
            'vat_paid': vat_paid,
            'vat_balance': vat_collected - vat_paid
        })
    
    return quarterly_data

def get_customer_summary():
    """Get financial summary by customer"""
    customer_data = []
    
    # Get all customers
    customers = Customer.query.all()
    
    for customer in customers:
        # Get all invoices for this customer
        income_invoices = Invoice.query.filter_by(
            customer_id=customer.id, 
            invoice_type='income'
        ).all()
        
        expense_invoices = Invoice.query.filter_by(
            customer_id=customer.id, 
            invoice_type='expense'
        ).all()
        
        # Calculate totals for income
        income = sum(inv.amount_excl_vat for inv in income_invoices)
        expenses = sum(inv.amount_excl_vat for inv in expense_invoices)
        vat_collected = sum(inv.vat_amount for inv in income_invoices)
        vat_paid = sum(inv.vat_amount for inv in expense_invoices)
        
        customer_data.append({
            'customer_id': customer.id,
            'customer_name': customer.name,
            'customer_type': customer.customer_type,
            'income': income,
            'expenses': expenses,
            'vat_collected': vat_collected,
            'vat_paid': vat_paid,
            'invoice_count': len(income_invoices) + len(expense_invoices)
        })
    
    # Sort by income, highest first
    customer_data.sort(key=lambda x: x['income'], reverse=True)
    
    return customer_data

# Helper function to get VAT rates (for dropdown)
def get_vat_rates():
    """Return the available Belgian VAT rates"""
    return [
        {'value': 0.0, 'label': '0%'},
        {'value': 6.0, 'label': '6%'},
        {'value': 21.0, 'label': '21%'}
    ]
