import os
from pymongo import MongoClient
from dotenv import load_dotenv
import streamlit as st

# Load root .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "debt_collector")

@st.cache_resource
def get_db():
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]
