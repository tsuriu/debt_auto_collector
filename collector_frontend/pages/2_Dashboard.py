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
from loguru import logger
from config import Config

st.set_page_config(page_title="Dashboard de Cobrança", layout="wide")

# Apply shared light theme
apply_light_theme()

# Additional Dashboard-specific CSS
st.markdown("""
<style>
    /* Trend indicators */
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
    
    /* Custom Table fallback */
    .custom-table {
        width: 100% !important;
        border-collapse: collapse !important;
        background-color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# Error handling wrapper
try:
    db = get_db()
    db.command('ping')  # Test connection
except Exception as e:
    st.error(f"❌ Conexão com o banco de dados falhou: {e}")
    st.info("Por favor, verifique suas configurações de banco de dados na página de Configurações.")
    st.stop()

# --- Controles da Barra Lateral ---
st.sidebar.title("⚙️ Controles do Dashboard")

instances = list(db.instance_config.find({"status.active": True}, {"instance_name": 1, "erp.type": 1}))
if not instances:
    st.warning("Nenhuma instância ativa encontrada.")
    st.stop()

instance_options = [i["instance_name"] for i in instances]
selected_instance_name = st.sidebar.selectbox("Selecionar Visualização", instance_options)

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

# --- Data Fetching Logic ---
def get_latest_metrics(full_id):
    return db.metrics.find_one({"instance_full_id": full_id}, sort=[("timestamp", -1)])

def get_historical_metrics(full_id, limit=100):
    # Filter for data from today only (00:00:00 onwards)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    query = {
        "instance_full_id": full_id,
        "timestamp": {"$gte": today_start}
    }
    return list(db.metrics.find(query, sort=[("timestamp", -1)], limit=limit))

last_update_ts = None
inst_doc = next(i for i in instances if i["instance_name"] == selected_instance_name)
f_id = f"{selected_instance_name}-{inst_doc.get('erp',{}).get('type','ixc')}-{str(inst_doc['_id'])}"
m = get_latest_metrics(f_id)

if m:
    last_update_ts = m.get("timestamp")
    data = m["data"]
    if "bill" not in data and "bills" in data:
        data["bill"] = data["bills"]
    hist_metrics = get_historical_metrics(f_id, limit=24)
else:
    data = {}
    hist_metrics = []

# --- Layout: Header ---
# col_h1, col_h2 = st.columns([8, 2])
# with col_h1:
#     st.markdown("### ⊞ Debt Collection Report")
#     st.markdown("<p style='color: #64748b; margin-top: -15px;'>Real-time insights into clients and billing status</p>", unsafe_allow_html=True)
# with col_h2:
#     st.markdown("<div style='display: flex; gap: 8px; justify-content: flex-end;'>", unsafe_allow_html=True)
#     # Buttons removed as requested
#     st.markdown("</div>", unsafe_allow_html=True)

# st.markdown("<br>", unsafe_allow_html=True)

# --- Layout: Clients ---
with st.container():
    time_ago = format_time_ago(last_update_ts)
    
    # Cabeçalho com Controles
    col_title, col_ctrl = st.columns([1.5, 1])
    with col_title:
        st.markdown(f"<div class='section-header' style='margin-bottom: 0;'>👤 Clientes <span style='color: #64748b; font-weight: 400; font-size: 0.9rem; margin-left: 10px;'>({selected_instance_name})</span></div>", unsafe_allow_html=True)
    with col_ctrl:
        # Linha de mini-controles
        c1, c2 = st.columns([1.5, 1])
        
        # Comportamento de atualização fixo
        auto_refresh = True
        refresh_interval = 60
        
        with c1:
            st.markdown(f"<div class='ctrl-box-last'>Última: {last_update_ts.strftime('%H:%M:%S') if last_update_ts else 'N/A'}</div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='ctrl-box-time'>{time_ago}</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    c_col1, c_col2, c_col3 = st.columns([1, 1.5, 3])
    
    with c_col1:
        st.markdown(f"""
        <div class='flex-center'>
            <div class='kpi-label'>Total Ativos <span class='kpi-trend trend-up'>📈 +2.4%</span></div>
            <div class='kpi-value' style='font-size: 1.8rem !important;'>{data.get('clients', {}).get('total', 0):,}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with c_col2:
        on_debt = data.get('clients', {}).get('count_with_open_debt', 0)
        total_c = data.get('clients', {}).get('total', 1)
        pct_debt = (on_debt / total_c) * 100
        st.markdown(f"""
        <div class='flex-center' style='background: #fef2f2; padding: 20px; border-radius: 12px; border: 1px solid #fee2e2;'>
            <div class='kpi-label' style='color: #ef4444;'>Em Dívida <span style='background: #fee2e2; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem;'>{pct_debt:.1f}%</span></div>
            <div class='kpi-value' style='color: #ef4444; font-size: 1.8rem !important;'>{on_debt:,}</div>
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
                "data": ["Clientes"],
                "show": False
            },
            "series": [
                {
                    "name": "Pré-Cobrança",
                    "type": "bar",
                    "stack": "total",
                    "label": {
                        "show": True,
                        "fontWeight": "bold"
                    },
                    "emphasis": {"focus": "series"},
                    "itemStyle": {"color": "#f59e0b"},
                    "data": [pre_debt]
                },
                {
                    "name": "Cobrança Forçada",
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

# --- Layout: Visão Geral de Faturas ---
with st.container():
    st.markdown("<div class='section-header'>🧾 Visão Geral de Faturas <span style='margin-left: auto; color: #94a3b8;'>...</span></div>", unsafe_allow_html=True)
    
    b_col1, b_col2, b_col3 = st.columns([1, 3, 1])
    
    expired_total = data.get('bill', {}).get('expired', 0)
    val_pre = data.get('bill', {}).get('value_pre_force_debt_collection', 0)
    val_force = data.get('bill', {}).get('value_force_debt_collection', 0)
    expired_value = val_pre + val_force
    
    cnt_pre = data.get('bill', {}).get('count_pre_force_debt_collection', 0)
    cnt_force = data.get('bill', {}).get('count_force_debt_collection', 0)

    with b_col1:
        st.markdown(f"""
        <div class='flex-center' style='gap: 16px;'>
            <div class='flex-center' style='flex-direction: row; gap: 12px; background: white; padding: 12px 20px; border-radius: 12px; border: 1px solid #e2e8f0; width: 100%; justify-content: space-between;'>
                <div class='kpi-label' style='margin-bottom: 0;'>Total Vencido</div>
                <div class='kpi-value' style='font-size: 1.6rem !important;'>{expired_total:,}</div>
            </div>
            <div class='flex-center' style='flex-direction: row; gap: 12px; background: white; padding: 12px 20px; border-radius: 12px; border: 1px solid #e2e8f0; width: 100%; justify-content: space-between;'>
                <div class='kpi-label' style='margin-bottom: 0;'>Valor Vencido</div>
                <div class='kpi-value' style='font-size: 1.6rem !important;'>R$ {expired_value:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with b_col2:
        # ECharts Stacked Horizontal Bar for Bill Counts
        options = {
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"}
            },
            "legend": {"bottom": 0},
            "grid": {
                "left": 10, "right": 20, "top": 10, "bottom": 30, "containLabel": True
            },
            "xAxis": {"type": "value"},
            "yAxis": {
                "type": "category",
                "data": ["Faturas"],
                "show": False
            },
            "series": [
                {
                    "name": "Pré-Cobrança",
                    "type": "bar",
                    "stack": "total",
                    "label": {"show": True, "fontWeight": "bold"},
                    "emphasis": {"focus": "series"},
                    "itemStyle": {"color": "#f59e0b"},
                    "data": [cnt_pre]
                },
                {
                    "name": "Cobrança Forçada",
                    "type": "bar",
                    "stack": "total",
                    "label": {"show": True, "fontWeight": "bold"},
                    "emphasis": {"focus": "series"},
                    "itemStyle": {"color": "#ef4444"},
                    "data": [cnt_force]
                }
            ]
        }
        st_echarts(options=options, height="140px")
        
    with b_col3:
        # Blocos coloridos para detalhamento de valor - Empilhados Verticalmente
        st.markdown(f"""
        <div class='flex-center' style='gap: 16px;'>
            <div class='flex-center' style='background: #fffbeb; padding: 12px 20px; border-radius: 12px; border: 1px solid #fde68a; width: 100%;'>
                <div class='kpi-label' style='color: #92400e; font-size: 0.75rem; margin-bottom: 4px;'>PRÉ-COBRANÇA</div>
                <div class='kpi-value' style='color: #b45309; font-size: 1.5rem !important;'>R$ {val_pre:,.2f}</div>
            </div>
            <div class='flex-center' style='background: #fef2f2; padding: 12px 20px; border-radius: 12px; border: 1px solid #fee2e2; width: 100%;'>
                <div class='kpi-label' style='color: #991b1b; font-size: 0.75rem; margin-bottom: 4px;'>COBRANÇA FORÇADA</div>
                <div class='kpi-value' style='color: #b91c1c; font-size: 1.5rem !important;'>R$ {val_force:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- Layout: Gráficos ---
c1, c2, c3 = st.columns(3)

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
            "tooltip": {"trigger": "axis"},
           # "legend": {"data": ["Count"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": df_tipo['Tipo'].tolist(),
                "axisLabel": {"interval": 0, "rotate": 30}
            },
            "yAxis": {"type": "value"},
            "series": [{
                "name": "Count",
                "type": "bar",
                "data": df_tipo['Count'].tolist(),
                "itemStyle": {"color": "#5b73e8", "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top"}
            }]
        }
        st_echarts(options=options, height="400px")
    else:
        st.info("No data available")

with c2:
    st.markdown("<div class='section-header'>🗺️ Bairro</div>", unsafe_allow_html=True)
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
            "tooltip": {"trigger": "axis"},
           # "legend": {"data": ["Count"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": df_bairro['Bairro'].tolist(),
                "axisLabel": {"interval": 0, "rotate": 30}
            },
            "yAxis": {"type": "value"},
            "series": [{
                "name": "Count",
                "type": "bar",
                "data": df_bairro['Count'].tolist(),
                "itemStyle": {"color": "#5b73e8", "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top"}
            }]
        }
        st_echarts(options=options, height="400px")
    else:
        st.info("No data available")

with c3:
    st.markdown("<div class='section-header'>⏳ Dívida por Atraso (Dias)</div>", unsafe_allow_html=True)
    exp_age_raw = data.get('bill', {}).get('bill_stats', {}).get('expired_age', [])
    
    # expired_age can be a list of dicts (single instance) or a dict (Global view merge)
    if isinstance(exp_age_raw, dict):
        df_age = pd.DataFrame(list(exp_age_raw.items()), columns=['Age', 'Count'])
    else:
        df_age = pd.DataFrame(exp_age_raw)
        if not df_age.empty:
            df_age = df_age.rename(columns={'_id': 'Age', 'count': 'Count'})
    
    if not df_age.empty:
        # Robustly find count/Count column
        count_col = next((c for c in df_age.columns if c.lower() == 'count'), None)
        if count_col:
            df_age = df_age.rename(columns={count_col: 'Count'})
        
        if 'Age' in df_age.columns:
            df_age['Age'] = df_age['Age'].astype(int)
        
        if 'Count' in df_age.columns:
            df_age = df_age.sort_values('Count', ascending=False).head(8)
            df_age = df_age.sort_values('Age') if 'Age' in df_age.columns else df_age
        
        options = {
            "tooltip": {"trigger": "axis"},
           # "legend": {"data": ["Count"]},
            "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
            "xAxis": {
                "type": "category",
                "data": [f"{int(x)}d" for x in df_age['Age']],
            },
            "yAxis": {"type": "value"},
            "series": [{
                "name": "Count",
                "type": "bar",
                "data": df_age['Count'].tolist(),
                "itemStyle": {"color": "#6366f1", "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top"}
            }]
        }
        st_echarts(options=options, height="400px")
    else:
        st.info("No data available")

st.markdown("<br>", unsafe_allow_html=True)

# --- Layout: Visão Geral CDR ---
with st.container():
    st.markdown("<div class='section-header'>📞 Visão Geral CDR (Detalhes de Chamadas)</div>", unsafe_allow_html=True)
    
    cdr_col1, cdr_col3, cdr_col2 = st.columns([1, 2.8, 1.2])
    
    cdr_data = data.get("cdr_stats", {})
    disp_colors = {
        'ANSWERED': '#10b981', 
        'BUSY': '#f59e0b', 
        'FAILED': '#ef4444', 
        'NO ANSWER': '#6366f1', 
        'NO ANSWER MACHINE': '#6366f1', 
        'CONGESTION': '#94a3b8'
    }
    
    with cdr_col1:
        st.markdown(f"""
        <div class='flex-center' style='white-space: nowrap; background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 12px;'>
            <div class='kpi-label' style='font-size: 0.8rem;'>Total de Chamadas</div>
            <div class='kpi-value' style='font-size: 1.6rem;'>{cdr_data.get('total_calls', 0):,}</div>
        </div>
        <div class='flex-center' style='white-space: nowrap; background: #f8fafc; padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0;'>
            <div class='kpi-label' style='font-size: 0.8rem;'>Duração Média</div>
            <div class='kpi-value' style='font-size: 1.6rem;'>{cdr_data.get('average_duration', 0):.1f}s</div>
        </div>
        """, unsafe_allow_html=True)

    with cdr_col2:
        disps = cdr_data.get("dispositions", {})
        # Define chaves para mostrar em ordem
        disp_keys = ['ANSWERED', 'BUSY', 'FAILED', 'NO ANSWER', 'NO ANSWER MACHINE', 'CONGESTION']
        disp_labels = {
            'ANSWERED': 'Atendidas',
            'BUSY': 'Ocupado',
            'FAILED': 'Falhou',
            'NO ANSWER': 'Não Atendidas',
            'NO ANSWER MACHINE': 'Não Atendidas Máquina',
            'CONGESTION': 'Congestionamento'
        }
        
        for key in disp_keys:
            val = disps.get(key, 0)
            color = disp_colors.get(key, "#94a3b8")
            label = disp_labels.get(key, key)
            st.markdown(f"""
            <div class='flex-center' style='background: {color}; padding: 12px 16px; border-radius: 10px; margin-bottom: 10px; border: 1px solid rgba(0,0,0,0.1); height: 50px;'>
                <div style='color: white; font-size: 1.25rem; font-weight: 700; display: flex; align-items: center; justify-content: center; gap: 12px; width: 100%;'>
                    <span style='font-size: 0.85rem; opacity: 1; text-transform: uppercase; letter-spacing: 0.05em;'>{label} :</span>
                    <span>{val:,}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with cdr_col3:
        # Processar dados históricos para o Gráfico de Área Empilhada
        if hist_metrics:
            df_entries = []
            for h in hist_metrics:
                # Agrupar por timestamp arredondado para um eixo X mais limpo
                ts = h.get("timestamp")
                if isinstance(ts, str): ts = datetime.fromisoformat(ts)
                
                # Arredondar para janela de 10 min para consolidar pontos globais se necessário
                ts_key = ts.replace(second=0, microsecond=0)
                
                cdr_h = h.get("data", {}).get("cdr_stats", {})
                disps_h = cdr_h.get("dispositions", {})
                entry = {"timestamp": ts_key}
                entry.update(disps_h)
                df_entries.append(entry)
            
            df_hist_graph = pd.DataFrame(df_entries).fillna(0)
            if not df_hist_graph.empty:
                df_hist_graph = df_hist_graph.groupby("timestamp").sum().reset_index()
                df_hist_graph = df_hist_graph.sort_values("timestamp")
                
                # Disposições Necessárias
                series_data = []
                
                for key in disp_keys:
                    series_data.append({
                        "name": disp_labels.get(key, key),
                        "type": "line",
                        "stack": "Total",
                        "areaStyle": {},
                        "emphasis": {"focus": "series"},
                        "data": df_hist_graph[key].tolist() if key in df_hist_graph else [0] * len(df_hist_graph),
                        "itemStyle": {"color": disp_colors.get(key, "#ccc")}
                    })
                
                options = {
                    "tooltip": {
                        "trigger": "axis",
                        "axisPointer": {"type": "cross", "label": {"backgroundColor": "#6a7985"}}
                    },
                    "legend": {"data": list(disp_labels.values())},
                    "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
                    "xAxis": [{
                        "type": "category",
                        "boundaryGap": False,
                        "data": df_hist_graph["timestamp"].dt.strftime("%H:%M").tolist()
                    }],
                    "yAxis": [{"type": "value"}],
                    "series": series_data
                }
                st_echarts(options=options, height="400px")
            else:
                st.info("Nenhum dado histórico de CDR encontrado")
        else:
            st.info("Nenhum dado histórico de CDR encontrado")

if auto_refresh:
    if Config.DEBUG:
        logger.info(f"Atualização automática habilitada ({selected_instance_name}). Atualizando...")
    time.sleep(refresh_interval)
    st.rerun()
