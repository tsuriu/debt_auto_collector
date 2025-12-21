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
            
            logger.info("Database indices ensured.")
        except Exception as e:
            logger.error(f"Error creating indices: {e}")


def get_active_instances():
    db = Database().get_db()
    return list(db.instance_config.find({"status.active": True}))

# Deprecated: save_bills and get_existing_bill_ids are no longer used in main.py
