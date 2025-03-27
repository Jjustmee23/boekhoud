import requests
import base64
import logging
import sys
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_admin_screenshot():
    """Inloggen als admin en een screenshot maken van de beheerpagina"""
    session = requests.Session()
    
    # Haal eerst de login pagina op om CSRF token te krijgen
    try:
        login_page = session.get('http://localhost:5000/login')
        logger.info(f"Login pagina status: {login_page.status_code}")
    except Exception as e:
        logger.error(f"Fout bij ophalen login pagina: {str(e)}")
        return
    
    # Inloggen als admin
    login_data = {
        'username': 'admin',
        'password': 'admin'  # Standaard wachtwoord, pas aan indien nodig
    }
    
    try:
        login_response = session.post('http://localhost:5000/login', data=login_data, allow_redirects=True)
        logger.info(f"Login status: {login_response.status_code}")
        logger.info(f"Na login URL: {login_response.url}")
    except Exception as e:
        logger.error(f"Fout bij inloggen: {str(e)}")
        return
    
    # Beheerpagina bezoeken
    try:
        admin_page = session.get('http://localhost:5000/admin')
        logger.info(f"Admin pagina status: {admin_page.status_code}")
        
        # Sla de HTML op in een bestand
        with open('admin_page.html', 'w') as f:
            f.write(admin_page.text)
        logger.info("Admin pagina HTML opgeslagen in admin_page.html")
        
        # Verifieer de aanwezigheid van de nieuwe velden
        if "ms_graph_shared_mailbox" in admin_page.text and "ms_graph_use_shared_mailbox" in admin_page.text:
            logger.info("Gedeelde mailbox velden gevonden in de admin pagina!")
        else:
            logger.warning("Gedeelde mailbox velden NIET gevonden in de admin pagina!")
            
    except Exception as e:
        logger.error(f"Fout bij ophalen admin pagina: {str(e)}")
        return

if __name__ == "__main__":
    get_admin_screenshot()