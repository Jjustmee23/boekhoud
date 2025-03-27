"""
Migration script to add email functionality to the application.
This creates the email_settings, email_templates, and email_messages tables.
"""

from app import app, db
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the tables to be added
def migrate_database():
    """Create email tables and update relationships"""
    
    logging.info("Starting email functionality migration")
    
    try:
        with app.app_context():
            # Add Email settings table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS email_settings (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                    smtp_server VARCHAR(100),
                    smtp_port INTEGER,
                    smtp_username VARCHAR(100),
                    smtp_password VARCHAR(100),
                    email_from VARCHAR(100),
                    email_from_name VARCHAR(100),
                    use_ms_graph BOOLEAN DEFAULT FALSE,
                    ms_graph_client_id VARCHAR(100),
                    ms_graph_client_secret VARCHAR(100),
                    ms_graph_tenant_id VARCHAR(100),
                    ms_graph_sender_email VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP,
                    CONSTRAINT uq_workspace_email_settings UNIQUE (workspace_id)
                )
            """))
            
            # Add Email templates table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS email_templates (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                    name VARCHAR(100),
                    subject VARCHAR(255),
                    body_html TEXT,
                    is_default BOOLEAN DEFAULT FALSE,
                    template_type VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            
            # Add Email messages table
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS email_messages (
                    id SERIAL PRIMARY KEY,
                    workspace_id INTEGER REFERENCES workspaces(id) ON DELETE CASCADE,
                    message_id VARCHAR(255) UNIQUE,
                    subject VARCHAR(255),
                    sender VARCHAR(255),
                    recipient VARCHAR(255),
                    body_text TEXT,
                    body_html TEXT,
                    received_date TIMESTAMP,
                    is_processed BOOLEAN DEFAULT FALSE,
                    status VARCHAR(50) DEFAULT 'received',
                    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
                    attachments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """))
            
            # Set global system email settings using environment variables
            system_settings_sql = text("""
                INSERT INTO email_settings (
                    workspace_id, use_ms_graph, ms_graph_client_id, 
                    ms_graph_client_secret, ms_graph_tenant_id, ms_graph_sender_email
                ) VALUES (
                    (SELECT id FROM workspaces LIMIT 1), 
                    true, 
                    :client_id, :client_secret, :tenant_id, :sender_email
                ) ON CONFLICT (workspace_id) DO UPDATE SET
                    use_ms_graph = EXCLUDED.use_ms_graph,
                    ms_graph_client_id = EXCLUDED.ms_graph_client_id,
                    ms_graph_client_secret = EXCLUDED.ms_graph_client_secret,
                    ms_graph_tenant_id = EXCLUDED.ms_graph_tenant_id,
                    ms_graph_sender_email = EXCLUDED.ms_graph_sender_email
            """)
            
            # Only attempt to set defaults if there are workspaces
            import os
            client_id = os.environ.get('MS_GRAPH_CLIENT_ID')
            client_secret = os.environ.get('MS_GRAPH_CLIENT_SECRET')
            tenant_id = os.environ.get('MS_GRAPH_TENANT_ID')
            sender_email = os.environ.get('MS_GRAPH_SENDER_EMAIL')
            
            # Controleer of er workspaces bestaan
            result = db.session.execute(text("SELECT COUNT(*) FROM workspaces"))
            workspace_exists = result.scalar() > 0
            
            if workspace_exists and all([client_id, client_secret, tenant_id, sender_email]):
                db.session.execute(
                    system_settings_sql, 
                    {
                        'client_id': client_id, 
                        'client_secret': client_secret, 
                        'tenant_id': tenant_id, 
                        'sender_email': sender_email
                    }
                )
                logging.info("Added global email settings using environment variables")
            
            # Create a couple of default email templates for the first workspace
            templates = [
                {
                    "name": "Factuur verzonden",
                    "subject": "Nieuwe factuur van {{company_name}}",
                    "body_html": """
                    <html>
                        <head>
                            <style>
                                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                                .header { background-color: #0078D4; color: white; padding: 20px; text-align: center; }
                                .content { padding: 20px; background-color: #f9f9f9; }
                                .footer { font-size: 12px; color: #666; margin-top: 30px; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="header">
                                    <h1>Nieuwe factuur</h1>
                                </div>
                                <div class="content">
                                    <p>Beste {{customer_name}},</p>
                                    
                                    <p>Hierbij ontvangt u factuur {{invoice_number}} met een totaalbedrag van €{{amount_incl_vat}}.</p>
                                    
                                    <p>De factuur vindt u als bijlage bij deze e-mail.</p>
                                    
                                    <p>Met vriendelijke groet,<br>{{company_name}}</p>
                                </div>
                                <div class="footer">
                                    <p>Factuurgegevens:<br>
                                    Factuurnummer: {{invoice_number}}<br>
                                    Datum: {{invoice_date}}<br>
                                    Bedrag: €{{amount_incl_vat}}</p>
                                </div>
                            </div>
                        </body>
                    </html>
                    """,
                    "is_default": True,
                    "template_type": "invoice"
                },
                {
                    "name": "Betalingsherinnering",
                    "subject": "Herinnering: Openstaande factuur {{invoice_number}}",
                    "body_html": """
                    <html>
                        <head>
                            <style>
                                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                                .header { background-color: #0078D4; color: white; padding: 20px; text-align: center; }
                                .content { padding: 20px; background-color: #f9f9f9; }
                                .footer { font-size: 12px; color: #666; margin-top: 30px; }
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="header">
                                    <h1>Betalingsherinnering</h1>
                                </div>
                                <div class="content">
                                    <p>Beste {{customer_name}},</p>
                                    
                                    <p>Volgens onze administratie hebben wij nog geen betaling ontvangen voor factuur {{invoice_number}} 
                                    met een totaalbedrag van €{{amount_incl_vat}}, die vervallen is op {{due_date}}.</p>
                                    
                                    <p>Zou u deze factuur op korte termijn kunnen voldoen? De factuur vindt u nogmaals als bijlage bij deze e-mail.</p>
                                    
                                    <p>Als u de factuur inmiddels heeft betaald, kunt u deze herinnering als niet verzonden beschouwen.</p>
                                    
                                    <p>Met vriendelijke groet,<br>{{company_name}}</p>
                                </div>
                                <div class="footer">
                                    <p>Factuurgegevens:<br>
                                    Factuurnummer: {{invoice_number}}<br>
                                    Datum: {{invoice_date}}<br>
                                    Vervaldatum: {{due_date}}<br>
                                    Bedrag: €{{amount_incl_vat}}</p>
                                </div>
                            </div>
                        </body>
                    </html>
                    """,
                    "is_default": True,
                    "template_type": "reminder"
                }
            ]
            
            # Als er tenminste één workspace is, voeg de standaardtemplates toe
            if workspace_exists:
                for template in templates:
                    insert_template_sql = text("""
                        INSERT INTO email_templates (
                            workspace_id, name, subject, body_html, 
                            is_default, template_type, created_at
                        ) VALUES (
                            (SELECT id FROM workspaces LIMIT 1), 
                            :name, :subject, :body_html, :is_default, :template_type, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT DO NOTHING
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
                    
                logging.info("Added default email templates")
            
            db.session.commit()
            logging.info("Database migration completed successfully")
    
    except Exception as e:
        logging.error(f"Migration failed: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    migrate_database()