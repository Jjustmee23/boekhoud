"""
Test script voor Microsoft 365 OAuth 2.0 functionaliteit.
Dit script test direct de authenticatie en SMTP e-mail verzending via Microsoft 365 OAuth 2.0.
"""

import os
import base64
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

# Configureer logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Laad omgevingsvariabelen
load_dotenv()

def test_oauth_token():
    """Test OAuth 2.0 token verkrijgen van Microsoft 365"""
    
    # Configuratie ophalen uit omgevingsvariabelen of direct invoeren
    client_id = os.environ.get('MS_GRAPH_CLIENT_ID')
    client_secret = os.environ.get('MS_GRAPH_CLIENT_SECRET')
    tenant_id = os.environ.get('MS_GRAPH_TENANT_ID')
    
    if not all([client_id, client_secret, tenant_id]):
        logger.error("Ontbrekende configuratie. Controleer de omgevingsvariabelen.")
        logger.info("MS_GRAPH_CLIENT_ID, MS_GRAPH_CLIENT_SECRET, MS_GRAPH_TENANT_ID zijn vereist.")
        return None
    
    try:
        # MSAL initialiseren
        logger.info(f"Initialiseren MSAL voor tenant: {tenant_id}")
        authority = f'https://login.microsoftonline.com/{tenant_id}'
        
        # Voor SMTP gebruik de juiste scope
        scope = ['https://outlook.office365.com/.default']
        
        # Token aanvragen via client credentials flow
        app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,  # Dit moet een string zijn!
            authority=authority
        )
        
        # Token ophalen
        logger.info("Token aanvragen...")
        result = app.acquire_token_for_client(scopes=scope)
        
        if 'access_token' not in result:
            logger.error(f"Fout bij verkrijgen token: {result.get('error')}")
            logger.error(f"Error beschrijving: {result.get('error_description')}")
            return None
        
        # Toon slechts een deel van het token voor veiligheid
        token_preview = result['access_token'][:10] + "..." if result['access_token'] else None
        logger.info(f"Token succesvol verkregen: {token_preview}")
        
        return result['access_token']
            
    except Exception as e:
        logger.error(f"Onverwachte fout bij OAuth token verkrijgen: {str(e)}")
        return None

def test_send_email(access_token=None):
    """Test e-mail verzenden via SMTP met OAuth 2.0 authenticatie"""
    
    if not access_token:
        access_token = test_oauth_token()
        
    if not access_token:
        logger.error("Geen toegangstoken beschikbaar. Email test overgeslagen.")
        return False
    
    sender_email = os.environ.get('MS_GRAPH_SENDER_EMAIL')
    test_recipient = os.environ.get('TEST_EMAIL_RECIPIENT', sender_email)
    
    if not sender_email:
        logger.error("Geen afzender e-mailadres gevonden in de omgevingsvariabelen (MS_GRAPH_SENDER_EMAIL).")
        return False
    
    try:
        # Maak XOAUTH2 string voor SMTP authenticatie
        auth_string = f"user={sender_email}\x01auth=Bearer {access_token}\x01\x01"
        auth_bytes = base64.b64encode(auth_string.encode())
        
        # Maak het e-mail bericht
        msg = MIMEMultipart()
        msg['Subject'] = "Test e-mail via Microsoft 365 OAuth 2.0"
        msg['From'] = sender_email
        msg['To'] = test_recipient
        
        # HTML e-mail inhoud
        body_html = """
        <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                    .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                    h1 { color: #2c3e50; margin-bottom: 20px; }
                    .content { background-color: #f9f9f9; padding: 20px; border-radius: 5px; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Microsoft 365 OAuth 2.0 Test</h1>
                    <div class="content">
                        <p>Dit is een testbericht verzonden via Microsoft 365 SMTP met OAuth 2.0 authenticatie.</p>
                        <p>Als je dit bericht ontvangt, werkt de OAuth 2.0 configuratie correct!</p>
                        <p>Je kunt nu e-mails verzenden via Microsoft 365 met moderne veilige authenticatie.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        # Voeg HTML inhoud toe aan het bericht
        msg.attach(MIMEText(body_html, 'html'))
        
        # SMTP verbinding maken met Microsoft 365
        logger.info(f"Verbinding maken met SMTP server: smtp.office365.com")
        with smtplib.SMTP('smtp.office365.com', 587) as server:
            server.set_debuglevel(1)  # Meer debug informatie tonen
            server.starttls()
            server.ehlo()
            
            # Authenticeren met XOAUTH2
            logger.info("SMTP authenticatie met XOAUTH2...")
            server.docmd('AUTH', 'XOAUTH2 ' + auth_bytes.decode())
            
            # E-mail verzenden
            logger.info(f"E-mail verzenden naar: {test_recipient}")
            server.send_message(msg)
            
            logger.info(f"E-mail succesvol verzonden naar {test_recipient}")
            return True
            
    except Exception as e:
        logger.error(f"Fout bij verzenden e-mail: {str(e)}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("Microsoft 365 OAuth 2.0 E-mail Test")
    print("=" * 50 + "\n")
    
    print("1. Testen van OAuth 2.0 token verkrijgen...")
    token = test_oauth_token()
    
    if token:
        print("\n2. Testen van e-mail verzenden via SMTP met OAuth 2.0...")
        result = test_send_email(token)
        
        if result:
            print("\nSUCCES: Microsoft 365 OAuth 2.0 werkt correct!")
            print("Je kunt nu e-mails verzenden met moderne authenticatie.")
        else:
            print("\nFOUT: Token verkregen, maar e-mail verzenden mislukt.")
            print("Controleer of het afzender e-mailadres correct is en of de app de juiste permissies heeft.")
    else:
        print("\nFOUT: Kon geen OAuth 2.0 token verkrijgen.")
        print("Controleer de CLIENT_ID, CLIENT_SECRET, en TENANT_ID instellingen.")