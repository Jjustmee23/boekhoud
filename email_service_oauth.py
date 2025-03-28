"""
E-mail service module voor het versturen van e-mails via Microsoft 365 met OAuth 2.0 authenticatie.
Deze module integreert de Microsoft365OAuth implementatie met de bestaande EmailService.
"""

import os
import logging
import base64
from flask import url_for, current_app
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from microsoft_365_oauth import Microsoft365OAuth

# Logger configuratie
logger = logging.getLogger(__name__)

class EmailServiceOAuth:
    """
    E-mail service voor het versturen van e-mails via Microsoft 365 met OAuth 2.0 authenticatie.
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
        
        # Initialiseer de OAuth helper
        self.ms_oauth = Microsoft365OAuth(email_settings)
    
    def is_configured(self):
        """Controleert of alle benodigde instellingen aanwezig zijn"""
        return self.ms_oauth.is_configured()
    
    def send_email(self, recipient, subject, body_html, cc=None, attachments=None):
        """
        Verstuur een e-mail via Microsoft 365 met OAuth 2.0
        
        Args:
            recipient: E-mailadres van de ontvanger (of lijst van ontvangers)
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (optioneel), string of lijst
            attachments: Lijst van bijlagen (optioneel), elk een dict met 'path' en 'filename'
        
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        return self.ms_oauth.send_email(recipient, subject, body_html, cc, attachments)
    
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
                        <p>Klik op de onderstaande link om uw account te activeren en aan de slag te gaan:</p>
                        <p><a href="{activation_url}" class="btn">Activeer uw account</a></p>
                        <p>Of kopieer deze URL naar uw browser: {activation_url}</p>
                        <div class="footer">
                            <p>Dit is een automatisch gegenereerd bericht. Reageer niet op deze e-mail.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            return self.send_email(recipient_email, subject, body_html)
    
    def send_user_invitation(self, recipient_email, workspace_name, activation_token, admin=False, display_name=None):
        """
        Stuur een uitnodiging voor een nieuwe gebruiker in een workspace
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            workspace_name: Naam van de workspace
            activation_token: Token voor activatie en eerste login
            admin: Boolean of de gebruiker admin rechten heeft
            display_name: Naam van de gebruiker (optioneel)
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
                    'name': display_name or 'Beste gebruiker',
                    'workspace_name': workspace_name,
                    'activation_url': activation_url,
                    'role': 'beheerder' if admin else 'gebruiker'
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
            greeting = f"Beste {display_name}" if display_name else "Beste"
            role_text = "beheerder" if admin else "gebruiker"
            subject = f"Uitnodiging: U bent toegevoegd als {role_text} aan {workspace_name}"
            
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
                        <h1>U bent uitgenodigd!</h1>
                        <p>{greeting},</p>
                        <p>U bent uitgenodigd als {role_text} voor de werkruimte '{workspace_name}' op ons facturatie platform.</p>
                        <p>Klik op de onderstaande link om uw account te activeren en aan de slag te gaan:</p>
                        <p><a href="{activation_url}" class="btn">Activeer uw account</a></p>
                        <p>Of kopieer deze URL naar uw browser: {activation_url}</p>
                        <div class="footer">
                            <p>Dit is een automatisch gegenereerd bericht. Reageer niet op deze e-mail.</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            return self.send_email(recipient_email, subject, body_html)