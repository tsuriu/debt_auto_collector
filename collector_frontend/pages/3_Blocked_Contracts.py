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

def get_all_blocked_contracts(fid):
    # Returns a map of contract_id -> contract_doc for easy lookup
    cursor = db.blocked_contracts.find({"instance_full_id": fid}, {"_id": 0})
    return {c.get("id"): c for c in cursor}

def get_expired_bills(fid):
    return list(db.bills.find({"instance_full_id": fid, "vencimento_status": "expired"}, {"_id": 0}))

metrics_doc = get_latest_metrics(full_id)
hist_docs = get_historical_metrics(full_id)
blocked_map = get_all_blocked_contracts(full_id)
expired_bills = get_expired_bills(full_id)

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
    
    b_data = doc.get("data", {}).get("blocked_contracts", {})
    
    # Aggregates for this timestamp
    row = {"timestamp": ts.strftime("%H:%M")}
    
    # Try new format 'counts' first, then fallback to old format 'list_by'
    counts_data = b_data.get("counts", {})
    list_by_data = b_data.get("list_by", {})
    
    # Internet
    i_counts = counts_data.get("status_internet")
    if i_counts is None: # Fallback to old format
        i_groups = list_by_data.get("status_internet", {})
        i_counts = {k: len(v) for k, v in i_groups.items()}
    
    for k, val in i_counts.items():
        if k == "A": continue # Ignore Ativo
        label = internet_labels.get(k, k)
        row[f"internet_{label}"] = val
        
    # Speed
    s_counts = counts_data.get("status_velocidade")
    if s_counts is None: # Fallback to old format
        s_groups = list_by_data.get("status_velocidade", {})
        s_counts = {k: len(v) for k, v in s_groups.items()}
        
    for k, val in s_counts.items():
        label = speed_labels.get(k, k)
        row[f"speed_{label}"] = val
        
    history_records.append(row)

df_hist = pd.DataFrame(history_records).fillna(0)

# Colors
speed_colors = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#64748b"]
net_colors = ["#ef4444", "#f97316", "#22c55e", "#06b6d4", "#6366f1"]

from streamlit_echarts import st_echarts

# --- Evolution Data Processing ---
speed_cols = [c for c in df_hist.columns if c.startswith("speed_")]
net_cols = [c for c in df_hist.columns if c.startswith("internet_")]

counters_speed = {}
series_speed = []
for idx, col in enumerate(speed_cols):
    name = col.replace("speed_", "")
    val = df_hist[col].iloc[-1] if not df_hist.empty else 0
    counters_speed[name] = {"val": int(val), "color": speed_colors[idx % len(speed_colors)]}
    series_speed.append({
        "name": name, "type": "line", "stack": "Total", "areaStyle": {},
        "emphasis": {"focus": "series"}, "data": df_hist[col].tolist()
    })

counters_net = {}
series_net = []
for idx, col in enumerate(net_cols):
    name = col.replace("internet_", "")
    val = df_hist[col].iloc[-1] if not df_hist.empty else 0
    counters_net[name] = {"val": int(val), "color": net_colors[idx % len(net_colors)]}
    series_net.append({
        "name": name, "type": "bar", "stack": "Total",
        "emphasis": {"focus": "series"}, "data": df_hist[col].tolist()
    })

# --- Evolution and Counters Row ---
col1, col2, col3, col4 = st.columns([3, 3, 1.2, 1.8])

with col1:
    st.markdown("##### 🚀 Status Velocidade (Evolução)")
    if not df_hist.empty:
        options_speed = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": [{"type": "category", "boundaryGap": False, "data": df_hist["timestamp"].tolist()}],
            "yAxis": [{"type": "value"}],
            "series": series_speed,
            "color": speed_colors
        }
        st_echarts(options=options_speed, height="350px", key="blocked_speed_chart")
    else:
        st.info("Sem dados históricos.")

with col2:
    st.markdown("##### 🌐 Status Internet (Evolução)")
    if not df_hist.empty:
        options_net = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": [{"type": "category", "data": df_hist["timestamp"].tolist()}],
            "yAxis": [{"type": "value"}],
            "series": series_net,
            "color": net_colors
        }
        st_echarts(options=options_net, height="350px", key="blocked_net_chart")
    else:
        st.info("Sem dados históricos.")

with col3:
    st.markdown("<div style='height: 45px;'></div>", unsafe_allow_html=True) # Spacer to align with chart titles
    if counters_speed:
        st.markdown("<div style='height: 60px; display: flex; flex-direction: column; justify-content: center; gap: 20px;'>", unsafe_allow_html=True)
        for name, data in counters_speed.items():
            st.markdown(f"""
            <div style='background-color: {data['color']}20; border: 1px solid {data['color']}; border-radius: 8px; padding: 10px; text-align: center; height: 110px; display: flex; flex-direction: column; justify-content: center;'>
                 <div style='font-size: 0.85rem; color: {data['color']}; font-weight: 600; line-height: 1.1;'>{name}</div>
                 <div style='font-size: 1.6rem; color: {data['color']}; font-weight: 800;'>{data['val']}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

with col4:
    st.markdown("<div style='height: 45px;'></div>", unsafe_allow_html=True) # Spacer to align with chart titles
    if counters_net:
        st.markdown("<div style='height: 20px; display: flex; flex-direction: column; justify-content: center; gap: 10px;'>", unsafe_allow_html=True)
        for name, data in counters_net.items():
            st.markdown(f"""
            <div style='background-color: {data['color']}20; border: 1px solid {data['color']}; border-radius: 8px; padding: 8px; text-align: center; height: 75px; display: flex; flex-direction: column; justify-content: center;'>
                 <div style='font-size: 0.75rem; color: {data['color']}; font-weight: 600; line-height: 1.1;'>{name}</div>
                 <div style='font-size: 1.2rem; color: {data['color']}; font-weight: 800;'>{data['val']}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# --- New Stats Charts ---
st.markdown("<br>", unsafe_allow_html=True)
c_stat1, c_stat2, c_stat3 = st.columns(3)

stats = blocked_data.get("stats", {})

with c_stat1:
    st.markdown("##### 🌐 Tipo Cliente")
    tc_stats = stats.get("tipo_cliente", {})
    if tc_stats:
        # Convert to list of dicts for easier processing
        tc_data_list = []
        for name, counts in tc_stats.items():
            total = counts.get("short", 0) + counts.get("long", 0)
            tc_data_list.append({"Tipo": name, "short": counts.get("short", 0), "long": counts.get("long", 0), "total": total})
        
        df_tc = pd.DataFrame(tc_data_list).sort_values("total", ascending=False).head(10)
        
        options_tc = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "25%", "containLabel": True},
            "xAxis": {"type": "category", "data": df_tc['Tipo'].tolist(), "axisLabel": {"interval": 0, "rotate": 35}},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": "≤ 7 dias", "type": "bar", "stack": "total",
                    "data": df_tc['short'].tolist(), "itemStyle": {"color": "#10b981"}
                },
                {
                    "name": "> 7 dias", "type": "bar", "stack": "total",
                    "data": df_tc['long'].tolist(), "itemStyle": {"color": "#ef4444"}
                }
            ]
        }
        st_echarts(options=options_tc, height="350px", key="blocked_tipo_chart")

with c_stat2:
    st.markdown("##### 🗺️ Bairro")
    b_stats = stats.get("bairro", {})
    if b_stats:
        b_data_list = []
        for name, counts in b_stats.items():
            total = counts.get("short", 0) + counts.get("long", 0)
            b_data_list.append({"Bairro": name, "short": counts.get("short", 0), "long": counts.get("long", 0), "total": total})
        
        df_b = pd.DataFrame(b_data_list).sort_values("total", ascending=False).head(10)
        
        options_b = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "25%", "containLabel": True},
            "xAxis": {"type": "category", "data": df_b['Bairro'].tolist(), "axisLabel": {"interval": 0, "rotate": 35}},
            "yAxis": {"type": "value"},
            "series": [
                {
                    "name": "≤ 7 dias", "type": "bar", "stack": "total",
                    "data": df_b['short'].tolist(), "itemStyle": {"color": "#10b981"}
                },
                {
                    "name": "> 7 dias", "type": "bar", "stack": "total",
                    "data": df_b['long'].tolist(), "itemStyle": {"color": "#ef4444"}
                }
            ]
        }
        st_echarts(options=options_b, height="350px", key="blocked_bairro_chart")

with c_stat3:
    st.markdown("##### ⏳ Dívida por Atraso (Dias)")
    age_stats = stats.get("expired_age", {})
    if age_stats:
        # Sort age stats by the numeric value of the key
        sorted_age_keys = sorted(age_stats.keys(), key=lambda x: int(x) if x.isdigit() else 999)
        
        # Get unique statuses for series
        unique_statuses = set()
        for s_dict in age_stats.values():
            unique_statuses.update(s_dict.keys())
        
        status_series = []
        for i, status in enumerate(sorted(unique_statuses)):
            label = internet_labels.get(status, status)
            data_points = []
            for k in sorted_age_keys:
                dp_val = age_stats[k].get(status, 0)
                data_points.append(dp_val)
            
            # Color coding based on age category for non-stacked simple bars? 
            # No, user wants vertical stacked. So we stack by status.
            # But the user also wants "separed colors to contracts with bills.expired_age <= 7 and > 7".
            # For this age chart, X-axis IS the age. So the color difference can be visual.
            # We can use visualMap or color specific data items.
            
            # For simplicity and clarity, let's keep the stacks by status and use colors from net_colors.
            status_series.append({
                "name": label, "type": "bar", "stack": "total",
                "data": data_points,
                "itemStyle": {"color": net_colors[i % len(net_colors)]}
            })
        
        options_age = {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "legend": {"top": 0},
            "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
            "xAxis": {"type": "category", "data": [f"{k}d" for k in sorted_age_keys]},
            "yAxis": {"type": "value"},
            "series": [
                *status_series,
                # Use markArea on the first series to highlight groups
                {
                    "name": "Background", "type": "bar", "stack": "total", "data": [0] * len(sorted_age_keys),
                    "markArea": {
                        "silent": True,
                        "itemStyle": {"color": "rgba(110, 110, 110, 0.05)"},
                        "data": [
                            [{"name": "≤ 7d", "xAxis": "1d" if "1" in sorted_age_keys else sorted_age_keys[0]}, {"xAxis": "7d"}],
                            [{"name": "> 7d", "xAxis": "8d" if "8" in sorted_age_keys else sorted_age_keys[min(7, len(sorted_age_keys)-1)]}, {"xAxis": sorted_age_keys[-1]}]
                        ]
                    }
                }
            ],
            # Add visualMap to highlight short vs long columns background or similar?
            # Or just let the users see the gap.
            "graphic": [
                {
                    "type": "text", "left": "center", "top": "bottom",
                    "style": {"text": "≤ 7 dias (Curto Prazo)  |  > 7 dias (Longo Prazo)", "fill": "#64748b", "fontSize": 10}
                }
            ]
        }
        st_echarts(options=options_age, height="350px", key="blocked_age_chart")
    else:
        st.info("Dados de vencimento não disponíveis.")

st.markdown("<br>", unsafe_allow_html=True)

# --- Analysis Logic for Table ---
# We need to flattening unique contracts. 
# A contract might appear in multiple lists? 
# Usually 'list_by' assumes partition, but if we have multiple grouping dimensions, we just pick ONE dimension to iterate and flatten,
# Or iterate distinct IDs if we have a full list.
# The MetricsService `all_blocked` fetch suggests we have all contracts.
# Status Internet group should contain all valid contracts (or N/A). So iterating that group is sufficient.

flat_rows = []
for bill in expired_bills:
    cid = bill.get("id_contrato")
    contract = blocked_map.get(cid)
    
    # Format status
    if contract:
        i_status = internet_labels.get(contract.get("status_internet"), contract.get("status_internet"))
        s_status = speed_labels.get(contract.get("status_velocidade"), contract.get("status_velocidade"))
        status_bloqueio = f"🌐 {i_status} | 🚀 {s_status}"
    else:
        status_bloqueio = "✅ Ativo / Não Bloqueado"

    flat_rows.append({
        "ID Fatura": bill.get("id"),
        "ID Contrato": cid,
        "Cliente": bill.get("razao") or "Desconhecido",
        "Bairro": bill.get("bairro"),
        "Tipo Cliente": bill.get("tipo_cliente"),
        "Valor": bill.get("valor_aberto"),
        "Vencimento": bill.get("data_vencimento"),
        "Dias Atraso": bill.get("expired_age"),
        "Status Bloqueio": status_bloqueio
    })
    # Calculate 'Dias Suspenso' (from contract data if available)
    days_susp = 0
    if contract:
        d_susp = contract.get("data_inicial_suspensao")
        if d_susp:
            try:
                if isinstance(d_susp, str):
                    d_obj = pd.to_datetime(d_susp).date()
                elif isinstance(d_susp, datetime):
                    d_obj = d_susp.date()
                else:
                    d_obj = None
                
                if d_obj:
                    days_susp = (datetime.now().date() - d_obj).days
            except Exception:
                days_susp = 0
    
    flat_rows[-1]["Dias Suspenso"] = days_susp


# --- Table Section ---
st.markdown("---")
st.markdown("### 📋 Detalhes das Faturas em Atraso")

if flat_rows:
    df_all = pd.DataFrame(flat_rows)
    # Define important columns
    important_cols = ["ID Fatura", "Cliente", "Valor", "Vencimento", "Dias Atraso", "Status Bloqueio"]
    
    # Split by delay
    df_short = df_all[df_all["Dias Atraso"] <= 7][important_cols].sort_values("Dias Atraso", ascending=False)
    df_long = df_all[df_all["Dias Atraso"] > 7][important_cols].sort_values("Dias Atraso", ascending=False)

    col_t1, col_t2 = st.columns(2)
    
    with col_t1:
        st.markdown("##### ⏳ Curto Prazo (≤ 7 dias)")
        if not df_short.empty:
            df_short["ID Fatura"] = df_short["ID Fatura"].astype(str)
            st.dataframe(
                df_short,
                width="stretch",
                hide_index=True,
                height=400,
                column_config={
                    "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                    "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "Dias Atraso": st.column_config.NumberColumn("Atraso", format="%d")
                }
            )
        else:
            st.info("Nenhuma fatura nesta categoria.")

    with col_t2:
        st.markdown("##### 📅 Longo Prazo (> 7 dias)")
        if not df_long.empty:
            df_long["ID Fatura"] = df_long["ID Fatura"].astype(str)
            st.dataframe(
                df_long,
                width="stretch",
                hide_index=True,
                height=400,
                column_config={
                    "Vencimento": st.column_config.DateColumn("Vencimento", format="DD/MM/YYYY"),
                    "Valor": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "Dias Atraso": st.column_config.NumberColumn("Atraso", format="%d")
                }
            )
        else:
            st.info("Nenhuma fatura nesta categoria.")

    st.markdown("""
    <style>
    div[data-testid="stDataFrame"] > div {
        background-color: white !important;
    }
    </style>
    """, unsafe_allow_html=True)
else:
    st.info("Nenhum contrato bloqueado encontrado.")

# Auto refresh every 60 seconds
time.sleep(60)
st.rerun()
