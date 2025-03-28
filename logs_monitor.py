"""
Logs monitoring module voor het bekijken en analyseren van logs.
Biedt een webinterface voor toegang tot logbestanden en foutmeldingen.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from models import User, db

# Maximaal aantal regels om uit een log bestand te lezen
MAX_LOG_LINES = 500

# Blueprint registreren
logs_bp = Blueprint('logs', __name__, url_prefix='/admin/logs')

# Logger voor deze module
logger = logging.getLogger(__name__)

@logs_bp.before_request
def check_admin_access():
    """Controleer of de huidige gebruiker admin rechten heeft"""
    if not current_user.is_authenticated or not (current_user.is_admin or current_user.is_super_admin):
        logger.warning(f"Niet-geautoriseerde toegangspoging tot logs door gebruiker: {current_user.username if current_user.is_authenticated else 'niet ingelogd'}")
        abort(403)  # Forbidden

@logs_bp.route('/')
@login_required
def logs_dashboard():
    """Hoofdpagina voor log monitoring"""
    log_files = _get_available_log_files()
    return render_template('logs_dashboard.html', log_files=log_files, now=datetime.now())

@logs_bp.route('/view/<log_file>')
@login_required
def view_log(log_file):
    """Bekijk een specifiek logbestand"""
    log_path = os.path.join('logs', log_file)
    
    # Veiligheidscontrole: voorkom directory traversal
    if not os.path.exists(log_path) or '..' in log_file or not log_file.endswith('.log'):
        logger.error(f"Ongeldige log bestandsaanvraag: {log_file}")
        abort(404)
    
    # Haal het aantal regels op dat bekeken moet worden
    lines_count = request.args.get('lines', default=100, type=int)
    if lines_count > MAX_LOG_LINES:
        lines_count = MAX_LOG_LINES
    
    log_content = _read_log_file(log_path, lines_count)
    
    return render_template('log_viewer.html', 
                           log_file=log_file, 
                           log_content=log_content,
                           lines_count=lines_count,
                           now=datetime.now())

@logs_bp.route('/api/logs/<log_file>')
@login_required
def api_get_logs(log_file):
    """API endpoint voor het ophalen van logbestanden in JSON-formaat"""
    log_path = os.path.join('logs', log_file)
    
    # Veiligheidscontrole
    if not os.path.exists(log_path) or '..' in log_file or not log_file.endswith('.log'):
        logger.error(f"Ongeldige API log bestandsaanvraag: {log_file}")
        return jsonify({"error": "Log bestand niet gevonden"}), 404
    
    lines_count = request.args.get('lines', default=100, type=int)
    if lines_count > MAX_LOG_LINES:
        lines_count = MAX_LOG_LINES
    
    log_content = _read_log_file(log_path, lines_count)
    
    # Controleren of het JSON-formaat is
    if log_file.endswith('.json.log'):
        try:
            json_logs = []
            for line in log_content:
                if line.strip():
                    json_logs.append(json.loads(line))
            return jsonify(json_logs)
        except json.JSONDecodeError:
            logger.error(f"Fout bij het parsen van JSON log: {log_file}")
            return jsonify({"error": "Ongeldig JSON formaat in logbestand"}), 500
    
    return jsonify({"log_content": log_content})

@logs_bp.route('/api/stats')
@login_required
def api_get_stats():
    """API endpoint voor het ophalen van logstatistieken"""
    stats = {
        'error_count': _count_log_level('error.log', 'ERROR'),
        'warning_count': _count_log_level('app.log', 'WARNING'),
        'info_count': _count_log_level('app.log', 'INFO'),
        'recent_errors': _get_recent_errors(),
        'log_sizes': _get_log_sizes()
    }
    return jsonify(stats)

@logs_bp.route('/error-test')
@login_required
def error_test():
    """Testpagina om verschillende errors te genereren voor log testing"""
    error_type = request.args.get('type', 'info')
    
    if not current_user.is_admin and not current_user.is_super_admin:
        logger.warning(f"Niet-admin gebruiker probeerde error-test uit te voeren: {current_user.username}")
        abort(403)
    
    if error_type == 'info':
        logger.info("Test INFO bericht gegenereerd via error-test")
        flash("INFO bericht is gelogd", "info")
    elif error_type == 'warning':
        logger.warning("Test WARNING bericht gegenereerd via error-test")
        flash("WARNING bericht is gelogd", "warning")
    elif error_type == 'error':
        logger.error("Test ERROR bericht gegenereerd via error-test")
        flash("ERROR bericht is gelogd", "danger")
    elif error_type == 'exception':
        try:
            # Genereer een bewuste exceptie
            undefined_variable / 10
        except Exception as e:
            logger.exception(f"Test EXCEPTION gegenereerd via error-test: {str(e)}")
            flash(f"EXCEPTION is gelogd: {str(e)}", "danger")
    elif error_type == '500':
        # Simuleer een 500 interne server fout
        abort(500)
    
    return render_template('logs_dashboard.html', log_files=_get_available_log_files(), now=datetime.now())

@logs_bp.route('/analytics')
@login_required
def logs_analytics():
    """Pagina voor loganalyse en visualisatie"""
    error_trend = _analyze_error_trend()
    return render_template('logs_analytics.html', error_trend=error_trend, now=datetime.now())

def _get_available_log_files():
    """Verkrijg een lijst van beschikbare logbestanden"""
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        return []
    
    log_files = []
    for file in os.listdir(logs_dir):
        if file.endswith('.log'):
            file_path = os.path.join(logs_dir, file)
            file_size = os.path.getsize(file_path)
            file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            log_files.append({
                'name': file,
                'size': _format_size(file_size),
                'modified': file_modified.strftime('%Y-%m-%d %H:%M:%S'),
                'size_bytes': file_size
            })
    
    # Sorteer op meest recent gewijzigd
    log_files.sort(key=lambda x: x['modified'], reverse=True)
    return log_files

def _read_log_file(log_path, lines_count):
    """Lees de laatste N regels van een logbestand"""
    try:
        with open(log_path, 'r', encoding='utf-8') as file:
            # Voor grote bestanden lezen we alleen de laatste N regels
            if lines_count > 0:
                # Efficiënte manier om de laatste N regels te lezen
                lines = file.readlines()
                return lines[-lines_count:] if len(lines) > lines_count else lines
            else:
                # Als lines_count 0 is, lees alles
                return file.readlines()
    except Exception as e:
        logger.error(f"Fout bij het lezen van logbestand {log_path}: {str(e)}")
        return [f"Fout bij het lezen van logbestand: {str(e)}"]

def _count_log_level(log_file, level):
    """Tel het aantal regels in een logbestand met een bepaald logniveau"""
    log_path = os.path.join('logs', log_file)
    if not os.path.exists(log_path):
        return 0
    
    count = 0
    try:
        with open(log_path, 'r', encoding='utf-8') as file:
            for line in file:
                if f" {level} " in line:
                    count += 1
    except Exception as e:
        logger.error(f"Fout bij het tellen van logniveau {level} in {log_file}: {str(e)}")
    
    return count

def _get_recent_errors(days=1):
    """Verkrijg recente fouten uit de error.log"""
    log_path = os.path.join('logs', 'error.log')
    if not os.path.exists(log_path):
        return []
    
    errors = []
    one_day_ago = datetime.now() - timedelta(days=days)
    
    try:
        with open(log_path, 'r', encoding='utf-8') as file:
            for line in file:
                try:
                    # Parse de datum uit het logbericht
                    date_str = line.split(' - ')[0]
                    log_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S,%f')
                    
                    if log_date >= one_day_ago:
                        errors.append(line.strip())
                except (ValueError, IndexError):
                    # Sla ongeldige regels over
                    continue
    except Exception as e:
        logger.error(f"Fout bij het ophalen van recente fouten: {str(e)}")
    
    return errors[-10:]  # Laatste 10 fouten

def _get_log_sizes():
    """Verkrijg de groottes van alle logbestanden"""
    log_sizes = {}
    logs_dir = 'logs'
    
    if not os.path.exists(logs_dir):
        return log_sizes
    
    for file in os.listdir(logs_dir):
        if file.endswith('.log'):
            file_path = os.path.join(logs_dir, file)
            log_sizes[file] = _format_size(os.path.getsize(file_path))
    
    return log_sizes

def _format_size(size_bytes):
    """Formatteer bytes naar een leesbare grootte"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

def _analyze_error_trend():
    """Analyseer de trend van fouten over de laatste 7 dagen"""
    log_path = os.path.join('logs', 'error.log')
    if not os.path.exists(log_path):
        return {}
    
    # Initialiseer de trend dictionary met de afgelopen 7 dagen
    trend = {}
    for i in range(7, 0, -1):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        trend[date] = 0
    
    try:
        with open(log_path, 'r', encoding='utf-8') as file:
            for line in file:
                try:
                    # Parse de datum uit het logbericht
                    date_str = line.split(' - ')[0]
                    log_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S,%f')
                    day = log_date.strftime('%Y-%m-%d')
                    
                    if day in trend:
                        trend[day] += 1
                except (ValueError, IndexError):
                    # Sla ongeldige regels over
                    continue
    except Exception as e:
        logger.error(f"Fout bij het analyseren van fouttrend: {str(e)}")
    
    return trend

def register_error_notification_handlers(app):
    """Registreer handlers voor foutmeldingen"""
    # Maak een mail_handler aan voor kritieke fouten
    if hasattr(app, 'mail') and app.config.get('ADMIN_EMAIL'):
        from logging.handlers import SMTPHandler
        
        mail_handler = SMTPHandler(
            mailhost=app.config.get('MAIL_SERVER', 'localhost'),
            fromaddr=app.config.get('MAIL_DEFAULT_SENDER', 'no-reply@example.com'),
            toaddrs=[app.config.get('ADMIN_EMAIL')],
            subject='[KRITIEKE FOUT] Applicatie Foutmelding'
        )
        mail_handler.setLevel(logging.ERROR)
        mail_handler.setFormatter(logging.Formatter(
            '''
            Tijd: %(asctime)s
            Bestand: %(pathname)s
            Functie: %(funcName)s
            Regel: %(lineno)d
            
            Bericht: 
            %(message)s
            '''))
        
        app.logger.addHandler(mail_handler)
        logger.info("E-mailnotificaties voor fouten geconfigureerd")