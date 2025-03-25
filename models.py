from datetime import datetime
import uuid
from decimal import Decimal

# In-memory database storage
customers = {}  # id -> customer
invoices = {}   # id -> invoice

# Helper function to generate next invoice number
def get_next_invoice_number():
    """Generate the next invoice number in format INV-YYYY-XXXX"""
    year = datetime.now().year
    # Count invoices for this year
    count = sum(1 for inv in invoices.values() if f"INV-{year}" in inv['invoice_number'])
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
def add_invoice(customer_id, date, invoice_type, amount_incl_vat, vat_rate):
    """Add a new invoice"""
    if customer_id not in customers:
        return None
    
    invoice_id = str(uuid.uuid4())
    
    # Convert to Decimal for accurate calculations
    amount_incl_vat = Decimal(str(amount_incl_vat))
    vat_rate = Decimal(str(vat_rate))
    
    # Calculate amounts
    vat_amount = amount_incl_vat - (amount_incl_vat / (1 + vat_rate / 100))
    amount_excl_vat = amount_incl_vat - vat_amount
    
    invoice = {
        'id': invoice_id,
        'invoice_number': get_next_invoice_number(),
        'customer_id': customer_id,
        'date': date,
        'invoice_type': invoice_type,  # 'income' or 'expense'
        'amount_incl_vat': float(amount_incl_vat),
        'amount_excl_vat': float(amount_excl_vat),
        'vat_rate': float(vat_rate),
        'vat_amount': float(vat_amount),
        'created_at': datetime.now()
    }
    
    invoices[invoice_id] = invoice
    return invoice

def update_invoice(invoice_id, customer_id, date, invoice_type, amount_incl_vat, vat_rate):
    """Update an existing invoice"""
    if invoice_id not in invoices or customer_id not in customers:
        return None
    
    # Convert to Decimal for accurate calculations
    amount_incl_vat = Decimal(str(amount_incl_vat))
    vat_rate = Decimal(str(vat_rate))
    
    # Calculate amounts
    vat_amount = amount_incl_vat - (amount_incl_vat / (1 + vat_rate / 100))
    amount_excl_vat = amount_incl_vat - vat_amount
    
    invoice = invoices[invoice_id]
    invoice['customer_id'] = customer_id
    invoice['date'] = date
    invoice['invoice_type'] = invoice_type
    invoice['amount_incl_vat'] = float(amount_incl_vat)
    invoice['amount_excl_vat'] = float(amount_excl_vat)
    invoice['vat_rate'] = float(vat_rate)
    invoice['vat_amount'] = float(vat_amount)
    invoice['updated_at'] = datetime.now()
    
    return invoice

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
    # Filter invoices by period
    filtered_invoices = list(invoices.values())
    
    # Filter by year
    filtered_invoices = [
        inv for inv in filtered_invoices 
        if datetime.strptime(inv['date'], '%Y-%m-%d').year == year
    ]
    
    # Filter by quarter or month if specified
    if quarter:
        filtered_invoices = [
            inv for inv in filtered_invoices
            if ((datetime.strptime(inv['date'], '%Y-%m-%d').month - 1) // 3) + 1 == quarter
        ]
    
    if month:
        filtered_invoices = [
            inv for inv in filtered_invoices
            if datetime.strptime(inv['date'], '%Y-%m-%d').month == month
        ]
    
    # Calculate VAT grids
    grid_03 = sum(inv['amount_excl_vat'] for inv in filtered_invoices if inv['invoice_type'] == 'income')
    grid_54 = sum(inv['vat_amount'] for inv in filtered_invoices if inv['invoice_type'] == 'income')
    grid_59 = sum(inv['vat_amount'] for inv in filtered_invoices if inv['invoice_type'] == 'expense')
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
        # Get all invoices for this month
        month_invoices = [
            inv for inv in invoices.values()
            if datetime.strptime(inv['date'], '%Y-%m-%d').year == year
            and datetime.strptime(inv['date'], '%Y-%m-%d').month == month
        ]
        
        income = sum(inv['amount_excl_vat'] for inv in month_invoices if inv['invoice_type'] == 'income')
        expenses = sum(inv['amount_excl_vat'] for inv in month_invoices if inv['invoice_type'] == 'expense')
        vat_collected = sum(inv['vat_amount'] for inv in month_invoices if inv['invoice_type'] == 'income')
        vat_paid = sum(inv['vat_amount'] for inv in month_invoices if inv['invoice_type'] == 'expense')
        
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
        
        # Get all invoices for this quarter
        quarter_invoices = [
            inv for inv in invoices.values()
            if datetime.strptime(inv['date'], '%Y-%m-%d').year == year
            and start_month <= datetime.strptime(inv['date'], '%Y-%m-%d').month <= end_month
        ]
        
        income = sum(inv['amount_excl_vat'] for inv in quarter_invoices if inv['invoice_type'] == 'income')
        expenses = sum(inv['amount_excl_vat'] for inv in quarter_invoices if inv['invoice_type'] == 'expense')
        vat_collected = sum(inv['vat_amount'] for inv in quarter_invoices if inv['invoice_type'] == 'income')
        vat_paid = sum(inv['vat_amount'] for inv in quarter_invoices if inv['invoice_type'] == 'expense')
        
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
    
    for customer_id, customer in customers.items():
        # Get all invoices for this customer
        customer_invoices = [inv for inv in invoices.values() if inv['customer_id'] == customer_id]
        
        income = sum(inv['amount_excl_vat'] for inv in customer_invoices if inv['invoice_type'] == 'income')
        vat_collected = sum(inv['vat_amount'] for inv in customer_invoices if inv['invoice_type'] == 'income')
        invoice_count = len([inv for inv in customer_invoices if inv['invoice_type'] == 'income'])
        
        customer_data.append({
            'customer_id': customer_id,
            'customer_name': customer['name'],
            'income': income,
            'vat_collected': vat_collected,
            'invoice_count': invoice_count
        })
    
    # Sort by income, highest first
    customer_data.sort(key=lambda x: x['income'], reverse=True)
    
    return customer_data
