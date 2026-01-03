import streamlit as st
from db import get_db
from utils import test_mongo_connection, format_datetime
from utils_css import apply_light_theme
import os

st.set_page_config(
    page_title="Centro de Controle - Debt Collector",
    page_icon="🤖",
    layout="wide"
)

# Aplicar tema claro
apply_light_theme()

st.title("🤖 Centro de Controle - Debt Collector")

st.markdown("""
Bem-vindo à interface de gerenciamento do cobrador automático. Use a barra lateral para navegar entre:

- **📋 Instâncias**: Gerencie as configurações de suas instâncias ERP e Asterisk (CRUD).
- **📊 Dashboard**: Visualize métricas de cobrança, status de dívidas e desempenho do discador.
- **⚙️ Configurações**: Atualize as variáveis de ambiente globais do projeto (`.env`).
""")

# Health Check do Sistema
db = get_db()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DB_NAME", "debt_collector")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🔧 Status do Sistema")
    
    # Testar conexão com o banco de dados
    try:
        db.command('ping')
        st.success("✅ Banco de Dados: Conectado")
        
        # Obter estatísticas das coleções
        collections = db.list_collection_names()
        st.caption(f"Coleções: {len(collections)}")
    except Exception as e:
        st.error(f"❌ Banco de Dados: Desconectado")
        st.caption(f"Erro: {str(e)[:50]}...")

with col2:
    st.subheader("📊 Estatísticas Rápidas")
    
    try:
        # Contar instâncias ativas
        active_instances = db.instance_config.count_documents({"status.active": True})
        total_instances = db.instance_config.count_documents({})
        st.metric("Instâncias Ativas", active_instances, delta=f"{total_instances} total")
        
        # Timestamp das últimas métricas
        latest_metric = db.metrics.find_one({}, sort=[("timestamp", -1)])
        if latest_metric:
            last_update = format_datetime(latest_metric.get("timestamp"))
            st.caption(f"Últimas Métricas: {last_update}")
        else:
            st.caption("Nenhuma métrica coletada ainda")
            
    except Exception as e:
        st.warning("Não foi possível carregar as estatísticas")

with col3:
    st.subheader("🚀 Ações Rápidas")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📋 Instâncias", use_container_width=True):
            st.switch_page("pages/1_Instances.py")
    
    with col_b:
        if st.button("📊 Dashboard", use_container_width=True):
            st.switch_page("pages/2_Dashboard.py")
    
    if st.button("⚙️ Configurações", use_container_width=True):
        st.switch_page("pages/3_Settings.py")

# Prévia de Atividade Recente
st.divider()
st.subheader("⚡ Atividade Recente do Sistema")

try:
    recent_logs = list(db.history_action_log.find({}).sort("occurred_at", -1).limit(5))
    if recent_logs:
        for log in recent_logs:
            icon = "📞" if "dialer" in log.get("action", "") else "⚙️"
            time_str = format_datetime(log.get("occurred_at"))
            action = log.get("action", "unknown").replace("_", " ").title()
            # Tradução básica de ações conhecidas
            action_map = {
                "Clients Update": "Atualização de Clientes",
                "Bills Update": "Atualização de Faturas",
                "Dialer Job": "Execução do Discador",
                "Metrics Job": "Coleta de Métricas",
                "Reports Update": "Atualização de Relatórios"
            }
            display_action = action_map.get(action, action)
            st.write(f"{icon} **{time_str}** - {display_action}")
    else:
        st.info("Nenhuma atividade recente encontrada. O serviço pode ainda não estar rodando.")
except Exception as e:
    st.warning("Não foi possível carregar a atividade recente")

st.divider()
st.caption("💡 Dica: Habilite a atualização automática no Dashboard para modo de monitoramento em TV")
