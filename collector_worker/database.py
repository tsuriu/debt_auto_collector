from pymongo import MongoClient
from config import Config
from loguru import logger

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
            collections = self.get_collections()
            report["details"]["collections"] = collections
            
            # 3. Check Critical Indices
            # Just listing them for now
            report["details"]["indices"] = {}
            for col_name in ["clients", "bills", "history_action_log"]:
                 if col_name in collections:
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
