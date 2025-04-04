"""
Backup service module voor het maken en herstellen van back-ups van de database en uploads.
Dit module biedt functionaliteit voor het maken van volledige of gedeeltelijke back-ups van
een werkruimte en het herstellen van deze back-ups.
"""

import os
import json
import logging
import datetime
import shutil
import tempfile
import zipfile
import uuid
import traceback
from sqlalchemy import create_engine, inspect, MetaData, Table, select, text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

# Setup logging
logger = logging.getLogger(__name__)

class BackupService:
    """
    Service voor het maken en herstellen van back-ups.
    Ondersteunt zowel volledige back-ups van een werkruimte als selectieve back-ups van bepaalde gegevens.
    """
    
    def __init__(self, app=None, db=None):
        """
        Initialiseer de BackupService
        
        Args:
            app: Flask app (optioneel)
            db: SQLAlchemy db instantie (optioneel)
        """
        self.app = app
        self.db = db
        self.backup_dir = os.environ.get("BACKUP_DIR", "backups")
        
        # Maak de backup directory als deze niet bestaat
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)
            
        # Maak een uploads directory als deze niet bestaat (voor herstellen van uploads)
        uploads_dir = os.path.join("static", "uploads")
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir, exist_ok=True)
    
    def create_backup(self, workspace_id=None, include_uploads=True, tables=None, backup_name=None):
        """
        Maak een backup van de database en optioneel uploads
        
        Args:
            workspace_id: ID van de werkruimte om te backuppen (None voor alle werkruimtes)
            include_uploads: Of uploads moeten worden opgenomen in de backup
            tables: Lijst van tabellen om te backuppen (None voor alle tabellen)
            backup_name: Aangepaste naam voor de backup (anders wordt automatisch een naam gegenereerd)
            
        Returns:
            dict: Informatie over de gemaakte backup
        """
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_id = str(uuid.uuid4())[:8]
            
            if backup_name:
                backup_name = secure_filename(backup_name)
                filename = f"{backup_name}_{timestamp}.zip"
            else:
                workspace_str = f"workspace_{workspace_id}_" if workspace_id else "all_workspaces_"
                filename = f"backup_{workspace_str}{timestamp}_{backup_id}.zip"
                
            backup_path = os.path.join(self.backup_dir, filename)
            
            # Tijdelijke directory voor het verzamelen van de backup bestanden
            with tempfile.TemporaryDirectory() as temp_dir:
                # Maak de database backup
                db_backup_path = os.path.join(temp_dir, "database_backup.json")
                self._backup_database(db_backup_path, workspace_id, tables)
                
                # Backups van uploads indien nodig
                uploads_path = None
                if include_uploads:
                    # Bepaal uploads directory voor deze werkruimte
                    if workspace_id:
                        workspace_upload_dir = os.path.join("static", "uploads", str(workspace_id))
                        if os.path.exists(workspace_upload_dir):
                            uploads_path = workspace_upload_dir
                    else:
                        # Voor alle werkruimtes, gebruik de hoofdupload directory
                        uploads_path = os.path.join("static", "uploads")
                
                # Creëer een ZIP bestand met alle backup data
                with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
                    # Voeg database backup toe
                    backup_zip.write(db_backup_path, arcname="database_backup.json")
                    
                    # Voeg uploads toe als die er zijn
                    if include_uploads and uploads_path and os.path.exists(uploads_path):
                        for root, _, files in os.walk(uploads_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(uploads_path))
                                backup_zip.write(file_path, arcname=os.path.join("uploads", arcname))
                    
                    # Voeg metadata toe aan de backup
                    metadata = {
                        "backup_id": backup_id,
                        "timestamp": timestamp,
                        "workspace_id": workspace_id,
                        "include_uploads": include_uploads,
                        "tables": tables,
                        "version": "1.0"
                    }
                    
                    # Schrijf metadata naar een bestand in de ZIP
                    metadata_path = os.path.join(temp_dir, "backup_metadata.json")
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)
                    
                    backup_zip.write(metadata_path, arcname="backup_metadata.json")
            
            backup_info = {
                "backup_id": backup_id,
                "filename": filename,
                "path": backup_path,
                "size": os.path.getsize(backup_path),
                "timestamp": timestamp,
                "workspace_id": workspace_id,
                "include_uploads": include_uploads,
                "tables": tables
            }
            
            logger.info(f"Backup succesvol gemaakt: {backup_path}")
            return backup_info
            
        except Exception as e:
            logger.error(f"Fout bij maken van backup: {str(e)}")
            logger.error(traceback.format_exc())
            raise
    
    def list_backups(self, workspace_id=None):
        """
        Lijst alle beschikbare backups
        
        Args:
            workspace_id: Filter op werkruimte ID (optioneel)
            
        Returns:
            list: Lijst met backup informatie
        """
        backups = []
        
        try:
            if not os.path.exists(self.backup_dir):
                return []
                
            for filename in os.listdir(self.backup_dir):
                if not filename.endswith('.zip'):
                    continue
                    
                backup_path = os.path.join(self.backup_dir, filename)
                
                try:
                    with zipfile.ZipFile(backup_path, 'r') as zip_file:
                        if "backup_metadata.json" not in zip_file.namelist():
                            continue
                            
                        with zip_file.open("backup_metadata.json") as metadata_file:
                            metadata = json.load(metadata_file)
                            
                        # Filter op werkruimte indien nodig
                        if workspace_id is not None and metadata.get("workspace_id") != workspace_id:
                            continue
                            
                        backups.append({
                            "backup_id": metadata.get("backup_id"),
                            "filename": filename,
                            "path": backup_path,
                            "size": os.path.getsize(backup_path),
                            "timestamp": metadata.get("timestamp"),
                            "created_at": datetime.datetime.strptime(metadata.get("timestamp"), "%Y%m%d_%H%M%S"),
                            "workspace_id": metadata.get("workspace_id"),
                            "include_uploads": metadata.get("include_uploads"),
                            "tables": metadata.get("tables"),
                            "version": metadata.get("version")
                        })
                except (zipfile.BadZipFile, KeyError, json.JSONDecodeError):
                    # Skip invalid backup files
                    logger.warning(f"Ongeldige backup: {filename}")
                    continue
            
            # Sorteer op aanmaakdatum, nieuwste eerst
            backups.sort(key=lambda x: x.get("created_at", datetime.datetime.min), reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Fout bij ophalen van backups: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def restore_backup(self, backup_path, workspace_id=None, include_uploads=True, tables=None):
        """
        Herstel een backup
        
        Args:
            backup_path: Pad naar het backup bestand
            workspace_id: Herstel naar specifieke werkruimte (None voor origineel)
            include_uploads: Of uploads moeten worden hersteld
            tables: Lijst van tabellen om te herstellen (None voor alle tabellen)
            
        Returns:
            bool: True als herstel succesvol was, anders False
        """
        temp_dir = None
        
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup bestand niet gevonden: {backup_path}")
                return False
            
            # Tijdelijke directory voor het uitpakken van de backup
            temp_dir = tempfile.mkdtemp()
            
            # Pak het backup bestand uit
            with zipfile.ZipFile(backup_path, 'r') as zip_file:
                zip_file.extractall(temp_dir)
            
            # Lees de metadata
            metadata_path = os.path.join(temp_dir, "backup_metadata.json")
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Bepaal de originele werkruimte ID
            original_workspace_id = metadata.get("workspace_id")
            target_workspace_id = workspace_id or original_workspace_id
            
            # Herstel database data
            db_backup_path = os.path.join(temp_dir, "database_backup.json")
            self._restore_database(db_backup_path, target_workspace_id, original_workspace_id, tables)
            
            # Herstel uploads indien nodig
            if include_uploads and metadata.get("include_uploads", False):
                uploads_dir = os.path.join(temp_dir, "uploads")
                if os.path.exists(uploads_dir):
                    # Bepaal doelmap voor uploads
                    target_uploads_dir = os.path.join("static", "uploads")
                    if target_workspace_id:
                        target_uploads_dir = os.path.join(target_uploads_dir, str(target_workspace_id))
                    
                    # Maak doelmap als deze niet bestaat
                    os.makedirs(target_uploads_dir, exist_ok=True)
                    
                    # Kopieer bestanden
                    for root, _, files in os.walk(uploads_dir):
                        for file in files:
                            src_path = os.path.join(root, file)
                            rel_path = os.path.relpath(src_path, uploads_dir)
                            
                            # Pas de workspace_id aan indien nodig
                            if original_workspace_id and target_workspace_id and original_workspace_id != target_workspace_id:
                                rel_path_parts = rel_path.split(os.path.sep)
                                if len(rel_path_parts) > 0 and rel_path_parts[0] == str(original_workspace_id):
                                    rel_path_parts[0] = str(target_workspace_id)
                                    rel_path = os.path.join(*rel_path_parts)
                            
                            dest_path = os.path.join(target_uploads_dir, rel_path)
                            dest_dir = os.path.dirname(dest_path)
                            
                            # Maak tussenliggende mappen indien nodig
                            os.makedirs(dest_dir, exist_ok=True)
                            
                            # Kopieer bestand
                            shutil.copy2(src_path, dest_path)
            
            logger.info(f"Backup succesvol hersteld vanaf: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Fout bij herstellen van backup: {str(e)}")
            logger.error(traceback.format_exc())
            return False
        finally:
            # Ruim de tijdelijke directory op
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    def delete_backup(self, backup_path):
        """
        Verwijder een backup bestand
        
        Args:
            backup_path: Pad naar het backup bestand
            
        Returns:
            bool: True als verwijderen succesvol was, anders False
        """
        try:
            if not os.path.exists(backup_path):
                logger.error(f"Backup bestand niet gevonden: {backup_path}")
                return False
            
            os.remove(backup_path)
            logger.info(f"Backup succesvol verwijderd: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Fout bij verwijderen van backup: {str(e)}")
            return False
    
    def _backup_database(self, output_path, workspace_id=None, selected_tables=None):
        """
        Maak een backup van de database
        
        Args:
            output_path: Pad om de database backup naar te schrijven
            workspace_id: ID van de werkruimte om te backuppen (None voor alle werkruimtes)
            selected_tables: Lijst van tabellen om te backuppen (None voor alle tabellen)
        """
        if self.app is None or self.db is None:
            from app import app, db
            self.app = app
            self.db = db
        
        with self.app.app_context():
            try:
                # Metadata initialiseren
                metadata = MetaData()
                metadata.reflect(bind=self.db.engine)
                
                # Bepaal tabellen voor backup
                tables_to_backup = []
                for table_name, table in metadata.tables.items():
                    if selected_tables and table_name not in selected_tables:
                        continue
                    tables_to_backup.append(table)
                
                # Data verzamelen
                data = {}
                for table in tables_to_backup:
                    table_name = table.name
                    query = select(table)
                    
                    # Filter op werkruimte indien nodig
                    if workspace_id and 'workspace_id' in [c.name for c in table.columns]:
                        query = query.where(table.c.workspace_id == workspace_id)
                    
                    result = self.db.session.execute(query)
                    rows = [dict(row._mapping) for row in result]
                    
                    # Converteer UUID en datetime objecten naar strings
                    for row in rows:
                        for key, value in row.items():
                            if isinstance(value, uuid.UUID):
                                row[key] = str(value)
                            elif isinstance(value, datetime.datetime):
                                row[key] = value.isoformat()
                            elif isinstance(value, datetime.date):
                                row[key] = value.isoformat()
                    
                    data[table_name] = rows
                
                # Schrijf de data naar het output bestand
                with open(output_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.info(f"Database backup gemaakt: {len(tables_to_backup)} tabellen, {output_path}")
                return True
                
            except Exception as e:
                logger.error(f"Fout bij maken van database backup: {str(e)}")
                logger.error(traceback.format_exc())
                raise
    
    def _restore_database(self, backup_path, target_workspace_id=None, original_workspace_id=None, selected_tables=None):
        """
        Herstel de database van een backup
        
        Args:
            backup_path: Pad naar de database backup
            target_workspace_id: ID van de werkruimte om naar te herstellen (None voor origineel)
            original_workspace_id: ID van de werkruimte in de backup (None voor alle werkruimtes)
            selected_tables: Lijst van tabellen om te herstellen (None voor alle tabellen)
            
        Returns:
            bool: True als herstel succesvol was, anders False
        """
        if self.app is None or self.db is None:
            from app import app, db
            self.app = app
            self.db = db
        
        with self.app.app_context():
            try:
                # Lees de backup data
                with open(backup_path, 'r') as f:
                    data = json.load(f)
                
                # Metadata initialiseren
                metadata = MetaData()
                metadata.reflect(bind=self.db.engine)
                
                # Transactie voor atomaire operatie
                connection = self.db.engine.connect()
                trans = connection.begin()
                
                try:
                    for table_name, rows in data.items():
                        if selected_tables and table_name not in selected_tables:
                            continue
                        
                        if table_name not in metadata.tables:
                            logger.warning(f"Tabel {table_name} bestaat niet in de database, wordt overgeslagen")
                            continue
                        
                        table = metadata.tables[table_name]
                        
                        # Pas workspace_id aan indien nodig
                        if target_workspace_id and original_workspace_id and target_workspace_id != original_workspace_id:
                            if 'workspace_id' in [c.name for c in table.columns]:
                                for row in rows:
                                    if row.get('workspace_id') == original_workspace_id:
                                        row['workspace_id'] = target_workspace_id
                        
                        # Verwijder bestaande data voor deze werkruimte en tabel indien nodig
                        if 'workspace_id' in [c.name for c in table.columns]:
                            workspace_filter = {}
                            if target_workspace_id:
                                workspace_filter = {'workspace_id': target_workspace_id}
                            
                            if workspace_filter:
                                connection.execute(table.delete().where(
                                    table.c.workspace_id == workspace_filter['workspace_id']
                                ))
                        
                        # Voeg de nieuwe data toe
                        if rows:
                            # Pas kolommen aan om alleen bestaande kolommen te gebruiken
                            column_names = [c.name for c in table.columns]
                            for row in rows:
                                filtered_row = {k: v for k, v in row.items() if k in column_names}
                                
                                # Skip gebruikersdata voor zekere tabellen zoals User
                                if table_name == 'user' and target_workspace_id and 'id' in filtered_row:
                                    continue
                                
                                # Voeg rij toe
                                connection.execute(table.insert().values(**filtered_row))
                    
                    # Commit de transactie
                    trans.commit()
                    logger.info(f"Database succesvol hersteld van: {backup_path}")
                    return True
                    
                except Exception as e:
                    # Rollback bij fouten
                    trans.rollback()
                    logger.error(f"Fout bij herstellen van database, rollback uitgevoerd: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
                finally:
                    connection.close()
                    
            except Exception as e:
                logger.error(f"Fout bij herstellen van database: {str(e)}")
                logger.error(traceback.format_exc())
                raise
    
    def schedule_backup(self, workspace_id=None, interval="daily", time="02:00", retention_days=30):
        """
        Plan een automatische backup
        
        Args:
            workspace_id: ID van de werkruimte (None voor alle werkruimtes)
            interval: Interval ('hourly', 'daily', 'weekly', 'monthly')
            time: Tijdstip voor de backup (formaat: "HH:MM")
            retention_days: Aantal dagen om backups te bewaren
            
        Returns:
            dict: Informatie over de geplande backup
        """
        # Dit is een dummy implementatie - in een echte omgeving zou dit 
        # bijvoorbeeld een cron job of een achtergrondtaak instellen
        
        schedule_id = str(uuid.uuid4())[:8]
        
        schedule_info = {
            "schedule_id": schedule_id,
            "workspace_id": workspace_id,
            "interval": interval,
            "time": time,
            "retention_days": retention_days,
            "status": "active",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        # In een echte implementatie zou deze informatie in de database worden opgeslagen
        
        logger.info(f"Backup planning ingesteld: {schedule_info}")
        return schedule_info

# Hulpklasse voor backup abonnementen
class BackupSubscription:
    """
    Klasse voor het beheren van backup abonnementen
    """
    
    FREE_PLAN = "free"
    BASIC_PLAN = "basic"
    PREMIUM_PLAN = "premium"
    ENTERPRISE_PLAN = "enterprise"
    
    def __init__(self, db):
        """
        Initialiseer de BackupSubscription
        
        Args:
            db: SQLAlchemy db instantie
        """
        self.db = db
    
    @staticmethod
    def get_plan_limits(plan):
        """
        Haal de limieten op voor een bepaald abonnement
        
        Args:
            plan: Abonnement type
            
        Returns:
            dict: Limieten voor het abonnement
        """
        limits = {
            BackupSubscription.FREE_PLAN: {
                "max_backups": 2,
                "auto_backup": False,
                "retention_days": 7,
                "include_uploads": False
            },
            BackupSubscription.BASIC_PLAN: {
                "max_backups": 5,
                "auto_backup": True,
                "retention_days": 14,
                "include_uploads": True
            },
            BackupSubscription.PREMIUM_PLAN: {
                "max_backups": 10,
                "auto_backup": True,
                "retention_days": 30,
                "include_uploads": True
            },
            BackupSubscription.ENTERPRISE_PLAN: {
                "max_backups": 30,
                "auto_backup": True,
                "retention_days": 90,
                "include_uploads": True
            }
        }
        
        return limits.get(plan, limits[BackupSubscription.FREE_PLAN])
    
    @staticmethod
    def get_plan_description(plan):
        """
        Haal de omschrijving op voor een bepaald abonnement
        
        Args:
            plan: Abonnement type
            
        Returns:
            dict: Omschrijving van het abonnement
        """
        descriptions = {
            BackupSubscription.FREE_PLAN: {
                "name": "Gratis",
                "description": "Basis backup functionaliteit zonder automatische backups",
                "price_monthly": 0,
                "price_yearly": 0,
                "features": [
                    "Maximaal 2 backups tegelijk",
                    "Backups worden 7 dagen bewaard",
                    "Handmatige backups"
                ]
            },
            BackupSubscription.BASIC_PLAN: {
                "name": "Basis",
                "description": "Eenvoudige backup oplossing voor kleine bedrijven",
                "price_monthly": 5,
                "price_yearly": 50,
                "features": [
                    "Maximaal 5 backups tegelijk",
                    "Dagelijkse automatische backups",
                    "Inclusief uploads en bestanden",
                    "14 dagen backup historie"
                ]
            },
            BackupSubscription.PREMIUM_PLAN: {
                "name": "Premium",
                "description": "Uitgebreide backup oplossing voor groeiende bedrijven",
                "price_monthly": 10,
                "price_yearly": 100,
                "features": [
                    "Maximaal 10 backups tegelijk",
                    "Instelbare backup schema's",
                    "Prioriteit herstellen",
                    "30 dagen backup historie"
                ]
            },
            BackupSubscription.ENTERPRISE_PLAN: {
                "name": "Enterprise",
                "description": "Complete backup oplossing voor grote organisaties",
                "price_monthly": 25,
                "price_yearly": 250,
                "features": [
                    "Maximaal 30 backups tegelijk",
                    "Geavanceerde backup schema's",
                    "90 dagen backup historie",
                    "Dedicated ondersteuning"
                ]
            }
        }
        
        return descriptions.get(plan, descriptions[BackupSubscription.FREE_PLAN])
    
    def get_workspace_subscription(self, workspace_id):
        """
        Haal het huidige backup abonnement op voor een werkruimte
        
        Args:
            workspace_id: ID van de werkruimte
            
        Returns:
            dict: Abonnement informatie
        """
        # In een echte implementatie zou dit uit de database komen
        # Voor nu maken we een dummy abonnement
        
        return {
            "plan": BackupSubscription.FREE_PLAN,
            "workspace_id": workspace_id,
            "status": "active",
            "start_date": datetime.datetime.now().isoformat(),
            "end_date": (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat(),
            "limits": self.get_plan_limits(BackupSubscription.FREE_PLAN)
        }
    
    def update_workspace_subscription(self, workspace_id, plan):
        """
        Werk het backup abonnement bij voor een werkruimte
        
        Args:
            workspace_id: ID van de werkruimte
            plan: Nieuw abonnement type
            
        Returns:
            dict: Bijgewerkt abonnement
        """
        # In een echte implementatie zou dit in de database worden bijgewerkt
        # Voor nu maken we een dummy update
        
        return {
            "plan": plan,
            "workspace_id": workspace_id,
            "status": "active",
            "start_date": datetime.datetime.now().isoformat(),
            "end_date": (datetime.datetime.now() + datetime.timedelta(days=365)).isoformat(),
            "limits": self.get_plan_limits(plan)
        }