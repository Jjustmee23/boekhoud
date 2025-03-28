"""
Log viewer module
Routes voor het weergeven en beheren van applicatie logbestanden
"""
import os
import re
import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, abort, send_file
from flask_login import login_required, current_user
from models import User
from utils import admin_required

# Creëer een Blueprint voor de log viewer routes
log_bp = Blueprint('logs', __name__, url_prefix='/logs')

# Pad naar logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

# Configuratiewaarden
MAX_LOG_LINES = 1000  # Maximaal aantal regels per pagina
LOG_FILES = {
    'app': os.path.join(LOGS_DIR, 'app.log'),
    'error': os.path.join(LOGS_DIR, 'error.log'),
    'json': os.path.join(LOGS_DIR, 'app.json.log')
}

@log_bp.route('/')
@login_required
def index():
    """Logbestanden overzicht pagina"""
    # Als de gebruiker niet is ingelogd, redirect naar login 
    # (de login_required decorator doet dit automatisch)
    # Als de gebruiker geen admin is, 403 error tonen
    if not current_user.is_admin:
        abort(403)  # Forbidden
        
    log_files = {}
    for log_type, log_path in LOG_FILES.items():
        if os.path.exists(log_path):
            log_stats = {
                'path': log_path,
                'size': os.path.getsize(log_path) / 1024,  # KB
                'modified': datetime.fromtimestamp(os.path.getmtime(log_path)),
                'lines': count_lines(log_path)
            }
            log_files[log_type] = log_stats
    
    return render_template('log_viewer.html', 
                          title='Log Viewer', 
                          log_files=log_files,
                          active_page='logs')

@log_bp.route('/view/<log_type>')
@login_required
def view_log(log_type):
    """Een specifiek logbestand bekijken"""
    if log_type not in LOG_FILES:
        abort(404)
        
    # Controle op toegangsrechten
    if not current_user.is_admin:
        abort(403)  # Forbidden
        
    log_path = LOG_FILES[log_type]
    if not os.path.exists(log_path):
        abort(404)
        
    # Parameters voor filtering en paginering
    page = int(request.args.get('page', 1))
    lines_per_page = int(request.args.get('lines', 100))
    filter_text = request.args.get('filter', '')
    level_filter = request.args.get('level', '')
    
    # Logdata ophalen met filtering
    log_data = read_log_file(log_path, page, lines_per_page, filter_text, level_filter)
    
    # Totaal aantal regels voor paginering
    total_lines = count_filtered_lines(log_path, filter_text, level_filter)
    total_pages = (total_lines + lines_per_page - 1) // lines_per_page
    
    return render_template('log_content.html',
                          title=f'{log_type.capitalize()} Log',
                          log_type=log_type,
                          log_data=log_data,
                          current_page=page,
                          total_pages=total_pages,
                          lines_per_page=lines_per_page,
                          filter_text=filter_text,
                          level_filter=level_filter,
                          active_page='logs')

@log_bp.route('/api/<log_type>')
@login_required
def api_log(log_type):
    """API endpoint om logdata in JSON-formaat op te halen"""
    if log_type not in LOG_FILES:
        return jsonify({'error': 'Log file not found'}), 404
        
    # Controle op toegangsrechten
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
        
    log_path = LOG_FILES[log_type]
    if not os.path.exists(log_path):
        return jsonify({'error': 'Log file not found'}), 404
        
    # Parameters voor filtering en paginering
    page = int(request.args.get('page', 1))
    lines_per_page = int(request.args.get('lines', 100))
    filter_text = request.args.get('filter', '')
    level_filter = request.args.get('level', '')
    
    # Logdata ophalen met filtering
    log_data = read_log_file(log_path, page, lines_per_page, filter_text, level_filter)
    
    # Totaal aantal regels voor paginering
    total_lines = count_filtered_lines(log_path, filter_text, level_filter)
    total_pages = (total_lines + lines_per_page - 1) // lines_per_page
    
    return jsonify({
        'log_type': log_type,
        'data': log_data,
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'lines_per_page': lines_per_page,
            'total_lines': total_lines
        }
    })

@log_bp.route('/download/<log_type>')
@login_required
def download_log(log_type):
    """Download een logbestand"""
    if log_type not in LOG_FILES:
        abort(404)
        
    # Controle op toegangsrechten
    if not current_user.is_admin:
        abort(403)  # Forbidden
        
    log_path = LOG_FILES[log_type]
    if not os.path.exists(log_path):
        abort(404)
        
    # Bestand als download aanbieden
    return send_file(log_path, 
                    as_attachment=True,
                    download_name=f"{log_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

@log_bp.route('/clear/<log_type>', methods=['POST'])
@login_required
def clear_log(log_type):
    """Een logbestand leegmaken"""
    if log_type not in LOG_FILES:
        abort(404)
        
    # Controle op toegangsrechten
    if not current_user.is_super_admin:  # Extra controle: alleen super admins
        abort(403)  # Forbidden
        
    log_path = LOG_FILES[log_type]
    if not os.path.exists(log_path):
        abort(404)
        
    # Backup maken van het bestand voordat we het leegmaken
    backup_path = f"{log_path}.bak"
    try:
        with open(log_path, 'r') as src, open(backup_path, 'w') as dst:
            dst.write(src.read())
            
        # Bestand leegmaken
        with open(log_path, 'w') as f:
            f.write(f"# Log cleared on {datetime.now().isoformat()} by {current_user.username}\n")
            
        return jsonify({'success': True, 'message': 'Log file cleared successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

# Helper functies
def read_log_file(filepath, page=1, lines_per_page=100, filter_text='', level_filter=''):
    """Lees een logbestand met paginering en filtering"""
    if not os.path.exists(filepath):
        return []
        
    # JSON log anders behandelen
    if filepath.endswith('.json.log'):
        return read_json_log(filepath, page, lines_per_page, filter_text, level_filter)
        
    # Regulier log bestand lezen
    log_entries = []
    filtered_count = 0
    total_count = 0
    
    # Bereken welke regels we nodig hebben
    start_line = (page - 1) * lines_per_page
    end_line = start_line + lines_per_page
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            # Filteren op tekst en log niveau indien nodig
            if filter_text and filter_text.lower() not in line.lower():
                continue
                
            if level_filter:
                # Zoeken naar log niveau in de regel (INFO, WARNING, ERROR, etc.)
                if not re.search(f'- {level_filter.upper()} -', line):
                    continue
            
            # Als we binnen de paginering vallen, voeg toe aan resultaat
            if start_line <= filtered_count < end_line:
                log_entries.append(line.strip())
                
            filtered_count += 1
            
            # Stop als we genoeg regels hebben
            if filtered_count >= end_line:
                break
                
    return log_entries

def read_json_log(filepath, page=1, lines_per_page=100, filter_text='', level_filter=''):
    """Lees een JSON log bestand met paginering en filtering"""
    if not os.path.exists(filepath):
        return []
        
    log_entries = []
    filtered_count = 0
    
    # Bereken welke regels we nodig hebben
    start_line = (page - 1) * lines_per_page
    end_line = start_line + lines_per_page
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            # Skip lege regels
            if not line.strip():
                continue
                
            try:
                # Parse JSON data
                log_data = json.loads(line)
                
                # Filteren op tekst en log niveau indien nodig
                if filter_text:
                    # Zoek in de hele JSON string
                    if filter_text.lower() not in json.dumps(log_data).lower():
                        continue
                        
                if level_filter and 'level' in log_data:
                    if log_data['level'].upper() != level_filter.upper():
                        continue
                
                # Als we binnen de paginering vallen, voeg toe aan resultaat
                if start_line <= filtered_count < end_line:
                    log_entries.append(log_data)
                    
                filtered_count += 1
                
                # Stop als we genoeg regels hebben
                if filtered_count >= end_line:
                    break
            except json.JSONDecodeError:
                # Ongeldige JSON overslaan
                continue
                
    return log_entries

def count_lines(filepath):
    """Tel het aantal regels in een bestand"""
    if not os.path.exists(filepath):
        return 0
        
    count = 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for _ in f:
            count += 1
    return count

def count_filtered_lines(filepath, filter_text='', level_filter=''):
    """Tel het aantal regels dat voldoet aan de filter criteria"""
    if not os.path.exists(filepath):
        return 0
        
    count = 0
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            # Filteren op tekst en log niveau indien nodig
            if filter_text and filter_text.lower() not in line.lower():
                continue
                
            if level_filter:
                # Voor JSON logs
                if filepath.endswith('.json.log'):
                    try:
                        log_data = json.loads(line)
                        if log_data.get('level', '').upper() != level_filter.upper():
                            continue
                    except json.JSONDecodeError:
                        continue
                # Voor normale logs
                else:
                    if not re.search(f'- {level_filter.upper()} -', line):
                        continue
            
            count += 1
                
    return count