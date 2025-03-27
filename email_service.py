import os
import json
import msal
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import url_for, current_app
import uuid
import logging

# Configuratie voor Microsoft Graph API
class MSGraphConfig:
    def __init__(self, settings=None):
        # Als workspace-specifieke instellingen worden meegegeven, gebruik deze
        if settings and settings.use_ms_graph:
            self.client_id = settings.ms_graph_client_id
            self.client_secret = settings.ms_graph_client_secret
            self.tenant_id = settings.ms_graph_tenant_id
            self.sender_email = settings.ms_graph_sender_email
        else:
            # Anders gebruik de globale instellingen via omgevingsvariabelen
            self.client_id = os.environ.get('MS_GRAPH_CLIENT_ID')
            self.client_secret = os.environ.get('MS_GRAPH_CLIENT_SECRET')
            self.tenant_id = os.environ.get('MS_GRAPH_TENANT_ID')
            self.sender_email = os.environ.get('MS_GRAPH_SENDER_EMAIL')
            
        # Altijd authority en scope instellen
        self.authority = f'https://login.microsoftonline.com/{self.tenant_id}'
        self.scope = ['https://graph.microsoft.com/.default']
        
    def is_configured(self):
        """Controleer of alle vereiste configuratiewaarden zijn ingesteld"""
        return all([
            self.client_id, self.client_secret, self.tenant_id, 
            self.authority, self.scope, self.sender_email
        ])

# Configuratie voor SMTP server
class SMTPConfig:
    def __init__(self, settings=None):
        if settings:
            self.server = settings.smtp_server
            self.port = settings.smtp_port
            self.username = settings.smtp_username
            self.password = settings.smtp_password
            self.from_email = settings.email_from
            self.from_name = settings.email_from_name
        else:
            self.server = os.environ.get('SMTP_SERVER')
            self.port = os.environ.get('SMTP_PORT')
            self.username = os.environ.get('SMTP_USERNAME')
            self.password = os.environ.get('SMTP_PASSWORD')
            self.from_email = os.environ.get('EMAIL_FROM')
            self.from_name = os.environ.get('EMAIL_FROM_NAME')
            
        # Convert port to integer if it's a string
        if isinstance(self.port, str) and self.port.isdigit():
            self.port = int(self.port)
            
    def is_configured(self):
        """Controleer of alle vereiste configuratiewaarden zijn ingesteld"""
        return all([
            self.server, self.port, self.username, 
            self.password, self.from_email
        ])

# Service voor het verzenden van e-mails via Microsoft Graph API of SMTP
class EmailService:
    def __init__(self, email_settings=None):
        """
        Initialiseer de email service met optionele workspace-specifieke instellingen
        
        Args:
            email_settings: EmailSettings model voor een specifieke workspace (optioneel)
                            Als niet opgegeven, worden systeem-instellingen gebruikt
        """
        self.logger = logging.getLogger(__name__)
        self.email_settings = email_settings
        
        # Maak configuratie objecten op basis van de instellingen
        self.ms_graph_config = MSGraphConfig(email_settings)
        self.smtp_config = SMTPConfig(email_settings)
        
        # Bepaal de methode van verzenden
        if email_settings and email_settings.use_ms_graph:
            self.use_ms_graph = True
        elif self.ms_graph_config.is_configured():
            self.use_ms_graph = True
        elif self.smtp_config.is_configured():
            self.use_ms_graph = False
        else:
            self.use_ms_graph = True  # Default naar MS Graph als nichts beschikbaar
        
    def get_token(self):
        """Verkrijg een toegangstoken van Microsoft Identity Platform"""
        if not self.ms_graph_config.is_configured():
            self.logger.error("Microsoft Graph API is niet geconfigureerd.")
            return None
            
        app = msal.ConfidentialClientApplication(
            self.ms_graph_config.client_id,
            authority=self.ms_graph_config.authority,
            client_credential={"client_secret": self.ms_graph_config.client_secret},
        )
        
        result = app.acquire_token_for_client(scopes=self.ms_graph_config.scope)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            self.logger.error(f"Error bij het verkrijgen van toegangstoken: {result.get('error')}")
            self.logger.error(f"Beschrijving: {result.get('error_description')}")
            return None
    
    def send_via_smtp(self, recipient_email, subject, body_html, cc=None, attachments=None):
        """Verzend e-mail via SMTP"""
        if not self.smtp_config.is_configured():
            self.logger.error("SMTP is niet geconfigureerd.")
            return False
            
        try:
            # Maak bericht
            msg = MIMEMultipart()
            msg['Subject'] = subject
            
            # Voeg afzender toe
            from_address = f"{self.smtp_config.from_name} <{self.smtp_config.from_email}>" if self.smtp_config.from_name else self.smtp_config.from_email
            msg['From'] = from_address
            
            # Voeg ontvanger(s) toe
            msg['To'] = recipient_email
            
            # Voeg CC-ontvangers toe
            if cc:
                if isinstance(cc, str):
                    cc = [cc]
                msg['Cc'] = ', '.join(cc)
            
            # Voeg HTML inhoud toe
            msg.attach(MIMEText(body_html, 'html'))
            
            # Voeg bijlagen toe indien aanwezig
            if attachments:
                for attachment in attachments:
                    with open(attachment['path'], 'rb') as file:
                        part = MIMEApplication(file.read(), Name=attachment['filename'])
                    
                    part['Content-Disposition'] = f'attachment; filename="{attachment["filename"]}"'
                    msg.attach(part)
            
            # Maak verbinding met SMTP server en verstuur
            with smtplib.SMTP(self.smtp_config.server, self.smtp_config.port) as server:
                server.starttls()
                server.login(self.smtp_config.username, self.smtp_config.password)
                
                # Bepaal alle ontvangers voor verzending
                all_recipients = [recipient_email]
                if cc:
                    all_recipients.extend(cc if isinstance(cc, list) else [cc])
                
                server.sendmail(
                    self.smtp_config.from_email, 
                    all_recipients, 
                    msg.as_string()
                )
                
            self.logger.info(f"E-mail succesvol verzonden naar {recipient_email} via SMTP")
            return True
                
        except Exception as e:
            self.logger.error(f"Error bij het verzenden van e-mail via SMTP: {str(e)}")
            return False
        
    def send_via_ms_graph(self, recipient_email, subject, body_html, cc=None, attachments=None):
        """Verzend e-mail via Microsoft Graph API"""
        if not self.ms_graph_config.is_configured():
            self.logger.error("Microsoft Graph API is niet geconfigureerd.")
            return False
            
        access_token = self.get_token()
        if not access_token:
            return False
        
        # Microsoft Graph API endpoint voor het verzenden van e-mail
        endpoint = 'https://graph.microsoft.com/v1.0/users/' + self.ms_graph_config.sender_email + '/sendMail'
        
        # E-mail opbouwen volgens Microsoft Graph API formaat
        email_msg = {
            'message': {
                'subject': subject,
                'body': {
                    'contentType': 'HTML',
                    'content': body_html
                },
                'toRecipients': [
                    {
                        'emailAddress': {
                            'address': recipient_email
                        }
                    }
                ]
            },
            'saveToSentItems': 'true'
        }
        
        # CC-ontvangers toevoegen indien opgegeven
        if cc:
            cc_recipients = []
            if isinstance(cc, str):
                cc = [cc]  # Converteer enkele string naar lijst
                
            for cc_email in cc:
                cc_recipients.append({
                    'emailAddress': {
                        'address': cc_email
                    }
                })
                
            if cc_recipients:
                email_msg['message']['ccRecipients'] = cc_recipients
        
        # Headers voor de API-aanvraag
        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(endpoint, headers=headers, json=email_msg)
            if response.status_code == 202:  # 202 Accepted is succes
                self.logger.info(f"E-mail succesvol verzonden naar {recipient_email} via MS Graph")
                return True
            else:
                self.logger.error(f"Error bij het verzenden van e-mail: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Exception bij het verzenden van e-mail: {str(e)}")
            return False
            
    def send_email(self, recipient_email, subject, body_html, cc=None, attachments=None):
        """
        Verzend een e-mail via de geconfigureerde methode (MS Graph of SMTP)
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (optioneel), string of lijst
            attachments: Lijst van bijlagen (optioneel), elk een dict met 'path' en 'filename'
        
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        if self.use_ms_graph:
            return self.send_via_ms_graph(recipient_email, subject, body_html, cc, attachments)
        else:
            return self.send_via_smtp(recipient_email, subject, body_html, cc, attachments)

    def send_workspace_invitation(self, recipient_email, workspace_name, activation_token, customer_name=None):
        """
        Stuur een uitnodiging voor een nieuwe workspace naar een klant
        
        Args:
            recipient_email: E-mailadres van de ontvanger
            workspace_name: Naam van de workspace
            activation_token: Token voor activatie en eerste login
            customer_name: Naam van de klant (optioneel)
        """
        # Bepaal de activatie-URL
        activation_url = url_for(
            'activate_workspace', 
            token=activation_token, 
            workspace=workspace_name,
            _external=True
        )
        
        greeting = f"Beste {customer_name}" if customer_name else "Beste"
        
        subject = f"Uitnodiging: Uw nieuwe facturatie platform workspace '{workspace_name}'"
        
        # HTML body van de e-mail
        body_html = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #0078D4; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .button {{ display: inline-block; background-color: #0078D4; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
                    .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Uw nieuwe facturatie platform</h1>
                    </div>
                    <div class="content">
                        <p>{greeting},</p>
                        
                        <p>Er is een nieuwe workspace voor u aangemaakt in ons facturatie systeem met de naam <strong>'{workspace_name}'</strong>.</p>
                        
                        <p>Bij uw eerste login wordt u de beheerder van deze werkruimte. U kunt vervolgens extra gebruikers toevoegen en beheren.</p>
                        
                        <p>Klik op onderstaande knop om uw werkruimte te activeren en uw account in te stellen:</p>
                        
                        <div style="text-align: center;">
                            <a href="{activation_url}" class="button">Werkruimte activeren</a>
                        </div>
                        
                        <p>Of kopieer en plak deze URL in uw browser:</p>
                        <p>{activation_url}</p>
                        
                        <p>Deze activatielink is 7 dagen geldig.</p>
                        
                        <p>Met vriendelijke groet,<br>Het Facturatie Platform Team</p>
                    </div>
                    <div class="footer">
                        <p>Dit is een automatisch gegenereerd bericht. Antwoorden op deze e-mail worden niet gelezen.</p>
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
        # Bepaal de activatie-URL
        activation_url = url_for(
            'activate_user', 
            token=activation_token, 
            workspace=workspace_name,
            _external=True
        )
        
        invited_by = f"U bent uitgenodigd door {inviter_name}" if inviter_name else "U bent uitgenodigd"
        
        subject = f"Uitnodiging: Toegang tot facturatie platform '{workspace_name}'"
        
        # HTML body van de e-mail
        body_html = f"""
        <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #0078D4; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .button {{ display: inline-block; background-color: #0078D4; color: white; padding: 12px 24px; 
                              text-decoration: none; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
                    .footer {{ font-size: 12px; color: #666; margin-top: 30px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Uitnodiging voor '{workspace_name}'</h1>
                    </div>
                    <div class="content">
                        <p>Beste,</p>
                        
                        <p>{invited_by} om toegang te krijgen tot de werkruimte <strong>'{workspace_name}'</strong> op ons facturatie platform.</p>
                        
                        <p>Klik op onderstaande knop om uw account te activeren:</p>
                        
                        <div style="text-align: center;">
                            <a href="{activation_url}" class="button">Account activeren</a>
                        </div>
                        
                        <p>Of kopieer en plak deze URL in uw browser:</p>
                        <p>{activation_url}</p>
                        
                        <p>Deze activatielink is 48 uur geldig.</p>
                        
                        <p>Met vriendelijke groet,<br>Het Facturatie Platform Team</p>
                    </div>
                    <div class="footer">
                        <p>Dit is een automatisch gegenereerd bericht. Antwoorden op deze e-mail worden niet gelezen.</p>
                    </div>
                </div>
            </body>
        </html>
        """
        
        return self.send_email(recipient_email, subject, body_html)

# Voeg extra methoden toe aan de EmailService klasse
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
        
        # Haal de workspace-specifieke e-mailinstellingen op
        email_settings = EmailSettings.query.filter_by(workspace_id=workspace_id).first()
        
        # Maak een nieuwe instantie met de workspace-specifieke instellingen
        return EmailService(email_settings)
    
    @staticmethod
    def send_email_for_workspace(workspace_id, recipient_email, subject, body_html, cc=None, attachments=None):
        """
        Verzend e-mail voor een specifieke workspace
        
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
        # Maak een instantie voor deze workspace
        service = EmailServiceHelper.create_for_workspace(workspace_id)
        
        # Verstuur de e-mail
        return service.send_email(recipient_email, subject, body_html, cc, attachments)
    
    @staticmethod
    def receive_email(message_data, workspace_id=None):
        """
        Verwerk een ontvangen e-mail en sla deze op in de database
        
        Args:
            message_data: Dictionary met e-mailgegevens (onderwerp, afzender, etc.)
            workspace_id: Optionele workspace ID voor directe toewijzing
            
        Returns:
            EmailMessage: Het aangemaakte e-mailbericht object
        """
        from models import EmailMessage, db, Customer
        from datetime import datetime
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Voeg noodzakelijke velden toe aan e-mailbericht
        message = EmailMessage(
            workspace_id=workspace_id,
            message_id=message_data.get('message_id'),
            subject=message_data.get('subject'),
            sender=message_data.get('sender'),
            recipient=message_data.get('recipient'),
            body_text=message_data.get('body_text'),
            body_html=message_data.get('body_html'),
            received_date=message_data.get('received_date') or datetime.now(),
            status='received'
        )
        
        # Als er bijlagen zijn, sla deze op
        if 'attachments' in message_data and message_data['attachments']:
            message.set_attachments(message_data['attachments'])
        
        # Als er een afzender is, probeer deze te koppelen aan een klant
        if message.sender and workspace_id:
            # Zoek een klant met hetzelfde e-mailadres in de workspace
            customer = Customer.query.filter_by(
                email=message.sender,
                workspace_id=workspace_id
            ).first()
            
            if customer:
                message.customer_id = customer.id
        
        # Sla het bericht op in de database
        db.session.add(message)
        db.session.commit()
        
        # Log het ontvangen bericht
        logger.info(f"E-mail ontvangen en opgeslagen: {message.subject}")
        
        return message

# Globale instantie voor systeem-e-mails
email_service = EmailService()