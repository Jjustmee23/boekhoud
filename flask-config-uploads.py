"""
Configuratie voor grote bestandsuploads in Flask
Dit script moet worden geïmporteerd in de Flask applicatie om grote uploads mogelijk te maken
"""

from flask import Flask, current_app

def configure_large_uploads(app):
    """
    Configureert de Flask app voor grote bestandsuploads tot 1GB
    
    Args:
        app: Flask applicatie instantie
    """
    # Maximale bestandsgrootte instellen op 1GB
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB in bytes
    
    # Timeout voor uploads verhogen in Werkzeug
    if hasattr(app, 'config'):
        app.config['UPLOAD_TIMEOUT'] = 600  # 10 minuten timeout voor uploads
    
    print("Grote bestandsuploads geconfigureerd (tot 1GB).")
    
    return app

def configure_storage_path(app, storage_path=None):
    """
    Configureert het pad voor opslag van geüploade bestanden
    
    Args:
        app: Flask applicatie instantie
        storage_path: Pad voor opslag van bestanden, standaard is 'static/uploads'
    """
    if storage_path is None:
        storage_path = 'static/uploads'
    
    import os
    
    # Maak het pad aan als het niet bestaat
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)
    
    app.config['UPLOAD_FOLDER'] = storage_path
    app.config['MAX_UPLOAD_FILES'] = 20  # Maximaal aantal bestanden per upload
    
    print(f"Upload map geconfigureerd: {storage_path}")
    
    return app

# Voorbeeld gebruik:
# from flask_config_uploads import configure_large_uploads, configure_storage_path
#
# app = Flask(__name__)
# app = configure_large_uploads(app)
# app = configure_storage_path(app, 'static/uploads')