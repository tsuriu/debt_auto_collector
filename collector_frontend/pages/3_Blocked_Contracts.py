import streamlit as st
import pandas as pd
from db import get_db
from datetime import datetime
from utils_css import apply_light_theme
from loguru import logger
import time

st.set_page_config(page_title="Blocked Contracts", layout="wide")
apply_light_theme()

# --- Custom CSS ---
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
    .status-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# --- Database Connection ---
try:
    db = get_db()
except Exception as e:
    st.error(f"Failed to connect to database: {e}")
    st.stop()

# --- Sidebar ---
st.sidebar.title("⚙️ Controls")

instances = list(db.instance_config.find({"status.active": True}, {"instance_name": 1, "erp.type": 1}))
if not instances:
    st.warning("No active instances found.")
    st.stop()

instance_options = [i["instance_name"] for i in instances]
selected_instance_name = st.sidebar.selectbox("Select Instance", instance_options)

inst_doc = next(i for i in instances if i["instance_name"] == selected_instance_name)
full_id = f"{selected_instance_name}-{inst_doc.get('erp',{}).get('type','ixc')}-{str(inst_doc['_id'])}"

def format_time_ago(dt):
    if not dt:
        return "Desconhecido"
    now = datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    if seconds < 60:
        return "Agora mesmo"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes}m atrás"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}h atrás"
    else:
        days = int(seconds // 86400)
        return f"{days}d atrás"

# --- Data Fetching ---
def get_latest_metrics(fid):
    return db.metrics.find_one({"instance_full_id": fid}, sort=[("timestamp", -1)])

def get_historical_metrics(fid, limit=48):    # Fetch last 24-48h roughly
    return list(db.metrics.find(
        {"instance_full_id": fid}, 
        {"timestamp": 1, "data.blocked_contracts": 1}, 
        sort=[("timestamp", -1)], 
        limit=limit
    ))

metrics_doc = get_latest_metrics(full_id)
hist_docs = get_historical_metrics(full_id)
blocked_data = {}
timestamp = None

if metrics_doc:
    timestamp = metrics_doc.get("timestamp")
    blocked_data = metrics_doc.get("data", {}).get("blocked_contracts", {})

# --- Header ---
col_head, col_time = st.columns([3, 1])
with col_head:
    st.markdown(f"## 🚫 Contratos Bloqueados <span style='font-size: 1rem; color: #64748b; font-weight: 400;'>({selected_instance_name})</span>", unsafe_allow_html=True)
with col_time:
    if timestamp:
        st.markdown(f"""
        <div style='display: flex; gap: 8px; justify-content: flex-end; margin-top: 5px;'>
            <div class='ctrl-box-last'>Última: {timestamp.strftime('%H:%M:%S')}</div>
            <div class='ctrl-box-time'>{format_time_ago(timestamp)}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Historical Data Processing ---
# We need to process history for the charts
# Structure: data -> blocked_contracts -> list_by -> {field} -> {value: [list]}
# Count len(list) for each value.

hist_data_internet = {}
hist_data_speed = {}
timestamps = []

# --- Label Mappings ---
speed_labels = {
    "N": "Normal",
    "R": "Reduzida"
}
internet_labels = {
    "D": "Desativado",
    "CM": "Bloqueio Manual",
    "CA": "Bloqueio Automático",
    "FA": "Financeiro em atraso",
    "AA": "Aguardando Assinatura"
}
# Note: "A" (Ativo) ignored as requested.

history_records = []
for doc in reversed(hist_docs):
    ts = doc.get("timestamp")
    if not ts: continue
    
    b_data = doc.get("data", {}).get("blocked_contracts", {}).get("list_by", {})
    
    # Aggregates for this timestamp
    row = {"timestamp": ts.strftime("%H:%M")}
    
    # Internet
    i_groups = b_data.get("status_internet", {})
    for k, v in i_groups.items():
        if k == "A": continue # Ignore Ativo
        label = internet_labels.get(k, k)
        row[f"internet_{label}"] = len(v)
        
    # Speed
    s_groups = b_data.get("status_velocidade", {})
    for k, v in s_groups.items():
        label = speed_labels.get(k, k)
        row[f"speed_{label}"] = len(v)
        
    history_records.append(row)

df_hist = pd.DataFrame(history_records).fillna(0)

# --- Top Charts ---
c_chart1, c_chart2 = st.columns(2)

# Colors
speed_colors = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#64748b"]
net_colors = ["#ef4444", "#f97316", "#22c55e", "#06b6d4", "#6366f1"]

from streamlit_echarts import st_echarts

with c_chart1:
    st.markdown("##### 🚀 Status Velocidade (Evolução)")
    if not df_hist.empty:
        # Extract Speed columns
        speed_cols = [c for c in df_hist.columns if c.startswith("speed_")]
        series_speed = []
        counters_speed = {}
        for idx, col in enumerate(speed_cols):
            name = col.replace("speed_", "")
            val = df_hist[col].iloc[-1] if not df_hist.empty else 0
            counters_speed[name] = {"val": int(val), "color": speed_colors[idx % len(speed_colors)]}
            
            series_speed.append({
                "name": name,
                "type": "line",
                "stack": "Total",
                "areaStyle": {},
                "emphasis": {"focus": "series"},
                "data": df_hist[col].tolist()
            })
            
        options_speed = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": [{"type": "category", "boundaryGap": False, "data": df_hist["timestamp"].tolist()}],
            "yAxis": [{"type": "value"}],
            "series": series_speed,
            "color": speed_colors
        }
        st_echarts(options=options_speed, height="300px", key="blocked_speed_chart")
        
        # Counters Container
        st.markdown("<div style='display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;'>", unsafe_allow_html=True)
        cols_c = st.columns(len(counters_speed))
        for i, (name, data) in enumerate(counters_speed.items()):
            with cols_c[i]:
                st.markdown(f"""
                <div style='background-color: {data['color']}20; border: 1px solid {data['color']}; border-radius: 8px; padding: 10px; text-align: center; height: 90px; display: flex; flex-direction: column; justify-content: center;'>
                     <div style='font-size: 0.75rem; color: {data['color']}; font-weight: 600; line-height: 1.1;'>{name}</div>
                     <div style='font-size: 1.2rem; color: {data['color']}; font-weight: 800;'>{data['val']}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        st.info("Sem dados históricos.")

with c_chart2:
    st.markdown("##### 🌐 Status Internet (Evolução)")
    if not df_hist.empty:
        # Extract Internet columns
        net_cols = [c for c in df_hist.columns if c.startswith("internet_")]
        series_net = []
        counters_net = {}
        for idx, col in enumerate(net_cols):
            name = col.replace("internet_", "")
            val = df_hist[col].iloc[-1] if not df_hist.empty else 0
            counters_net[name] = {"val": int(val), "color": net_colors[idx % len(net_colors)]}
            
            series_net.append({
                "name": name,
                "type": "bar",
                "stack": "Total",
                "emphasis": {"focus": "series"},
                "data": df_hist[col].tolist()
            })
            
        options_net = {
             "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": [{"type": "category", "data": df_hist["timestamp"].tolist()}],
            "yAxis": [{"type": "value"}],
            "series": series_net,
            "color": net_colors
        }
        st_echarts(options=options_net, height="300px", key="blocked_net_chart")
        
        # Counters Container
        st.markdown("<div style='display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px;'>", unsafe_allow_html=True)
        cols_c2 = st.columns(len(counters_net))
        for i, (name, data) in enumerate(counters_net.items()):
            with cols_c2[i]:
                st.markdown(f"""
                <div style='background-color: {data['color']}20; border: 1px solid {data['color']}; border-radius: 8px; padding: 10px; text-align: center; height: 90px; display: flex; flex-direction: column; justify-content: center;'>
                     <div style='font-size: 0.75rem; color: {data['color']}; font-weight: 600; line-height: 1.1;'>{name}</div>
                     <div style='font-size: 1.2rem; color: {data['color']}; font-weight: 800;'>{data['val']}</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        st.info("Sem dados históricos.")


st.markdown("<br>", unsafe_allow_html=True)

# --- Analysis Logic for Table ---
list_by = blocked_data.get("list_by", {})
# We need to flattening unique contracts. 
# A contract might appear in multiple lists? 
# Usually 'list_by' assumes partition, but if we have multiple grouping dimensions, we just pick ONE dimension to iterate and flatten,
# Or iterate distinct IDs if we have a full list.
# The MetricsService `all_blocked` fetch suggests we have all contracts.
# Status Internet group should contain all valid contracts (or N/A). So iterating that group is sufficient.

flat_rows = []
seen_ids = set()

# Iterate over status_internet groups (primary partition)
# AND status_velocidade groups just in case some are missing?
# Actually, the service fetches ALL and groups them. So every contract is in exactly one internet_status group.
for status, items in list_by.get("status_internet", {}).items():
    for item in items:
        cid = item.get("id")
        if cid in seen_ids: continue
        seen_ids.add(cid)
        
        flat_rows.append({
            "ID Contrato": item.get("id"),
            "ID Cliente": item.get("id_cliente"),
            "Cliente": item.get("razao") or "Desconhecido",
            "Status Internet": item.get("status_internet"),
            "Status Velocidade": item.get("status_velocidade"),
            "Data Suspensão": item.get("data_inicial_suspensao"),
        })
        
        # Calculate 'Dias Suspenso'
        d_susp = item.get("data_inicial_suspensao")
        days_diff = 0
        if d_susp:
            try:
                if isinstance(d_susp, str):
                    # Attempt common formats
                    # IXC often sends YYYY-MM-DD
                    d_obj = pd.to_datetime(d_susp).date()
                elif isinstance(d_susp, datetime):
                    d_obj = d_susp.date()
                else:
                    d_obj = None
                
                if d_obj:
                    days_diff = (datetime.now().date() - d_obj).days
            except Exception:
                days_diff = 0
        
        flat_rows[-1]["Dias Suspenso"] = days_diff


# --- Days Suspended Chart ---
if flat_rows:
    st.markdown("##### 📅 Distribuição por Dias de Suspensão")
    df_chart = pd.DataFrame(flat_rows)
    # Count frequencies
    if "Dias Suspenso" in df_chart.columns:
        counts = df_chart["Dias Suspenso"].value_counts().sort_index()
        
        # Prepare data for ECharts
        # x_data = [str(d) for d in counts.index]
        # But maybe too many bars?
        # Let's show all for now as requested.
        
        x_data = counts.index.astype(str).tolist()
        y_data = counts.values.tolist()
        
        options_days = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"left": "3%", "right": "4%", "bottom": "10%", "containLabel": True},
            "xAxis": [{"type": "category", "data": x_data, "name": "Dias"}],
            "yAxis": [{"type": "value", "name": "Contratos"}],
            "series": [
                {
                    "name": "Contratos",
                    "type": "bar",
                    "data": y_data,
                    "itemStyle": {"color": "#6366f1"}
                }
            ]
        }
        st_echarts(options=options_days, height="300px", key="days_suspended_chart")
        st.markdown("<br>", unsafe_allow_html=True)


# --- Single Table ---
st.markdown("##### 📋 Detalhes dos Contratos")
if flat_rows:
    df_table = pd.DataFrame(flat_rows)
    
    # Styling for white background is default in Streamlit Light Mode, but we can force some CSS wrapper if needed.
    # The user asked "Use white background". 
    # Let's ensure columns are strings/ints as appropriate
    df_table["ID Contrato"] = df_table["ID Contrato"].astype(str)
    df_table["ID Cliente"] = df_table["ID Cliente"].astype(str)
    
    # Increase height to show more lines (e.g. 500-600px instead of default)
    st.dataframe(
        df_table, 
        width="stretch", 
        hide_index=True,
        height=800,
        column_config={
            "Data Suspensão": st.column_config.DateColumn("Data Suspensão", format="DD/MM/YYYY"),
            "Dias Suspenso": st.column_config.NumberColumn("Dias Suspenso", format="%d")
        }
    )
    
    # Add CSS to force dataframe background to white just in case
    st.markdown("""
    <style>
    div[data-testid="stDataFrame"] > div {
        background-color: white !important; /* Force white background on dataframe container */
    }
    </style>
    """, unsafe_allow_html=True)

else:
    st.info("Nenhum contrato bloqueado encontrado.")

# Auto refresh every 60 seconds
time.sleep(60)
st.rerun()
