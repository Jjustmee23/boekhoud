from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from . import customer_blueprint
from models import (
    add_customer, update_customer, delete_customer, get_customer, get_customers,
    get_invoices
)
from utils import format_currency, get_vat_rates

# Customer management routes
@customer_blueprint.route('/')
def customers_list():
    # Get filter parameters
    customer_type = request.args.get('type')
    
    # Get customers with filters
    customers_data = get_customers(customer_type=customer_type)
    
    return render_template(
        'customers.html',
        customers=customers_data,
        filter_type=customer_type,
        format_currency=format_currency,
        now=datetime.now()
    )

@customer_blueprint.route('/new', methods=['GET', 'POST'])
def new_customer():
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        vat_number = request.form.get('vat_number') or None
        email = request.form.get('email') or None
        phone = request.form.get('phone') or None
        first_name = request.form.get('first_name') or None
        last_name = request.form.get('last_name') or None
        street = request.form.get('street') or None
        postal_code = request.form.get('postal_code') or None
        city = request.form.get('city') or None
        country = request.form.get('country') or None
        default_vat_rate = request.form.get('default_vat_rate') or 21.0
        customer_type = request.form.get('customer_type') or 'customer'
        
        # Validate data
        if not name:
            flash('Name is required', 'danger')
            return render_template(
                'customer_form.html',
                customer=request.form,
                vat_rates=get_vat_rates(),
                now=datetime.now()
            )
        
        # Add customer
        try:
            customer, message = add_customer(
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
                default_vat_rate=float(default_vat_rate) if default_vat_rate else 21.0,
                customer_type=customer_type
            )
            
            if customer:
                flash(message, 'success')
                return redirect(url_for('customer.view_customer', customer_id=customer['id']))
            else:
                flash(message, 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        return render_template(
            'customer_form.html',
            customer=request.form,
            vat_rates=get_vat_rates(),
            now=datetime.now()
        )
    
    # GET request - show the form
    return render_template(
        'customer_form.html',
        customer={'customer_type': 'customer', 'default_vat_rate': 21.0},
        vat_rates=get_vat_rates(),
        now=datetime.now()
    )

@customer_blueprint.route('/<customer_id>')
def view_customer(customer_id):
    customer = get_customer(customer_id)
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('customer.customers_list'))
    
    # Get invoices for this customer
    invoices = get_invoices(customer_id=customer_id)
    
    # Calculate totals
    total_income = sum(invoice['amount_incl_vat'] for invoice in invoices if invoice['invoice_type'] == 'income')
    total_expenses = sum(invoice['amount_incl_vat'] for invoice in invoices if invoice['invoice_type'] == 'expense')
    total_balance = total_income - total_expenses
    
    # Calculate VAT totals
    total_vat_collected = sum(invoice['vat_amount'] for invoice in invoices if invoice['invoice_type'] == 'income')
    total_vat_paid = sum(invoice['vat_amount'] for invoice in invoices if invoice['invoice_type'] == 'expense')
    total_vat_balance = total_vat_collected - total_vat_paid
    
    return render_template(
        'customer_detail.html',
        customer=customer,
        invoices=invoices,
        total_income=total_income,
        total_expenses=total_expenses,
        total_balance=total_balance,
        total_vat_collected=total_vat_collected,
        total_vat_paid=total_vat_paid,
        total_vat_balance=total_vat_balance,
        format_currency=format_currency,
        now=datetime.now()
    )

@customer_blueprint.route('/<customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = get_customer(customer_id)
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('customer.customers_list'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        vat_number = request.form.get('vat_number') or None
        email = request.form.get('email') or None
        phone = request.form.get('phone') or None
        first_name = request.form.get('first_name') or None
        last_name = request.form.get('last_name') or None
        street = request.form.get('street') or None
        postal_code = request.form.get('postal_code') or None
        city = request.form.get('city') or None
        country = request.form.get('country') or None
        default_vat_rate = request.form.get('default_vat_rate') or 21.0
        customer_type = request.form.get('customer_type') or 'customer'
        
        # Validate data
        if not name:
            flash('Name is required', 'danger')
            return render_template(
                'customer_form.html',
                customer=request.form,
                vat_rates=get_vat_rates(),
                edit_mode=True,
                now=datetime.now()
            )
        
        # Update customer
        try:
            updated_customer, message = update_customer(
                customer_id=customer_id,
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
                default_vat_rate=float(default_vat_rate) if default_vat_rate else 21.0,
                customer_type=customer_type
            )
            
            if updated_customer:
                flash(message, 'success')
                return redirect(url_for('customer.view_customer', customer_id=customer_id))
            else:
                flash(message, 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        return render_template(
            'customer_form.html',
            customer=request.form,
            vat_rates=get_vat_rates(),
            edit_mode=True,
            now=datetime.now()
        )
    
    # GET request - show the form
    return render_template(
        'customer_form.html',
        customer=customer,
        vat_rates=get_vat_rates(),
        edit_mode=True,
        now=datetime.now()
    )

@customer_blueprint.route('/<customer_id>/delete', methods=['POST'])
def delete_customer_route(customer_id):
    success, message = delete_customer(customer_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('customer.customers_list'))