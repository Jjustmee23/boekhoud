import os
import logging
from datetime import datetime
from decimal import Decimal
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify, session
from app import app
from models import (
    add_customer, update_customer, delete_customer, get_customer, get_customers,
    add_invoice, update_invoice, delete_invoice, get_invoice, get_invoices,
    calculate_vat_report, get_monthly_summary, get_quarterly_summary, get_customer_summary
)
from utils import (
    format_currency, format_decimal, generate_pdf_invoice, export_to_excel, export_to_csv,
    get_vat_rates, date_to_quarter, get_quarters, get_months, get_years
)

# Dashboard routes
@app.route('/')
def dashboard():
    # Get current year
    current_year = datetime.now().year
    
    # Get summaries
    monthly_summary = get_monthly_summary(current_year)
    quarterly_summary = get_quarterly_summary(current_year)
    customer_summary = get_customer_summary()
    
    # Calculate totals for the year
    year_income = sum(month['income'] for month in monthly_summary)
    year_expenses = sum(month['expenses'] for month in monthly_summary)
    year_profit = year_income - year_expenses
    
    # Calculate VAT totals
    vat_collected = sum(month['vat_collected'] for month in monthly_summary)
    vat_paid = sum(month['vat_paid'] for month in monthly_summary)
    vat_balance = vat_collected - vat_paid
    
    # Get recent invoices
    recent_invoices = get_invoices()[:5]  # Get 5 most recent
    
    # Enrich invoices with customer data
    for invoice in recent_invoices:
        customer = get_customer(invoice['customer_id'])
        invoice['customer_name'] = customer['name'] if customer else 'Unknown Customer'
    
    return render_template(
        'dashboard.html',
        monthly_summary=monthly_summary,
        quarterly_summary=quarterly_summary,
        customer_summary=customer_summary,
        year_income=year_income,
        year_expenses=year_expenses,
        year_profit=year_profit,
        vat_collected=vat_collected,
        vat_paid=vat_paid,
        vat_balance=vat_balance,
        recent_invoices=recent_invoices,
        current_year=current_year,
        format_currency=format_currency,
        get_customer=get_customer,
        now=datetime.now()
    )

@app.route('/dashboard/api/monthly-data/<int:year>')
def api_monthly_data(year):
    """API endpoint for monthly chart data"""
    monthly_data = get_monthly_summary(year)
    
    # Format data for Chart.js
    labels = [month['month_name'] for month in monthly_data]
    income_data = [float(month['income']) for month in monthly_data]
    expense_data = [float(month['expenses']) for month in monthly_data]
    profit_data = [float(month['profit']) for month in monthly_data]
    
    return jsonify({
        'labels': labels,
        'income': income_data,
        'expenses': expense_data,
        'profit': profit_data
    })

@app.route('/dashboard/api/quarterly-data/<int:year>')
def api_quarterly_data(year):
    """API endpoint for quarterly chart data"""
    quarterly_data = get_quarterly_summary(year)
    
    # Format data for Chart.js
    labels = [f"Q{quarter['quarter']}" for quarter in quarterly_data]
    income_data = [float(quarter['income']) for quarter in quarterly_data]
    expense_data = [float(quarter['expenses']) for quarter in quarterly_data]
    profit_data = [float(quarter['profit']) for quarter in quarterly_data]
    
    return jsonify({
        'labels': labels,
        'income': income_data,
        'expenses': expense_data,
        'profit': profit_data
    })

# Invoice management routes
@app.route('/invoices')
def invoices_list():
    # Get filter parameters
    customer_id = request.args.get('customer_id')
    invoice_type = request.args.get('type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Get invoices with filters
    invoices_data = get_invoices(
        customer_id=customer_id,
        invoice_type=invoice_type,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get all customers for filter dropdown
    customers_data = get_customers()
    
    # Enrich invoices with customer data
    for invoice in invoices_data:
        customer = get_customer(invoice['customer_id'])
        invoice['customer_name'] = customer['name'] if customer else 'Unknown Customer'
    
    return render_template(
        'invoices.html',
        invoices=invoices_data,
        customers=customers_data,
        filter_customer_id=customer_id,
        filter_type=invoice_type,
        filter_start_date=start_date,
        filter_end_date=end_date,
        format_currency=format_currency
    )

@app.route('/invoices/new', methods=['GET', 'POST'])
def new_invoice():
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        date = request.form.get('date')
        invoice_type = request.form.get('type')
        amount_incl_vat = request.form.get('amount_incl_vat')
        vat_rate = request.form.get('vat_rate')
        
        # Validate data
        if not all([customer_id, date, invoice_type, amount_incl_vat, vat_rate]):
            flash('All fields are required', 'danger')
            customers_data = get_customers()
            return render_template(
                'invoice_form.html',
                customers=customers_data,
                vat_rates=get_vat_rates(),
                invoice={'date': datetime.now().strftime('%Y-%m-%d'), 'type': 'income'}
            )
        
        # Add invoice
        try:
            invoice = add_invoice(
                customer_id=customer_id,
                date=date,
                invoice_type=invoice_type,
                amount_incl_vat=float(amount_incl_vat),
                vat_rate=float(vat_rate)
            )
            
            if invoice:
                flash('Invoice added successfully', 'success')
                return redirect(url_for('invoices_list'))
            else:
                flash('Failed to add invoice', 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        customers_data = get_customers()
        return render_template(
            'invoice_form.html',
            customers=customers_data,
            vat_rates=get_vat_rates(),
            invoice=request.form
        )
    
    # GET request - show the form
    customers_data = get_customers()
    return render_template(
        'invoice_form.html',
        customers=customers_data,
        vat_rates=get_vat_rates(),
        invoice={'date': datetime.now().strftime('%Y-%m-%d'), 'type': 'income'}
    )

@app.route('/invoices/<invoice_id>')
def view_invoice(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoices_list'))
    
    customer = get_customer(invoice['customer_id'])
    
    return render_template(
        'invoice_detail.html',
        invoice=invoice,
        customer=customer,
        format_currency=format_currency
    )

@app.route('/invoices/<invoice_id>/edit', methods=['GET', 'POST'])
def edit_invoice(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoices_list'))
    
    if request.method == 'POST':
        # Get form data
        customer_id = request.form.get('customer_id')
        date = request.form.get('date')
        invoice_type = request.form.get('type')
        amount_incl_vat = request.form.get('amount_incl_vat')
        vat_rate = request.form.get('vat_rate')
        
        # Validate data
        if not all([customer_id, date, invoice_type, amount_incl_vat, vat_rate]):
            flash('All fields are required', 'danger')
            customers_data = get_customers()
            return render_template(
                'invoice_form.html',
                invoice=invoice,
                customers=customers_data,
                vat_rates=get_vat_rates(),
                edit_mode=True
            )
        
        # Update invoice
        try:
            updated_invoice = update_invoice(
                invoice_id=invoice_id,
                customer_id=customer_id,
                date=date,
                invoice_type=invoice_type,
                amount_incl_vat=float(amount_incl_vat),
                vat_rate=float(vat_rate)
            )
            
            if updated_invoice:
                flash('Invoice updated successfully', 'success')
                return redirect(url_for('view_invoice', invoice_id=invoice_id))
            else:
                flash('Failed to update invoice', 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        customers_data = get_customers()
        return render_template(
            'invoice_form.html',
            invoice=request.form,
            customers=customers_data,
            vat_rates=get_vat_rates(),
            edit_mode=True
        )
    
    # GET request - show the form
    customers_data = get_customers()
    return render_template(
        'invoice_form.html',
        invoice=invoice,
        customers=customers_data,
        vat_rates=get_vat_rates(),
        edit_mode=True
    )

@app.route('/invoices/<invoice_id>/delete', methods=['POST'])
def delete_invoice_route(invoice_id):
    success, message = delete_invoice(invoice_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('invoices_list'))

@app.route('/invoices/<invoice_id>/pdf')
def generate_invoice_pdf(invoice_id):
    invoice = get_invoice(invoice_id)
    if not invoice:
        flash('Invoice not found', 'danger')
        return redirect(url_for('invoices_list'))
    
    customer = get_customer(invoice['customer_id'])
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('invoices_list'))
    
    # Generate PDF
    pdf_path = generate_pdf_invoice(invoice, customer)
    
    # Filename for download
    filename = f"Invoice-{invoice['invoice_number']}.pdf"
    
    # Send file and then delete it after sending
    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# Customer management routes
@app.route('/customers')
def customers_list():
    customers_data = get_customers()
    
    # Add invoice counts and totals
    for customer in customers_data:
        customer_invoices = get_invoices(customer_id=customer['id'])
        customer['invoice_count'] = len(customer_invoices)
        customer['total_amount'] = sum(
            inv['amount_incl_vat'] 
            for inv in customer_invoices 
            if inv['invoice_type'] == 'income'
        )
    
    return render_template(
        'customers.html',
        customers=customers_data,
        format_currency=format_currency
    )

@app.route('/customers/new', methods=['GET', 'POST'])
def new_customer():
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        address = request.form.get('address')
        vat_number = request.form.get('vat_number')
        email = request.form.get('email')
        
        # Validate data
        if not all([name, address, email]):
            flash('Name, address and email are required', 'danger')
            return render_template(
                'customer_form.html',
                customer=request.form
            )
        
        # Add customer
        try:
            customer = add_customer(
                name=name,
                address=address,
                vat_number=vat_number,
                email=email
            )
            
            if customer:
                flash('Customer added successfully', 'success')
                return redirect(url_for('customers_list'))
            else:
                flash('Failed to add customer', 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        return render_template(
            'customer_form.html',
            customer=request.form
        )
    
    # GET request - show the form
    return render_template('customer_form.html')

@app.route('/customers/<customer_id>')
def view_customer(customer_id):
    customer = get_customer(customer_id)
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('customers_list'))
    
    # Get customer invoices
    customer_invoices = get_invoices(customer_id=customer_id)
    
    # Calculate total income and expense
    total_income = sum(
        inv['amount_incl_vat'] 
        for inv in customer_invoices 
        if inv['invoice_type'] == 'income'
    )
    total_expense = sum(
        inv['amount_incl_vat'] 
        for inv in customer_invoices 
        if inv['invoice_type'] == 'expense'
    )
    
    return render_template(
        'customer_detail.html',
        customer=customer,
        invoices=customer_invoices,
        total_income=total_income,
        total_expense=total_expense,
        format_currency=format_currency
    )

@app.route('/customers/<customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    customer = get_customer(customer_id)
    if not customer:
        flash('Customer not found', 'danger')
        return redirect(url_for('customers_list'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        address = request.form.get('address')
        vat_number = request.form.get('vat_number')
        email = request.form.get('email')
        
        # Validate data
        if not all([name, address, email]):
            flash('Name, address and email are required', 'danger')
            return render_template(
                'customer_form.html',
                customer=request.form,
                edit_mode=True
            )
        
        # Update customer
        try:
            updated_customer = update_customer(
                customer_id=customer_id,
                name=name,
                address=address,
                vat_number=vat_number,
                email=email
            )
            
            if updated_customer:
                flash('Customer updated successfully', 'success')
                return redirect(url_for('view_customer', customer_id=customer_id))
            else:
                flash('Failed to update customer', 'danger')
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
        
        # If we get here, there was an error
        return render_template(
            'customer_form.html',
            customer=request.form,
            edit_mode=True
        )
    
    # GET request - show the form
    return render_template(
        'customer_form.html',
        customer=customer,
        edit_mode=True
    )

@app.route('/customers/<customer_id>/delete', methods=['POST'])
def delete_customer_route(customer_id):
    success, message = delete_customer(customer_id)
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('customers_list'))

# Reports routes
@app.route('/reports')
def reports():
    # Get the current year and quarter
    current_year = datetime.now().year
    current_quarter = date_to_quarter(datetime.now())
    
    return render_template(
        'reports.html',
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        current_year=current_year,
        current_quarter=current_quarter
    )

@app.route('/reports/monthly/<int:year>', methods=['GET'])
def monthly_report(year):
    monthly_data = get_monthly_summary(year)
    
    # Get export format
    export_format = request.args.get('format')
    if export_format:
        if export_format == 'excel':
            temp_file = export_to_excel(
                monthly_data, 
                f'Monthly_Report_{year}.xlsx',
                columns=['month_name', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Monthly_Report_{year}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            temp_file = export_to_csv(
                monthly_data, 
                f'Monthly_Report_{year}.csv',
                columns=['month_name', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Monthly_Report_{year}.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'reports.html',
        report_type='monthly',
        report_data=monthly_data,
        year=year,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency
    )

@app.route('/reports/quarterly/<int:year>', methods=['GET'])
def quarterly_report(year):
    quarterly_data = get_quarterly_summary(year)
    
    # Get export format
    export_format = request.args.get('format')
    if export_format:
        if export_format == 'excel':
            temp_file = export_to_excel(
                quarterly_data, 
                f'Quarterly_Report_{year}.xlsx',
                columns=['quarter', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Quarterly_Report_{year}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            temp_file = export_to_csv(
                quarterly_data, 
                f'Quarterly_Report_{year}.csv',
                columns=['quarter', 'income', 'expenses', 'profit', 'vat_collected', 'vat_paid', 'vat_balance']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'Quarterly_Report_{year}.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'reports.html',
        report_type='quarterly',
        report_data=quarterly_data,
        year=year,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency
    )

@app.route('/reports/customers', methods=['GET'])
def customer_report():
    customer_data = get_customer_summary()
    
    # Get export format
    export_format = request.args.get('format')
    if export_format:
        if export_format == 'excel':
            temp_file = export_to_excel(
                customer_data, 
                'Customer_Report.xlsx',
                columns=['customer_name', 'income', 'vat_collected', 'invoice_count']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name='Customer_Report.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            temp_file = export_to_csv(
                customer_data, 
                'Customer_Report.csv',
                columns=['customer_name', 'income', 'vat_collected', 'invoice_count']
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name='Customer_Report.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'reports.html',
        report_type='customers',
        report_data=customer_data,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency
    )

# VAT report routes
@app.route('/vat-report')
def vat_report_form():
    return render_template(
        'vat_report.html',
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        current_year=datetime.now().year,
        current_quarter=date_to_quarter(datetime.now())
    )

@app.route('/vat-report/generate', methods=['POST'])
def generate_vat_report():
    # Get form data
    year = int(request.form.get('year'))
    report_type = request.form.get('report_type')  # 'quarterly' or 'monthly'
    
    if report_type == 'quarterly':
        quarter = int(request.form.get('quarter'))
        month = None
        report = calculate_vat_report(year=year, quarter=quarter)
        period_name = f"Q{quarter} {year}"
    else:  # monthly
        month = int(request.form.get('month'))
        quarter = None
        report = calculate_vat_report(year=year, month=month)
        month_name = datetime(year, month, 1).strftime('%B')
        period_name = f"{month_name} {year}"
    
    # Get export format
    export_format = request.form.get('export_format')
    if export_format:
        if export_format == 'excel':
            # Prepare data for export
            export_data = [{
                'Period': period_name,
                'Grid 03 (Sales excl. VAT)': report['grid_03'],
                'Grid 54 (Output VAT)': report['grid_54'],
                'Grid 59 (Input VAT)': report['grid_59'],
                'Grid 71 (VAT Balance)': report['grid_71']
            }]
            
            temp_file = export_to_excel(
                export_data, 
                f'VAT_Report_{period_name}.xlsx'
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'VAT_Report_{period_name}.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        elif export_format == 'csv':
            # Prepare data for export
            export_data = [{
                'Period': period_name,
                'Grid 03 (Sales excl. VAT)': report['grid_03'],
                'Grid 54 (Output VAT)': report['grid_54'],
                'Grid 59 (Input VAT)': report['grid_59'],
                'Grid 71 (VAT Balance)': report['grid_71']
            }]
            
            temp_file = export_to_csv(
                export_data, 
                f'VAT_Report_{period_name}.csv'
            )
            return send_file(
                temp_file,
                as_attachment=True,
                download_name=f'VAT_Report_{period_name}.csv',
                mimetype='text/csv'
            )
    
    # Regular HTML response
    return render_template(
        'vat_report.html',
        report=report,
        period_name=period_name,
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        format_currency=format_currency
    )

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('base.html', error='Page not found', now=datetime.now()), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('base.html', error='An internal error occurred', now=datetime.now()), 500
