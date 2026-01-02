import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_echarts import st_echarts
from db import get_db
from datetime import datetime, timedelta
import time
from utils import format_currency, safe_get
from utils_css import apply_light_theme

st.set_page_config(page_title="Collection Dashboard", layout="wide")

# Apply shared light theme
apply_light_theme()

# Additional Dashboard-specific CSS
st.markdown("""
<style>
    /* KPI Styling */
    .kpi-label {
        font-size: 0.875rem !important;
        color: #64748b !important;
        font-weight: 600 !important;
        margin-bottom: 4px !important;
    }
    .kpi-value {
        font-size: 2.25rem !important;
        font-weight: 700 !important;
        color: #0f172a !important;
    }
    .kpi-trend {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        padding: 2px 8px !important;
        border-radius: 9999px !important;
        margin-left: 8px !important;
    }
    .trend-up {
        background-color: #dcfce7 !important;
        color: #15803d !important;
    }
    
    /* Progress Bar */
    .progress-container {
        width: 100% !important;
        background-color: #f1f5f9 !important;
        border-radius: 9999px !important;
        height: 8px !important;
        margin-top: 8px !important;
    }
    .progress-bar-pre {
        background-color: #f59e0b !important;
        height: 8px !important;
        border-radius: 9999px !important;
    }
    .progress-bar-debt {
        background-color: #ef4444 !important;
        height: 8px !important;
        border-radius: 9999px !important;
    }
    
    /* Section Headers */
    .section-header {
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        margin-bottom: 20px !important;
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 1.125rem !important;
    }
    
    /* Table Styling */
    .custom-table {
        width: 100% !important;
        border-collapse: collapse !important;
        background-color: white !important;
    }
    .custom-table th {
        background-color: #f8fafc !important;
        color: #64748b !important;
        text-transform: uppercase !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.05em !important;
        padding: 12px !important;
        text-align: left !important;
        border-bottom: 2px solid #e2e8f0 !important;
    }
    .custom-table td {
        padding: 12px !important;
        border-bottom: 1px solid #f1f5f9 !important;
        font-size: 0.875rem !important;
        color: #334155 !important;
    }
</style>
""", unsafe_allow_html=True)

# Error handling wrapper
try:
    db = get_db()
    db.command('ping')  # Test connection
except Exception as e:
    st.error(f"❌ Database connection failed: {e}")
    st.info("Please check your database settings in the Settings page.")
    st.stop()

# --- Sidebar Controls ---
st.sidebar.title("⚙️ Dashboard Controls")
auto_refresh = st.sidebar.checkbox("Auto-Refresh (1m)", value=False)

if auto_refresh:
    st.sidebar.caption("Last Update: " + datetime.now().strftime("%H:%M:%S"))
    time.sleep(60)
    st.rerun()

instances = list(db.instance_config.find({"status.active": True}, {"instance_name": 1, "erp.type": 1}))
instance_options = ["🌍 Global (All Active)"] + [i["instance_name"] for i in instances]
selected_instance_name = st.sidebar.selectbox("Select View", instance_options)

# --- Data Fetching Logic ---
def get_latest_metrics(full_id):
    return db.metrics.find_one({"instance_full_id": full_id}, sort=[("timestamp", -1)])

if selected_instance_name == "🌍 Global (All Active)":
    total_metrics = {
        "clients": {"total": 0, "count_with_open_debt": 0, "count_pre_force_debt_collection": 0, "count_force_debt_collection": 0},
        "bill": {"total": 0, "expired": 0, "count_pre_force_debt_collection": 0, "value_pre_force_debt_collection": 0.0, "count_force_debt_collection": 0, "value_force_debt_collection": 0.0, "bill_stats": {}},
        "actions_today": {"dialer_triggers": 0}
    }
    
    for inst in instances:
        f_id = f"{inst['instance_name']}-{inst.get('erp',{}).get('type','ixc')}-{str(inst['_id'])}"
        m = get_latest_metrics(f_id)
        if m and "data" in m:
            d = m["data"]
            c = d.get("clients", {})
            total_metrics["clients"]["total"] += c.get("total", 0)
            total_metrics["clients"]["count_with_open_debt"] += c.get("count_with_open_debt", 0)
            total_metrics["clients"]["count_pre_force_debt_collection"] += c.get("count_pre_force_debt_collection", 0)
            total_metrics["clients"]["count_force_debt_collection"] += c.get("count_force_debt_collection", 0)

            b = d.get("bill") if "bill" in d else d.get("bills", {})
            total_metrics["bill"]["total"] += b.get("total", 0)
            total_metrics["bill"]["expired"] += b.get("expired", 0)
            total_metrics["bill"]["count_pre_force_debt_collection"] += b.get("count_pre_force_debt_collection", 0)
            total_metrics["bill"]["value_pre_force_debt_collection"] += b.get("value_pre_force_debt_collection", 0.0)
            total_metrics["bill"]["count_force_debt_collection"] += b.get("count_force_debt_collection", 0)
            total_metrics["bill"]["value_force_debt_collection"] += b.get("value_force_debt_collection", 0.0)
            
            # Merge bill_stats for Global
            b_stats = b.get("bill_stats", {})
            for key in ["tipo_cliente", "bairro"]:
                if key in b_stats:
                    if key not in total_metrics["bill"]["bill_stats"]:
                        total_metrics["bill"]["bill_stats"][key] = {}
                    for subkey, val in b_stats[key].items():
                        total_metrics["bill"]["bill_stats"][key][subkey] = total_metrics["bill"]["bill_stats"][key].get(subkey, 0) + val

            total_metrics["actions_today"]["dialer_triggers"] += d.get("actions_today", {}).get("dialer_triggers", 0)
    
    data = total_metrics
else:
    inst_doc = next(i for i in instances if i["instance_name"] == selected_instance_name)
    f_id = f"{selected_instance_name}-{inst_doc.get('erp',{}).get('type','ixc')}-{str(inst_doc['_id'])}"
    m = get_latest_metrics(f_id)
    data = m["data"] if m else {}
    if "bill" not in data and "bills" in data:
        data["bill"] = data["bills"]

# --- Layout: Header ---
col_h1, col_h2 = st.columns([8, 2])
with col_h1:
    st.markdown("### ⊞ Collection")
    st.markdown("<p style='color: #64748b; margin-top: -15px;'>Real-time insights into clients and billing status</p>", unsafe_allow_html=True)
with col_h2:
    st.markdown("<div style='display: flex; gap: 8px; justify-content: flex-end;'>", unsafe_allow_html=True)
    st.button("⊞ Filter", type="secondary")
    st.button("📥 Export Report", type="primary")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Layout: Clients ---
with st.container():
    st.markdown("<div class='section-header'>👤 Clients <span style='margin-left: auto; font-size: 0.75rem; background: #dbeafe; color: #1e40af; padding: 2px 8px; border-radius: 4px;'>Updated Today</span></div>", unsafe_allow_html=True)
    
    c_col1, c_col2, c_col3 = st.columns([1, 1.5, 3])
    
    with c_col1:
        st.markdown(f"""
        <div class='kpi-label'>Active Total <span class='kpi-trend trend-up'>📈 +2.4%</span></div>
        <div class='kpi-value'>{data.get('clients', {}).get('total', 0):,}</div>
        """, unsafe_allow_html=True)
        
    with c_col2:
        on_debt = data.get('clients', {}).get('count_with_open_debt', 0)
        total_c = data.get('clients', {}).get('total', 1)
        pct_debt = (on_debt / total_c) * 100
        st.markdown(f"""
        <div style='background: #fef2f2; padding: 20px; border-radius: 12px; height: 100%; border: 1px solid #fee2e2;'>
            <div class='kpi-label' style='color: #ef4444;'>On Debt <span style='float: right; background: #fee2e2; padding: 2px 6px; border-radius: 4px;'>{pct_debt:.1f}%</span></div>
            <div class='kpi-value' style='color: #ef4444;'>{on_debt:,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c_col3:
        pre_debt = data.get('clients', {}).get('count_pre_force_debt_collection', 0)
        debt_coll = data.get('clients', {}).get('count_force_debt_collection', 0)
        
        # ECharts Stacked Horizontal Bar
        options = {
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"}
            },
            "legend": {},
            "grid": {
                "left": 0,
                "right": 0,
                "top": 10,
                "bottom": 0,
            #     "containLabel": True
            },
            "xAxis": {
                "type": "value",
                # "show": True
            },
            "yAxis": {
                "type": "category",
                "data": ["Clients"],
                "show": False
            },
            "series": [
                {
                    "name": "Pre-Debt Collector",
                    "type": "bar",
                    "stack": "total",
                    "label": {
                        "show": True,
                        # "position": "inside",
                        # "formatter": f"{pre_debt}",
                        # "color": "#fff",
                        # "fontSize": 14,
                        "fontWeight": "bold"
                    },
                    "emphasis": {"focus": "series"},
                    "itemStyle": {"color": "#f59e0b"},
                    "data": [pre_debt]
                },
                {
                    "name": "Debt Collector",
                    "type": "bar",
                    "stack": "total",
                    "label": {
                        "show": True,
                        # "position": "inside",
                        # "formatter": f"{debt_coll}",
                        # "color": "#fff",
                        # "fontSize": 14,
                        "fontWeight": "bold"
                    },
                    "emphasis": {"focus": "series"},
                    "itemStyle": {"color": "#ef4444"},
                    "data": [debt_coll]
                }
            ]
        }
        
        # st.markdown("""
        # <div style='font-size: 0.75rem; font-weight: 600; margin-bottom: 8px;'>
        #     <span style='color: #f59e0b;'>●</span> Pre-Debt Collector &nbsp;
        #     <span style='color: #ef4444;'>●</span> Debt Collector
        # </div>
        # """, unsafe_allow_html=True)
        st_echarts(options=options, height="100px")

st.markdown("<br>", unsafe_allow_html=True)

# --- Layout: Bills Overview ---
with st.container():
    st.markdown("<div class='section-header'>🧾 Bills Overview <span style='margin-left: auto; color: #94a3b8;'>...</span></div>", unsafe_allow_html=True)
    
    b_col1, b_col2 = st.columns([1, 2])
    
    with b_col1:
        st.markdown(f"""
        <div style='margin-bottom: 24px;'>
            <div class='kpi-label'>Expired Total</div>
            <div class='kpi-value'>{data.get('bill', {}).get('expired', 0):,}</div>
        </div>
        <div>
            <div class='kpi-label'>Expired Value</div>
            <div class='kpi-value'>R$ {data.get('bill', {}).get('value_pre_force_debt_collection', 0) + data.get('bill', {}).get('value_force_debt_collection', 0):,.2f}</div>
            <div style='color: #94a3b8; font-size: 0.75rem;'>Exact: R$ {data.get('bill', {}).get('value_pre_force_debt_collection', 0) + data.get('bill', {}).get('value_force_debt_collection', 0):,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with b_col2:
        val_pre = data.get('bill', {}).get('value_pre_force_debt_collection', 0)
        val_force = data.get('bill', {}).get('value_force_debt_collection', 0)
        cnt_pre = data.get('bill', {}).get('count_pre_force_debt_collection', 0)
        cnt_force = data.get('bill', {}).get('count_force_debt_collection', 0)
        
        st.markdown(f"""
        <table class='custom-table' style='width: 100%; border-collapse: collapse;'>
            <thead>
                <tr>
                    <th>Stage</th>
                    <th>Count</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><span style='color: #f59e0b;'>●</span> Pre-Debt Collection</td>
                    <td>{cnt_pre}</td>
                    <td>R$ {val_pre:,.2f}</td>
                </tr>
                <tr>
                    <td><span style='color: #ef4444;'>●</span> Debt Collector</td>
                    <td>{cnt_force}</td>
                    <td>R$ {val_force:,.2f}</td>
                </tr>
            </tbody>
        </table>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Layout: Charts ---
c1, c2 = st.columns(2)

with c1:
    st.markdown("<div class='section-header'>🌐 Tipo Cliente</div>", unsafe_allow_html=True)
    tipo_stats = data.get('bill', {}).get('bill_stats', {}).get('tipo_cliente', {})
    if tipo_stats:
        df_tipo = pd.DataFrame(list(tipo_stats.items()), columns=['Tipo', 'Count'])
        df_tipo = df_tipo.sort_values('Count', ascending=False).head(8)  # Top 8
        
        # Calculate total for percentages
        total = df_tipo['Count'].sum()
        
        # Prepare data for Nightingale Rose
        chart_data = []
        for _, row in df_tipo.iterrows():
            pct = (row['Count'] / total) * 100
            chart_data.append({
                "value": row['Count'],
                "name": f"{row['Tipo']}: {row['Count']} ({pct:.1f}%)"
            })
        
        options = {
            "tooltip": {"trigger": "item"},
            "series": [{
                "name": "Tipo Cliente",
                "type": "pie",
                "radius": ["30%", "70%"],
                "center": ["50%", "50%"],
                "roseType": "area",
                "itemStyle": {
                    "borderRadius": 8
                },
                "label": {
                    "show": True,
                    "fontSize": 11,
                    "color": "#0f172a"
                },
                "data": chart_data
            }]
        }
        st_echarts(options=options, height="350px")
    else:
        st.info("No data available")

with c2:
    st.markdown("<div class='section-header'>🗺️ Bairro (Neighborhood)</div>", unsafe_allow_html=True)
    bairro_stats = data.get('bill', {}).get('bill_stats', {}).get('bairro', {})
    if bairro_stats:
        df_bairro = pd.DataFrame(list(bairro_stats.items()), columns=['Bairro', 'Count'])
        df_bairro = df_bairro.sort_values('Count', ascending=False).head(8)  # Top 8
        
        # Calculate total for percentages
        total = df_bairro['Count'].sum()
        
        # Prepare data for Nightingale Rose
        chart_data = []
        for _, row in df_bairro.iterrows():
            pct = (row['Count'] / total) * 100
            chart_data.append({
                "value": row['Count'],
                "name": f"{row['Bairro']}: {row['Count']} ({pct:.1f}%)"
            })
        
        options = {
            "tooltip": {"trigger": "item"},
            "series": [{
                "name": "Bairro",
                "type": "pie",
                "radius": ["30%", "70%"],
                "center": ["50%", "50%"],
                "roseType": "area",
                "itemStyle": {
                    "borderRadius": 8
                },
                "label": {
                    "show": True,
                    "fontSize": 11,
                    "color": "#0f172a"
                },
                "data": chart_data
            }]
        }
        st_echarts(options=options, height="350px")
    else:
        st.info("No data available")
