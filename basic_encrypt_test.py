"""
Directe test van de encryptie functie
"""

def encrypt_secret(secret):
    """
    Versleutel een geheim voor opslag.
    
    Deze implementatie slaat nu het geheim direct op zonder versleuteling om problemen
    met de authenticatie te voorkomen.
    """
    if not secret:
        return None
    
    # Retourneer het geheim ongewijzigd
    return secret

def decrypt_secret(encrypted_secret):
    """
    Ontsleutel een opgeslagen geheim.
    
    Omdat we het geheim direct opslaan, retourneren we het ongewijzigd.
    """
    if not encrypted_secret:
        return None
        
    # Retourneer het geheim ongewijzigd
    return encrypted_secret

def test_encryption():
    """Test de aangepaste encryptie functies"""
    test_secret = "TestGeheimeSleutel123"
    encrypted = encrypt_secret(test_secret)
    decrypted = decrypt_secret(encrypted)
    
    print(f"Originele secret: {test_secret}")
    print(f"Gecodeerde secret: {encrypted}")
    print(f"Gedecodeerde secret: {decrypted}")
    
    if test_secret == encrypted and test_secret == decrypted:
        print("SUCCESS: Versleuteling uitgeschakeld - geheime sleutel blijft ongewijzigd")
    else:
        print("ERROR: Versleuteling werkt niet zoals verwacht")

if __name__ == "__main__":
    test_encryption()