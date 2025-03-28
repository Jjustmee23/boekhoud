"""
Test script voor de EmailServiceOAuth module.
Dit script test de e-mailfunctionaliteit met Microsoft 365 OAuth 2.0 authenticatie.
"""

import os
import logging
from dotenv import load_dotenv
from email_service_oauth import EmailServiceOAuth

# Configureer logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Laad omgevingsvariabelen
load_dotenv()

def test_oauth_email_service():
    """Test de EmailServiceOAuth functionaliteit"""
    
    print("\n" + "=" * 50)
    print("EmailServiceOAuth Test")
    print("=" * 50 + "\n")
    
    # Instantieer de emailservice met systeem-instellingen
    email_service = EmailServiceOAuth()
    
    # Controleer configuratie
    if not email_service.is_configured():
        logger.error("EmailServiceOAuth is niet correct geconfigureerd")
        logger.info("Controleer de Microsoft 365 OAuth instellingen in de database of .env bestand")
        print("\nFOUT: EmailServiceOAuth is niet correct geconfigureerd.")
        print("Controleer de volgende instellingen:")
        print("- MS_GRAPH_CLIENT_ID")
        print("- MS_GRAPH_CLIENT_SECRET")
        print("- MS_GRAPH_TENANT_ID")
        print("- MS_GRAPH_SENDER_EMAIL")
        return False
    
    # Test e-mail parameters
    test_recipient = os.environ.get("TEST_EMAIL_RECIPIENT")
    if not test_recipient:
        test_recipient = input("Voer een testadres in om de e-mail naar te sturen: ")
    
    # Test e-mail verzenden
    html_content = """
    <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                h1 { color: #2c3e50; margin-bottom: 20px; }
                .content { background-color: #f9f9f9; padding: 20px; border-radius: 5px; }
                .footer { margin-top: 20px; font-size: 12px; color: #7f8c8d; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>EmailServiceOAuth Test</h1>
                <div class="content">
                    <p>Dit is een testbericht verzonden via de nieuwe EmailServiceOAuth klasse.</p>
                    <p>De e-mail gebruikt Microsoft 365 OAuth 2.0 authenticatie voor veilige verzending.</p>
                    <p>Als je dit bericht ontvangt, is de e-mailintegratie succesvol geconfigureerd!</p>
                </div>
                <div class="footer">
                    <p>Dit is een automatisch gegenereerd testbericht.</p>
                </div>
            </div>
        </body>
    </html>
    """
    
    try:
        logger.info(f"Test e-mail verzenden naar {test_recipient}")
        result = email_service.send_email(
            recipient=test_recipient,
            subject="Test EmailServiceOAuth",
            body_html=html_content
        )
        
        if result:
            print("\nSUCCES: E-mail is succesvol verzonden!")
            print(f"Controleer de inbox van {test_recipient}")
            logger.info("E-mail succesvol verzonden")
            return True
        else:
            print("\nFOUT: E-mail verzenden mislukt.")
            logger.error("E-mail verzenden mislukt")
            return False
    
    except Exception as e:
        logger.error(f"Onverwachte fout bij e-mail verzenden: {str(e)}")
        print(f"\nFOUT: Onverwachte fout bij e-mail verzenden: {str(e)}")
        return False

if __name__ == "__main__":
    test_oauth_email_service()