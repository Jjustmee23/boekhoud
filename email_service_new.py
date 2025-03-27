"""
E-mail service module voor het versturen van e-mails via Microsoft 365 met OAuth 2.0 authenticatie.
Implementeert Microsoft Authentication Library (MSAL) voor het verkrijgen van OAuth2 tokens.
"""
import os
import base64
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import current_app
from msal import ConfidentialClientApplication

# Logger configuratie
logger = logging.getLogger(__name__)

class EmailService:
    """
    E-mail service voor het versturen van e-mails via Microsoft 365 met OAuth 2.0 authenticatie.
    Haalt de instellingen op uit de database.
    """
    
    def __init__(self, email_settings=None):
        """
        Initialiseer de EmailService
        
        Args:
            email_settings: EmailSettings model voor een specifieke workspace (optioneel)
                           Als None, worden de systeem-instellingen gebruikt
        """
        self.logger = logging.getLogger(__name__)
        self.email_settings = email_settings
        
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
                    
                # Als er een probleem is met de ontvangen gecrypteerde client secret, probeer fallback
                if self.client_secret and self.client_secret.startswith('Nm'):
                    self.client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET", "")
        except Exception as e:
            self.logger.error(f"Fout bij ophalen van systeem-instellingen: {str(e)}")
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
            self.logger.error("Microsoft 365 OAuth niet correct geconfigureerd")
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
                    self.logger.error(f"Fout bij verkrijgen token: {result.get('error')}")
                    self.logger.error(f"Error beschrijving: {result.get('error_description')}")
                else:
                    self.logger.error("Onbekende fout bij het verkrijgen van een token")
                return None
            
            self.logger.info("OAuth2 token succesvol verkregen")
            return result['access_token']
            
        except Exception as e:
            self.logger.error(f"Exception bij het verkrijgen van OAuth token: {str(e)}")
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
            self.logger.error("E-mail instellingen niet volledig geconfigureerd")
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
                server.starttls()
                server.ehlo()
                
                # SMTP authenticatie met OAuth2
                server.docmd('AUTH', 'XOAUTH2 ' + auth_bytes.decode())
                
                # E-mail verzenden
                server.send_message(msg)
                
                self.logger.info(f"E-mail succesvol verzonden naar {recipients}")
                return True
                
        except Exception as e:
            self.logger.error(f"Fout bij versturen e-mail: {str(e)}")
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
                
                self.logger.info(f"Bijlage toegevoegd: {filename}")
            except Exception as e:
                self.logger.error(f"Fout bij toevoegen bijlage {attachment.get('filename', 'unknown')}: {str(e)}")
    
    def send_template_email(self, recipient, template_name, template_params, cc=None, attachments=None):
        """
        Verstuur een e-mail op basis van een sjabloon
        
        Args:
            recipient: E-mailadres van de ontvanger
            template_name: Naam van het template om te gebruiken
            template_params: Dict met parameters voor het template
            cc: Carbon copy ontvangers (optioneel)
            attachments: Lijst van bijlagen (optioneel)
            
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        from models import EmailTemplate
        
        try:
            # Zoek het template in de database
            workspace_id = getattr(self.email_settings, 'workspace_id', None) if self.email_settings else None
            
            with current_app.app_context():
                # Zoek eerst workspace-specifiek template indien email_settings een workspace heeft
                if workspace_id:
                    template = EmailTemplate.query.filter_by(
                        workspace_id=workspace_id,
                        name=template_name
                    ).first()
                else:
                    template = None
                    
                # Als geen workspace-specifiek template, zoek naar een systeem template
                if not template:
                    template = EmailTemplate.query.filter_by(
                        workspace_id=None,
                        name=template_name
                    ).first()
                    
                if not template:
                    self.logger.error(f"E-mail template '{template_name}' niet gevonden")
                    return False
                
                # Vul template in met parameters
                import jinja2
                env = jinja2.Environment()
                subject_template = env.from_string(template.subject)
                body_template = env.from_string(template.body_html)
                
                subject = subject_template.render(**template_params)
                body_html = body_template.render(**template_params)
                
                # Verstuur de e-mail
                return self.send_email(recipient, subject, body_html, cc, attachments)
                
        except Exception as e:
            self.logger.error(f"Fout bij versturen template e-mail: {str(e)}")
            return False
    
    def send_workspace_invitation(self, recipient_email, workspace_name, activation_token, customer_name=None):
        """
        Stuur een uitnodiging voor een nieuwe workspace naar een klant
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            workspace_name: Naam van de workspace
            activation_token: Token voor activatie en eerste login
            customer_name: Naam van de klant (optioneel)
        """
        from flask import url_for
        
        try:
            with current_app.app_context():
                # Bepaal de activatie-URL
                activation_url = url_for(
                    'activate_workspace', 
                    token=activation_token, 
                    workspace=workspace_name,
                    _external=True
                )
                
                # Stel parameters in voor het template
                template_params = {
                    'customer_name': customer_name or 'Geachte klant',
                    'workspace_name': workspace_name,
                    'activation_url': activation_url
                }
                
                # Verstuur de e-mail met het juiste template
                return self.send_template_email(
                    recipient_email,
                    'workspace_invitation',
                    template_params
                )
        except Exception as e:
            self.logger.error(f"Fout bij versturen workspace uitnodiging: {str(e)}")
            
            # Fallback: handmatige e-mail verzenden
            greeting = f"Beste {customer_name}" if customer_name else "Beste"
            subject = f"Uitnodiging: Uw nieuwe facturatie platform workspace '{workspace_name}'"
            
            body_html = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        h1 {{ color: #2c3e50; margin-bottom: 20px; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background-color: #3498db; color: white; 
                               text-decoration: none; border-radius: 4px; font-weight: bold; }}
                        .footer {{ margin-top: 40px; font-size: 0.9em; color: #7f8c8d; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Welkom bij uw nieuwe werkruimte!</h1>
                        <p>{greeting},</p>
                        <p>U bent uitgenodigd om gebruik te maken van uw nieuwe werkruimte '{workspace_name}' op ons facturatie platform.</p>
                        <p>Om te beginnen, klik op onderstaande link om uw account te activeren:</p>
                        <p><a href="{activation_url}" class="btn">Activeer uw account</a></p>
                        <p>Of kopieer deze URL in uw browser:</p>
                        <p><small>{activation_url}</small></p>
                        <p>Na activatie kunt u inloggen en uw accountgegevens beheren.</p>
                        <div class="footer">
                            <p>Met vriendelijke groeten,<br>Het team van MidaWeb</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            return self.send_email(recipient_email, subject, body_html)
    
    def send_user_invitation(self, recipient_email, workspace_name, activation_token, inviter_name=None):
        """
        Stuur een uitnodiging naar een gebruiker voor toegang tot een workspace
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            workspace_name: Naam van de workspace
            activation_token: Token voor activatie en eerste login
            inviter_name: Naam van de persoon die de uitnodiging stuurt (optioneel)
        """
        from flask import url_for
        
        try:
            with current_app.app_context():
                # Bepaal de activatie-URL
                activation_url = url_for(
                    'activate_user', 
                    token=activation_token, 
                    _external=True
                )
                
                # Stel parameters in voor het template
                template_params = {
                    'workspace_name': workspace_name,
                    'activation_url': activation_url,
                    'inviter_name': inviter_name or 'De beheerder'
                }
                
                # Verstuur de e-mail met het juiste template
                return self.send_template_email(
                    recipient_email,
                    'user_invitation',
                    template_params
                )
        except Exception as e:
            self.logger.error(f"Fout bij versturen gebruikersuitnodiging: {str(e)}")
            
            # Fallback: handmatige e-mail verzenden
            inviter = inviter_name or "De beheerder"
            subject = f"Uitnodiging: Toegang tot werkruimte '{workspace_name}'"
            
            body_html = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        h1 {{ color: #2c3e50; margin-bottom: 20px; }}
                        .btn {{ display: inline-block; padding: 10px 20px; background-color: #3498db; color: white; 
                               text-decoration: none; border-radius: 4px; font-weight: bold; }}
                        .footer {{ margin-top: 40px; font-size: 0.9em; color: #7f8c8d; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Uitnodiging voor toegang</h1>
                        <p>Beste,</p>
                        <p>{inviter} heeft u uitgenodigd om toegang te krijgen tot werkruimte '{workspace_name}' op ons facturatie platform.</p>
                        <p>Om te beginnen, klik op onderstaande link om uw account te activeren:</p>
                        <p><a href="{activation_url}" class="btn">Activeer uw account</a></p>
                        <p>Of kopieer deze URL in uw browser:</p>
                        <p><small>{activation_url}</small></p>
                        <p>Na activatie kunt u inloggen en uw accountgegevens beheren.</p>
                        <div class="footer">
                            <p>Met vriendelijke groeten,<br>Het team van MidaWeb</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            return self.send_email(recipient_email, subject, body_html)

class EmailServiceHelper:
    """Helper class met statische methoden voor e-mail services"""
    
    @staticmethod
    def create_for_workspace(workspace_id):
        """
        Maak een EmailService-instantie voor een specifieke workspace
        
        Args:
            workspace_id: ID van de workspace
            
        Returns:
            EmailService: Nieuwe instantie met workspace-specifieke instellingen
        """
        from models import EmailSettings
        
        try:
            with current_app.app_context():
                # Haal e-mail instellingen op voor de workspace
                email_settings = EmailSettings.query.filter_by(workspace_id=workspace_id).first()
                
                # Maak een nieuwe EmailService-instantie met deze instellingen
                return EmailService(email_settings)
                
        except Exception as e:
            logger.error(f"Fout bij maken EmailService voor workspace {workspace_id}: {str(e)}")
            
            # Fallback naar systeem-instellingen
            return EmailService()
    
    @staticmethod
    def send_email_for_workspace(workspace_id, recipient_email, subject, body_html, cc=None, attachments=None):
        """
        Verstuur e-mail voor een specifieke workspace
        
        Args:
            workspace_id: ID van de workspace
            recipient_email: E-mailadres van de ontvanger
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (optioneel)
            attachments: Lijst van bijlagen (optioneel)
            
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        email_service = EmailServiceHelper.create_for_workspace(workspace_id)
        return email_service.send_email(recipient_email, subject, body_html, cc, attachments)
    
    @staticmethod
    def send_template_email_for_workspace(workspace_id, recipient_email, template_name, template_params, cc=None, attachments=None):
        """
        Verstuur template e-mail voor een specifieke workspace
        
        Args:
            workspace_id: ID van de workspace
            recipient_email: E-mailadres van de ontvanger
            template_name: Naam van het template
            template_params: Parameters voor het template
            cc: Carbon copy ontvangers (optioneel)
            attachments: Lijst van bijlagen (optioneel)
            
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        email_service = EmailServiceHelper.create_for_workspace(workspace_id)
        return email_service.send_template_email(recipient_email, template_name, template_params, cc, attachments)