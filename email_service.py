import os
import json
import msal
import requests
from flask import url_for, current_app
import uuid
import logging

# Configuratie voor Microsoft Graph API
class MSGraphConfig:
    def __init__(self):
        # App registratie gegevens (zullen via omgevingsvariabelen worden ingesteld)
        self.client_id = os.environ.get('MS_GRAPH_CLIENT_ID')
        self.client_secret = os.environ.get('MS_GRAPH_CLIENT_SECRET')
        self.tenant_id = os.environ.get('MS_GRAPH_TENANT_ID')
        self.authority = f'https://login.microsoftonline.com/{self.tenant_id}'
        self.scope = ['https://graph.microsoft.com/.default']
        self.sender_email = os.environ.get('MS_GRAPH_SENDER_EMAIL')
        
    def is_configured(self):
        """Controleer of alle vereiste configuratiewaarden zijn ingesteld"""
        return all([
            self.client_id, self.client_secret, self.tenant_id, 
            self.authority, self.scope, self.sender_email
        ])

# Service voor het verzenden van e-mails via Microsoft Graph API
class EmailService:
    def __init__(self):
        self.config = MSGraphConfig()
        self.logger = logging.getLogger(__name__)
        
    def get_token(self):
        """Verkrijg een toegangstoken van Microsoft Identity Platform"""
        if not self.config.is_configured():
            self.logger.error("Microsoft Graph API is niet geconfigureerd.")
            return None
            
        app = msal.ConfidentialClientApplication(
            self.config.client_id,
            authority=self.config.authority,
            client_credential=self.config.client_secret,
        )
        
        result = app.acquire_token_for_client(scopes=self.config.scope)
        
        if "access_token" in result:
            return result["access_token"]
        else:
            self.logger.error(f"Error bij het verkrijgen van toegangstoken: {result.get('error')}")
            self.logger.error(f"Beschrijving: {result.get('error_description')}")
            return None

    def send_email(self, recipient_email, subject, body_html, cc=None, attachments=None):
        """Verzend een e-mail via Microsoft Graph API"""
        if not self.config.is_configured():
            self.logger.error("Microsoft Graph API is niet geconfigureerd.")
            return False
            
        access_token = self.get_token()
        if not access_token:
            return False
            
        # Microsoft Graph API endpoint voor het verzenden van e-mail
        endpoint = 'https://graph.microsoft.com/v1.0/users/' + self.config.sender_email + '/sendMail'
        
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
                self.logger.info(f"E-mail succesvol verzonden naar {recipient_email}")
                return True
            else:
                self.logger.error(f"Error bij het verzenden van e-mail: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Exception bij het verzenden van e-mail: {str(e)}")
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

# Singleton instantie
email_service = EmailService()