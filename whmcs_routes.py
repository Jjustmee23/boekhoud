"""
Routes voor WHMCS-integratie en synchronisatie
"""
import os
import json
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, current_app, redirect, url_for, flash
from flask_login import login_required, current_user
from whmcs_service import WHMCSService
from models import Customer, Invoice, SystemSettings
from database import db
from utils import admin_required, super_admin_required

whmcs_bp = Blueprint('whmcs', __name__)

@whmcs_bp.route('/admin/whmcs')
@login_required
@admin_required
def whmcs_dashboard():
    """WHMCS-integratie dashboard"""
    # Haal WHMCS-instellingen op
    settings = SystemSettings.query.filter_by(key='whmcs_integration').first()
    
    # Haal statistieken op
    whmcs_customers_count = Customer.query.filter_by(
        synced_from_whmcs=True,
        workspace_id=current_user.workspace_id
    ).count() if not current_user.is_super_admin else Customer.query.filter_by(synced_from_whmcs=True).count()
    
    whmcs_invoices_count = Invoice.query.filter_by(
        synced_from_whmcs=True,
        workspace_id=current_user.workspace_id
    ).count() if not current_user.is_super_admin else Invoice.query.filter_by(synced_from_whmcs=True).count()
    
    # Controleer de WHMCS API-status
    whmcs_service = WHMCSService()
    is_configured = whmcs_service.is_configured()
    
    # Check API-status voor meer gedetailleerde informatie
    api_status = None
    if is_configured:
        try:
            api_status = whmcs_service.check_api_status()
        except Exception as e:
            current_app.logger.error(f"Error checking WHMCS API status: {str(e)}")
            api_status = {
                'enabled': False,
                'message': f"Fout bij controleren API-status: {str(e)}",
                'details': {'error': str(e)}
            }
    
    # Converteer laatste synchronisatietijd naar een leesbare string
    last_sync_str = None
    if settings and settings.whmcs_last_sync:
        last_sync_str = settings.whmcs_last_sync.strftime('%d-%m-%Y %H:%M:%S')
    
    return render_template(
        'admin/whmcs_dashboard.html',
        settings=settings,
        whmcs_customers_count=whmcs_customers_count,
        whmcs_invoices_count=whmcs_invoices_count,
        is_configured=is_configured,
        api_status=api_status,
        whmcs_api_url=whmcs_service.api_url,
        whmcs_api_identifier=whmcs_service.api_identifier,
        # Verberg de geheimen voor de veiligheid maar toon indicators
        whmcs_api_secret_set=bool(whmcs_service.api_secret),
        whmcs_api_token_set=bool(whmcs_service.api_token),
        last_sync=last_sync_str
    )

@whmcs_bp.route('/admin/whmcs/settings', methods=['POST'])
@login_required
@admin_required
def update_whmcs_settings():
    """Update WHMCS-integratie instellingen"""
    # Haal gegevens op uit het formulier
    whmcs_api_url = request.form.get('whmcs_api_url')
    whmcs_api_identifier = request.form.get('whmcs_api_identifier')
    whmcs_api_secret = request.form.get('whmcs_api_secret')
    whmcs_api_token = request.form.get('whmcs_api_token')
    auto_sync = 'auto_sync' in request.form
    
    # Haal bestaande instellingen op of maak nieuw
    settings = SystemSettings.query.filter_by(key='whmcs_integration').first()
    if not settings:
        settings = SystemSettings(key='whmcs_integration', value='enabled')
        db.session.add(settings)
    
    # Update de instellingen
    settings.whmcs_api_url = whmcs_api_url
    
    # Sla Identifier en Secret alleen op als er geen token wordt gebruikt
    if not whmcs_api_token:
        settings.whmcs_api_identifier = whmcs_api_identifier
        if whmcs_api_secret:  # Alleen bijwerken als er een waarde is opgegeven
            settings.whmcs_api_secret = whmcs_api_secret
    else:
        # Als er een token is, verwijder de identifier/secret
        settings.whmcs_api_identifier = None
        settings.whmcs_api_secret = None
        
    # Sla token op
    settings.whmcs_api_token = whmcs_api_token if whmcs_api_token else settings.whmcs_api_token
    
    settings.whmcs_auto_sync = auto_sync
    settings.updated_at = datetime.now()
    
    # Sla op in de database
    db.session.commit()
    
    # Update ook het .env bestand voor persistente opslag
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        
        # Lees bestaande inhoud
        env_content = {}
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        env_content[key] = value
        
        # Update met nieuwe waarden
        env_content['WHMCS_API_URL'] = whmcs_api_url
        
        # Sla Identifier en Secret alleen op als er geen token wordt gebruikt
        if not whmcs_api_token:
            env_content['WHMCS_API_IDENTIFIER'] = whmcs_api_identifier
            if whmcs_api_secret:
                env_content['WHMCS_API_SECRET'] = whmcs_api_secret
        else:
            # Als er een token is, verwijder de identifier/secret uit env
            if 'WHMCS_API_IDENTIFIER' in env_content:
                del env_content['WHMCS_API_IDENTIFIER']
            if 'WHMCS_API_SECRET' in env_content:
                del env_content['WHMCS_API_SECRET']
            # Sla token op
            env_content['WHMCS_API_TOKEN'] = whmcs_api_token
        
        # Schrijf terug naar bestand
        with open(env_path, 'w') as f:
            for key, value in env_content.items():
                f.write(f"{key}={value}\n")
    except Exception as e:
        current_app.logger.error(f"Fout bij bijwerken .env bestand: {str(e)}")
    
    # Test de verbinding na bijwerken van instellingen
    whmcs_service = WHMCSService()
    if whmcs_service.is_configured():
        api_status = whmcs_service.check_api_status()
        if api_status['enabled']:
            flash('WHMCS-instellingen succesvol bijgewerkt en verbinding getest', 'success')
        else:
            flash(f'WHMCS-instellingen bijgewerkt, maar er is een probleem met de verbinding: {api_status["message"]}', 'warning')
    else:
        flash('WHMCS-instellingen bijgewerkt, maar API is niet volledig geconfigureerd', 'warning')
    
    return redirect(url_for('whmcs.whmcs_dashboard'))

@whmcs_bp.route('/admin/whmcs/test-connection', methods=['POST'])
@login_required
@admin_required
def test_whmcs_connection():
    """Test de verbinding met de WHMCS API"""
    whmcs_service = WHMCSService()
    
    try:
        if not whmcs_service.is_configured():
            return jsonify({
                'success': False,
                'message': 'WHMCS API is niet geconfigureerd. Voeg API-gegevens toe.'
            })
        
        # Gebruik de verbeterde check_api_status methode voor gedetailleerde informatie
        api_status = whmcs_service.check_api_status()
        
        if api_status['enabled']:
            # API is succesvol
            system_url = api_status['details'].get('system_url', 'Onbekend')
            api_version = api_status['details'].get('api_version', 'Onbekend')
            
            return jsonify({
                'success': True,
                'message': 'Verbinding met WHMCS API succesvol!',
                'data': {
                    'system_url': system_url,
                    'api_version': api_version,
                    'status': api_status
                }
            })
        else:
            # API heeft een probleem
            return jsonify({
                'success': False,
                'message': api_status['message'],
                'data': {
                    'details': api_status['details'],
                    'status': api_status
                }
            })
    except Exception as e:
        current_app.logger.error(f"Error testing WHMCS connection: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Fout bij verbinden met WHMCS API: {str(e)}"
        })

@whmcs_bp.route('/admin/whmcs/sync/clients', methods=['POST'])
@login_required
@admin_required
def sync_whmcs_clients():
    """Synchroniseer klanten van WHMCS naar de applicatie"""
    whmcs_service = WHMCSService()
    
    try:
        if not whmcs_service.is_configured():
            return jsonify({
                'success': False,
                'message': 'WHMCS API is niet geconfigureerd. Voeg API-gegevens toe.'
            })
        
        # Synchroniseer klanten
        workspace_id = current_user.workspace_id if not current_user.is_super_admin else request.form.get('workspace_id')
        if workspace_id is None or workspace_id == '':
            return jsonify({
                'success': False,
                'message': 'Geen werkruimte ID opgegeven voor synchronisatie'
            })
        
        result = whmcs_service.sync_clients_to_app(int(workspace_id))
        
        # Update laatste synchronisatietijd
        settings = SystemSettings.query.filter_by(key='whmcs_integration').first()
        if settings:
            settings.whmcs_last_sync = datetime.now()
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f"Synchronisatie voltooid: {result['added']} klanten toegevoegd, {result['updated']} bijgewerkt",
            'data': result
        })
    except Exception as e:
        current_app.logger.error(f"Fout bij synchroniseren van WHMCS-klanten: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Fout bij synchroniseren van WHMCS-klanten: {str(e)}"
        })

@whmcs_bp.route('/admin/whmcs/sync/invoices', methods=['POST'])
@login_required
@admin_required
def sync_whmcs_invoices():
    """Synchroniseer facturen van WHMCS naar de applicatie"""
    whmcs_service = WHMCSService()
    
    try:
        if not whmcs_service.is_configured():
            return jsonify({
                'success': False,
                'message': 'WHMCS API is niet geconfigureerd. Voeg API-gegevens toe.'
            })
        
        # Bepaal werkruimte
        workspace_id = current_user.workspace_id if not current_user.is_super_admin else request.form.get('workspace_id')
        if workspace_id is None or workspace_id == '':
            return jsonify({
                'success': False,
                'message': 'Geen werkruimte ID opgegeven voor synchronisatie'
            })
        
        # Factuurstatus filter (optioneel)
        status = request.form.get('status')
        
        # Synchroniseer facturen
        result = whmcs_service.sync_invoices_to_app(int(workspace_id), status)
        
        # Update laatste synchronisatietijd
        settings = SystemSettings.query.filter_by(key='whmcs_integration').first()
        if settings:
            settings.whmcs_last_sync = datetime.now()
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f"Synchronisatie voltooid: {result['added']} facturen toegevoegd, {result['updated']} bijgewerkt, {result['no_customer']} zonder gekoppelde klant",
            'data': result
        })
    except Exception as e:
        current_app.logger.error(f"Fout bij synchroniseren van WHMCS-facturen: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"Fout bij synchroniseren van WHMCS-facturen: {str(e)}"
        })

@whmcs_bp.route('/admin/whmcs/client/<int:whmcs_client_id>')
@login_required
@admin_required
def view_whmcs_client(whmcs_client_id):
    """Bekijk details van een WHMCS-klant"""
    whmcs_service = WHMCSService()
    
    try:
        if not whmcs_service.is_configured():
            flash('WHMCS API is niet geconfigureerd. Voeg API-gegevens toe.', 'danger')
            return redirect(url_for('whmcs.whmcs_dashboard'))
        
        # Haal klantgegevens op uit WHMCS
        client_data = whmcs_service.get_client(client_id=whmcs_client_id)
        
        if not client_data:
            flash(f'Klant met ID {whmcs_client_id} niet gevonden in WHMCS', 'danger')
            return redirect(url_for('whmcs.whmcs_dashboard'))
        
        # Haal facturen op voor deze klant
        invoices_data = whmcs_service.get_invoices(client_id=whmcs_client_id)
        
        # Controleer of de klant al gesynchroniseerd is met de applicatie
        workspace_id = current_user.workspace_id if not current_user.is_super_admin else None
        query = Customer.query.filter_by(whmcs_client_id=whmcs_client_id)
        if workspace_id:
            query = query.filter_by(workspace_id=workspace_id)
        local_customer = query.first()
        
        return render_template(
            'admin/whmcs_client_details.html',
            client=client_data,
            invoices=invoices_data,
            local_customer=local_customer
        )
    except Exception as e:
        flash(f'Fout bij ophalen van WHMCS-klantgegevens: {str(e)}', 'danger')
        return redirect(url_for('whmcs.whmcs_dashboard'))

@whmcs_bp.route('/admin/whmcs/invoice/<int:whmcs_invoice_id>')
@login_required
@admin_required
def view_whmcs_invoice(whmcs_invoice_id):
    """Bekijk details van een WHMCS-factuur"""
    whmcs_service = WHMCSService()
    
    try:
        if not whmcs_service.is_configured():
            flash('WHMCS API is niet geconfigureerd. Voeg API-gegevens toe.', 'danger')
            return redirect(url_for('whmcs.whmcs_dashboard'))
        
        # Haal factuurgegevens op uit WHMCS
        invoice_data = whmcs_service.get_invoice(whmcs_invoice_id)
        
        if not invoice_data:
            flash(f'Factuur met ID {whmcs_invoice_id} niet gevonden in WHMCS', 'danger')
            return redirect(url_for('whmcs.whmcs_dashboard'))
        
        # Controleer of de factuur al gesynchroniseerd is met de applicatie
        workspace_id = current_user.workspace_id if not current_user.is_super_admin else None
        query = Invoice.query.filter_by(whmcs_invoice_id=whmcs_invoice_id)
        if workspace_id:
            query = query.filter_by(workspace_id=workspace_id)
        local_invoice = query.first()
        
        return render_template(
            'admin/whmcs_invoice_details.html',
            invoice=invoice_data,
            local_invoice=local_invoice
        )
    except Exception as e:
        flash(f'Fout bij ophalen van WHMCS-factuurgegevens: {str(e)}', 'danger')
        return redirect(url_for('whmcs.whmcs_dashboard'))