import jwt
import datetime
import secrets
import string
import os
from flask import current_app

class TokenHelper:
    def __init__(self, secret_key=None, expires_in=86400):  # standaard 24 uur (in seconden)
        self.secret_key = secret_key or os.environ.get('TOKEN_SECRET') or os.environ.get('SESSION_SECRET')
        self.expires_in = expires_in
        
    def generate_token(self, data, expires_in=None):
        """
        Genereer een JWT token met de opgegeven data en vervaltijd
        
        Args:
            data: Dictionary met gegevens om in het token op te slaan
            expires_in: Vervaltijd in seconden (standaard uit de constructor)
            
        Returns:
            str: JWT token
        """
        expiration = datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in or self.expires_in)
        
        payload = {
            'exp': expiration,
            'iat': datetime.datetime.utcnow(),
            'data': data
        }
        
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
        
    def verify_token(self, token):
        """
        Verifieer een JWT token en haal de data eruit
        
        Args:
            token: JWT token string
            
        Returns:
            dict or None: De data uit het token of None als het token ongeldig is
        """
        try:
            # Decodeer en verifieer het token
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload['data']
        except jwt.ExpiredSignatureError:
            # Token is verlopen
            return None
        except jwt.InvalidTokenError:
            # Token is ongeldig
            return None
    
    def generate_workspace_invitation_token(self, workspace_id, workspace_name, customer_email, expires_in=604800):  # 7 dagen
        """
        Genereer een token voor workspace uitnodiging
        
        Args:
            workspace_id: ID van de workspace
            workspace_name: Naam van de workspace (voor betere gebruikerservaring)
            customer_email: E-mail van de klant
            expires_in: Vervaltijd in seconden (standaard 7 dagen)
            
        Returns:
            str: JWT token
        """
        data = {
            'type': 'workspace_invitation',
            'workspace_id': workspace_id,
            'workspace_name': workspace_name,
            'email': customer_email
        }
        
        return self.generate_token(data, expires_in)
    
    def generate_user_invitation_token(self, workspace_id, workspace_name, email, is_admin=False, expires_in=172800):  # 48 uur
        """
        Genereer een token voor gebruikersuitnodiging
        
        Args:
            workspace_id: ID van de workspace
            workspace_name: Naam van de workspace (voor betere gebruikerservaring)
            email: E-mail van de gebruiker
            is_admin: Of de gebruiker admin moet zijn in de workspace
            expires_in: Vervaltijd in seconden (standaard 48 uur)
            
        Returns:
            str: JWT token
        """
        data = {
            'type': 'user_invitation',
            'workspace_id': workspace_id,
            'workspace_name': workspace_name,
            'email': email,
            'is_admin': is_admin
        }
        
        return self.generate_token(data, expires_in)
    
    def generate_password(self, length=12):
        """
        Genereer een willekeurig sterk wachtwoord
        
        Args:
            length: Lengte van het wachtwoord
            
        Returns:
            str: Gegenereerd wachtwoord
        """
        # Definieer tekensets
        uppercase_letters = string.ascii_uppercase
        lowercase_letters = string.ascii_lowercase
        digits = string.digits
        special_chars = '!@#$%^&*()-_=+[]{}|;:,.<>?'
        
        # Zorg ervoor dat het wachtwoord minimaal één karakter uit elke set heeft
        password = []
        password.append(secrets.choice(uppercase_letters))
        password.append(secrets.choice(lowercase_letters))
        password.append(secrets.choice(digits))
        password.append(secrets.choice(special_chars))
        
        # Vul de rest van het wachtwoord aan met willekeurige karakters
        all_chars = uppercase_letters + lowercase_letters + digits + special_chars
        password.extend(secrets.choice(all_chars) for _ in range(length - 4))
        
        # Schud de karakters door elkaar
        secrets.SystemRandom().shuffle(password)
        
        # Combineer tot een string
        return ''.join(password)

# Singleton instantie
token_helper = TokenHelper()