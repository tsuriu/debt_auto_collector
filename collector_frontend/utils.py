"""Shared utility functions for the Streamlit frontend."""
import streamlit as st
from datetime import datetime
import json
from pymongo import MongoClient

def format_currency(amount):
    """Format a number as Brazilian Real currency."""
    return f"R$ {amount:,.2f}"

def format_datetime(dt):
    """Format datetime for display."""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except:
            return dt
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"

def status_badge(is_active):
    """Return a colored status badge."""
    if is_active:
        return "🟢 Active"
    return "🔴 Inactive"

def safe_get(data, *keys, default=0):
    """Safely navigate nested dictionaries."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data if data != {} else default

def test_mongo_connection(uri, db_name):
    """Test MongoDB connection and return status."""
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.server_info()
        db = client[db_name]
        # Try a simple operation
        db.list_collection_names()
        return True, "✅ Connection successful"
    except Exception as e:
        return False, f"❌ Connection failed: {str(e)}"

def export_to_json(data, filename):
    """Create a downloadable JSON file."""
    json_str = json.dumps(data, indent=2, default=str)
    return json_str.encode('utf-8')

def show_loading(message="Loading..."):
    """Display a loading spinner."""
    return st.spinner(message)

def confirm_action(message, key=None):
    """Show a confirmation dialog for destructive actions."""
    if key:
        return st.checkbox(f"⚠️ {message}", key=key)
    return st.checkbox(f"⚠️ {message}")
