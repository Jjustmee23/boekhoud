"""
Migratiescript om extra e-mailtemplates toe te voegen.
Dit script voegt de volgende templates toe:
- user_invitation: Voor het uitnodigen van gebruikers voor een workspace
- workspace_invitation: Voor het uitnodigen van klanten voor een nieuwe workspace
"""

from app import app, db
from sqlalchemy import text
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_database():
    """Voeg nieuwe e-mailtemplates toe"""
    
    logging.info("Start migratie voor extra e-mailtemplates")
    
    try:
        with app.app_context():
            # Controleer eerst of er al templates bestaan
            result = db.session.execute(text("SELECT COUNT(*) FROM email_templates"))
            templates_exist = result.scalar() > 0
            
            if not templates_exist:
                logging.info("Geen bestaande templates gevonden. Voeg eerst de basis e-mail tabellen toe.")
                return
            
            # Definieer de nieuwe templates
            templates = [
                {
                    "name": "user_invitation",
                    "subject": "Uitnodiging voor toegang tot {{workspace_name}}",
                    "body_html": """
                    <html>
                        <head>
                            <style>
                                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                                .header { background-color: #0078D4; color: white; padding: 20px; text-align: center; }
                                .content { padding: 20px; background-color: #f9f9f9; }
                                .button { display: inline-block; padding: 12px 24px; background-color: #0078D4; color: white; 
                                         text-decoration: none; border-radius: 4px; margin: 20px 0; }
                                .footer { font-size: 12px; color: #666; margin-top: 30px; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="header">
                                    <h1>Uitnodiging voor toegang</h1>
                                </div>
                                <div class="content">
                                    <p>Beste gebruiker,</p>
                                    
                                    <p>U bent uitgenodigd door {% if inviter_name %}{{inviter_name}}{% else %}beheerder{% endif %} 
                                    om toegang te krijgen tot de MidaWeb omgeving van {{workspace_name}}.</p>
                                    
                                    <p>Klik op onderstaande link om uw account te activeren:</p>
                                    
                                    <p style="text-align: center;">
                                        <a href="{{activation_url}}" class="button">Account activeren</a>
                                    </p>
                                    
                                    <p>Als de knop niet werkt, kopieer dan deze link naar uw browser:</p>
                                    <p>{{activation_url}}</p>
                                    
                                    <p>Deze link is 48 uur geldig.</p>
                                    
                                    <p>Met vriendelijke groet,<br>Het MidaWeb Team</p>
                                </div>
                                <div class="footer">
                                    <p>Dit is een automatisch gegenereerd bericht. Antwoorden op deze e-mail worden niet gelezen.</p>
                                </div>
                            </div>
                        </body>
                    </html>
                    """,
                    "is_default": True,
                    "template_type": "invitation"
                },
                {
                    "name": "workspace_invitation",
                    "subject": "Welkom bij MidaWeb - Uw nieuwe workspace {{workspace_name}}",
                    "body_html": """
                    <html>
                        <head>
                            <style>
                                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                                .header { background-color: #0078D4; color: white; padding: 20px; text-align: center; }
                                .content { padding: 20px; background-color: #f9f9f9; }
                                .button { display: inline-block; padding: 12px 24px; background-color: #0078D4; color: white; 
                                         text-decoration: none; border-radius: 4px; margin: 20px 0; }
                                .footer { font-size: 12px; color: #666; margin-top: 30px; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="header">
                                    <h1>Welkom bij MidaWeb</h1>
                                </div>
                                <div class="content">
                                    <p>Beste {% if customer_name %}{{customer_name}}{% else %}klant{% endif %},</p>
                                    
                                    <p>Welkom bij MidaWeb! We hebben een nieuwe workspace voor u ingericht: <strong>{{workspace_name}}</strong>.</p>
                                    
                                    <p>Klik op onderstaande link om uw account te activeren en toegang te krijgen tot uw nieuwe workspace:</p>
                                    
                                    <p style="text-align: center;">
                                        <a href="{{activation_url}}" class="button">Account activeren</a>
                                    </p>
                                    
                                    <p>Als de knop niet werkt, kopieer dan deze link naar uw browser:</p>
                                    <p>{{activation_url}}</p>
                                    
                                    <p>Deze link is 48 uur geldig. Na activatie kunt u direct inloggen en gebruik maken van alle functies die MidaWeb biedt.</p>
                                    
                                    <p>Met vriendelijke groet,<br>Het MidaWeb Team</p>
                                </div>
                                <div class="footer">
                                    <p>Als u vragen heeft over uw account of workspace, neem dan contact op met onze support afdeling.</p>
                                </div>
                            </div>
                        </body>
                    </html>
                    """,
                    "is_default": True,
                    "template_type": "invitation"
                }
            ]
            
            # Voeg systeembrede templates toe (workspace_id=NULL)
            for template in templates:
                # Controleer of template al bestaat
                check_sql = text("""
                    SELECT COUNT(*) FROM email_templates
                    WHERE name = :name AND workspace_id IS NULL
                """)
                
                result = db.session.execute(check_sql, {"name": template["name"]})
                template_exists = result.scalar() > 0
                
                if not template_exists:
                    insert_template_sql = text("""
                        INSERT INTO email_templates (
                            workspace_id, name, subject, body_html, 
                            is_default, template_type, created_at
                        ) VALUES (
                            NULL, :name, :subject, :body_html, 
                            :is_default, :template_type, CURRENT_TIMESTAMP
                        )
                    """)
                    
                    db.session.execute(
                        insert_template_sql,
                        {
                            "name": template["name"],
                            "subject": template["subject"],
                            "body_html": template["body_html"],
                            "is_default": template["is_default"],
                            "template_type": template["template_type"]
                        }
                    )
                    
                    logging.info(f"Template '{template['name']}' toegevoegd als systeembreed template")
            
            # Commit de wijzigingen
            db.session.commit()
            logging.info("E-mailtemplates migratie voltooid")
            
    except Exception as e:
        logging.error(f"Fout tijdens de migratie van e-mailtemplates: {str(e)}")
        db.session.rollback()
        raise

if __name__ == "__main__":
    migrate_database()