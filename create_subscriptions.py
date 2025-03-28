"""
Script voor het aanmaken van standaard abonnementen
Dit script initialiseert realistische abonnementen voor het facturatie systeem.

Uitvoeren met: python create_subscriptions.py
"""
import os
import json
import logging
from datetime import datetime
from app import app, db
from models import Subscription

def create_default_subscriptions():
    """Maak standaard abonnementen aan voor het systeem"""
    
    # Controleer of er al abonnementen bestaan
    existing_subscriptions = Subscription.query.count()
    if existing_subscriptions > 0:
        print("Er bestaan al abonnementen. Script wordt beëindigd om dubbele aanmaak te voorkomen.")
        return False
    
    # Abonnementen definities
    subscriptions = [
        # Starter abonnement - Ideaal voor ZZP'ers en kleine ondernemingen
        {
            "name": "Starter",
            "description": "Ideaal voor ZZP'ers en startende ondernemingen. 1 gebruiker en tot 50 facturen per maand.",
            "price_monthly": 9.95,
            "price_yearly": 99.00,    # ~17% korting bij jaarlijkse betaling
            "max_users": 1,
            "max_invoices_per_month": 50,
            "price_per_extra_user": 5.00,
            "features": {
                "facturen": True,
                "klantenbeheer": True,
                "basis_rapporten": True,
                "documentverwerking": False,
                "email_integratie": False,
                "api_toegang": False,
                "prioriteit_support": False,
                "eerste_maand_gratis": True
            }
        },
        
        # Groei abonnement - Voor groeiende bedrijven
        {
            "name": "Groei",
            "description": "Voor groeiende bedrijven. 3 gebruikers en tot 150 facturen per maand.",
            "price_monthly": 24.95,
            "price_yearly": 249.00,   # ~17% korting
            "max_users": 3,
            "max_invoices_per_month": 150,
            "price_per_extra_user": 7.00,
            "features": {
                "facturen": True,
                "klantenbeheer": True,
                "basis_rapporten": True,
                "geavanceerde_rapporten": True,
                "documentverwerking": True,
                "email_integratie": True,
                "api_toegang": False,
                "prioriteit_support": False,
                "eerste_maand_gratis": True
            }
        },
        
        # Professional abonnement - Voor gevestigde bedrijven
        {
            "name": "Professional",
            "description": "Complete oplossing voor gevestigde bedrijven. 10 gebruikers en tot 500 facturen per maand.",
            "price_monthly": 49.95,
            "price_yearly": 499.00,   # ~17% korting
            "max_users": 10,
            "max_invoices_per_month": 500,
            "price_per_extra_user": 5.00,
            "features": {
                "facturen": True,
                "klantenbeheer": True,
                "basis_rapporten": True,
                "geavanceerde_rapporten": True,
                "documentverwerking": True,
                "email_integratie": True,
                "api_toegang": True,
                "prioriteit_support": True,
                "eerste_maand_gratis": True
            }
        },
        
        # Enterprise abonnement - Voor grote ondernemingen
        {
            "name": "Enterprise",
            "description": "Op maat gemaakte oplossing voor grote ondernemingen. Onbeperkte gebruikers en facturen.",
            "price_monthly": 99.95,
            "price_yearly": 999.00,   # ~17% korting
            "max_users": 30,
            "max_invoices_per_month": 2000,
            "price_per_extra_user": 3.00,
            "features": {
                "facturen": True,
                "klantenbeheer": True,
                "basis_rapporten": True,
                "geavanceerde_rapporten": True,
                "documentverwerking": True,
                "email_integratie": True,
                "api_toegang": True,
                "prioriteit_support": True,
                "dedicated_account_manager": True,
                "eerste_maand_gratis": True
            }
        }
    ]
    
    # Maak de abonnementen aan in de database
    created_subscriptions = []
    try:
        for sub_data in subscriptions:
            subscription = Subscription(
                name=sub_data["name"],
                description=sub_data["description"],
                price_monthly=sub_data["price_monthly"],
                price_yearly=sub_data["price_yearly"],
                max_users=sub_data["max_users"],
                max_invoices_per_month=sub_data["max_invoices_per_month"],
                price_per_extra_user=sub_data["price_per_extra_user"],
                is_active=True,
                features=json.dumps(sub_data["features"])
            )
            db.session.add(subscription)
            created_subscriptions.append(subscription)
        
        db.session.commit()
        print(f"Succesvol {len(created_subscriptions)} abonnementen aangemaakt!")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Fout bij het aanmaken van abonnementen: {str(e)}")
        return False

if __name__ == "__main__":
    with app.app_context():
        create_default_subscriptions()