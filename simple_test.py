"""
Eenvoudige test voor de versleutelingsfuncties
"""
import logging
from models import EmailSettings

# Logging configureren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_encryption_functions():
    """Test of de versleutelingsfuncties correct werken"""
    test_secret = "TestGeheimeSleutel123"
    encrypted = EmailSettings.encrypt_secret(test_secret)
    decrypted = EmailSettings.decrypt_secret(encrypted)
    
    print(f"Originele secret: {test_secret}")
    print(f"Gecodeerde secret: {encrypted}")
    print(f"Gedecodeerde secret: {decrypted}")
    
    if test_secret == encrypted and test_secret == decrypted:
        print("SUCCESS: Versleuteling uitgeschakeld - geheime sleutel blijft ongewijzigd")
    else:
        print("ERROR: Versleuteling werkt niet zoals verwacht")

if __name__ == "__main__":
    test_encryption_functions()