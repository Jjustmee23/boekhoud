"""
Mollie betalingsservice voor abonnementen
"""
import os
import logging
from datetime import datetime, timedelta
import json
import requests
from app import app, db
from flask import url_for
from models import MollieSettings, Payment, Workspace, Subscription

class MollieService:
    """Service voor Mollie betalingsintegratie"""
    
    def __init__(self):
        """Initialiseer de Mollie service"""
        self.api_key = os.getenv('MOLLIE_API_KEY')
        self.base_url = 'https://api.mollie.com/v2'
        self.headers = None
        self.update_headers()
    
    def update_headers(self):
        """Update headers met huidige API key"""
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def set_api_key(self, api_key):
        """Stel een nieuwe API-sleutel in"""
        self.api_key = api_key
        self.update_headers()
        
    def get_settings(self, workspace_id=None):
        """
        Haal de Mollie-instellingen op
        
        Args:
            workspace_id: Optionele workspace ID voor specifieke instellingen
            
        Returns:
            MollieSettings: De gevonden instellingen of None
        """
        if workspace_id:
            return MollieSettings.query.filter_by(workspace_id=workspace_id).first()
        else:
            return MollieSettings.query.filter_by(is_system_default=True).first()
    
    def is_configured(self, workspace_id=None):
        """
        Controleer of Mollie is geconfigureerd
        
        Args:
            workspace_id: Optionele workspace ID voor specifieke instellingen
            
        Returns:
            bool: True als geconfigureerd, anders False
        """
        settings = self.get_settings(workspace_id)
        
        if settings and settings.api_key:
            return True
        
        # Fallback naar systeem-instellingen
        return self.api_key is not None and self.api_key != ''
    
    def get_active_api_key(self, workspace_id=None):
        """
        Haal de actieve API-sleutel op, eerst uit workspace, dan uit systeem
        
        Args:
            workspace_id: Optionele workspace ID voor specifieke instellingen
            
        Returns:
            str: De API-sleutel of None
        """
        settings = self.get_settings(workspace_id)
        
        if settings and settings.api_key:
            return settings.api_key
        
        return self.api_key
    
    def create_payment(self, workspace_id, subscription_id, period='monthly'):
        """
        Maak een nieuwe betaling aan voor een abonnement
        
        Args:
            workspace_id: ID van de workspace
            subscription_id: ID van het abonnement
            period: 'monthly' of 'yearly'
            
        Returns:
            dict: Betalingsgegevens inclusief payment_url of None bij fouten
        """
        # Haal workspace en abonnement op
        workspace = Workspace.query.get(workspace_id)
        subscription = Subscription.query.get(subscription_id)
        
        if not workspace or not subscription:
            logging.error(f"Workspace of abonnement niet gevonden: workspace={workspace_id}, subscription={subscription_id}")
            return None
        
        # Bepaal bedrag op basis van periode
        amount = subscription.price_monthly if period == 'monthly' else subscription.price_yearly
        description = f"{subscription.name} abonnement ({period})"
        
        # Genereer unieke ordercode
        order_id = f"SUB-{workspace_id}-{subscription_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Controleer of Mollie is geconfigureerd
        api_key = self.get_active_api_key(workspace_id)
        if not api_key:
            logging.error("Geen Mollie API key geconfigureerd")
            return None
        
        # Stel tijdelijke API key in
        original_key = self.api_key
        self.set_api_key(api_key)
        
        try:
            # Bouw webhook en redirect URLs
            webhook_url = url_for('payment_webhook', _external=True)
            redirect_url = url_for('payment_return', _external=True)
            
            # Maak betalingsaanvraag
            payment_data = {
                'amount': {
                    'currency': 'EUR',
                    'value': f"{amount:.2f}"
                },
                'description': description,
                'redirectUrl': redirect_url,
                'webhookUrl': webhook_url,
                'metadata': {
                    'workspace_id': workspace_id,
                    'subscription_id': subscription_id,
                    'period': period,
                    'order_id': order_id
                }
            }
            
            # Verstuur aanvraag naar Mollie API
            response = requests.post(
                f"{self.base_url}/payments",
                headers=self.headers,
                json=payment_data
            )
            
            # Controleer respons
            if response.status_code == 201:
                payment_info = response.json()
                
                # Bepaal vervaldatum
                expiry_date = datetime.now() + timedelta(days=14)
                
                # Maak betaling aan in database
                payment = Payment(
                    mollie_payment_id=payment_info['id'],
                    workspace_id=workspace_id,
                    subscription_id=subscription_id,
                    amount=amount,
                    currency='EUR',
                    period=period,
                    status=payment_info['status'],
                    payment_method=payment_info.get('method'),
                    payment_url=payment_info['_links']['checkout']['href'],
                    expiry_date=expiry_date
                )
                
                db.session.add(payment)
                db.session.commit()
                
                # Geef betalingsgegevens terug
                return {
                    'payment_id': payment.id,
                    'mollie_payment_id': payment.mollie_payment_id,
                    'payment_url': payment.payment_url,
                    'status': payment.status,
                    'amount': payment.amount,
                    'currency': payment.currency
                }
            else:
                error_data = response.json() if response.content else {'message': 'Unknown error'}
                logging.error(f"Fout bij aanmaken Mollie betaling: {response.status_code} - {error_data}")
                return None
                
        except Exception as e:
            logging.error(f"Uitzondering bij aanmaken Mollie betaling: {str(e)}")
            return None
        finally:
            # Herstel originele API key
            self.set_api_key(original_key)
    
    def check_payment_status(self, mollie_payment_id, workspace_id=None):
        """
        Controleer de status van een betaling
        
        Args:
            mollie_payment_id: Mollie betalings-ID
            workspace_id: Optionele workspace ID voor specifieke instellingen
            
        Returns:
            dict: Betalingsstatus of None bij fouten
        """
        # Controleer of Mollie is geconfigureerd
        api_key = self.get_active_api_key(workspace_id)
        if not api_key:
            logging.error("Geen Mollie API key geconfigureerd")
            return None
        
        # Stel tijdelijke API key in
        original_key = self.api_key
        self.set_api_key(api_key)
        
        try:
            # Haal betalingsstatus op
            response = requests.get(
                f"{self.base_url}/payments/{mollie_payment_id}",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logging.error(f"Fout bij ophalen betalingsstatus: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Uitzondering bij ophalen betalingsstatus: {str(e)}")
            return None
        finally:
            # Herstel originele API key
            self.set_api_key(original_key)
    
    def process_payment_webhook(self, mollie_payment_id):
        """
        Verwerk een webhook-aanroep van Mollie
        
        Args:
            mollie_payment_id: Mollie betalings-ID
            
        Returns:
            bool: True als verwerking succesvol was, anders False
        """
        try:
            # Haal betaling op uit database
            payment = Payment.query.filter_by(mollie_payment_id=mollie_payment_id).first()
            
            if not payment:
                logging.error(f"Betaling niet gevonden voor Mollie ID: {mollie_payment_id}")
                return False
            
            # Controleer betalingsstatus
            payment_info = self.check_payment_status(mollie_payment_id, payment.workspace_id)
            
            if not payment_info:
                logging.error(f"Kon status niet ophalen voor betaling: {mollie_payment_id}")
                return False
            
            # Update betalingsstatus
            payment.status = payment_info['status']
            payment.payment_method = payment_info.get('method')
            
            # Als betaling succesvol is, activeer abonnement
            if payment_info['status'] == 'paid':
                # Haal workspace en abonnement op
                workspace = Workspace.query.get(payment.workspace_id)
                subscription = Subscription.query.get(payment.subscription_id)
                
                if workspace and subscription:
                    # Bereken start- en einddatum
                    start_date = datetime.now()
                    
                    # Bepaal abonnementsperiode
                    if payment.period == 'monthly':
                        end_date = start_date + timedelta(days=30)
                    else:  # yearly
                        end_date = start_date + timedelta(days=365)
                    
                    # Update workspace met nieuwe abonnement
                    workspace.subscription_id = subscription.id
                    workspace.subscription_start_date = start_date
                    workspace.subscription_end_date = end_date
                    workspace.billing_cycle = payment.period
                    
                    # Log succes
                    logging.info(f"Abonnement geactiveerd voor workspace {workspace.id}: {subscription.name}")
            
            # Sla wijzigingen op
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Fout bij verwerken betalings-webhook: {str(e)}")
            return False
    
    def get_payment_methods(self, workspace_id=None):
        """
        Haal beschikbare betaalmethoden op
        
        Args:
            workspace_id: Optionele workspace ID voor specifieke instellingen
            
        Returns:
            list: Lijst met betaalmethoden of None bij fouten
        """
        # Controleer of Mollie is geconfigureerd
        api_key = self.get_active_api_key(workspace_id)
        if not api_key:
            logging.error("Geen Mollie API key geconfigureerd")
            return None
        
        # Stel tijdelijke API key in
        original_key = self.api_key
        self.set_api_key(api_key)
        
        try:
            # Haal betaalmethoden op
            response = requests.get(
                f"{self.base_url}/methods",
                headers=self.headers
            )
            
            if response.status_code == 200:
                return response.json().get('_embedded', {}).get('methods', [])
            else:
                logging.error(f"Fout bij ophalen betaalmethoden: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Uitzondering bij ophalen betaalmethoden: {str(e)}")
            return None
        finally:
            # Herstel originele API key
            self.set_api_key(original_key)

# Globale instantie van MollieService
mollie_service = MollieService()