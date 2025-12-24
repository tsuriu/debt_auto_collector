from pymongo import MongoClient
from config import Config
from loguru import logger
import json
import os
from bson import ObjectId

class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance.client = MongoClient(Config.MONGO_URI)
            cls._instance.db = cls._instance.client[Config.DB_NAME]
            logger.info(f"Connected to MongoDB: {Config.DB_NAME}")
        return cls._instance

    def get_db(self):
        return self.db

    def get_collections(self):
        return self.db.list_collection_names()

    def ensure_indices(self):
        try:
            # Clients
            self.db.clients.create_index([("instance_full_id", 1), ("id", 1)], unique=True)
            
            # Bills
            self.db.bills.create_index("full_id", unique=True)
            self.db.bills.create_index([("instance_full_id", 1), ("vencimento_status", 1)])
            
            # History Action Log
            self.db.history_action_log.create_index("full_id")
            self.db.history_action_log.create_index([("occurred_at", -1)])
            self.db.history_action_log.create_index("instance_full_id")
            
            # Compound Index for Dialer Performance
            self.db.history_action_log.create_index([
                ("instance_full_id", 1), 
                ("action", 1), 
                ("details.number", 1), 
                ("occurred_at", -1)
            ])
            
            logger.info("Database indices ensured.")
        except Exception as e:
            logger.error(f"Error creating indices: {e}")

    def ensure_collections(self):
        """
        Check for required collections. Note: MongoDB creates lazily.
        But we specifically need 'instance_config' to prompt the app to run.
        """
        report = {"created": [], "existing": []}
        try:
            required = ["clients", "bills", "history_action_log", "last_reports", "data_reference", "instance_config"]
            existing = self.get_collections()
            
            for r in required:
                if r not in existing:
                    logger.info(f"Collection '{r}' missing. Creating explicitly.")
                    self.db.create_collection(r)
                    report["created"].append(r)
                else:
                    report["existing"].append(r)
            
            # Auto-Seed instance_config if missing or empty
            # Re-check existing because we might have just created it
            if "instance_config" not in existing or self.db.instance_config.count_documents({}) == 0:
                self.seed_instance_config()
                
            return report
        except Exception as e:
            logger.error(f"Error ensuring collections: {e}")
            raise

    def seed_instance_config(self):
        """
        Looks for instance_data_sample.json in root or ../ and seeds it.
        """
        try:
            # Possible locations
            paths = ["instance_data_sample.json", "../instance_data_sample.json", "/app/instance_data_sample.json"]
            
            data = None
            for p in paths:
                if os.path.exists(p):
                    with open(p, 'r') as f:
                        data = json.load(f)
                    break
            
            if data:
                # Handle extended JSON (e.g. {"$oid": ...})
                if "_id" in data and "$oid" in data["_id"]:
                    data["_id"] = ObjectId(data["_id"]["$oid"])
                
                # Check duplication
                if not self.db.instance_config.find_one({"_id": data["_id"]}):
                    self.db.instance_config.insert_one(data)
                    logger.info(f"Seeded 'instance_config' from {p}")
            else:
                logger.warning("No seed file (instance_data_sample.json) found. 'instance_config' is empty.")
                
        except Exception as e:
            logger.error(f"Failed to seed instance_config: {e}")


    def verify_structure(self):
        """
        Verifies database connectivity and indices.
        Returns a dict with status details.
        """
        report = {"status": "ok", "details": {}}
        try:
            # 1. Ping
            self.db.command('ping')
            report["details"]["connection"] = "Connected"
            
            # 2. Check Collections
            coll_report = self.ensure_collections() 
            report["details"]["collections"] = coll_report
            
            # 3. Check Critical Indices
            self.ensure_indices() 
            
            # Detailed Indices Report
            report["details"]["indices"] = {}
            for col_name in coll_report["existing"] + coll_report["created"]:
                 idxs = list(self.db[col_name].list_indexes())
                 report["details"]["indices"][col_name] = [i['name'] for i in idxs]
            
        except Exception as e:
            report["status"] = "error"
            report["error"] = str(e)
            
        return report

def get_active_instances():
    db = Database().get_db()
    return list(db.instance_config.find({"status.active": True}))

# Deprecated: save_bills and get_existing_bill_ids are no longer used in main.py
