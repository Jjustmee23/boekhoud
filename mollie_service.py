"""
Mollie betalingsservice voor integratie met Mollie API
"""
import os
import logging
from mollie.api.client import Client
from mollie.api.error import Error as MollieError
from app import app, db
from models import MollieSettings, Payment, Workspace, Subscription

class MollieService:
    """
    Service klasse voor interactie met Mollie API
    
    Deze service biedt methoden voor het verwerken van betalingen,
    verificatie van betalingsstatus en webhooks voor Mollie.
    """
    
    def __init__(self):
        """Initialiseer de Mollie service"""
        self.mollie_client = None
        self.settings = None
        # Initialisatie wordt uitgevoerd bij het eerste gebruik
    
    def _initialize(self):
        """
        Initialiseer de Mollie client met instellingen uit de database
        """
        # Dit moet worden uitgevoerd binnen een app context
        with app.app_context():
            # Haal instellingen op uit de database
            self.settings = MollieSettings.query.first()
            
            if not self.settings:
                # Maak standaard instellingen aan als ze nog niet bestaan
                self.settings = MollieSettings(
                    api_key_test=os.environ.get('MOLLIE_TEST_API_KEY', ''),
                    api_key_live=os.environ.get('MOLLIE_LIVE_API_KEY', ''),
                    is_test_mode=True,
                    webhook_url=os.environ.get('MOLLIE_WEBHOOK_URL', ''),
                    redirect_url=os.environ.get('MOLLIE_REDIRECT_URL', '')
                )
                db.session.add(self.settings)
                db.session.commit()
        
        # Initialiseer Mollie client
        try:
            self.mollie_client = Client()
            api_key = self.settings.get_active_api_key()
            if api_key:
                self.mollie_client.set_api_key(api_key)
            else:
                logging.warning("Geen Mollie API key geconfigureerd")
        except Exception as e:
            logging.error(f"Fout bij initialiseren Mollie client: {str(e)}")
            self.mollie_client = None
    
    def is_configured(self):
        """
        Controleer of de Mollie service correct is geconfigureerd
        
        Returns:
            bool: True als de service correct is geconfigureerd, anders False
        """
        # Zorg ervoor dat initialisatie is uitgevoerd
        if self.mollie_client is None:
            self._initialize()
        
        if not self.mollie_client:
            return False
        
        # Controleer of er een actieve API key is ingesteld
        if self.settings is None:
            return False
            
        api_key = self.settings.get_active_api_key()
        if not api_key:
            return False
        
        return True
    
    def update_settings(self, api_key_test=None, api_key_live=None, 
                        is_test_mode=None, webhook_url=None, redirect_url=None):
        """
        Update de Mollie instellingen
        
        Args:
            api_key_test: Test API key
            api_key_live: Live API key
            is_test_mode: Boolean voor test mode
            webhook_url: URL voor Mollie webhooks
            redirect_url: URL voor redirect na betaling
            
        Returns:
            bool: True als de update succesvol was, anders False
        """
        # Zorg ervoor dat initialisatie is uitgevoerd
        if self.settings is None:
            self._initialize()
            
        with app.app_context():
            try:
                if api_key_test is not None:
                    self.settings.api_key_test = api_key_test
                
                if api_key_live is not None:
                    self.settings.api_key_live = api_key_live
                
                if is_test_mode is not None:
                    self.settings.is_test_mode = is_test_mode
                
                if webhook_url is not None:
                    self.settings.webhook_url = webhook_url
                
                if redirect_url is not None:
                    self.settings.redirect_url = redirect_url
                
                db.session.commit()
                
                # Herinitialiseer de client met nieuwe instellingen
                self._initialize()
                
                return True
            except Exception as e:
                logging.error(f"Fout bij updaten Mollie instellingen: {str(e)}")
                db.session.rollback()
                return False
    
    def create_payment(self, workspace_id, subscription_id, period):
        """
        Maak een nieuwe betaling aan
        
        Args:
            workspace_id: ID van de werkruimte
            subscription_id: ID van het abonnement
            period: 'monthly' of 'yearly'
            
        Returns:
            dict: Betalingsgegevens inclusief betaal-URL of None bij fouten
        """
        if not self.is_configured():
            logging.error("Mollie service is niet correct geconfigureerd")
            return None
        
        with app.app_context():
            try:
                # Haal workspace en subscription op
                workspace = Workspace.query.get(workspace_id)
                subscription = Subscription.query.get(subscription_id)
                
                if not workspace or not subscription:
                    logging.error(f"Workspace of subscription niet gevonden: {workspace_id}, {subscription_id}")
                    return None
                
                # Bepaal het te betalen bedrag
                amount = subscription.price_monthly if period == 'monthly' else subscription.price_yearly
                
                # Voeg kosten voor extra gebruikers toe
                if workspace.extra_users > 0:
                    if period == 'monthly':
                        amount += workspace.extra_users * subscription.price_per_extra_user
                    else:
                        amount += workspace.extra_users * subscription.price_per_extra_user * 12
                
                # Genereer beschrijving
                description = f"{subscription.name} abonnement ({period}) - {workspace.name}"
                
                # Maak de betaling aan in Mollie
                mollie_payment = self.mollie_client.payments.create({
                    'amount': {
                        'currency': 'EUR',
                        'value': f"{amount:.2f}"
                    },
                    'description': description,
                    'redirectUrl': self.settings.redirect_url,
                    'webhookUrl': self.settings.webhook_url,
                    'metadata': {
                        'workspace_id': workspace_id,
                        'subscription_id': subscription_id,
                        'period': period
                    }
                })
                
                # Sla betaling op in database
                payment = Payment(
                    mollie_payment_id=mollie_payment.id,
                    workspace_id=workspace_id,
                    subscription_id=subscription_id,
                    amount=amount,
                    period=period,
                    status=mollie_payment.status,
                    payment_url=mollie_payment.checkout_url,
                    payment_method=mollie_payment.method if hasattr(mollie_payment, 'method') else None
                )
                db.session.add(payment)
                db.session.commit()
                
                return {
                    'payment_id': payment.id,
                    'mollie_payment_id': payment.mollie_payment_id,
                    'amount': payment.amount,
                    'status': payment.status,
                    'payment_url': payment.payment_url
                }
            
            except MollieError as e:
                logging.error(f"Mollie API fout: {str(e)}")
                return None
            except Exception as e:
                logging.error(f"Fout bij aanmaken betaling: {str(e)}")
                db.session.rollback()
                return None
    
    def check_payment_status(self, payment_id):
        """
        Controleer de status van een betaling
        
        Args:
            payment_id: ID van de betaling in onze database
            
        Returns:
            dict: Statusgegevens van de betaling of None bij fouten
        """
        if not self.is_configured():
            logging.error("Mollie service is niet correct geconfigureerd")
            return None
        
        with app.app_context():
            try:
                # Haal betaling op uit database
                payment = Payment.query.get(payment_id)
                if not payment:
                    logging.error(f"Betaling niet gevonden: {payment_id}")
                    return None
                
                # Haal betaling op uit Mollie API
                mollie_payment = self.mollie_client.payments.get(payment.mollie_payment_id)
                
                # Update status in database
                payment.status = mollie_payment.status
                db.session.commit()
                
                return {
                    'payment_id': payment.id,
                    'mollie_payment_id': payment.mollie_payment_id,
                    'status': payment.status,
                    'is_paid': mollie_payment.is_paid()
                }
            
            except MollieError as e:
                logging.error(f"Mollie API fout: {str(e)}")
                return None
            except Exception as e:
                logging.error(f"Fout bij controleren betaling: {str(e)}")
                return None
    
    def process_webhook(self, mollie_payment_id):
        """
        Verwerk een webhook van Mollie
        
        Args:
            mollie_payment_id: Mollie betaling ID uit de webhook
            
        Returns:
            bool: True als verwerking succesvol was, anders False
        """
        if not self.is_configured():
            logging.error("Mollie service is niet correct geconfigureerd")
            return False
        
        with app.app_context():
            try:
                # Haal de betaling op uit Mollie API
                mollie_payment = self.mollie_client.payments.get(mollie_payment_id)
                
                # Zoek de bijbehorende betaling in onze database
                payment = Payment.query.filter_by(mollie_payment_id=mollie_payment_id).first()
                if not payment:
                    logging.error(f"Betaling niet gevonden voor Mollie ID: {mollie_payment_id}")
                    return False
                
                # Update status
                payment.status = mollie_payment.status
                
                # Als de betaling is voltooid, werk dan het abonnement bij
                if mollie_payment.is_paid():
                    workspace = Workspace.query.get(payment.workspace_id)
                    if workspace:
                        # Update abonnement
                        workspace.subscription_id = payment.subscription_id
                        
                        # Bepaal abonnementsduur
                        from datetime import datetime, timedelta
                        now = datetime.now()
                        
                        # Start datum is nu
                        workspace.subscription_start_date = now
                        
                        # Bepaal einddatum op basis van periode
                        if payment.period == 'monthly':
                            workspace.subscription_end_date = now + timedelta(days=30)
                            workspace.billing_cycle = 'monthly'
                        else:
                            workspace.subscription_end_date = now + timedelta(days=365)
                            workspace.billing_cycle = 'yearly'
                
                db.session.commit()
                return True
            
            except MollieError as e:
                logging.error(f"Mollie API fout: {str(e)}")
                return False
            except Exception as e:
                logging.error(f"Fout bij verwerken webhook: {str(e)}")
                db.session.rollback()
                return False
    
    def cancel_subscription(self, workspace_id):
        """
        Annuleer een abonnement
        
        Args:
            workspace_id: ID van de werkruimte
            
        Returns:
            bool: True als annulering succesvol was, anders False
        """
        with app.app_context():
            try:
                workspace = Workspace.query.get(workspace_id)
                if not workspace:
                    logging.error(f"Werkruimte niet gevonden: {workspace_id}")
                    return False
                
                # Reset abonnementsinformatie
                workspace.subscription_id = None
                workspace.subscription_start_date = None
                workspace.subscription_end_date = None
                
                db.session.commit()
                return True
            except Exception as e:
                logging.error(f"Fout bij annuleren abonnement: {str(e)}")
                db.session.rollback()
                return False

# Globale mollie service instantie
mollie_service = MollieService()