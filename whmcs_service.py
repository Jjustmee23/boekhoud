"""
WHMCS API Service voor integratie met de applicatie
Zorgt voor synchronisatie van klanten en facturen tussen WHMCS en de applicatie
"""
import os
import time
import uuid
import json
import hashlib
import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import current_app
from models import Customer, Invoice, InvoiceItem, SystemSettings
from database import db

class WHMCSService:
    """Service voor communicatie met de WHMCS API"""
    
    # Singleton instantie voor hergebruik
    _instance = None
    
    def __new__(cls):
        """Implementeer singleton patroon om één instantie te hergebruiken"""
        if cls._instance is None:
            cls._instance = super(WHMCSService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialiseer de WHMCS API-service met configuratie uit environment variabelen of de database"""
        # Voorkom dubbele initialisatie door singleton patroon
        if getattr(self, '_initialized', False):
            return
            
        # Stel logger in
        self.logger = logging.getLogger(__name__)
        
        # Probeer eerst uit environment variabelen
        self.api_url = os.environ.get('WHMCS_API_URL')
        self.api_identifier = os.environ.get('WHMCS_API_IDENTIFIER')
        self.api_secret = os.environ.get('WHMCS_API_SECRET')
        
        # Markeer als geïnitialiseerd
        self._initialized = True
        
        self.logger.info(f"Env WHMCS_API_URL: {self.api_url}")
        self.logger.info(f"Env WHMCS_API_IDENTIFIER: {self.api_identifier}")
        self.logger.info(f"Env WHMCS_API_SECRET set: {bool(self.api_secret)}")
        
        # Als niet in environment, probeer database
        if not self.is_configured():
            settings = SystemSettings.query.filter_by(key='whmcs_integration').first()
            if settings:
                self.logger.info(f"DB whmcs_api_url: {settings.whmcs_api_url}")
                self.logger.info(f"DB whmcs_api_identifier: {settings.whmcs_api_identifier}")
                self.logger.info(f"DB whmcs_api_secret set: {bool(settings.whmcs_api_secret)}")
                
                self.api_url = settings.whmcs_api_url
                self.api_identifier = settings.whmcs_api_identifier
                self.api_secret = settings.whmcs_api_secret

    def is_configured(self) -> bool:
        """Controleer of de API-gegevens zijn geconfigureerd"""
        return bool(self.api_url and self.api_identifier and self.api_secret)
        
    def save_whmcs_settings(self, api_url: str, api_identifier: str, api_secret: str, auto_sync: bool = False) -> bool:
        """
        Sla de WHMCS API-instellingen op in de database
        
        Args:
            api_url: De URL naar de WHMCS API
            api_identifier: De API identifier
            api_secret: Het API secret
            auto_sync: Of automatische synchronisatie moet worden ingeschakeld
            
        Returns:
            bool: True als het opslaan is gelukt, anders False
        """
        try:
            # Haal de bestaande instellingen op of maak een nieuwe aan
            settings = SystemSettings.query.filter_by(key='whmcs_integration').first()
            if not settings:
                settings = SystemSettings(key='whmcs_integration', value=json.dumps({}))
                db.session.add(settings)
            
            # Update de instellingen
            settings.whmcs_api_url = api_url
            settings.whmcs_api_identifier = api_identifier
            settings.whmcs_api_secret = api_secret
            settings.whmcs_auto_sync = auto_sync
            settings.whmcs_last_sync = None  # Reset laatste sync timestamp
            
            # Update ook de huidige instantie
            self.api_url = api_url
            self.api_identifier = api_identifier
            self.api_secret = api_secret
            
            db.session.commit()
            self.logger.info("WHMCS settings saved successfully")
            return True
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error saving WHMCS settings: {str(e)}")
            return False

    def _make_api_request(self, action: str, params: Dict = None) -> Dict:
        """
        Maak een verzoek naar de WHMCS API
        
        Args:
            action: De API-actie die moet worden uitgevoerd
            params: Aanvullende parameters voor het verzoek
        
        Returns:
            Dict: De API-respons als dictionary
        """
        if not self.is_configured():
            self.logger.error("WHMCS API niet geconfigureerd")
            return {"result": "error", "message": "WHMCS API niet geconfigureerd"}
        
        # Basis parameters
        request_params = {
            'action': action,
            'identifier': self.api_identifier,
            'secret': self.api_secret,
            'responsetype': 'json',
        }
        
        # Voeg eventuele extra parameters toe
        if params:
            request_params.update(params)
        
        try:
            # Log de API URL voor debugging
            self.logger.info(f"Making WHMCS API request to URL: {self.api_url}")
            # Maak API-verzoek
            response = requests.post(self.api_url, data=request_params, timeout=30)
            response.raise_for_status()  # Raising an exception for 4XX/5XX responses
            
            # Parse JSON-respons
            result = response.json()
            
            # Log resultaat (zonder gevoelige gegevens)
            censored_result = dict(result)
            if 'clients' in censored_result and isinstance(censored_result['clients'], list):
                censored_result['clients'] = f"[{len(censored_result['clients'])} clients]"
            if 'invoices' in censored_result and isinstance(censored_result['invoices'], list):
                censored_result['invoices'] = f"[{len(censored_result['invoices'])} invoices]"
            
            self.logger.debug(f"WHMCS API response for {action}: {json.dumps(censored_result)[:500]}...")
            
            return result
        except requests.RequestException as e:
            self.logger.error(f"WHMCS API request error: {str(e)}")
            return {"result": "error", "message": f"Request error: {str(e)}"}
        except json.JSONDecodeError:
            self.logger.error("Invalid JSON response from WHMCS API")
            return {"result": "error", "message": "Invalid JSON response"}
        except Exception as e:
            self.logger.error(f"Unexpected error in WHMCS API request: {str(e)}")
            return {"result": "error", "message": f"Unexpected error: {str(e)}"}

    def get_clients(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        Haal klanten op uit WHMCS
        
        Args:
            limit: Maximum aantal klanten om op te halen
            offset: Vanaf welke positie klanten op te halen
        
        Returns:
            List[Dict]: Lijst van klantgegevens
        """
        params = {
            'limitstart': offset,
            'limitnum': limit,
        }
        
        result = self._make_api_request('GetClients', params)
        
        if result.get('result') == 'success' and 'clients' in result:
            return result['clients']['client']
        
        self.logger.warning(f"Failed to get clients from WHMCS: {result.get('message', 'Unknown error')}")
        return []

    def get_client(self, client_id: int = None, email: str = None) -> Optional[Dict]:
        """
        Haal een specifieke klant op basis van ID of e-mail
        
        Args:
            client_id: WHMCS klant ID
            email: E-mailadres van de klant
        
        Returns:
            Dict: Klantgegevens of None als niet gevonden
        """
        params = {}
        if client_id:
            params['clientid'] = client_id
        elif email:
            params['email'] = email
        else:
            self.logger.error("Client ID or email is required")
            return None
        
        result = self._make_api_request('GetClientsDetails', params)
        
        if result.get('result') == 'success':
            return result['client'] if 'client' in result else result
        
        # Log waarschuwing maar geen error, omdat zoeken op niet-bestaande klant normaal is
        if result.get('message') != 'Client ID Not Found':
            self.logger.warning(f"Failed to get client details from WHMCS: {result.get('message', 'Unknown error')}")
        
        return None

    def get_invoices(self, client_id: int = None, status: str = None, limit: int = 100) -> List[Dict]:
        """
        Haal facturen op uit WHMCS
        
        Args:
            client_id: Filter op WHMCS klant ID (optioneel)
            status: Filter op factuurstatus (optioneel)
            limit: Maximum aantal facturen om op te halen
        
        Returns:
            List[Dict]: Lijst van factuurgegevens
        """
        params = {'limitnum': limit}
        
        if client_id:
            params['userid'] = client_id
        
        if status:
            params['status'] = status
        
        result = self._make_api_request('GetInvoices', params)
        
        if result.get('result') == 'success' and 'invoices' in result and 'invoice' in result['invoices']:
            # Als er maar één factuur is, krijgen we een dict terug in plaats van een lijst
            invoices = result['invoices']['invoice']
            if isinstance(invoices, dict):
                return [invoices]
            return invoices
        
        self.logger.warning(f"Failed to get invoices from WHMCS: {result.get('message', 'Unknown error')}")
        return []

    def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        """
        Haal een specifieke factuur op
        
        Args:
            invoice_id: WHMCS factuur ID
        
        Returns:
            Dict: Factuurgegevens of None als niet gevonden
        """
        params = {'invoiceid': invoice_id}
        
        result = self._make_api_request('GetInvoice', params)
        
        if result.get('result') == 'success':
            return result
        
        # Log waarschuwing maar geen error, omdat zoeken op niet-bestaande factuur normaal is
        if result.get('message') != 'Invoice ID Not Found':
            self.logger.warning(f"Failed to get invoice from WHMCS: {result.get('message', 'Unknown error')}")
        
        return None

    def sync_clients_to_app(self, workspace_id: int) -> Dict:
        """
        Synchroniseer klanten van WHMCS naar de applicatie
        
        Args:
            workspace_id: ID van de werkruimte waaraan de klanten moeten worden toegevoegd
        
        Returns:
            Dict: Resultaten van de synchronisatie
        """
        self.logger.info(f"Starting client sync from WHMCS to app for workspace {workspace_id}")
        
        # Statistieken bijhouden
        stats = {
            'added': 0,
            'updated': 0,
            'failed': 0,
            'total': 0
        }
        
        # Ophalen van alle actieve klanten van WHMCS
        whmcs_clients = self.get_clients(limit=500)  # Een hoger limiet voor bulksynchronisatie
        stats['total'] = len(whmcs_clients)
        
        for client_data in whmcs_clients:
            try:
                whmcs_client_id = int(client_data.get('id'))
                
                # Controleer of de klant al bestaat in de app
                existing_customer = Customer.query.filter_by(
                    whmcs_client_id=whmcs_client_id,
                    workspace_id=workspace_id
                ).first()
                
                if existing_customer:
                    # Update bestaande klant
                    self._update_customer_from_whmcs(existing_customer, client_data)
                    stats['updated'] += 1
                    self.logger.debug(f"Updated customer from WHMCS: {existing_customer.id} (WHMCS ID: {whmcs_client_id})")
                else:
                    # Maak nieuwe klant aan
                    new_customer = self._create_customer_from_whmcs(client_data, workspace_id)
                    if new_customer:
                        stats['added'] += 1
                        self.logger.debug(f"Added new customer from WHMCS: {new_customer.id} (WHMCS ID: {whmcs_client_id})")
                    else:
                        stats['failed'] += 1
                        self.logger.warning(f"Failed to create customer from WHMCS ID: {whmcs_client_id}")
            except Exception as e:
                stats['failed'] += 1
                self.logger.error(f"Error syncing WHMCS client: {str(e)}")
        
        # Aanpassen van het tijdstempel van de laatste synchronisatie
        # (Dit zal later worden gedaan in de controller)
        
        self.logger.info(f"Completed WHMCS client sync: {stats}")
        return stats

    def _create_customer_from_whmcs(self, client_data: Dict, workspace_id: int) -> Optional[Customer]:
        """Maak een nieuwe klant aan op basis van WHMCS-klantgegevens"""
        try:
            # Extract en map klantgegevens
            company = client_data.get('companyname', '').strip()
            customer_type = 'business' if company else 'individual'
            
            # Als er geen bedrijfsnaam is, gebruik de volledige naam als bedrijfsnaam
            # Dit is nodig omdat company_name een verplicht veld is in ons model
            if not company:
                company = f"{client_data.get('firstname', '')} {client_data.get('lastname', '')}".strip()
                # Als er nog steeds geen naam is, gebruik een standaard
                if not company:
                    company = "Client zonder naam"
            
            # Maak nieuw klantobject
            customer = Customer(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                company_name=company,
                vat_number=client_data.get('tax_id', ''),
                first_name=client_data.get('firstname', ''),
                last_name=client_data.get('lastname', ''),
                email=client_data.get('email', ''),
                phone=client_data.get('phonenumber', ''),
                street=client_data.get('address1', ''),
                house_number='',  # WHMCS slaat huisnummer niet apart op
                postal_code=client_data.get('postcode', ''),
                city=client_data.get('city', ''),
                country=client_data.get('country', 'België'),
                customer_type=customer_type,
                default_vat_rate=21.0,  # Standaard Belgisch tarief
                created_at=datetime.now(),
                whmcs_client_id=int(client_data.get('id')),
                synced_from_whmcs=True,
                whmcs_last_sync=datetime.now()
            )
            
            # Sla op in database
            db.session.add(customer)
            db.session.commit()
            return customer
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error creating customer from WHMCS data: {str(e)}")
            return None

    def _update_customer_from_whmcs(self, customer: Customer, client_data: Dict) -> bool:
        """Update een bestaande klant met WHMCS-klantgegevens"""
        try:
            # Extract en map klantgegevens
            company = client_data.get('companyname', '').strip()
            customer_type = 'business' if company else 'individual'
            
            # Als er geen bedrijfsnaam is, gebruik de volledige naam als bedrijfsnaam
            if not company:
                company = f"{client_data.get('firstname', '')} {client_data.get('lastname', '')}".strip()
                # Als er nog steeds geen naam is, gebruik een standaard
                if not company:
                    company = "Client zonder naam"
            
            # Update klantgegevens
            customer.company_name = company
            customer.vat_number = client_data.get('tax_id', '')
            customer.first_name = client_data.get('firstname', '')
            customer.last_name = client_data.get('lastname', '')
            customer.email = client_data.get('email', '')
            customer.phone = client_data.get('phonenumber', '')
            customer.street = client_data.get('address1', '')
            # house_number blijft onveranderd omdat WHMCS dit niet apart opslaat
            customer.postal_code = client_data.get('postcode', '')
            customer.city = client_data.get('city', '')
            customer.country = client_data.get('country', 'België')
            customer.customer_type = customer_type
            customer.whmcs_last_sync = datetime.now()
            
            # Sla op in database
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error updating customer from WHMCS data: {str(e)}")
            return False

    def sync_invoices_to_app(self, workspace_id: int, status: str = None) -> Dict:
        """
        Synchroniseer facturen van WHMCS naar de applicatie
        
        Args:
            workspace_id: ID van de werkruimte waaraan de facturen moeten worden toegevoegd
            status: Filter op factuurstatus (optioneel)
        
        Returns:
            Dict: Resultaten van de synchronisatie
        """
        self.logger.info(f"Starting invoice sync from WHMCS to app for workspace {workspace_id}")
        
        # Statistieken bijhouden
        stats = {
            'added': 0,
            'updated': 0,
            'failed': 0,
            'no_customer': 0,
            'total': 0
        }
        
        # Ophalen van facturen van WHMCS
        # Als er geen status is opgegeven, halen we alle facturen op
        whmcs_invoices = self.get_invoices(status=status, limit=500)  # Een hoger limiet voor bulksynchronisatie
        stats['total'] = len(whmcs_invoices)
        
        for invoice_data in whmcs_invoices:
            try:
                whmcs_invoice_id = int(invoice_data.get('id'))
                whmcs_client_id = int(invoice_data.get('userid'))
                
                # Haal de klant op uit de app op basis van WHMCS-klant-ID
                customer = Customer.query.filter_by(
                    whmcs_client_id=whmcs_client_id,
                    workspace_id=workspace_id
                ).first()
                
                if not customer:
                    # Als de klant niet bestaat, slaan we de factuur over
                    stats['no_customer'] += 1
                    self.logger.warning(f"Customer not found for WHMCS invoice {whmcs_invoice_id} (WHMCS client ID: {whmcs_client_id})")
                    continue
                
                # Controleer of de factuur al bestaat in de app
                existing_invoice = Invoice.query.filter_by(
                    whmcs_invoice_id=whmcs_invoice_id,
                    workspace_id=workspace_id
                ).first()
                
                # Haal gedetailleerde factuurgegevens op uit WHMCS
                detailed_invoice = self.get_invoice(whmcs_invoice_id)
                
                if existing_invoice:
                    # Update bestaande factuur
                    self._update_invoice_from_whmcs(existing_invoice, invoice_data, detailed_invoice)
                    stats['updated'] += 1
                    self.logger.debug(f"Updated invoice from WHMCS: {existing_invoice.id} (WHMCS ID: {whmcs_invoice_id})")
                else:
                    # Maak nieuwe factuur aan
                    new_invoice = self._create_invoice_from_whmcs(invoice_data, detailed_invoice, customer, workspace_id)
                    if new_invoice:
                        stats['added'] += 1
                        self.logger.debug(f"Added new invoice from WHMCS: {new_invoice.id} (WHMCS ID: {whmcs_invoice_id})")
                    else:
                        stats['failed'] += 1
                        self.logger.warning(f"Failed to create invoice from WHMCS ID: {whmcs_invoice_id}")
            except Exception as e:
                stats['failed'] += 1
                self.logger.error(f"Error syncing WHMCS invoice: {str(e)}")
        
        self.logger.info(f"Completed WHMCS invoice sync: {stats}")
        return stats

    def _create_invoice_from_whmcs(self, invoice_data: Dict, detailed_invoice: Dict, customer: Customer, workspace_id: int) -> Optional[Invoice]:
        """Maak een nieuwe factuur aan op basis van WHMCS-factuurgegevens"""
        try:
            # Parse datums
            date_created = None
            date_due = None
            try:
                date_created = datetime.strptime(invoice_data.get('date'), '%Y-%m-%d')
                date_due = datetime.strptime(invoice_data.get('duedate'), '%Y-%m-%d')
            except (ValueError, TypeError):
                # Gebruik huidige datum als fallback
                date_created = datetime.now()
                date_due = datetime.now()
            
            # Converteer WHMCS-status naar app-status
            status = self._map_whmcs_status_to_app(invoice_data.get('status'))
            
            # Bereken BTW-bedragen
            amount_incl_vat = float(invoice_data.get('total', 0))
            vat_rate = 21.0  # Standaard Belgisch tarief
            
            # WHMCS slaat bedragen op inclusief BTW
            # We berekenen het bedrag exclusief BTW en het BTW-bedrag
            amount_excl_vat = amount_incl_vat / (1 + (vat_rate / 100))
            vat_amount = amount_incl_vat - amount_excl_vat
            
            # Maak nieuw factuurobject
            invoice = Invoice(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                customer_id=customer.id,
                invoice_number=f"WHMCS-{invoice_data.get('invoicenum', invoice_data.get('id'))}",
                date=date_created.date(),
                due_date=date_due.date(),
                invoice_type='income',  # Alle WHMCS-facturen zijn inkomsten
                amount_excl_vat=amount_excl_vat,
                amount_incl_vat=amount_incl_vat,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                status=status,
                notes=invoice_data.get('notes', ''),
                created_at=datetime.now(),
                whmcs_invoice_id=int(invoice_data.get('id')),
                synced_from_whmcs=True,
                whmcs_last_sync=datetime.now()
            )
            
            # Sla op in database
            db.session.add(invoice)
            db.session.commit()
            
            # Maak factuuritems aan als gedetailleerde factuurgegevens beschikbaar zijn
            if detailed_invoice and 'items' in detailed_invoice and 'item' in detailed_invoice['items']:
                self._create_invoice_items_from_whmcs(invoice, detailed_invoice['items']['item'])
            
            return invoice
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error creating invoice from WHMCS data: {str(e)}")
            return None

    def _update_invoice_from_whmcs(self, invoice: Invoice, invoice_data: Dict, detailed_invoice: Dict) -> bool:
        """Update een bestaande factuur met WHMCS-factuurgegevens"""
        try:
            # Parse datums
            date_created = None
            date_due = None
            try:
                date_created = datetime.strptime(invoice_data.get('date'), '%Y-%m-%d')
                date_due = datetime.strptime(invoice_data.get('duedate'), '%Y-%m-%d')
            except (ValueError, TypeError):
                # Gebruik huidige datums als fallback
                date_created = invoice.date or datetime.now()
                date_due = invoice.due_date or datetime.now()
            
            # Converteer WHMCS-status naar app-status
            status = self._map_whmcs_status_to_app(invoice_data.get('status'))
            
            # Bereken BTW-bedragen
            amount_incl_vat = float(invoice_data.get('total', 0))
            vat_rate = 21.0  # Standaard Belgisch tarief
            
            # WHMCS slaat bedragen op inclusief BTW
            # We berekenen het bedrag exclusief BTW en het BTW-bedrag
            amount_excl_vat = amount_incl_vat / (1 + (vat_rate / 100))
            vat_amount = amount_incl_vat - amount_excl_vat
            
            # Update factuurgegevens
            invoice.date = date_created.date()
            invoice.due_date = date_due.date()
            invoice.amount_excl_vat = amount_excl_vat
            invoice.amount_incl_vat = amount_incl_vat
            invoice.vat_rate = vat_rate
            invoice.vat_amount = vat_amount
            invoice.status = status
            invoice.notes = invoice_data.get('notes', '')
            invoice.whmcs_last_sync = datetime.now()
            
            # Sla op in database
            db.session.commit()
            
            # Update factuuritems als gedetailleerde factuurgegevens beschikbaar zijn
            if detailed_invoice and 'items' in detailed_invoice and 'item' in detailed_invoice['items']:
                # Verwijder bestaande items en maak nieuwe aan
                InvoiceItem.query.filter_by(invoice_id=invoice.id).delete()
                self._create_invoice_items_from_whmcs(invoice, detailed_invoice['items']['item'])
            
            return True
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Error updating invoice from WHMCS data: {str(e)}")
            return False

    def _create_invoice_items_from_whmcs(self, invoice: Invoice, items_data: List[Dict]) -> None:
        """Maak factuuritems aan op basis van WHMCS-factuuritemgegevens"""
        # Normaliseer naar een lijst als het een enkele item is
        if isinstance(items_data, dict):
            items_data = [items_data]
        
        for item_data in items_data:
            try:
                description = item_data.get('description', '')
                amount = float(item_data.get('amount', 0))
                
                # WHMCS houdt geen aparte hoeveelheid bij, we gaan uit van 1
                quantity = 1.0
                
                # WHMCS slaat bedragen op inclusief BTW
                # We berekenen de eenheidsprijs exclusief BTW
                vat_rate = 21.0  # Standaard Belgisch tarief
                unit_price = amount / (1 + (vat_rate / 100))
                
                # Maak nieuw factuuritem aan
                invoice_item = InvoiceItem(
                    id=uuid.uuid4(),
                    invoice_id=invoice.id,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    vat_rate=vat_rate,
                    created_at=datetime.now()
                )
                
                db.session.add(invoice_item)
            except Exception as e:
                self.logger.error(f"Error creating invoice item from WHMCS data: {str(e)}")
        
        db.session.commit()

    def _map_whmcs_status_to_app(self, whmcs_status: str) -> str:
        """
        Converteer WHMCS-factuurstatus naar de applicatie-status
        
        Args:
            whmcs_status: WHMCS-factuurstatus
        
        Returns:
            str: Applicatie-factuurstatus
        """
        # WHMCS-statussen: Draft, Unpaid, Paid, Cancelled, Refunded, Collections, Payment Pending
        # App-statussen: processed, unprocessed, paid, overdue, cancelled
        
        status_map = {
            'Draft': 'unprocessed',
            'Unpaid': 'processed',
            'Paid': 'paid',
            'Cancelled': 'cancelled',
            'Refunded': 'cancelled',
            'Collections': 'overdue',
            'Payment Pending': 'processed'
        }
        
        return status_map.get(whmcs_status, 'processed')