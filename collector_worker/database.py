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

    def ping(self):
        """Checks connectivity to MongoDB."""
        self.db.command('ping')
        return True

    def get_collections(self):
        """Returns list of collection names."""
        return self.db.list_collection_names()

    def get_indices(self, collection_name):
        """Returns list of index names for a specific collection."""
        return [i['name'] for i in self.db[collection_name].list_indexes()]

    def ensure_collections(self):
        """Ensures all required collections exist."""
        required = ["clients", "bills", "history_action_log", "last_reports", "data_reference", "instance_config", "metrics"]
        existing = self.get_collections()
        created = []
        
        for name in required:
            if name not in existing:
                self.db.create_collection(name)
                created.append(name)
        
        # Check for seeding
        if "instance_config" not in existing or self.db.instance_config.count_documents({}) == 0:
            self.seed_instance_config()
            
        return {"existing": [c for c in required if c in existing], "created": created}

    def ensure_indices(self):
        """Ensures all required indices exist."""
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

            # Metrics
            self.db.metrics.create_index([("instance_full_id", 1), ("timestamp", -1)])
            return True
        except Exception as e:
            logger.error(f"Error ensuring indices: {e}")
            raise

    def seed_instance_config(self):
        """Seeds instance_config from JSON file OR hardcoded fallback if missing."""
        try:
            # 1. Try to find the file
            paths = ["instance_data_sample.json", "../instance_data_sample.json", "/app/instance_data_sample.json"]
            data = None
            for p in paths:
                if os.path.exists(p):
                    with open(p, 'r') as f:
                        data = json.load(f)
                        logger.info(f"Loading seed data from {p}")
                    break
            
            # 2. Fallback to hardcoded sample if file not found
            if not data:
                logger.warning("No seed file found. Using hardcoded fallback sample.")
                data = {
                    "_id": {"$oid": "69263d581bdf47cf8b276136"},
                    "instance_name": "sample",
                    "erp": {
                        "type": "ixc",
                        "base_url": "https://ixc.sample.com.br/webservice/v1",
                        "auth": {"user_id": "", "user_token": "sample_token"},
                        "filial_id": [1],
                        "request_param": {
                            "default_page_size": 600,
                            "max_records": 50000,
                            "delay_between_pages": 150,
                            "safety_limit": 1000
                        }
                    },
                    "charger": {
                        "minimum_days_to_charge": 7,
                        "max_days_to_search": 30,
                        "dial_interval": 4,
                        "dial_per_day": 3
                    },
                    "asterisk": {
                        "host": "0.0.0.0",
                        "port": "8088",
                        "username": "admin",
                        "password": "admin",
                        "context": "auto-charger-context",
                        "extension": "start",
                        "channel_type": "SIP",
                        "channel": "biller-trunk",
                        "num_channel_available": 10,
                        "cdr_host": "0.0.0.0",
                        "cdr_port": "8080",
                        "cdr_username": "admin",
                        "cdr_password": "admin"
                    },
                    "status": {
                        "active": False,
                        "last_sync": "2025-11-25T22:10:00-03:00",
                        "last_error": None,
                        "health": "ok"
                    },
                    "metadata": {
                        "created_at": "2025-11-25T21:00:00-03:00",
                        "updated_at": "2025-11-25T22:10:00-03:00",
                        "description": "Instância do cliente X"
                    }
                }

            # 3. Insert into DB
            if data:
                # Convert $oid if present (found in file-based JSON)
                if "_id" in data and isinstance(data["_id"], dict) and "$oid" in data["_id"]:
                    data["_id"] = ObjectId(data["_id"]["$oid"])
                
                # Check duplication before insert
                if not self.db.instance_config.find_one({"_id": data["_id"]}):
                    self.db.instance_config.insert_one(data)
                    logger.info("Successfully seeded 'instance_config' collection.")
                    
        except Exception as e:
            logger.error(f"Seeding failed: {e}")

def get_active_instances():
    db = Database().get_db()
    return list(db.instance_config.find({"status.active": True}))

# Deprecated: save_bills and get_existing_bill_ids are no longer used in main.py
