import tempfile
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, send_file
from . import report_blueprint
from models import (
    calculate_vat_report, get_monthly_summary, get_quarterly_summary, get_customer_summary
)
from utils import (
    format_currency, format_decimal, export_to_excel, export_to_csv,
    get_vat_rates, get_quarters, get_months, get_years
)

# Reports routes
@report_blueprint.route('/')
def reports():
    current_year = datetime.now().year
    return render_template(
        'reports.html',
        current_year=current_year,
        years=get_years(),
        now=datetime.now()
    )

@report_blueprint.route('/monthly/<int:year>', methods=['GET'])
def monthly_report(year):
    # Get monthly data
    monthly_data = get_monthly_summary(year)
    
    # Calculate yearly totals
    year_income = sum(month['income'] for month in monthly_data)
    year_expenses = sum(month['expenses'] for month in monthly_data)
    year_profit = year_income - year_expenses
    
    # Calculate yearly VAT totals
    year_vat_collected = sum(month['vat_collected'] for month in monthly_data)
    year_vat_paid = sum(month['vat_paid'] for month in monthly_data)
    year_vat_balance = year_vat_collected - year_vat_paid
    
    # Handle export
    format_type = request.args.get('format')
    if format_type in ['excel', 'csv']:
        # Prepare data for export
        export_data = []
        for month in monthly_data:
            export_data.append({
                'Month': month['month_name'],
                'Income': month['income'],
                'Expenses': month['expenses'],
                'Profit': month['profit'],
                'VAT Collected': month['vat_collected'],
                'VAT Paid': month['vat_paid'],
                'VAT Balance': month['vat_balance']
            })
        
        # Add totals row
        export_data.append({
            'Month': 'TOTAL',
            'Income': year_income,
            'Expenses': year_expenses,
            'Profit': year_profit,
            'VAT Collected': year_vat_collected,
            'VAT Paid': year_vat_paid,
            'VAT Balance': year_vat_balance
        })
        
        # Export to specified format
        filename = f"monthly_report_{year}"
        if format_type == 'excel':
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
                temp_path = temp.name
            
            export_to_excel(export_data, temp_path)
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{filename}.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:  # CSV
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp:
                temp_path = temp.name
            
            export_to_csv(export_data, temp_path)
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{filename}.csv",
                mimetype='text/csv'
            )
    
    # Render template
    return render_template(
        'monthly_report.html',
        monthly_data=monthly_data,
        year=year,
        years=get_years(),
        year_income=year_income,
        year_expenses=year_expenses,
        year_profit=year_profit,
        year_vat_collected=year_vat_collected,
        year_vat_paid=year_vat_paid,
        year_vat_balance=year_vat_balance,
        format_currency=format_currency,
        now=datetime.now()
    )

@report_blueprint.route('/quarterly/<int:year>', methods=['GET'])
def quarterly_report(year):
    # Get quarterly data
    quarterly_data = get_quarterly_summary(year)
    
    # Calculate yearly totals
    year_income = sum(quarter['income'] for quarter in quarterly_data)
    year_expenses = sum(quarter['expenses'] for quarter in quarterly_data)
    year_profit = year_income - year_expenses
    
    # Calculate yearly VAT totals
    year_vat_collected = sum(quarter['vat_collected'] for quarter in quarterly_data)
    year_vat_paid = sum(quarter['vat_paid'] for quarter in quarterly_data)
    year_vat_balance = year_vat_collected - year_vat_paid
    
    # Handle export
    format_type = request.args.get('format')
    if format_type in ['excel', 'csv']:
        # Prepare data for export
        export_data = []
        for quarter in quarterly_data:
            export_data.append({
                'Quarter': f"Q{quarter['quarter']}",
                'Income': quarter['income'],
                'Expenses': quarter['expenses'],
                'Profit': quarter['profit'],
                'VAT Collected': quarter['vat_collected'],
                'VAT Paid': quarter['vat_paid'],
                'VAT Balance': quarter['vat_balance']
            })
        
        # Add totals row
        export_data.append({
            'Quarter': 'TOTAL',
            'Income': year_income,
            'Expenses': year_expenses,
            'Profit': year_profit,
            'VAT Collected': year_vat_collected,
            'VAT Paid': year_vat_paid,
            'VAT Balance': year_vat_balance
        })
        
        # Export to specified format
        filename = f"quarterly_report_{year}"
        if format_type == 'excel':
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
                temp_path = temp.name
            
            export_to_excel(export_data, temp_path)
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{filename}.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:  # CSV
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp:
                temp_path = temp.name
            
            export_to_csv(export_data, temp_path)
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{filename}.csv",
                mimetype='text/csv'
            )
    
    # Render template
    return render_template(
        'quarterly_report.html',
        quarterly_data=quarterly_data,
        year=year,
        years=get_years(),
        year_income=year_income,
        year_expenses=year_expenses,
        year_profit=year_profit,
        year_vat_collected=year_vat_collected,
        year_vat_paid=year_vat_paid,
        year_vat_balance=year_vat_balance,
        format_currency=format_currency,
        now=datetime.now()
    )

@report_blueprint.route('/customers', methods=['GET'])
def customer_report():
    # Get customer summary data
    customer_data = get_customer_summary()
    
    # Calculate totals
    total_income = sum(c['income'] for c in customer_data)
    total_expenses = sum(c['expenses'] for c in customer_data)
    total_profit = total_income - total_expenses
    
    # Calculate VAT totals
    total_vat_collected = sum(c['vat_collected'] for c in customer_data)
    total_vat_paid = sum(c['vat_paid'] for c in customer_data)
    total_vat_balance = total_vat_collected - total_vat_paid
    
    # Handle export
    format_type = request.args.get('format')
    if format_type in ['excel', 'csv']:
        # Prepare data for export
        export_data = []
        for customer in customer_data:
            export_data.append({
                'Customer/Supplier': customer['name'],
                'Type': customer['customer_type'].capitalize(),
                'Income': customer['income'],
                'Expenses': customer['expenses'],
                'Balance': customer['balance'],
                'VAT Collected': customer['vat_collected'],
                'VAT Paid': customer['vat_paid'],
                'VAT Balance': customer['vat_balance']
            })
        
        # Add totals row
        export_data.append({
            'Customer/Supplier': 'TOTAL',
            'Type': '',
            'Income': total_income,
            'Expenses': total_expenses,
            'Balance': total_profit,
            'VAT Collected': total_vat_collected,
            'VAT Paid': total_vat_paid,
            'VAT Balance': total_vat_balance
        })
        
        # Export to specified format
        filename = "customer_report"
        if format_type == 'excel':
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp:
                temp_path = temp.name
            
            export_to_excel(export_data, temp_path)
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{filename}.xlsx",
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
        else:  # CSV
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp:
                temp_path = temp.name
            
            export_to_csv(export_data, temp_path)
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{filename}.csv",
                mimetype='text/csv'
            )
    
    # Render template
    return render_template(
        'customer_report.html',
        customers=customer_data,
        total_income=total_income,
        total_expenses=total_expenses,
        total_profit=total_profit,
        total_vat_collected=total_vat_collected,
        total_vat_paid=total_vat_paid,
        total_vat_balance=total_vat_balance,
        format_currency=format_currency,
        now=datetime.now()
    )

@report_blueprint.route('/vat')
def vat_report_form():
    current_year = datetime.now().year
    current_quarter = (datetime.now().month - 1) // 3 + 1
    
    return render_template(
        'vat_report_form.html',
        years=get_years(),
        quarters=get_quarters(),
        months=get_months(),
        default_year=current_year,
        default_quarter=current_quarter,
        default_month=datetime.now().month,
        now=datetime.now()
    )

@report_blueprint.route('/vat/generate', methods=['POST'])
def generate_vat_report():
    year = int(request.form.get('year', datetime.now().year))
    report_type = request.form.get('report_type', 'quarterly')
    quarter = int(request.form.get('quarter', 1)) if report_type == 'quarterly' else None
    month = int(request.form.get('month', 1)) if report_type == 'monthly' else None
    
    # Calculate VAT report
    vat_report = calculate_vat_report(year, quarter, month)
    
    # Determine period name for display
    if report_type == 'quarterly':
        period_name = f"Q{quarter} {year}"
    else:
        month_name = datetime(year, month, 1).strftime('%B')
        period_name = f"{month_name} {year}"
    
    # Render template
    return render_template(
        'vat_report.html',
        vat_report=vat_report,
        period_name=period_name,
        format_currency=format_currency,
        format_decimal=format_decimal,
        now=datetime.now()
    )