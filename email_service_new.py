"""
Nieuwe email service module die gebruik maakt van OAuth-tokens van gebruikers
voor het verzenden van e-mails namens de gebruiker.
"""

import os
import logging
import json
import time
import base64
from datetime import datetime, timedelta

import requests
from flask import url_for, current_app
import msal

# Logging configureren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MSGraphEmailService:
    """
    Class voor het verzenden van e-mails via Microsoft Graph API
    met ondersteuning voor OAuth-tokens van gebruikers.
    """
    
    def __init__(self, settings=None, user_token=None):
        """
        Initialiseer de MS Graph Email Service
        
        Args:
            settings: EmailSettings object met app-registratie instellingen
            user_token: UserOAuthToken object met gebruikersspecifieke token
        """
        self.settings = settings
        self.user_token = user_token
        
        # Microsoft Graph API configuratie
        self.graph_endpoint = 'https://graph.microsoft.com/v1.0'
        self.max_token_retry = 3
        
        # Client configuratie
        if self.user_token:
            # Gebruiker OAuth token modus
            self.client_mode = 'user_oauth'
        elif settings and settings.use_ms_graph:
            # Centrale app modus
            self.client_mode = 'app_auth'
            self.client_id = settings.ms_graph_client_id
            self.client_secret = settings.decrypt_secret(settings.ms_graph_client_secret)
            self.tenant_id = settings.ms_graph_tenant_id
            self.authority = f'https://login.microsoftonline.com/{self.tenant_id}'
            
            # Email configuratie voor app
            self.sender_email = settings.ms_graph_sender_email
            self.use_shared_mailbox = settings.ms_graph_use_shared_mailbox
            self.shared_mailbox = settings.ms_graph_shared_mailbox
            
            self.sender_name = settings.default_sender_name or settings.email_from_name or "MidaWeb"
        else:
            self.client_mode = None
    
    def _get_app_token(self):
        """
        Verkrijg een app token via client credentials flow
        """
        if not self.client_mode == 'app_auth':
            logger.error("App token kan alleen worden verkregen in app_auth modus")
            return None
        
        # MSAL app aanmaken
        app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )
        
        # Token verkrijgen
        scopes = ['https://graph.microsoft.com/.default']
        
        # Haal token op uit cache of via nieuwe aanvraag
        result = app.acquire_token_silent(scopes, account=None)
        if not result:
            logger.info(f"Geen token in cache, nieuwe token aanvragen voor tenant {self.tenant_id}")
            result = app.acquire_token_for_client(scopes=scopes)
        
        if "access_token" in result:
            logger.info("Succesvol app token verkregen")
            return result['access_token']
        else:
            logger.error(f"Kon geen app token verkrijgen: {result.get('error')}, {result.get('error_description')}")
            return None
    
    def _get_user_token(self):
        """
        Haal een geldig gebruikers token op of vernieuw het indien nodig
        """
        if not self.client_mode == 'user_oauth' or not self.user_token:
            logger.error("Gebruikers token kan alleen worden verkregen in user_oauth modus")
            return None
        
        # Check of token nog geldig is
        if self.user_token.is_valid:
            logger.info(f"Gebruiken van bestaand geldig token voor {self.user_token.email}")
            return self.user_token.decrypt_token(self.user_token.access_token)
        
        # Token is verlopen, probeer te vernieuwen
        if not self.user_token.refresh_token:
            logger.error(f"Geen refresh token beschikbaar voor gebruiker {self.user_token.email}")
            return None
        
        # Haal settings op voor app registratie gegevens
        from models import EmailSettings
        settings = EmailSettings.query.filter_by(workspace_id=self.user_token.workspace_id).first()
        if not settings:
            settings = EmailSettings.query.filter_by(workspace_id=None).first()
        
        if not settings or not settings.ms_graph_client_id or not settings.ms_graph_client_secret:
            logger.error("Geen app registratie gegevens beschikbaar voor token vernieuwing")
            return None
        
        # MSAL app aanmaken
        app = msal.PublicClientApplication(
            client_id=settings.ms_graph_client_id,
            authority=f'https://login.microsoftonline.com/common'
        )
        
        # Token vernieuwen
        refresh_token = self.user_token.decrypt_token(self.user_token.refresh_token)
        
        result = app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=self.user_token.oauth_scopes.split() if hasattr(self.user_token, 'oauth_scopes') else ['mail.send']
        )
        
        if "access_token" in result:
            logger.info(f"Token succesvol vernieuwd voor {self.user_token.email}")
            
            # Update token in database
            self.user_token.access_token = self.user_token.encrypt_token(result['access_token'])
            self.user_token.refresh_token = self.user_token.encrypt_token(result.get('refresh_token', refresh_token))
            
            # Update expiry
            expires_in = result.get('expires_in', 3600)
            self.user_token.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 min buffer
            
            from app import db
            db.session.commit()
            
            return result['access_token']
        else:
            logger.error(f"Kon token niet vernieuwen: {result.get('error')}, {result.get('error_description')}")
            return None
    
    def _get_token(self):
        """
        Verkrijg een geldig token op basis van de modus
        """
        if self.client_mode == 'app_auth':
            return self._get_app_token()
        elif self.client_mode == 'user_oauth':
            return self._get_user_token()
        else:
            logger.error("Geen geldige client modus geconfigureerd")
            return None
    
    def send_email(self, to_email, subject, body_html, cc=None, reply_to=None, attachments=None):
        """
        Verzend een e-mail via Microsoft Graph API
        
        Args:
            to_email: Ontvanger e-mailadres of lijst met e-mailadressen
            subject: Onderwerp van de e-mail
            body_html: HTML inhoud van de e-mail
            cc: CC e-mailadressen (optioneel)
            reply_to: Reply-to e-mailadres (optioneel)
            attachments: Lijst met bijlagen als dict met 'path' en optioneel 'name'
                    
        Returns:
            Tuple met (success, message)
        """
        # Bepaal token op basis van modus
        access_token = self._get_token()
        if not access_token:
            return False, "Geen geldig authenticatie token beschikbaar"
        
        # Maak een lijst van alle ontvangers
        if isinstance(to_email, str):
            to_email = [to_email]
        
        if isinstance(cc, str) and cc:
            cc = [cc]
        elif not cc:
            cc = []
        
        # Bepaal de afzender
        if self.client_mode == 'user_oauth':
            sender_email = self.user_token.email
            sender_name = self.user_token.display_name or sender_email.split('@')[0]
        else:
            if self.use_shared_mailbox and self.shared_mailbox:
                sender_email = self.shared_mailbox
            else:
                sender_email = self.sender_email
            
            sender_name = self.sender_name
        
        # Bereid het e-mail verzoek voor
        message = {
            'message': {
                'subject': subject,
                'body': {
                    'contentType': 'HTML',
                    'content': body_html
                },
                'toRecipients': [{'emailAddress': {'address': email}} for email in to_email],
                'from': {
                    'emailAddress': {
                        'address': sender_email,
                        'name': sender_name
                    }
                }
            }
        }
        
        # Voeg CC toe indien aanwezig
        if cc:
            message['message']['ccRecipients'] = [{'emailAddress': {'address': email}} for email in cc]
        
        # Voeg reply-to toe indien aanwezig
        if reply_to:
            message['message']['replyTo'] = [{'emailAddress': {'address': reply_to}}]
        
        # Voeg bijlagen toe indien aanwezig
        if attachments:
            message['message']['attachments'] = []
            for attachment in attachments:
                if isinstance(attachment, str):
                    path = attachment
                    name = os.path.basename(path)
                elif isinstance(attachment, dict):
                    path = attachment.get('path')
                    name = attachment.get('name') or os.path.basename(path)
                else:
                    continue
                
                if not os.path.exists(path):
                    logger.warning(f"Bijlage niet gevonden: {path}")
                    continue
                
                # Lees bestand en codeer als base64
                with open(path, 'rb') as file:
                    content_bytes = file.read()
                    content_b64 = base64.b64encode(content_bytes).decode('utf-8')
                
                # Voeg bijlage toe
                message['message']['attachments'].append({
                    '@odata.type': '#microsoft.graph.fileAttachment',
                    'name': name,
                    'contentType': 'application/octet-stream',
                    'contentBytes': content_b64
                })
        
        # Bepaal het endpoint op basis van de modus
        if self.client_mode == 'user_oauth':
            # In user_oauth modus sturen we het bericht namens de gebruiker
            endpoint = f"{self.graph_endpoint}/me/sendMail"
        else:
            # In app_auth modus, controleren of we een gedeelde mailbox gebruiken
            if self.use_shared_mailbox and self.shared_mailbox:
                endpoint = f"{self.graph_endpoint}/users/{self.shared_mailbox}/sendMail"
            else:
                endpoint = f"{self.graph_endpoint}/users/{sender_email}/sendMail"
        
        # Headers voor het verzoek
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Verstuur het verzoek
        try:
            response = requests.post(endpoint, headers=headers, json=message)
            
            if response.status_code == 202 or response.status_code == 200:
                logger.info(f"E-mail succesvol verzonden aan {to_email}")
                return True, "E-mail succesvol verzonden"
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', f"Status code: {response.status_code}")
                logger.error(f"Fout bij versturen e-mail: {error_msg}")
                return False, f"Fout bij versturen e-mail: {error_msg}"
        
        except Exception as e:
            logger.error(f"Uitzondering bij versturen e-mail: {str(e)}")
            return False, f"Uitzondering bij versturen e-mail: {str(e)}"


def send_activation_email(token, email, is_workspace=False):
    """
    Verzend een activatie e-mail met de gegenereerde token.
    
    Args:
        token: De gegenereerde JWT token als string
        email: E-mailadres van de ontvanger
        is_workspace: True als het een workspace activatie betreft, False voor gebruiker activatie
    """
    logger.info(f"{'Workspace' if is_workspace else 'Gebruiker'} activatie e-mail verzenden naar {email}")
    
    # Importeer benodigde modules binnen de functie om circulaire imports te voorkomen
    from models import EmailSettings
    from app import app
    
    # Haal basis URL en e-mailinstellingen op
    with app.app_context():
        settings = EmailSettings.query.filter_by(workspace_id=None).first()
        
        if not settings:
            # Gebruik standaard fallback instellingen als geen instellingen beschikbaar zijn
            logger.warning("Geen e-mailinstellingen gevonden, gebruik standaard fallback")
            base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
            sender_name = "MidaWeb"
        else:
            # Bepaal base URL vanuit configuratie of omgevingsvariabele
            base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
            sender_name = settings.default_sender_name or settings.email_from_name or "MidaWeb"
        
        # Maak activatie URL
        if is_workspace:
            activation_url = f"{base_url}/activate/workspace/{token}"
        else:
            activation_url = f"{base_url}/activate/user/{token}"
        
        # Bereid e-mail inhoud voor
        subject = "Activeer uw werkruimte" if is_workspace else "Activeer uw account"
        
        if is_workspace:
            body_html = f"""
            <html>
                <body>
                    <h1>Activeer uw werkruimte</h1>
                    <p>Klik op de onderstaande link om uw werkruimte te activeren:</p>
                    <p><a href="{activation_url}">{activation_url}</a></p>
                    <p>Deze link verloopt over 24 uur.</p>
                    <p>Met vriendelijke groet,<br/>{sender_name}</p>
                </body>
            </html>
            """
        else:
            body_html = f"""
            <html>
                <body>
                    <h1>Activeer uw account</h1>
                    <p>Klik op de onderstaande link om uw account te activeren:</p>
                    <p><a href="{activation_url}">{activation_url}</a></p>
                    <p>Deze link verloopt over 24 uur.</p>
                    <p>Met vriendelijke groet,<br/>{sender_name}</p>
                </body>
            </html>
            """
        
        # Verzend e-mail via MS Graph API indien geconfigureerd
        if settings and settings.use_ms_graph:
            email_service = MSGraphEmailService(settings=settings)
            success, message = email_service.send_email(
                to_email=email,
                subject=subject,
                body_html=body_html
            )
            
            if success:
                logger.info(f"Activatie e-mail succesvol verzonden naar {email}")
                return True
            else:
                logger.error(f"Fout bij versturen activatie e-mail: {message}")
                return False
        else:
            # Hier kun je een fallback e-mail provider toevoegen (bv. SMTP)
            logger.error("MS Graph API niet geconfigureerd en geen fallback beschikbaar")
            return False


def send_email_with_user_oauth(user, workspace_id, to_email, subject, body_html, cc=None, reply_to=None, attachments=None):
    """
    Verzend een e-mail namens de gebruiker met hun eigen OAuth token
    
    Args:
        user: User object van de afzender
        workspace_id: ID van de werkruimte
        to_email: Ontvanger e-mailadres(sen)
        subject: Onderwerp van de e-mail
        body_html: HTML inhoud van de e-mail
        cc: CC e-mailadressen (optioneel)
        reply_to: Reply-to e-mailadres (optioneel)
        attachments: Lijst met bijlagen
        
    Returns:
        Tuple met (success, message)
    """
    logger.info(f"E-mail versturen namens gebruiker {user.email} in werkruimte {workspace_id}")
    
    # Haal het OAuth token op voor deze gebruiker
    oauth_token = user.get_oauth_token(workspace_id=workspace_id)
    
    if not oauth_token:
        logger.error(f"Geen OAuth token gevonden voor gebruiker {user.email} in werkruimte {workspace_id}")
        return False, "Gebruiker heeft geen geldig OAuth token. Gelieve opnieuw in te loggen bij Microsoft."
    
    # Maak een email service met dit token
    email_service = MSGraphEmailService(user_token=oauth_token)
    
    # Verstuur de e-mail
    return email_service.send_email(
        to_email=to_email,
        subject=subject,
        body_html=body_html,
        cc=cc,
        reply_to=reply_to,
        attachments=attachments
    )


def get_microsoft_auth_url(workspace_id, redirect_uri=None):
    """
    Genereer een Microsoft OAuth authenticatie URL
    
    Args:
        workspace_id: ID van de werkruimte
        redirect_uri: URL om naar terug te keren na authenticatie
    
    Returns:
        Microsoft OAuth URL als string of None als er een fout optreedt
    """
    from flask import url_for
    from models import EmailSettings
    
    # Haal email settings op
    settings = EmailSettings.query.filter_by(workspace_id=workspace_id).first()
    if not settings:
        settings = EmailSettings.query.filter_by(workspace_id=None).first()
    
    if not settings or not settings.ms_graph_client_id:
        logger.error("Geen Microsoft OAuth configuratie beschikbaar")
        return None
    
    if not settings.allow_microsoft_oauth:
        logger.error("Microsoft OAuth is uitgeschakeld voor deze werkruimte")
        return None
    
    # Standaard scopes
    scopes = settings.oauth_scopes.split() if settings.oauth_scopes else ['mail.send']
    
    # Bouw de redirect_uri
    if not redirect_uri:
        # Gebruik de standaard callback URL
        try:
            redirect_uri = url_for('microsoft_auth_callback', workspace_id=workspace_id, _external=True)
        except RuntimeError:
            # Fallback als er geen app context is
            base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
            redirect_uri = f"{base_url}/auth/microsoft/callback/{workspace_id}"
    
    # Maak de MSAL app
    app = msal.PublicClientApplication(
        client_id=settings.ms_graph_client_id,
        authority="https://login.microsoftonline.com/common"
    )
    
    # Genereer de auth URL
    auth_url = app.get_authorization_request_url(
        scopes=scopes,
        redirect_uri=redirect_uri,
        state=workspace_id
    )
    
    return auth_url


def process_microsoft_auth_callback(code, workspace_id, redirect_uri=None):
    """
    Verwerk de callback van Microsoft OAuth en sla het token op
    
    Args:
        code: Authenticatie code van Microsoft
        workspace_id: ID van de werkruimte
        redirect_uri: Redirect URI die werd gebruikt voor de initiële aanvraag
    
    Returns:
        Tuple met (success, message, user_info)
    """
    from flask import url_for, current_app
    from models import EmailSettings, User, UserOAuthToken
    from app import db
    from flask_login import current_user
    
    if not current_user.is_authenticated:
        return False, "Gebruiker niet ingelogd", None
    
    # Haal email settings op
    settings = EmailSettings.query.filter_by(workspace_id=workspace_id).first()
    if not settings:
        settings = EmailSettings.query.filter_by(workspace_id=None).first()
    
    if not settings or not settings.ms_graph_client_id:
        return False, "Geen Microsoft OAuth configuratie beschikbaar", None
    
    # Bouw de redirect_uri
    if not redirect_uri:
        try:
            redirect_uri = url_for('microsoft_auth_callback', workspace_id=workspace_id, _external=True)
        except RuntimeError:
            base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
            redirect_uri = f"{base_url}/auth/microsoft/callback/{workspace_id}"
    
    # Configureer de MSAL app
    client_id = settings.ms_graph_client_id
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority="https://login.microsoftonline.com/common"
    )
    
    # Standaard scopes
    scopes = settings.oauth_scopes.split() if settings.oauth_scopes else ['mail.send']
    
    # Token verkrijgen met de autorisatiecode
    try:
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=scopes,
            redirect_uri=redirect_uri
        )
    except Exception as e:
        logger.error(f"Fout bij het verkrijgen van token: {str(e)}")
        return False, f"Fout bij het verkrijgen van token: {str(e)}", None
    
    # Controleer op fouten
    if "error" in result:
        error_msg = f"{result.get('error')}: {result.get('error_description')}"
        logger.error(f"OAuth fout: {error_msg}")
        return False, f"OAuth fout: {error_msg}", None
    
    # Token succesvol verkregen
    if "access_token" not in result:
        return False, "Geen toegangstoken ontvangen", None
    
    # Bepaal vervaldatum van token
    expires_in = result.get("expires_in", 3600)
    token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)  # 5 min buffer
    
    # Haal gebruikersinfo op
    user_info = get_user_info_from_microsoft(result["access_token"])
    if not user_info:
        return False, "Kon gebruikersinformatie niet ophalen", None
    
    # Zoek of maak een OAuth token record
    oauth_token = UserOAuthToken.query.filter_by(
        user_id=current_user.id,
        workspace_id=workspace_id,
        provider='microsoft'
    ).first()
    
    if not oauth_token:
        # Maak een nieuw token record
        oauth_token = UserOAuthToken(
            user_id=current_user.id,
            workspace_id=workspace_id,
            provider='microsoft'
        )
        db.session.add(oauth_token)
    
    # Update token informatie
    oauth_token.access_token = UserOAuthToken.encrypt_token(result["access_token"])
    oauth_token.refresh_token = UserOAuthToken.encrypt_token(result.get("refresh_token"))
    oauth_token.token_expiry = token_expiry
    oauth_token.email = user_info.get("email")
    oauth_token.display_name = user_info.get("name")
    oauth_token.updated_at = datetime.now()
    
    # Sla op in database
    try:
        db.session.commit()
        logger.info(f"OAuth token succesvol opgeslagen voor {user_info.get('email')}")
        return True, "Microsoft account succesvol gekoppeld", user_info
    except Exception as e:
        db.session.rollback()
        logger.error(f"Fout bij opslaan OAuth token: {str(e)}")
        return False, f"Fout bij opslaan autorisatie: {str(e)}", None


def get_user_info_from_microsoft(access_token):
    """
    Haal gebruikersinformatie op van Microsoft Graph API
    
    Args:
        access_token: Geldig access token voor Microsoft Graph API
    
    Returns:
        Dict met gebruikersinformatie of None als er een fout optreedt
    """
    graph_endpoint = 'https://graph.microsoft.com/v1.0'
    user_endpoint = f"{graph_endpoint}/me"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(user_endpoint, headers=headers)
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"Gebruikersinfo opgehaald voor {user_data.get('displayName', 'Onbekend')}")
            
            return {
                'id': user_data.get('id'),
                'email': user_data.get('userPrincipalName') or user_data.get('mail'),
                'name': user_data.get('displayName'),
                'given_name': user_data.get('givenName'),
                'surname': user_data.get('surname')
            }
        else:
            logger.error(f"Fout bij ophalen gebruikersinfo: {response.status_code}, {response.text}")
            return None
    
    except Exception as e:
        logger.error(f"Uitzondering bij ophalen gebruikersinfo: {str(e)}")
        return None