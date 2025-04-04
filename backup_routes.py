"""
Routes voor het beheren van backups in het systeem.
"""
import os
import json
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_login import login_required, current_user
from app import app, db
from models import Workspace, BackupSettings, BackupSchedule, BackupJob, User
from utils import format_currency, admin_required, super_admin_required
from backup_service import BackupService, BackupSubscription

# Logger setup
logger = logging.getLogger(__name__)

# Backup dashboard voor admins
@app.route('/admin/backups')
@login_required
@admin_required
def admin_backups():
    """
    Toont het backup beheer dashboard voor admins
    """
    # Haal de juiste werkruimtes op afhankelijk van rechten
    if current_user.is_super_admin:
        workspaces = Workspace.query.all()
    else:
        workspaces = Workspace.query.filter_by(id=current_user.workspace_id).all()
    
    # Maak een BackupService instantie
    backup_service = BackupService(app, db)
    
    # Haal beschikbare backup bestanden op per werkruimte
    workspace_backups = {}
    for workspace in workspaces:
        # Controleer of er backup_settings bestaan voor deze werkruimte
        backup_settings = BackupSettings.query.filter_by(workspace_id=workspace.id).first()
        
        # Als er geen instellingen zijn, maak ze aan met standaardwaarden
        if not backup_settings:
            backup_settings = BackupSettings(
                workspace_id=workspace.id,
                plan='free',
                backup_enabled=True,
                include_uploads=True,
                auto_backup_enabled=False,
                auto_backup_interval='daily',
                auto_backup_time='02:00',
                retention_days=7
            )
            db.session.add(backup_settings)
            db.session.commit()
        
        # Zoek bestaande backup bestanden
        backups = backup_service.list_backups(workspace_id=workspace.id)
        
        # Haal recente backup jobs op
        backup_jobs = BackupJob.query.filter_by(backup_settings_id=backup_settings.id).order_by(
            BackupJob.created_at.desc()).limit(10).all()
        
        # Haal plan limieten en beschrijving op
        plan_limits = backup_settings.get_plan_limits()
        plan_description = backup_settings.get_plan_description()
        
        # Voeg informatie toe aan de dictionary
        workspace_backups[workspace.id] = {
            'workspace': workspace,
            'backup_settings': backup_settings,
            'backups': backups,
            'backup_jobs': backup_jobs,
            'plan_limits': plan_limits,
            'plan_description': plan_description
        }
    
    # Extra informatie over abonnementen
    subscription_plans = [
        BackupSubscription.FREE_PLAN,
        BackupSubscription.BASIC_PLAN,
        BackupSubscription.PREMIUM_PLAN,
        BackupSubscription.ENTERPRISE_PLAN
    ]
    
    plan_details = {}
    for plan in subscription_plans:
        plan_details[plan] = BackupSubscription.get_plan_description(plan)
    
    return render_template(
        'admin_backups.html',
        workspace_backups=workspace_backups,
        workspaces=workspaces,
        subscription_plans=subscription_plans,
        plan_details=plan_details,
        format_currency=format_currency
    )

# API endpoints voor backup management
@app.route('/api/backups/create', methods=['POST'])
@login_required
@admin_required
def api_create_backup():
    """
    API endpoint om een backup te maken
    """
    data = request.json or {}
    workspace_id = data.get('workspace_id')
    include_uploads = data.get('include_uploads', True)
    backup_name = data.get('backup_name')
    tables = data.get('tables')
    
    # Valideer of de gebruiker toegang heeft tot deze werkruimte
    if not current_user.is_super_admin and current_user.workspace_id != int(workspace_id):
        return jsonify({
            'success': False,
            'message': 'Geen toegang tot deze werkruimte'
        }), 403
    
    # Controleer of er backup_settings bestaan voor deze werkruimte
    backup_settings = BackupSettings.query.filter_by(workspace_id=workspace_id).first()
    if not backup_settings:
        return jsonify({
            'success': False,
            'message': 'Backup instellingen niet gevonden voor deze werkruimte'
        }), 404
    
    # Controleer plan limieten
    plan_limits = backup_settings.get_plan_limits()
    existing_backups = BackupJob.query.filter_by(
        backup_settings_id=backup_settings.id, 
        status='completed'
    ).count()
    
    if existing_backups >= plan_limits.get('max_backups', 2):
        return jsonify({
            'success': False,
            'message': f"U heeft het maximum aantal backups bereikt ({plan_limits.get('max_backups')}). "
                      "Verwijder oude backups of upgrade uw abonnement."
        }), 400
    
    # Als het plan geen uploads toestaat, zet include_uploads op False
    if not plan_limits.get('include_uploads', False):
        include_uploads = False
    
    try:
        # Maak een BackupService instantie
        backup_service = BackupService(app, db)
        
        # Maak een nieuwe BackupJob aan
        backup_job = BackupJob(
            backup_settings_id=backup_settings.id,
            scheduled=False,
            backup_type='full' if include_uploads else 'database',
            status='running',
            include_uploads=include_uploads,
            tables=json.dumps(tables) if tables else None,
            start_time=datetime.now()
        )
        
        db.session.add(backup_job)
        db.session.commit()
        
        # Voer de backup uit
        backup_info = backup_service.create_backup(
            workspace_id=workspace_id,
            include_uploads=include_uploads,
            tables=tables,
            backup_name=backup_name
        )
        
        # Update de BackupJob met resultaten
        backup_job.status = 'completed'
        backup_job.end_time = datetime.now()
        backup_job.backup_id = backup_info.get('backup_id')
        backup_job.filename = backup_info.get('filename')
        backup_job.file_size = backup_info.get('size')
        backup_job.result_message = 'Backup succesvol voltooid'
        
        # Update de laatste backup datum in de instellingen
        backup_settings.last_backup_date = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Backup succesvol gemaakt',
            'backup_info': backup_info
        })
        
    except Exception as e:
        logger.error(f"Fout bij het maken van een backup: {str(e)}")
        
        # Update de BackupJob met foutinformatie als die bestaat
        if 'backup_job' in locals():
            backup_job.status = 'failed'
            backup_job.end_time = datetime.now()
            backup_job.error_details = str(e)
            db.session.commit()
        
        return jsonify({
            'success': False,
            'message': f'Fout bij het maken van een backup: {str(e)}'
        }), 500

@app.route('/api/backups/restore', methods=['POST'])
@login_required
@admin_required
def api_restore_backup():
    """
    API endpoint om een backup te herstellen
    """
    data = request.json or {}
    backup_filename = data.get('backup_filename')
    target_workspace_id = data.get('target_workspace_id')
    include_uploads = data.get('include_uploads', True)
    tables = data.get('tables')
    
    # Valideer of de gebruiker toegang heeft tot deze werkruimte
    if not current_user.is_super_admin and current_user.workspace_id != int(target_workspace_id):
        return jsonify({
            'success': False,
            'message': 'Geen toegang tot deze werkruimte'
        }), 403
    
    # Controleer of er backup_settings bestaan voor deze werkruimte
    backup_settings = BackupSettings.query.filter_by(workspace_id=target_workspace_id).first()
    if not backup_settings:
        return jsonify({
            'success': False,
            'message': 'Backup instellingen niet gevonden voor deze werkruimte'
        }), 404
    
    try:
        # Maak een BackupService instantie
        backup_service = BackupService(app, db)
        
        # Bepaal het volledige pad van het backup bestand
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
        backup_path = os.path.join(backup_dir, backup_filename)
        
        if not os.path.exists(backup_path):
            return jsonify({
                'success': False,
                'message': 'Backup bestand niet gevonden'
            }), 404
        
        # Herstel de backup
        result = backup_service.restore_backup(
            backup_path=backup_path,
            workspace_id=target_workspace_id,
            include_uploads=include_uploads,
            tables=tables
        )
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Backup succesvol hersteld'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Fout bij het herstellen van de backup'
            }), 500
            
    except Exception as e:
        logger.error(f"Fout bij het herstellen van een backup: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fout bij het herstellen van de backup: {str(e)}'
        }), 500

@app.route('/api/backups/delete', methods=['POST'])
@login_required
@admin_required
def api_delete_backup():
    """
    API endpoint om een backup te verwijderen
    """
    data = request.json or {}
    backup_filename = data.get('backup_filename')
    workspace_id = data.get('workspace_id')
    
    # Valideer of de gebruiker toegang heeft tot deze werkruimte
    if not current_user.is_super_admin and current_user.workspace_id != int(workspace_id):
        return jsonify({
            'success': False,
            'message': 'Geen toegang tot deze werkruimte'
        }), 403
    
    try:
        # Maak een BackupService instantie
        backup_service = BackupService(app, db)
        
        # Bepaal het volledige pad van het backup bestand
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
        backup_path = os.path.join(backup_dir, backup_filename)
        
        if not os.path.exists(backup_path):
            return jsonify({
                'success': False,
                'message': 'Backup bestand niet gevonden'
            }), 404
        
        # Verwijder ook de bijbehorende BackupJob als die bestaat
        backup_job = BackupJob.query.filter_by(filename=backup_filename).first()
        if backup_job:
            db.session.delete(backup_job)
            db.session.commit()
        
        # Verwijder het backup bestand
        result = backup_service.delete_backup(backup_path)
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Backup succesvol verwijderd'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Fout bij het verwijderen van de backup'
            }), 500
            
    except Exception as e:
        logger.error(f"Fout bij het verwijderen van een backup: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fout bij het verwijderen van de backup: {str(e)}'
        }), 500

@app.route('/api/backups/update-settings', methods=['POST'])
@login_required
@admin_required
def api_update_backup_settings():
    """
    API endpoint om backup instellingen bij te werken
    """
    data = request.json or {}
    workspace_id = data.get('workspace_id')
    
    # Valideer of de gebruiker toegang heeft tot deze werkruimte
    if not current_user.is_super_admin and current_user.workspace_id != int(workspace_id):
        return jsonify({
            'success': False,
            'message': 'Geen toegang tot deze werkruimte'
        }), 403
    
    # Controleer of er backup_settings bestaan voor deze werkruimte
    backup_settings = BackupSettings.query.filter_by(workspace_id=workspace_id).first()
    if not backup_settings:
        return jsonify({
            'success': False,
            'message': 'Backup instellingen niet gevonden voor deze werkruimte'
        }), 404
    
    try:
        # Update velden die zijn meegestuurd
        if 'backup_enabled' in data:
            backup_settings.backup_enabled = data['backup_enabled']
        
        if 'include_uploads' in data:
            backup_settings.include_uploads = data['include_uploads']
        
        if 'auto_backup_enabled' in data:
            backup_settings.auto_backup_enabled = data['auto_backup_enabled']
        
        if 'auto_backup_interval' in data:
            backup_settings.auto_backup_interval = data['auto_backup_interval']
        
        if 'auto_backup_time' in data:
            backup_settings.auto_backup_time = data['auto_backup_time']
        
        if 'auto_backup_day' in data:
            backup_settings.auto_backup_day = data['auto_backup_day']
        
        if 'retention_days' in data:
            backup_settings.retention_days = data['retention_days']
        
        # Als er een nieuw plan is, update het plan met de bijbehorende instellingen
        if 'plan' in data:
            backup_settings.update_plan(data['plan'], data.get('duration_months', 12))
        
        backup_settings.updated_at = datetime.now()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Backup instellingen succesvol bijgewerkt'
        })
        
    except Exception as e:
        logger.error(f"Fout bij het bijwerken van backup instellingen: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fout bij het bijwerken van backup instellingen: {str(e)}'
        }), 500

@app.route('/api/backups/download/<path:filename>')
@login_required
@admin_required
def download_backup(filename):
    """
    Download een backup bestand
    """
    # Maak een BackupService instantie om alle backups te bekijken
    backup_service = BackupService(app, db)
    backups = backup_service.list_backups()
    
    # Zoek de gevraagde backup
    backup_info = None
    for backup in backups:
        if backup['filename'] == filename:
            backup_info = backup
            break
    
    if not backup_info:
        flash('Backup bestand niet gevonden', 'danger')
        return redirect(url_for('admin_backups'))
    
    # Controleer of de gebruiker toegang heeft tot deze backup
    if not current_user.is_super_admin:
        workspace_id = backup_info.get('workspace_id')
        if workspace_id and workspace_id != current_user.workspace_id:
            flash('U heeft geen toegang tot deze backup', 'danger')
            return redirect(url_for('admin_backups'))
    
    # Bepaal het volledige pad van het backup bestand
    backup_dir = os.environ.get("BACKUP_DIR", "backups")
    backup_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(backup_path):
        flash('Backup bestand niet gevonden op de server', 'danger')
        return redirect(url_for('admin_backups'))
    
    # Stuur het bestand
    return send_file(
        backup_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/zip'
    )

@app.route('/api/backups/schedule', methods=['POST'])
@login_required
@admin_required
def api_schedule_backup():
    """
    API endpoint om een backup planning aan te maken of bij te werken
    """
    data = request.json or {}
    workspace_id = data.get('workspace_id')
    schedule_id = data.get('schedule_id')  # None voor nieuwe planning
    
    # Valideer of de gebruiker toegang heeft tot deze werkruimte
    if not current_user.is_super_admin and current_user.workspace_id != int(workspace_id):
        return jsonify({
            'success': False,
            'message': 'Geen toegang tot deze werkruimte'
        }), 403
    
    # Controleer of er backup_settings bestaan voor deze werkruimte
    backup_settings = BackupSettings.query.filter_by(workspace_id=workspace_id).first()
    if not backup_settings:
        return jsonify({
            'success': False,
            'message': 'Backup instellingen niet gevonden voor deze werkruimte'
        }), 404
    
    # Controleer plan limieten - alleen sommige abonnementen mogen automatische backups instellen
    plan_limits = backup_settings.get_plan_limits()
    if not plan_limits.get('auto_backup', False):
        return jsonify({
            'success': False,
            'message': 'Uw huidige abonnement ondersteunt geen automatische backups. '
                    'Upgrade uw abonnement om deze functionaliteit te gebruiken.'
        }), 400
    
    try:
        # Als er een bestaande schedule_id is, werk die bij
        if schedule_id:
            schedule = BackupSchedule.query.get(schedule_id)
            if not schedule or schedule.backup_settings_id != backup_settings.id:
                return jsonify({
                    'success': False,
                    'message': 'Planning niet gevonden'
                }), 404
        else:
            # Anders maak een nieuwe planning aan
            schedule = BackupSchedule(backup_settings_id=backup_settings.id)
        
        # Update velden
        schedule.interval = data.get('interval', 'daily')
        schedule.time = data.get('time', '02:00')
        
        if schedule.interval in ['weekly', 'monthly'] and 'day' in data:
            schedule.day = data['day']
        
        schedule.include_uploads = data.get('include_uploads', True)
        schedule.retention_days = data.get('retention_days', 7)
        schedule.is_active = data.get('is_active', True)
        
        if 'tables' in data:
            schedule.tables = json.dumps(data['tables'])
        
        # Bereken de volgende uitvoerdatum
        schedule.next_run = schedule.calculate_next_run()
        
        # Sla op
        if not schedule_id:
            db.session.add(schedule)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Backup planning succesvol bijgewerkt',
            'schedule_id': schedule.id,
            'next_run': schedule.next_run.isoformat() if schedule.next_run else None
        })
        
    except Exception as e:
        logger.error(f"Fout bij het inplannen van een backup: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fout bij het inplannen van een backup: {str(e)}'
        }), 500

@app.route('/api/backups/delete-schedule', methods=['POST'])
@login_required
@admin_required
def api_delete_schedule():
    """
    API endpoint om een backup planning te verwijderen
    """
    data = request.json or {}
    schedule_id = data.get('schedule_id')
    
    if not schedule_id:
        return jsonify({
            'success': False,
            'message': 'Geen planning ID opgegeven'
        }), 400
    
    # Zoek de planning
    schedule = BackupSchedule.query.get(schedule_id)
    if not schedule:
        return jsonify({
            'success': False,
            'message': 'Planning niet gevonden'
        }), 404
    
    # Haal de backup_settings en workspace_id op
    backup_settings = BackupSettings.query.get(schedule.backup_settings_id)
    if not backup_settings:
        return jsonify({
            'success': False,
            'message': 'Backup instellingen niet gevonden'
        }), 404
    
    # Valideer of de gebruiker toegang heeft tot deze werkruimte
    if not current_user.is_super_admin and current_user.workspace_id != backup_settings.workspace_id:
        return jsonify({
            'success': False,
            'message': 'Geen toegang tot deze werkruimte'
        }), 403
    
    try:
        # Verwijder de planning
        db.session.delete(schedule)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Backup planning succesvol verwijderd'
        })
        
    except Exception as e:
        logger.error(f"Fout bij het verwijderen van een backup planning: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Fout bij het verwijderen van een backup planning: {str(e)}'
        }), 500