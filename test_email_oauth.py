"""
Test script voor het testen van de OAuth 2.0 email functionaliteit met Microsoft 365.
"""

import os
import logging
from app import app
from email_service_oauth import EmailServiceOAuth
from microsoft_365_oauth import Microsoft365OAuth

# Configureer logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_oauth_email_send():
    """Test het versturen van een e-mail via Microsoft 365 met OAuth 2.0 authenticatie"""
    
    logger.info("Start OAuth email test")
    
    with app.app_context():
        try:
            # Initialiseer de EmailServiceOAuth
            email_service = EmailServiceOAuth()
            
            # Controleer of de service correct is geconfigureerd
            if not email_service.is_configured():
                logger.error("EmailServiceOAuth is niet correct geconfigureerd")
                logger.info("Controleer of de volgende omgevingsvariabelen zijn ingesteld:")
                logger.info("- MS_GRAPH_CLIENT_ID")
                logger.info("- MS_GRAPH_CLIENT_SECRET")
                logger.info("- MS_GRAPH_TENANT_ID")
                logger.info("- MS_GRAPH_SENDER_EMAIL")
                return False
            
            # Test ontvanger (uit omgevingsvariabele of eigen e-mailadres)
            test_recipient = os.environ.get("TEST_EMAIL_RECIPIENT", "your-email@example.com")
            
            # Maak een test e-mail
            subject = "Test e-mail van Microsoft 365 OAuth"
            body_html = """
            <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                        h1 { color: #2c3e50; margin-bottom: 20px; }
                        .content { background-color: #f9f9f9; padding: 20px; border-radius: 5px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Testbericht OAuth 2.0</h1>
                        <div class="content">
                            <p>Dit is een testbericht verzonden via Microsoft 365 met OAuth 2.0 authenticatie.</p>
                            <p>Als u dit bericht ontvangt, werkt de OAuth 2.0 configuratie correct!</p>
                        </div>
                    </div>
                </body>
            </html>
            """
            
            # Verstuur de e-mail
            logger.info(f"Versturen van test e-mail naar: {test_recipient}")
            result = email_service.send_email(test_recipient, subject, body_html)
            
            if result:
                logger.info("E-mail succesvol verzonden! OAuth 2.0 werkt correct.")
                return True
            else:
                logger.error("Fout bij het versturen van de e-mail via OAuth 2.0")
                return False
                
        except Exception as e:
            logger.error(f"Onverwachte fout bij testen van OAuth e-mail: {str(e)}")
            return False

def test_oauth_token():
    """Test alleen het verkrijgen van een OAuth token"""
    
    logger.info("Start OAuth token test")
    
    with app.app_context():
        try:
            # Initialiseer de Microsoft365OAuth helper
            ms_oauth = Microsoft365OAuth()
            
            # Controleer of de configuratie correct is
            if not ms_oauth.is_configured():
                logger.error("Microsoft365OAuth is niet correct geconfigureerd")
                return False
            
            # Probeer een token te verkrijgen
            token = ms_oauth.get_oauth_token()
            
            if token:
                logger.info("OAuth token succesvol verkregen!")
                # Toon alleen het begin van het token voor veiligheid
                token_preview = token[:10] + "..." if len(token) > 10 else token
                logger.info(f"Token (preview): {token_preview}")
                return True
            else:
                logger.error("Kon geen OAuth token verkrijgen")
                return False
                
        except Exception as e:
            logger.error(f"Onverwachte fout bij testen van OAuth token: {str(e)}")
            return False

if __name__ == "__main__":
    print("=" * 50)
    print("Microsoft 365 OAuth Email Test")
    print("=" * 50)
    
    # Test eerst het verkrijgen van een token
    print("\nTesten van OAuth token:")
    token_result = test_oauth_token()
    
    if token_result:
        # Als het token werkt, test het verzenden van een e-mail
        print("\nTesten van email verzending:")
        email_result = test_oauth_email_send()
        
        if email_result:
            print("\nSUCCES: Beide tests geslaagd! OAuth 2.0 configuratie werkt correct.")
            exit(0)
        else:
            print("\nFOUT: Token verkrijgen werkt, maar e-mail verzenden mislukt.")
            exit(1)
    else:
        print("\nFOUT: Kon geen OAuth token verkrijgen. Verdere tests worden overgeslagen.")
        exit(1)