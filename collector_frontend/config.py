import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    DB_NAME = os.getenv("DB_NAME", "debt_collector")
    raw_debug = os.getenv("DEBUG", "false")
    if isinstance(raw_debug, str):
        DEBUG = raw_debug.lower() == "true"
    else:
        DEBUG = bool(raw_debug)
