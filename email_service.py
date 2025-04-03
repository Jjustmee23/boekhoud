"""
E-mail service module voor het versturen van e-mails via Microsoft Graph API of SMTP.
Implementeert Microsoft Authentication Library (MSAL) voor authenticatie met Microsoft Graph API.
"""

import os
import json
import logging
import msal
import requests
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import url_for, current_app

# Logger configuratie
logger = logging.getLogger(__name__)

class EmailProvider:
    """Basis klasse voor e-mail providers"""
    
    def send(self, recipient, subject, body_html, cc=None, attachments=None):
        """Verstuur een e-mail (implementatie door subklassen)"""
        raise NotImplementedError("Deze methode moet worden geïmplementeerd door een subklasse")
    
    def is_configured(self):
        """Controleert of deze provider correct is geconfigureerd"""
        raise NotImplementedError("Deze methode moet worden geïmplementeerd door een subklasse")

class MSGraphProvider(EmailProvider):
    """Microsoft Graph API provider voor e-mail verzending via Office 365"""
    
    def __init__(self, settings=None):
        """
        Initialiseer Microsoft Graph Provider met e-mail instellingen
        
        Args:
            settings: EmailSettings object of None voor systeem-instellingen
        """
        from models import EmailSettings
        from app import app
        
        self.logger = logging.getLogger(__name__)
        self._client_app = None
        self._token = None
        
        # Standaardwaarden instellen
        self.client_id = None
        self.client_secret = None
        self.tenant_id = None
        self.sender_email = None
        self.default_sender_name = "MidaWeb"
        
        # Instellingen laden van settings object als dat is opgegeven
        if settings and settings.use_ms_graph:
            self._load_from_settings(settings)
        else:
            # Anders uit systeem-instellingen (bij None) of uit omgevingsvariabelen (fallback)
            self._load_from_system_settings(app)
        
        # Authority URL instellen voor MSAL
        if self.tenant_id:
            self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        else:
            self.authority = None
            
        # Stel de endpoint URL in - we gebruiken de versie 1.0 API
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
            
    def _load_from_settings(self, settings):
        """Laad instellingen uit EmailSettings object"""
        from models import EmailSettings
        
        self.client_id = settings.ms_graph_client_id
        self.client_secret = EmailSettings.decrypt_secret(settings.ms_graph_client_secret)
        self.tenant_id = settings.ms_graph_tenant_id
        
        # Bepaal het afzenderadres - gebruik een gedeelde mailbox indien ingesteld
        if hasattr(settings, 'ms_graph_use_shared_mailbox') and settings.ms_graph_use_shared_mailbox:
            if hasattr(settings, 'ms_graph_shared_mailbox') and settings.ms_graph_shared_mailbox:
                self.sender_email = settings.ms_graph_shared_mailbox
            else:
                # Fallback naar regulier afzenderadres
                self.sender_email = settings.ms_graph_sender_email
        else:
            self.sender_email = settings.ms_graph_sender_email
            
        # Stel afzendernaam in
        if settings.default_sender_name:
            self.default_sender_name = settings.default_sender_name
            
    def _load_from_system_settings(self, app):
        """Laad instellingen uit systeem instellingen of omgevingsvariabelen"""
        from models import EmailSettings
        
        with app.app_context():
            try:
                # Systeem-instellingen ophalen (workspace_id=None)
                system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
                if system_settings and system_settings.use_ms_graph:
                    self._load_from_settings(system_settings)
                else:
                    # Gebruik omgevingsvariabelen als fallback
                    self._load_from_environment()
            except Exception as e:
                self.logger.error(f"Fout bij ophalen van systeem-instellingen: {str(e)}")
                # Gebruik omgevingsvariabelen als fallback
                self._load_from_environment()
    
    def _load_from_environment(self):
        """Laad instellingen uit omgevingsvariabelen"""
        self.client_id = os.environ.get("MS_GRAPH_CLIENT_ID")
        self.client_secret = os.environ.get("MS_GRAPH_CLIENT_SECRET")
        self.tenant_id = os.environ.get("MS_GRAPH_TENANT_ID")
        self.sender_email = os.environ.get("MS_GRAPH_SENDER_EMAIL")
        
    def is_configured(self):
        """Controleert of alle benodigde instellingen aanwezig zijn"""
        return all([
            self.client_id, 
            self.client_secret, 
            self.tenant_id, 
            self.sender_email, 
            self.authority
        ])
        
    def _get_token(self):
        """
        Verkrijg een toegangstoken voor Microsoft Graph API
        
        Returns:
            str: Access token of None bij fouten
        """
        if not self.is_configured():
            self.logger.error("Microsoft Graph API niet correct geconfigureerd")
            return None
        
        if not self._client_app:
            # MSAL confidential client initialiseren
            self._client_app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                authority=self.authority,
                client_credential=self.client_secret
            )
        
        # Controleer of alle benodigde velden zijn ingevuld
        if not self.client_id or not self.client_secret or not self.tenant_id:
            self.logger.error(f"Missende MS Graph instellingen: client_id={'aanwezig' if self.client_id else 'ontbreekt'}, "
                          f"client_secret={'aanwezig' if self.client_secret else 'ontbreekt'}, "
                          f"tenant_id={'aanwezig' if self.tenant_id else 'ontbreekt'}")
            return None
        
        # Token voor client credentials flow aanvragen
        scopes = ["https://graph.microsoft.com/.default"]
        
        try:
            # Log meer details voor debugging
            self.logger.info(f"Verkrijgen van token voor tenant_id: {self.tenant_id}, client_id: {self.client_id[:5]}...")
            
            # Client credentials flow gebruiken (app-only authenticatie)
            result = self._client_app.acquire_token_for_client(scopes=scopes)
            
            if "access_token" in result:
                token_part = result["access_token"][:10] if result["access_token"] else "leeg"
                self.logger.info(f"Microsoft Graph API toegangstoken succesvol verkregen: {token_part}...")
                return result["access_token"]
            else:
                self.logger.error(f"Fout bij verkrijgen token: {result.get('error')}")
                self.logger.error(f"Error beschrijving: {result.get('error_description')}")
                if 'error_codes' in result:
                    self.logger.error(f"Error codes: {result.get('error_codes')}")
                return None
        except Exception as e:
            self.logger.error(f"Exception bij het verkrijgen van token: {str(e)}")
            import traceback
            self.logger.error(f"Stacktrace: {traceback.format_exc()}")
            return None
        
    def send(self, recipient, subject, body_html, cc=None, attachments=None):
        """
        Verstuur een e-mail via Microsoft Graph API
        
        Args:
            recipient: E-mailadres van de ontvanger
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (string of lijst)
            attachments: Lijst van bijlagen, elk een dict met 'path' en 'filename'
            
        Returns:
            bool: True als de e-mail succesvol is verzonden, anders False
        """
        if not self.is_configured():
            self.logger.error("Microsoft Graph API niet correct geconfigureerd")
            return False
        
        # Toegangstoken verkrijgen
        access_token = self._get_token()
        if not access_token:
            return False
        
        # Bepaal het juiste adres voor verzending (hoofdgebruiker of gedeelde mailbox)
        # Voor gedeelde mailboxen hebben we Mail.Send en Mail.Send.Shared permissies nodig
        send_from_address = self.sender_email
        
        if not send_from_address:
            self.logger.error("Geen afzender e-mailadres ingesteld")
            return False
            
        self.logger.info(f"Verzenden vanaf: {send_from_address}")
        
        # E-mail bericht opbouwen
        email_payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": recipient
                        }
                    }
                ],
                "from": {
                    "emailAddress": {
                        "address": send_from_address,
                        "name": self.default_sender_name or "MidaWeb"
                    }
                }
            },
            "saveToSentItems": "true"
        }
        
        # Voeg CC ontvangers toe indien opgegeven
        if cc:
            cc_recipients = []
            if isinstance(cc, str):
                cc = [cc]  # Converteer enkele string naar lijst
                
            for cc_email in cc:
                cc_recipients.append({
                    "emailAddress": {
                        "address": cc_email
                    }
                })
                
            if cc_recipients:
                email_payload["message"]["ccRecipients"] = cc_recipients
        
        # Bijlagen toevoegen indien aanwezig
        if attachments:
            self._add_attachments_to_message(email_payload, attachments)
        
        # API endpoint voor verzenden met gedeelde mailbox of hoofdaccount
        # Altijd '/users/{email}/sendMail' gebruiken voor app-only authenticatie
        endpoint = f"{self.graph_endpoint}/users/{send_from_address}/sendMail"
        
        # Headers voor de aanvraag
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            # POST aanvraag naar Microsoft Graph API
            self.logger.info(f"Versturen naar endpoint: {endpoint}")
            response = requests.post(endpoint, headers=headers, json=email_payload, verify=True)
            
            if response.status_code == 202:  # 202 Accepted betekent succes
                self.logger.info(f"E-mail succesvol verzonden naar {recipient} via Microsoft Graph API")
                return True
            else:
                self.logger.error(f"Fout bij versturen e-mail: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                
                # Controleer op specifieke foutcodes en geef duidelijkere foutmeldingen
                try:
                    error_data = response.json() if response.text else {}
                    error_code = error_data.get('error', {}).get('code', '')
                    error_message = error_data.get('error', {}).get('message', '')
                    
                    self.logger.error(f"Microsoft Graph foutcode: {error_code}")
                    self.logger.error(f"Microsoft Graph foutmelding: {error_message}")
                    
                    # Controleer op veelvoorkomende fouten en log extra details
                    if error_code == 'AuthenticationError':
                        self.logger.error(f"Authenticatiefout: controleer client ID, tenant ID en client secret")
                    elif error_code == 'MailboxNotEnabledForRESTAPI':
                        self.logger.error(f"Mailbox niet ingeschakeld voor Microsoft Graph API")
                    elif error_code == 'InvalidRecipients':
                        self.logger.error(f"Ongeldige ontvanger(s): {recipient}")
                except:
                    # Geen JSON response of andere fout bij verwerken
                    pass
                
                return False
        except requests.exceptions.SSLError as ssl_err:
            self.logger.error(f"SSL fout bij het versturen van e-mail: {str(ssl_err)}")
            self.logger.error("Dit kan worden veroorzaakt door ontbrekende of ongeldige SSL-certificaten")
            return False
        except requests.exceptions.ConnectionError as conn_err:
            self.logger.error(f"Verbindingsfout bij het versturen van e-mail: {str(conn_err)}")
            self.logger.error("Controleer de netwerkverbinding en firewalls")
            return False
        except Exception as e:
            self.logger.error(f"Exception bij het versturen van e-mail: {str(e)}")
            import traceback
            self.logger.error(f"Stacktrace: {traceback.format_exc()}")
            return False
    
    def _build_email_message(self, recipient, subject, body_html, cc=None):
        """Bouw het e-mail bericht in het formaat voor Microsoft Graph API"""
        # Basis e-mail bericht
        msg = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": body_html
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": recipient
                        }
                    }
                ]
            },
            "saveToSentItems": "true"
        }
        
        # Voeg 'from' alleen toe als er een expliciet afzenderadres is opgegeven
        # Bij gedeelde mailboxen zal de sendMail API automatisch 
        # het standaard adres van de geauthenticeerde gebruiker gebruiken
        if self.sender_email:
            msg["message"]["from"] = {
                "emailAddress": {
                    "address": self.sender_email,
                    "name": self.default_sender_name or "MidaWeb"
                }
            }
            
        # Voeg 'sender' toe als er een afzender is (belangrijk voor gedeelde mailboxen)
        if self.sender_email:
            msg["message"]["sender"] = {
                "emailAddress": {
                    "address": self.sender_email,
                    "name": self.default_sender_name or "MidaWeb"
                }
            }
        
        # Voeg CC ontvangers toe indien opgegeven
        if cc:
            cc_recipients = []
            if isinstance(cc, str):
                cc = [cc]  # Converteer enkele string naar lijst
                
            for cc_email in cc:
                cc_recipients.append({
                    "emailAddress": {
                        "address": cc_email
                    }
                })
                
            if cc_recipients:
                msg["message"]["ccRecipients"] = cc_recipients
                
        return msg
        
    def _add_attachments_to_message(self, email_payload, attachments):
        """Voeg bijlagen toe aan het bericht"""
        if not attachments:
            return
            
        # List voor bijlagen toevoegen aan bericht
        if "attachments" not in email_payload["message"]:
            email_payload["message"]["attachments"] = []
        
        for attachment in attachments:
            try:
                with open(attachment["path"], "rb") as file:
                    content = file.read()
                    
                import base64
                # Base64 encoderen van de inhoud
                content_b64 = base64.b64encode(content).decode("utf-8")
                
                # Bijlage toevoegen aan bericht
                email_payload["message"]["attachments"].append({
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": attachment["filename"],
                    "contentType": "application/octet-stream",
                    "contentBytes": content_b64
                })
                
                self.logger.info(f"Bijlage toegevoegd: {attachment['filename']}")
            except Exception as e:
                self.logger.error(f"Fout bij toevoegen bijlage {attachment['filename']}: {str(e)}")

class SMTPProvider(EmailProvider):
    """SMTP provider voor e-mail verzending via reguliere mail servers"""
    
    def __init__(self, settings=None):
        """
        Initialiseer SMTP Provider met e-mail instellingen
        
        Args:
            settings: EmailSettings object of None voor systeem-instellingen
        """
        from models import EmailSettings
        from app import app
        
        self.logger = logging.getLogger(__name__)
        
        # Standaardwaarden instellen
        self.server = None
        self.port = None
        self.username = None
        self.password = None
        self.from_email = None
        self.from_name = None
        self.use_ssl = True
        self.use_tls = False
        self.reply_to = None
        
        # Instellingen laden van settings object als dat is opgegeven
        if settings and not settings.use_ms_graph:
            self._load_from_settings(settings)
        else:
            # Anders uit systeem-instellingen (bij None) of uit omgevingsvariabelen (fallback)
            self._load_from_system_settings(app)
        
    def _load_from_settings(self, settings):
        """Laad instellingen uit EmailSettings object"""
        from models import EmailSettings
        
        self.server = settings.smtp_server
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = EmailSettings.decrypt_secret(settings.smtp_password)
        self.from_email = settings.email_from
        self.from_name = settings.email_from_name
        self.reply_to = settings.reply_to
        
        # Nieuwere configuratie-opties
        if hasattr(settings, 'smtp_use_ssl'):
            self.use_ssl = settings.smtp_use_ssl
        if hasattr(settings, 'smtp_use_tls'):
            self.use_tls = settings.smtp_use_tls
            
    def _load_from_system_settings(self, app):
        """Laad instellingen uit systeem instellingen of omgevingsvariabelen"""
        from models import EmailSettings
        
        with app.app_context():
            try:
                # Systeem-instellingen ophalen (workspace_id=None)
                system_settings = EmailSettings.query.filter_by(workspace_id=None).first()
                if system_settings and not system_settings.use_ms_graph:
                    self._load_from_settings(system_settings)
                else:
                    # Gebruik omgevingsvariabelen als fallback
                    self._load_from_environment()
            except Exception as e:
                self.logger.error(f"Fout bij ophalen van systeem-instellingen: {str(e)}")
                # Gebruik omgevingsvariabelen als fallback
                self._load_from_environment()
    
    def _load_from_environment(self):
        """Laad instellingen uit omgevingsvariabelen"""
        self.server = os.environ.get("SMTP_SERVER")
        port_str = os.environ.get("SMTP_PORT")
        self.port = int(port_str) if port_str and port_str.isdigit() else None
        self.username = os.environ.get("SMTP_USERNAME")
        self.password = os.environ.get("SMTP_PASSWORD")
        self.from_email = os.environ.get("EMAIL_FROM")
        self.from_name = os.environ.get("EMAIL_FROM_NAME")
        
        # Default voor SSL/TLS instellingen
        self.use_ssl = True
        self.use_tls = False
        
    def is_configured(self):
        """Controleert of alle benodigde instellingen aanwezig zijn"""
        return all([
            self.server, 
            self.port, 
            self.username, 
            self.password, 
            self.from_email
        ])
        
    def send(self, recipient, subject, body_html, cc=None, attachments=None):
        """
        Verstuur een e-mail via SMTP
        
        Args:
            recipient: E-mailadres van de ontvanger
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (string of lijst)
            attachments: Lijst van bijlagen, elk een dict met 'path' en 'filename'
            
        Returns:
            bool: True als de e-mail succesvol is verzonden, anders False
        """
        if not self.is_configured():
            self.logger.error("SMTP niet correct geconfigureerd")
            return False
        
        try:
            # Maak e-mail bericht
            msg = self._build_email_message(recipient, subject, body_html, cc)
            
            # Voeg bijlagen toe indien aanwezig
            if attachments:
                self._add_attachments_to_message(msg, attachments)
            
            # Bepaal ontvangers voor verzending
            recipients = [recipient]
            if cc:
                if isinstance(cc, str):
                    recipients.append(cc)
                else:
                    recipients.extend(cc)
            
            # Maak verbinding met SMTP server en verstuur e-mail
            self._send_via_smtp(msg, recipients)
            
            self.logger.info(f"E-mail succesvol verzonden naar {recipient} via SMTP")
            return True
            
        except Exception as e:
            self.logger.error(f"Fout bij versturen e-mail via SMTP: {str(e)}")
            return False
    
    def _build_email_message(self, recipient, subject, body_html, cc=None):
        """Bouw het e-mail bericht op voor SMTP verzending"""
        # Maak multipart bericht
        msg = MIMEMultipart()
        msg["Subject"] = subject
        
        # Voeg afzender toe
        if self.from_name:
            from_addr = f"{self.from_name} <{self.from_email}>"
        else:
            from_addr = self.from_email
            
        msg["From"] = from_addr
        
        # Voeg ontvanger toe
        msg["To"] = recipient
        
        # Voeg CC toe indien opgegeven
        if cc:
            if isinstance(cc, list):
                msg["Cc"] = ", ".join(cc)
            else:
                msg["Cc"] = cc
        
        # Voeg reply-to toe indien opgegeven
        if self.reply_to:
            msg["Reply-To"] = self.reply_to
            
        # Voeg HTML inhoud toe
        msg.attach(MIMEText(body_html, "html"))
        
        return msg
        
    def _add_attachments_to_message(self, msg, attachments):
        """Voeg bijlagen toe aan het bericht"""
        if not attachments:
            return
            
        for attachment in attachments:
            try:
                with open(attachment["path"], "rb") as file:
                    part = MIMEApplication(file.read(), Name=attachment["filename"])
                
                # Voeg headers toe
                part["Content-Disposition"] = f'attachment; filename="{attachment["filename"]}"'
                msg.attach(part)
            except Exception as e:
                self.logger.error(f"Fout bij toevoegen bijlage {attachment['filename']}: {str(e)}")
    
    def _send_via_smtp(self, msg, recipients):
        """Verstuur het bericht via de SMTP server"""
        if self.use_ssl:
            # Voor SSL verbinding (meestal poort 465)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.server, self.port, context=context) as server:
                server.login(self.username, self.password)
                server.sendmail(self.from_email, recipients, msg.as_string())
        else:
            # Voor niet-SSL verbinding (meestal poort 25 of 587)
            with smtplib.SMTP(self.server, self.port) as server:
                if self.use_tls:
                    server.starttls()  # Upgrade naar TLS indien nodig
                server.login(self.username, self.password)
                server.sendmail(self.from_email, recipients, msg.as_string())

class EmailService:
    """
    E-mail service voor het versturen van e-mails via verschillende providers.
    Bepaalt automatisch welke provider te gebruiken op basis van instellingen.
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
        
        # Providers initialiseren
        self.ms_graph_provider = MSGraphProvider(email_settings)
        self.smtp_provider = SMTPProvider(email_settings)
        
        # Bepaal welke provider te gebruiken
        if email_settings:
            self.use_ms_graph = email_settings.use_ms_graph
        else:
            # Als niet gespecificeerd, gebruik MS Graph indien geconfigureerd
            self.use_ms_graph = self.ms_graph_provider.is_configured()
            
            # Als MS Graph niet geconfigureerd is, probeer SMTP
            if not self.use_ms_graph and self.smtp_provider.is_configured():
                self.use_ms_graph = False
            else:
                # Default naar MS Graph als geen van beide geconfigureerd zijn
                self.use_ms_graph = True
    
    def send_email(self, recipient, subject, body_html, cc=None, attachments=None):
        """
        Verstuur een e-mail via de geselecteerde provider
        
        Args:
            recipient: E-mailadres van de ontvanger
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: Carbon copy ontvangers (optioneel), string of lijst
            attachments: Lijst van bijlagen (optioneel), elk een dict met 'path' en 'filename'
        
        Returns:
            bool: True als verzending succesvol was, anders False
        """
        if self.use_ms_graph:
            return self.ms_graph_provider.send(recipient, subject, body_html, cc, attachments)
        else:
            return self.smtp_provider.send(recipient, subject, body_html, cc, attachments)
            
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
        from app import app
        
        with app.app_context():
            # Zoek het template in de database
            try:
                # Zoek eerst workspace-specifiek template indien email_settings een workspace heeft
                if self.email_settings and self.email_settings.workspace_id:
                    template = EmailTemplate.query.filter_by(
                        workspace_id=self.email_settings.workspace_id,
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
        from app import app
        
        with app.app_context():
            try:
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
                    'activation_url': activation_url,
                    'registration_instructions': True
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
                            .header {{ background-color: #0078D4; color: white; padding: 20px; text-align: center; }}
                            .content {{ padding: 20px; background-color: #f9f9f9; }}
                            .button {{ display: inline-block; background-color: #0078D4; color: white; padding: 12px 24px; 
                                      text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                            .footer {{ padding: 20px; text-align: center; font-size: 0.8em; color: #777; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <h1>Welkom bij uw nieuwe administratie platform</h1>
                            </div>
                            <div class="content">
                                <p>{greeting},</p>
                                <p>We hebben een nieuwe workspace aangemaakt voor u in ons administratie platform: <strong>{workspace_name}</strong>.</p>
                                <p>Via dit platform kunt u uw facturen, klanten en betalingen beheren.</p>
                                <p>Klik op onderstaande link om uw workspace te activeren en een wachtwoord in te stellen:</p>
                                <p><a href="{activation_url}" class="button">Activeer uw workspace</a></p>
                                <p>Als de knop niet werkt, kunt u ook de volgende link kopiëren en plakken in uw browser:</p>
                                <p>{activation_url}</p>
                                <p>Deze link is 7 dagen geldig.</p>
                                <p>Met vriendelijke groet,<br>Het MidaWeb Team</p>
                            </div>
                            <div class="footer">
                                <p>Dit is een automatisch gegenereerde e-mail. Gelieve niet te antwoorden op dit bericht.</p>
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
        from app import app
        
        with app.app_context():
            try:
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
                    'inviter_name': inviter_name or 'De beheerder',
                    'registration_instructions': True
                }
                
                # Verstuur de e-mail met het juiste template
                return self.send_template_email(
                    recipient_email,
                    'user_invitation',
                    template_params
                )
            except Exception as e:
                self.logger.error(f"Fout bij versturen gebruikers uitnodiging: {str(e)}")
                
                # Fallback: handmatige e-mail verzenden
                inviter = inviter_name or "De beheerder"
                subject = f"Uitnodiging: Toegang tot {workspace_name} administratie platform"
                
                body_html = f"""
                <html>
                    <head>
                        <style>
                            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                            .header {{ background-color: #0078D4; color: white; padding: 20px; text-align: center; }}
                            .content {{ padding: 20px; background-color: #f9f9f9; }}
                            .button {{ display: inline-block; background-color: #0078D4; color: white; padding: 12px 24px; 
                                      text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                            .footer {{ padding: 20px; text-align: center; font-size: 0.8em; color: #777; }}
                            .instructions {{ background-color: #eef8ff; border-left: 4px solid #0078D4; padding: 15px; margin: 20px 0; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <h1>Uitnodiging Administratie Platform</h1>
                            </div>
                            <div class="content">
                                <p>Beste,</p>
                                <p>{inviter} heeft u uitgenodigd voor toegang tot de <strong>{workspace_name}</strong> werkruimte in het administratie platform.</p>
                                
                                <div class="instructions">
                                    <h3>Registratie-instructies:</h3>
                                    <ol>
                                        <li>Klik op de onderstaande knop "Activeer uw account"</li>
                                        <li>Vul uw gewenste gebruikersnaam en wachtwoord in op het registratieformulier</li>
                                        <li>Na het registreren, gebruikt u bij het inloggen:</li>
                                        <ul>
                                            <li>Werkruimte: <strong>{workspace_name}</strong></li>
                                            <li>Uw gekozen gebruikersnaam</li>
                                            <li>Uw gekozen wachtwoord</li>
                                        </ul>
                                    </ol>
                                </div>
                                
                                <p>Klik op onderstaande link om uw account te activeren:</p>
                                <p><a href="{activation_url}" class="button">Activeer uw account</a></p>
                                <p>Als de knop niet werkt, kunt u ook de volgende link kopiëren en plakken in uw browser:</p>
                                <p>{activation_url}</p>
                                <p>Deze link is 48 uur geldig.</p>
                                <p>Met vriendelijke groet,<br>Het MidaWeb Team</p>
                            </div>
                            <div class="footer">
                                <p>Dit is een automatisch gegenereerde e-mail. Gelieve niet te antwoorden op dit bericht.</p>
                            </div>
                        </div>
                    </body>
                </html>
                """
                
                return self.send_email(recipient_email, subject, body_html)

# Helper klasse met statische methoden
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
        from app import app
        
        with app.app_context():
            try:
                # Zoek workspace-specifieke instellingen
                settings = EmailSettings.query.filter_by(workspace_id=workspace_id).first()
                return EmailService(settings)
            except Exception as e:
                logging.error(f"Fout bij maken van EmailService voor workspace {workspace_id}: {str(e)}")
                # Fallback naar standaard EmailService
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
        service = EmailServiceHelper.create_for_workspace(workspace_id)
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
        from models import EmailMessage, db
        from app import app
        
        with app.app_context():
            try:
                # Bepaal de workspace ID op basis van de ontvanger of de expliciet opgegeven ID
                final_workspace_id = workspace_id
                
                if not final_workspace_id and "recipient" in message_data:
                    # Probeer workspace te bepalen uit het ontvanger e-mailadres
                    # Dit vereist een specifieke conventie zoals workspace_name@yourdomain.com
                    recipient = message_data.get("recipient", "").lower()
                    from models import Workspace
                    
                    # Eenvoudige implementatie: zoek naar alle workspaces en kijk of hun naam in het e-mailadres zit
                    workspaces = Workspace.query.all()
                    for workspace in workspaces:
                        if workspace.name.lower() in recipient:
                            final_workspace_id = workspace.id
                            break
                
                # Maak een nieuw e-mailbericht aan
                email_message = EmailMessage(
                    workspace_id=final_workspace_id,
                    message_id=message_data.get("message_id", str(uuid.uuid4())),
                    subject=message_data.get("subject", "(Geen onderwerp)"),
                    sender=message_data.get("sender", ""),
                    recipient=message_data.get("recipient", ""),
                    body_text=message_data.get("body_text", ""),
                    body_html=message_data.get("body_html", ""),
                    received_date=message_data.get("received_date", datetime.datetime.now()),
                    is_processed=False,
                    status="received"
                )
                
                # Bijlagen toevoegen indien aanwezig
                if "attachments" in message_data and message_data["attachments"]:
                    email_message.set_attachments(message_data["attachments"])
                
                # Opslaan in database
                db.session.add(email_message)
                db.session.commit()
                
                # Log de ontvangst
                logging.info(f"E-mail ontvangen en opgeslagen: {email_message.subject}")
                
                return email_message
                
            except Exception as e:
                logging.error(f"Fout bij verwerken van ontvangen e-mail: {str(e)}")
                # Rollback de transactie bij fouten
                db.session.rollback()
                raise e