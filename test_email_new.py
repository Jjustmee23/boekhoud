"""
Test script om de nieuwe e-mail service te testen zonder models imports.
Deze versie vermijdt de circulaire import door direct de omgevingsvariabelen te gebruiken.
"""
import os
import sys
import logging
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from msal import ConfidentialClientApplication
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class SimpleEmailService:
    """Vereenvoudigde versie van EmailService zonder model imports"""
    
    def __init__(self):
        # Direct instellingen uit omgevingsvariabelen laden
        self.client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
        self.client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
        self.tenant_id = os.environ.get("MS_GRAPH_TENANT_ID")
        self.email_account = os.environ.get("MS_GRAPH_SENDER_EMAIL")
        self.display_name = os.environ.get("EMAIL_FROM_NAME", "MidaWeb")
    
    def is_configured(self):
        """Controleert of alle benodigde instellingen aanwezig zijn"""
        return all([
            self.client_id, 
            self.client_secret, 
            self.tenant_id, 
            self.email_account
        ])
    
    def get_oauth_token(self):
        """
        Verkrijg een OAuth 2.0 token voor SMTP authenticatie
        
        Returns:
            str: OAuth2 token of None bij fouten
        """
        if not self.is_configured():
            logger.error("Microsoft 365 OAuth niet correct geconfigureerd")
            return None
        
        try:
            # Microsoft login authority en scope
            authority = f'https://login.microsoftonline.com/{self.tenant_id}'
            scope = ['https://outlook.office365.com/.default']  # Voor SMTP
            
            # Token ophalen via MSAL
            app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=authority
            )
            
            # Probeer silent token ophalen
            result = app.acquire_token_silent(scope, account=None)
            
            # Als geen token, haal nieuw token op
            if not result:
                result = app.acquire_token_for_client(scopes=scope)
            
            if 'access_token' not in result:
                if 'error' in result:
                    logger.error(f"Fout bij verkrijgen token: {result.get('error')}")
                    logger.error(f"Error beschrijving: {result.get('error_description')}")
                else:
                    logger.error("Onbekende fout bij het verkrijgen van een token")
                return None
            
            logger.info("OAuth2 token succesvol verkregen")
            return result['access_token']
            
        except Exception as e:
            logger.error(f"Exception bij het verkrijgen van OAuth token: {str(e)}")
            return None
    
    def send_email(self, recipient, subject, body_html, cc=None, attachments=None):
        """
        Verstuur een e-mail via Microsoft 365 SMTP met OAuth 2.0 authenticatie
        
        Args:
            recipient: E-mailadres van de ontvanger (of lijst van ontvangers)
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (optioneel), string of lijst
            attachments: Lijst van bijlagen (optioneel), elk een dict met 'path' en 'filename'
        
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        if not self.is_configured():
            logger.error("E-mail instellingen niet volledig geconfigureerd")
            return False
        
        try:
            # OAuth token ophalen
            access_token = self.get_oauth_token()
            if not access_token:
                return False
            
            # Formateer het OAuth2 authentication token voor SMTP
            auth_string = f"user={self.email_account}\x01auth=Bearer {access_token}\x01\x01"
            auth_bytes = base64.b64encode(auth_string.encode())
            
            # Maak het e-mail bericht
            msg = self._build_email_message(recipient, subject, body_html, cc)
            
            # Voeg bijlagen toe indien opgegeven
            if attachments:
                self._add_attachments_to_message(msg, attachments)
            
            # Bepaal ontvangers voor verzending
            recipients = [recipient] if isinstance(recipient, str) else recipient
            if cc:
                if isinstance(cc, str):
                    recipients.append(cc)
                else:
                    recipients.extend(cc)
            
            # SMTP verbinding maken en e-mail verzenden
            smtp_server = "smtp.office365.com"
            smtp_port = 587
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo() 
                server.starttls()
                server.ehlo()
                
                # SMTP authenticatie met OAuth2
                server.docmd('AUTH', 'XOAUTH2 ' + auth_bytes.decode())
                
                # E-mail verzenden
                server.send_message(msg)
                
                logger.info(f"E-mail succesvol verzonden naar {recipients}")
                return True
                
        except Exception as e:
            logger.error(f"Fout bij versturen e-mail: {str(e)}")
            return False
    
    def _build_email_message(self, recipient, subject, body_html, cc=None):
        """Bouw het e-mail bericht op"""
        # Maak multipart bericht voor HTML inhoud
        msg = MIMEMultipart()
        msg['Subject'] = subject
        
        # Afzender met display naam
        from_addr = f"{self.display_name} <{self.email_account}>"
        msg['From'] = from_addr
        
        # Ontvangers toevoegen
        if isinstance(recipient, list):
            msg['To'] = ', '.join(recipient)
        else:
            msg['To'] = recipient
            
        # CC toevoegen indien opgegeven
        if cc:
            if isinstance(cc, list):
                msg['Cc'] = ', '.join(cc)
            else:
                msg['Cc'] = cc
        
        # HTML inhoud toevoegen
        msg.attach(MIMEText(body_html, 'html'))
        
        return msg
    
    def _add_attachments_to_message(self, msg, attachments):
        """Voeg bijlagen toe aan het bericht"""
        if not attachments:
            return
        
        for attachment in attachments:
            try:
                path = attachment.get('path')
                filename = attachment.get('filename')
                
                if not path or not filename:
                    continue
                
                with open(path, 'rb') as file:
                    part = MIMEApplication(file.read(), Name=filename)
                
                # Toevoegen als bijlage
                part['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(part)
                
                logger.info(f"Bijlage toegevoegd: {filename}")
            except Exception as e:
                logger.error(f"Fout bij toevoegen bijlage {attachment.get('filename', 'unknown')}: {str(e)}")


def test_email_service():
    """Test functie om een e-mail te versturen met de vereenvoudigde service."""
    
    # Direct de instellingen printen (zonder gevoelige info)
    client_id = os.environ.get('MS_GRAPH_CLIENT_ID', '')
    client_id_masked = client_id[:6] + '*' * 8 + client_id[-4:] if client_id else 'Niet ingesteld'
    
    tenant_id = os.environ.get('MS_GRAPH_TENANT_ID', '') 
    tenant_id_masked = tenant_id[:6] + '*' * 8 + tenant_id[-4:] if tenant_id else 'Niet ingesteld'
    
    sender_email = os.environ.get('MS_GRAPH_SENDER_EMAIL', '')
    
    logger.info(f"Test gestart met instellingen:")
    logger.info(f"Client ID: {client_id_masked}")
    logger.info(f"Tenant ID: {tenant_id_masked}")
    logger.info(f"Sender Email: {sender_email}")
    logger.info(f"Client Secret: {'Ingesteld' if os.environ.get('MS_GRAPH_CLIENT_SECRET') else 'Niet ingesteld'}")
    
    # Vereenvoudigde e-mail service maken
    email_service = SimpleEmailService()
    
    # Test of configuratie aanwezig is
    if not email_service.is_configured():
        logger.error("E-mail service is niet correct geconfigureerd! Controleer de instellingen.")
        return False
    
    # Test OAuth token ophalen
    logger.info("OAuth token ophalen...")
    oauth_token = email_service.get_oauth_token()
    if not oauth_token:
        logger.error("Kon geen OAuth token ophalen!")
        return False
    
    logger.info("OAuth token succesvol opgehaald!")
    
    # Test e-mail sturen
    recipient = input("Voer een e-mailadres in voor de test: ").strip()
    if not recipient:
        logger.error("Geen ontvanger opgegeven. Test wordt afgebroken.")
        return False
    
    subject = "Test e-mail van nieuwe e-mail service"
    body_html = """
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                h1 { color: #2c3e50; }
                .highlight { background-color: #f9f9f9; padding: 10px; border-left: 4px solid #3498db; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Test e-mail</h1>
                <p>Dit is een test e-mail van de nieuwe e-mail service die gebruik maakt van Microsoft 365 SMTP met OAuth 2.0 authenticatie.</p>
                <div class="highlight">
                    <p>Als u deze e-mail ontvangt, werkt de nieuwe e-mail configuratie correct!</p>
                </div>
                <p>Met vriendelijke groeten,<br>Het MidaWeb Team</p>
            </div>
        </body>
    </html>
    """
    
    logger.info(f"E-mail versturen naar {recipient}...")
    success = email_service.send_email(recipient, subject, body_html)
    
    if success:
        logger.info("E-mail succesvol verzonden!")
        return True
    else:
        logger.error("E-mail verzenden mislukt!")
        return False

if __name__ == "__main__":
    print("=== E-mail Service Test ===")
    result = test_email_service()
    print(f"Test resultaat: {'GESLAAGD' if result else 'MISLUKT'}")
    sys.exit(0 if result else 1)