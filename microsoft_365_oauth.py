"""
Microsoft 365 OAuth 2.0 authenticatie module voor e-mailintegratie.

Deze module implementeert OAuth 2.0 authenticatie voor Microsoft 365 en 
biedt functies voor het verkrijgen van OAuth tokens en het verzenden
van e-mails via SMTP met OAuth 2.0.
"""

import os
import base64
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from msal import ConfidentialClientApplication
from flask import current_app

# Logger configuratie
logger = logging.getLogger(__name__)

class Microsoft365OAuth:
    """
    Microsoft 365 OAuth 2.0 authenticatie helper voor e-mail functionaliteit.
    Gebruikt MSAL (Microsoft Authentication Library) voor OAuth token verkrijging.
    """
    
    def __init__(self, settings=None):
        """
        Initialiseer de Microsoft 365 OAuth helper
        
        Args:
            settings: EmailSettings model voor een specifieke workspace (optioneel)
                     Als None, worden de systeem-instellingen gebruikt
        """
        self.email_settings = settings
        
        # Configuratievariabelen
        self.client_id = None
        self.client_secret = None
        self.tenant_id = None
        self.email_account = None
        self.display_name = None
        
        # Haal instellingen op
        self._load_settings()
    
    def _load_settings(self):
        """Laad de instellingen uit de database of fallback naar omgevingsvariabelen"""
        if self.email_settings:
            # Haal instellingen op uit het meegegeven EmailSettings object
            self._load_from_settings()
        else:
            # Haal systeem-instellingen op (workspace_id=None) of fallback naar omgevingsvariabelen
            self._load_from_system_settings()
    
    def _load_from_settings(self):
        """Laad instellingen uit EmailSettings object"""
        from models import EmailSettings
        
        self.client_id = self.email_settings.ms_graph_client_id
        self.client_secret = EmailSettings.decrypt_secret(self.email_settings.ms_graph_client_secret)
        self.tenant_id = self.email_settings.ms_graph_tenant_id
        
        # Bepaal het e-mail account voor authenticatie
        if hasattr(self.email_settings, 'ms_graph_sender_email'):
            self.email_account = self.email_settings.ms_graph_sender_email
            
        # Display name
        if hasattr(self.email_settings, 'default_sender_name') and self.email_settings.default_sender_name:
            self.display_name = self.email_settings.default_sender_name
        else:
            self.display_name = "MidaWeb"
    
    def _load_from_system_settings(self):
        """Laad instellingen uit systeem instellingen of omgevingsvariabelen"""
        from models import EmailSettings
        
        try:
            # Systeem-instellingen ophalen (workspace_id=None)
            with current_app.app_context():
                system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
                
                if system_settings:
                    self.email_settings = system_settings
                    self._load_from_settings()
                else:
                    # Fallback naar omgevingsvariabelen
                    self._load_from_environment()
        except Exception as e:
            logger.error(f"Fout bij ophalen van systeem-instellingen: {str(e)}")
            # Fallback naar omgevingsvariabelen
            self._load_from_environment()
    
    def _load_from_environment(self):
        """Laad instellingen uit omgevingsvariabelen"""
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
            
            # Debug de waarden voor betere foutopsporing
            client_id_preview = ""
            if self.client_id and len(self.client_id) > 10:
                client_id_preview = f"{self.client_id[:5]}...{self.client_id[-5:]}"
            elif self.client_id:
                client_id_preview = self.client_id
                
            logger.debug(f"Client ID: {client_id_preview}")
            logger.debug(f"Tenant ID: {self.tenant_id}")
            logger.debug(f"Email account: {self.email_account}")
            logger.debug(f"Authority: {authority}")
            
            # Token ophalen via MSAL
            # client_credential moet een string zijn voor client secret flow
            app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,  # Let op: dit moet de plain text secret zijn
                authority=authority
            )
            
            # Verkrijg token voor client credentials flow
            logger.debug(f"Scope voor token: {scope}")
            result = app.acquire_token_for_client(scopes=scope)
            
            if 'access_token' not in result:
                if 'error' in result:
                    logger.error(f"Fout bij verkrijgen token: {result.get('error')}")
                    logger.error(f"Error beschrijving: {result.get('error_description')}")
                else:
                    logger.error("Onbekende fout bij het verkrijgen van een token")
                return None
            
            # Toon een preview van het token (eerste 10 karakters) voor debugging
            token_preview = result['access_token'][:10] + "..." if result['access_token'] else None
            logger.info(f"OAuth2 token succesvol verkregen: {token_preview}")
            return result['access_token']
            
        except Exception as e:
            logger.error(f"Exception bij het verkrijgen van OAuth token: {str(e)}")
            # Log meer details over de exceptie voor betere foutopsporing
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
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
            logger.debug(f"Client ID aanwezig: {bool(self.client_id)}")
            logger.debug(f"Client Secret aanwezig: {bool(self.client_secret)}")
            logger.debug(f"Tenant ID aanwezig: {bool(self.tenant_id)}")
            logger.debug(f"Email account aanwezig: {bool(self.email_account)}")
            return False
        
        try:
            logger.info(f"Start e-mail verzenden met OAuth naar: {recipient}")
            
            # OAuth token ophalen
            access_token = self.get_oauth_token()
            if not access_token:
                logger.error("Geen toegangstoken verkregen, e-mail verzending gestopt")
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
            
            logger.info(f"Verbinding maken met {smtp_server}:{smtp_port}")
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                # Debug mode inschakelen voor SMTP voor uitgebreide logging
                server.set_debuglevel(1)
                
                logger.debug("Start TLS verbinding")
                server.starttls()
                
                logger.debug("EHLO commando")
                server.ehlo()
                
                # SMTP authenticatie met OAuth2
                logger.debug("OAuth2 authenticatie uitvoeren")
                response = server.docmd('AUTH', 'XOAUTH2 ' + auth_bytes.decode())
                logger.debug(f"AUTH response: {response}")
                
                # E-mail verzenden
                logger.debug(f"E-mail verzenden naar: {recipients}")
                server.send_message(msg)
                
                logger.info(f"E-mail succesvol verzonden naar {recipients}")
                return True
                
        except Exception as e:
            logger.error(f"Fout bij versturen e-mail: {str(e)}")
            # Meer details over de exceptie loggen
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
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