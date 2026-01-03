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
    """Retorna um selo de status colorido."""
    if is_active:
        return "🟢 Ativo"
    return "🔴 Inativo"

def safe_get(data, *keys, default=0):
    """Navega com segurança em dicionários aninhados."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data if data != {} else default

def test_mongo_connection(uri, db_name):
    """Testa a conexão com o MongoDB e retorna o status."""
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.server_info()
        db = client[db_name]
        # Tenta uma operação simples
        db.list_collection_names()
        return True, "✅ Conexão bem-sucedida"
    except Exception as e:
        return False, f"❌ Falha na conexão: {str(e)}"

def export_to_json(data, filename):
    """Cria um arquivo JSON para download."""
    json_str = json.dumps(data, indent=2, default=str)
    return json_str.encode('utf-8')

def show_loading(message="Carregando..."):
    """Exibe um spinner de carregamento."""
    return st.spinner(message)

def confirm_action(message, key=None):
    """Mostra uma caixa de confirmação para ações destrutivas."""
    if key:
        return st.checkbox(f"⚠️ {message}", key=key)
    return st.checkbox(f"⚠️ {message}")
