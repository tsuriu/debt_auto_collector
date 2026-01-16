import streamlit as st
import pandas as pd
from db import get_db
from datetime import datetime
import time
from utils import format_currency
from utils_css import apply_light_theme
from loguru import logger
from streamlit_echarts import st_echarts

st.set_page_config(page_title="Painel de Cobrança", layout="wide")

# Apply shared light theme
apply_light_theme()

# Custom CSS for this dashboard
st.markdown("""
<style>
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .kpi-card {
        background-color: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .kpi-title {
        color: #64748b;
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    .kpi-value {
        color: #0f172a;
        font-size: 2rem;
        font-weight: 700;
    }
    .ready-call {
        color: #ef4444 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Database Connection ---
try:
    db = get_db()
except Exception as e:
    st.error(f"❌ Falha na conexão com o banco de dados: {e}")
    st.stop()

# --- Page Header ---
st.markdown("## 💰 Painel de Cobrança <span style='font-size: 1rem; color: #64748b; font-weight: 400;'>| Foco em Contatos Manuais</span>", unsafe_allow_html=True)

# --- Sidebar Controls ---
st.sidebar.title("⚙️ Filtros")

# Instance Selection
instances = list(db.instance_config.find({"status.active": True}, {"instance_name": 1, "erp.type": 1}))
if not instances:
    st.warning("Nenhuma instância ativa encontrada.")
    st.stop()

instance_options = [i["instance_name"] for i in instances]
selected_instance_name = st.sidebar.selectbox("Selecionar Instância", instance_options)

inst_doc = next(i for i in instances if i["instance_name"] == selected_instance_name)
full_id = f"{selected_instance_name}-{inst_doc.get('erp',{}).get('type','ixc')}-{str(inst_doc['_id'])}"

# --- Data Fetching Functions ---
def get_expired_bills(fid):
    # Fetch bills with status A (unpaid) and expired
    return list(db.bills.find(
        {"instance_full_id": fid, "vencimento_status": "expired", "status": "A"},
        {"_id": 0}
    ))

def get_blocked_contract_info(fid):
    # Returns a map of id_contract -> info for quick lookup
    cursor = db.blocked_contracts.find(
        {"instance_full_id": fid}, 
        {"id_contract": 1, "status_internet": 1, "bill_status": 1, "desbloqueio_confianca_ativo": 1, "razao": 1, "_id": 0}
    )
    return {c.get("id_contract"): {
        "status_internet": c.get("status_internet"),
        "bill_status": c.get("bill_status"),
        "trust": c.get("desbloqueio_confianca_ativo") == "S",
        "razao": c.get("razao")
    } for c in cursor}

# --- Label Mappings ---
internet_labels = {
    "D": "Desativado",
    "CM": "Bloqueio Manual",
    "CA": "Bloqueio Automático",
    "FA": "Financeiro em atraso",
    "AA": "Aguardando Assinatura",
    "A": "Ativo"
}

bill_labels = {
    "A": "Aberto",
    "R": "Recebido",
    "C": "Cancelado"
}

# --- Initial Data Load ---
bills_raw = get_expired_bills(full_id)
blocked_map = get_blocked_contract_info(full_id)

if not bills_raw:
    st.info("Nenhuma fatura vencida pendente encontrada para esta instância.")
    st.stop()

# Prepare Dataframe for filtering
df_all = pd.DataFrame(bills_raw)

# Safe conversion of dates
if 'data_vencimento' in df_all.columns:
    df_all['data_vencimento'] = pd.to_datetime(df_all['data_vencimento']).dt.date

# Filter for Due Date in Sidebar
available_dates = sorted(list(df_all['data_vencimento'].unique()), reverse=False)

# "Some way to click" -> Use a selectbox but maybe also provide a 'Pills' style interface if available
st.sidebar.markdown("### 📅 Vencimento")
selected_date = st.sidebar.selectbox(
    "Selecione uma data para focar",
    options=["Todas"] + available_dates,
    index=0
)

if selected_date != "Todas":
    df_filtered = df_all[df_all['data_vencimento'] == selected_date]
else:
    df_filtered = df_all

# --- Join with Blocked Status and Calculate Action List ---
def hydrate_and_categorize(df, blocked_map):
    rows = []
    for _, bill in df.iterrows():
        cid = bill.get("id_contrato")
        contract_data = blocked_map.get(cid, {"status_internet": "A", "bill_status": "A", "trust": False})
        
        status_internet_code = contract_data.get("status_internet")
        bill_status_code = contract_data.get("bill_status")
        is_trust = contract_data.get("trust")
        
        status_internet = internet_labels.get(status_internet_code, status_internet_code)
        if is_trust:
            status_internet = f"{status_internet} (DC)"
        
        status_fatura = bill_labels.get(bill_status_code, bill_status_code)
        
        age = bill.get("expired_age", 0)
        
        rows.append({
            "Cliente": contract_data.get("razao") if contract_data.get("razao") else bill.get("razao") or "Desconhecido",
            "ID Contrato": cid,
            "DC": "Sim" if is_trust else "Não",
            "is_trust": is_trust,
            "status_code": status_internet_code,
            "Status Fatura": status_fatura,
            "Status Contrato": status_internet,
            "Vencimento": bill.get("data_vencimento"),
            "Valor": bill.get("valor_aberto"),
            "Atraso": age,
            "Precisa_Contato": age >= 8
        })
    return pd.DataFrame(rows)

df_hydrated = hydrate_and_categorize(df_filtered, blocked_map)

# --- KPI Section ---
total_overdue = len(df_hydrated["ID Contrato"].unique())
ready_for_call = len(df_hydrated[df_hydrated["Precisa_Contato"] == True]["ID Contrato"].unique())
trust_count = len(df_hydrated[df_hydrated["is_trust"] == True]["ID Contrato"].unique())

kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-title'>📄 Contratos em Atraso</div>
        <div class='kpi-value'>{total_overdue}</div>
    </div>
    """, unsafe_allow_html=True)

with kpi2:
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-title'>🔓 Desbloqueio Confiança</div>
        <div class='kpi-value' style='color: #f59e0b;'>{trust_count}</div>
        <div style='font-size: 0.7rem; color: #94a3b8; margin-top: 5px;'>(Somente contratos em atraso)</div>
    </div>
    """, unsafe_allow_html=True)

with kpi3:
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-title'>📞 Pronto para Contato (8+ dias)</div>
        <div class='kpi-value {"ready-call" if ready_for_call > 0 else ""}'>{ready_for_call}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Chart Section: Distribution by Vencimento (Stacked) ---
st.markdown(f"### 📊 Distribuição por Vencimento (Janela de Quantidade)")
df_chart = df_hydrated.groupby(["Vencimento", "DC"]).agg({"Cliente": "count"}).reset_index()
df_chart = df_chart.pivot(index="Vencimento", columns="DC", values="Cliente").fillna(0).reset_index()
df_chart = df_chart.sort_values("Vencimento")

if not df_chart.empty:
    vencimento_dates = [d.strftime("%d/%m") for d in df_chart["Vencimento"]]
    regular_data = df_chart["Não"].tolist() if "Não" in df_chart.columns else [0] * len(df_chart)
    trust_data = df_chart["Sim"].tolist() if "Sim" in df_chart.columns else [0] * len(df_chart)

    options_vencimento = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": ["Comum", "Desbl. Confiança"]},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
        "xAxis": [{"type": "category", "data": vencimento_dates}],
        "yAxis": [{"type": "value", "name": "Quantidade"}],
        "series": [
            {
                "name": "Comum",
                "type": "bar",
                "stack": "total",
                "data": regular_data,
                "itemStyle": {"color": "#5b73e8"}
            },
            {
                "name": "Desbl. Confiança",
                "type": "bar",
                "stack": "total",
                "data": trust_data,
                "itemStyle": {"color": "#f59e0b"}
            }
        ]
    }
    st_echarts(options=options_vencimento, height="350px", key="vencimento_chart_stacked")
else:
    st.info("Sem dados para o período selecionado.")

st.markdown("<br>", unsafe_allow_html=True)

# --- Action List Section ---
st.markdown("### 📋 Lista de Ação: Contato Manual Imediato")
st.markdown("<p style='color: #64748b; margin-top: -10px;'>Clientes com 8 dias ou mais de atraso e que já possuem contrato bloqueado ou com Desbloqueio Confiança.</p>", unsafe_allow_html=True)

# Robust Filter: Overdue AND (Status NOT 'A' OR DC True)
df_action = df_hydrated[
    (df_hydrated["Precisa_Contato"] == True) & 
    ((df_hydrated["status_code"] != "A") | (df_hydrated["is_trust"] == True))
].sort_values("Atraso", ascending=True)

if not df_action.empty:
    # Keep only important columns
    display_cols = ["Cliente", "DC", "Status Contrato", "Vencimento", "Valor", "Atraso"]
    st.dataframe(
        df_action[display_cols],
        width="stretch",
        hide_index=True,
        height=450,
        column_config={
            "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
            "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
            "Atraso": st.column_config.NumberColumn("Dias de Atraso", format="%d"),
            "DC": st.column_config.TextColumn("DC", width="small")
        }
    )
else:
    st.success("🎉 Nenhum cliente requer contato manual imediato no momento.")

st.markdown("---")

# --- All Overdue (Other) Section ---
with st.expander("🔍 Ver todas as faturas vencidas (Menos de 8 dias)"):
    df_others = df_hydrated[df_hydrated["Precisa_Contato"] == False].sort_values("Atraso", ascending=True)
    if not df_others.empty:
        st.dataframe(
            df_others.drop(columns=["Precisa_Contato"]),
            width="stretch",
            hide_index=True,
            column_config={
                "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                "Atraso": st.column_config.NumberColumn("Dias de Atraso", format="%d"),
                "ID Contrato": st.column_config.TextColumn("ID Contrato"),
                "Status Fatura": st.column_config.TextColumn("Status Fatura"),
                "DC": st.column_config.TextColumn("DC", width="small")
            }
        )
    else:
        st.info("Nenhuma outra fatura vencida encontrada.")
