"""
E-mail service module met OAuth 2.0 authenticatie voor Microsoft 365.
Deze module biedt functionaliteit voor het versturen van e-mails via moderne OAuth 2.0 authenticatie
in plaats van traditionele gebruikersnaam/wachtwoord methoden.
"""

import os
import logging
import base64
from flask import current_app
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from microsoft_365_oauth import Microsoft365OAuth

# Configuratie van logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

class EmailServiceOAuth:
    """
    E-mail service voor het versturen van e-mails via OAuth 2.0 authenticatie.
    Momenteel ondersteunt deze klasse Microsoft 365 OAuth 2.0.
    """
    
    def __init__(self, workspace_id=None):
        """
        Initialiseer de EmailServiceOAuth
        
        Args:
            workspace_id: ID van de workspace waarvoor de e-mailservice wordt gebruikt (optioneel)
                         Als None, worden de systeem-instellingen gebruikt
        """
        self.workspace_id = workspace_id
        self.ms_oauth = None
        
        # Initialiseer de juiste OAuth provider
        self._initialize_provider()

    def _initialize_provider(self):
        """Initialiseer de juiste OAuth provider op basis van instellingen"""
        try:
            from models import EmailSettings
            
            # Laad instellingen voor deze workspace indien opgegeven
            email_settings = None
            if self.workspace_id:
                # Gebruik instellingen van deze specifieke workspace
                email_settings = EmailSettings.query.filter_by(workspace_id=self.workspace_id).first()
                logger.debug(f"Workspace-specifieke e-mailinstellingen geladen voor workspace_id={self.workspace_id}")
            
            # Initialiseer Microsoft 365 OAuth provider
            self.ms_oauth = Microsoft365OAuth(settings=email_settings)
            
            # Log configuratie status
            if self.ms_oauth.is_configured():
                logger.info("Microsoft 365 OAuth succesvol geconfigureerd")
            else:
                logger.warning("Microsoft 365 OAuth niet volledig geconfigureerd")
                
        except Exception as e:
            logger.error(f"Fout bij initialiseren van OAuth provider: {str(e)}")
            self.ms_oauth = Microsoft365OAuth()  # Fallback naar systeem-instellingen
    
    def is_configured(self):
        """Controleert of de e-mailservice correct is geconfigureerd"""
        return self.ms_oauth and self.ms_oauth.is_configured()
    
    def send_email(self, recipient, subject, body_html, cc=None, attachments=None):
        """
        Verstuur een e-mail via de geconfigureerde OAuth provider
        
        Args:
            recipient: E-mailadres van de ontvanger (string of lijst)
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (optioneel, string of lijst)
            attachments: Lijst van bijlagen (optioneel), elk een dict met 'path' en 'filename'
        
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        if not self.is_configured():
            logger.error("E-mailservice niet correct geconfigureerd")
            return False
        
        try:
            # Controleer of MS OAuth provider is geïnitialiseerd
            if not self.ms_oauth:
                logger.error("Microsoft 365 OAuth provider is niet geïnitialiseerd")
                return False
                
            # Gebruik Microsoft 365 OAuth voor verzending
            logger.debug(f"E-mail versturen naar {recipient} via Microsoft 365 OAuth")
            result = self.ms_oauth.send_email(
                recipient=recipient,
                subject=subject,
                body_html=body_html,
                cc=cc,
                attachments=attachments
            )
            
            if result:
                logger.info(f"E-mail succesvol verzonden naar {recipient}")
            else:
                logger.error(f"E-mail verzenden naar {recipient} mislukt")
                
            return result
        except Exception as e:
            logger.error(f"Fout bij versturen e-mail: {str(e)}")
            # Meer details over de exceptie loggen
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return False
    
    def send_template_email(self, recipient, template_name, template_params, cc=None, attachments=None):
        """
        Verstuur een e-mail op basis van een sjabloon
        
        Args:
            recipient: E-mailadres van de ontvanger (string of lijst)
            template_name: Naam van het sjabloon
            template_params: Dict met parameters voor het sjabloon
            cc: Carbon copy ontvangers (optioneel, string of lijst) 
            attachments: Lijst van bijlagen (optioneel)
            
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        try:
            # Importeer Jinja2 voor het renderen van templates
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            
            # Setup Jinja2 environment
            env = Environment(
                loader=FileSystemLoader('templates/emails'),
                autoescape=select_autoescape(['html', 'xml'])
            )
            
            # Laad en render template
            template = env.get_template(f"{template_name}.html")
            html_content = template.render(**template_params)
            
            # Bepaal onderwerp (uit template params of default)
            subject = template_params.get('subject', f"Bericht van {current_app.config.get('SITE_NAME', 'onze applicatie')}")
            
            # Verstuur e-mail
            return self.send_email(
                recipient=recipient,
                subject=subject,
                body_html=html_content,
                cc=cc,
                attachments=attachments
            )
        
        except Exception as e:
            logger.error(f"Fout bij versturen template e-mail '{template_name}': {str(e)}")
            return False

    def send_workspace_invitation(self, recipient_email, workspace_name, activation_token, customer_name=None):
        """
        Stuur een uitnodiging voor een nieuwe workspace naar een klant
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            workspace_name: Naam van de workspace
            activation_token: Token voor activatie
            customer_name: Naam van de klant (optioneel)
        """
        from flask import url_for
        
        try:
            # Genereer de activatie URL
            activation_url = url_for('activate_workspace', token=activation_token, _external=True)
            
            # Bereid template parameters voor
            template_params = {
                'subject': f"Uitnodiging voor {workspace_name}",
                'workspace_name': workspace_name,
                'activation_url': activation_url,
                'customer_name': customer_name or recipient_email,
            }
            
            # Verstuur e-mail met template
            return self.send_template_email(
                recipient=recipient_email,
                template_name='workspace_invitation',
                template_params=template_params
            )
            
        except Exception as e:
            logger.error(f"Fout bij versturen workspace uitnodiging: {str(e)}")
            return False

    def send_user_invitation(self, recipient_email, workspace_name, activation_token, inviter_name=None):
        """
        Stuur een uitnodiging naar een gebruiker voor toegang tot een workspace
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            workspace_name: Naam van de workspace
            activation_token: Token voor activatie
            inviter_name: Naam van de persoon die de uitnodiging stuurt (optioneel)
        """
        from flask import url_for
        
        try:
            # Genereer de activatie URL
            activation_url = url_for('activate_user', token=activation_token, _external=True)
            
            # Bereid template parameters voor
            template_params = {
                'subject': f"Uitnodiging om deel te nemen aan {workspace_name}",
                'workspace_name': workspace_name,
                'activation_url': activation_url,
                'inviter_name': inviter_name or "De beheerder",
            }
            
            # Verstuur e-mail met template
            return self.send_template_email(
                recipient=recipient_email,
                template_name='user_invitation',
                template_params=template_params
            )
            
        except Exception as e:
            logger.error(f"Fout bij versturen gebruikers uitnodiging: {str(e)}")
            return False

class EmailServiceOAuthHelper:
    """Helper class met statische methoden voor e-mail services met OAuth authenticatie"""
    
    @staticmethod
    def create_for_workspace(workspace_id):
        """
        Maak een EmailServiceOAuth instantie voor een specifieke workspace
        
        Args:
            workspace_id: ID van de workspace
            
        Returns:
            EmailServiceOAuth: Nieuwe instantie met workspace-specifieke instellingen
        """
        return EmailServiceOAuth(workspace_id=workspace_id)
    
    @staticmethod
    def send_email_for_workspace(workspace_id, recipient_email, subject, body_html, cc=None, attachments=None):
        """
        Verstuur e-mail voor een specifieke workspace via OAuth
        
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
        email_service = EmailServiceOAuth(workspace_id=workspace_id)
        return email_service.send_email(
            recipient=recipient_email,
            subject=subject,
            body_html=body_html,
            cc=cc,
            attachments=attachments
        )