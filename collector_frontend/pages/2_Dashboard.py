import streamlit as st
import pandas as pd
import plotly.express as px
from db import get_db
from datetime import datetime, timedelta
import time
from utils import format_currency, safe_get

st.set_page_config(page_title="Monitor Dashboard", layout="wide")

# Error handling wrapper
try:
    db = get_db()
    db.command('ping')  # Test connection
except Exception as e:
    st.error(f"❌ Database connection failed: {e}")
    st.info("Please check your database settings in the Settings page.")
    st.stop()

# --- Sidebar Controls ---
st.sidebar.title("📺 TV Monitor Settings")
auto_refresh = st.sidebar.checkbox("Auto-Refresh (1m)", value=False, help="Enable automatic page refresh every 60 seconds")

if auto_refresh:
    # Small hack for auto-refresh in base Streamlit
    # It will trigger a rerun every 60 seconds
    st.sidebar.caption("Last Update: " + datetime.now().strftime("%H:%M:%S"))
    time.sleep(60)
    st.rerun()

instances = list(db.instance_config.find({"status.active": True}, {"instance_name": 1, "erp.type": 1}))
instance_options = ["🌍 Global (All Active)"] + [i["instance_name"] for i in instances]

selected_instance_name = st.sidebar.selectbox("Select View", instance_options)

st.title("📊 Debt Collector Monitoring")

# --- Data Fetching Logic ---
def get_latest_metrics(full_id):
    return db.metrics.find_one({"instance_full_id": full_id}, sort=[("timestamp", -1)])

if selected_instance_name == "🌍 Global (All Active)":
    # Aggregate Metrics
    total_metrics = {
        "clients": {"total": 0, "count_with_open_debt": 0, "count_with_expired_open_debt": 0},
        "bill": {"total": 0, "expired": 0, "total_expired_debt_amount": 0, "total_intime_debt_amount": 0},
        "actions_today": {"dialer_triggers": 0},
        "cdr_stats": {"total_calls": 0, "average_duration": 0}
    }
    
    for inst in instances:
        f_id = f"{inst['instance_name']}-{inst.get('erp',{}).get('type','ixc')}-{str(inst['_id'])}"
        m = get_latest_metrics(f_id)
        if m and "data" in m:
            d = m["data"]
            # Safely add
            total_metrics["clients"]["total"] += d.get("clients", {}).get("total", 0)
            total_metrics["clients"]["count_with_open_debt"] += d.get("clients", {}).get("count_with_open_debt", 0)
            
            b = d.get("bill") if "bill" in d else d.get("bills", {})
            total_metrics["bill"]["total"] += b.get("total", 0)
            total_metrics["bill"]["expired"] += b.get("expired", 0)
            total_metrics["bill"]["total_expired_debt_amount"] += b.get("total_expired_debt_amount", 0)
            total_metrics["bill"]["total_intime_debt_amount"] += b.get("total_intime_debt_amount", 0)
            
            total_metrics["actions_today"]["dialer_triggers"] += d.get("actions_today", {}).get("dialer_triggers", 0)
            total_metrics["cdr_stats"]["total_calls"] += d.get("cdr_stats", {}).get("total_calls", 0)

    data = total_metrics
    view_title = "Global Performance"
    metrics_query = {"instance_full_id": {"$in": [f"{i['instance_name']}-{i.get('erp',{}).get('type','ixc')}-{str(i['_id'])}" for i in instances]}}
else:
    # Single Instance
    inst_doc = next(i for i in instances if i["instance_name"] == selected_instance_name)
    f_id = f"{selected_instance_name}-{inst_doc.get('erp',{}).get('type','ixc')}-{str(inst_doc['_id'])}"
    m = get_latest_metrics(f_id)
    data = m["data"] if m else {}
    # Handle bills/bill key transition
    if "bill" not in data and "bills" in data:
        data["bill"] = data["bills"]
    view_title = f"{selected_instance_name} Status"
    metrics_query = {"instance_full_id": f_id}

# --- KPI Section ---
st.subheader(f"✨ {view_title}")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Clients in Debt", data.get("clients", {}).get("count_with_open_debt", 0))
    st.caption(f"Total Portfolio: {data.get('clients', {}).get('total', 0)}")

with col2:
    st.metric("Expired Bills", data.get("bill", {}).get("expired", 0))
    st.caption(f"Total Bills: {data.get('bill', {}).get('total', 0)}")

with col3:
    st.metric("Expired Amount", f"R$ {data.get('bill', {}).get('total_expired_debt_amount', 0):,.2f}")
    st.caption(f"In-Time: R$ {data.get('bill', {}).get('total_intime_debt_amount', 0):,.2f}")

with col4:
    st.metric("Triggers Today", data.get("actions_today", {}).get("dialer_triggers", 0))
    st.caption(f"CDR Count: {data.get('cdr_stats', {}).get('total_calls', 0)}")

# --- Charts & Activity ---
st.divider()
c_chart, c_log = st.columns([2, 1])

with c_chart:
    st.write("📈 **Debt Recovery Trends**")
    # Fetch recent history
    hist = list(db.metrics.find(metrics_query).sort("timestamp", -1).limit(40))
    if hist:
        # Group by timestamp for simple trend
        df_hist = pd.DataFrame([
            {
                "Time": h["timestamp"],
                "Expired": (h["data"].get("bill") or h["data"].get("bills", {})).get("total_expired_debt_amount", 0),
                "In-Time": (h["data"].get("bill") or h["data"].get("bills", {})).get("total_intime_debt_amount", 0)
            } for h in hist
        ])
        fig = px.area(df_hist, x="Time", y=["Expired", "In-Time"], 
                      color_discrete_map={"Expired": "red", "In-Time": "green"},
                      template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient history for trends.")

with c_log:
    st.write("⚡ **Live Activity (Last 15)**")
    # Fetch recent history_action_log
    log_query = {}
    if selected_instance_name != "🌍 Global (All Active)":
        log_query = {"instance_full_id": f_id}
    
    recent_logs = list(db.history_action_log.find(log_query).sort("occurred_at", -1).limit(15))
    if recent_logs:
        for log in recent_logs:
            # Color coded icons
            icon = "📞" if "dialer" in log.get("action", "") else "⚙️"
            time_str = log["occurred_at"].strftime("%H:%M")
            st.write(f"{icon} **{time_str}**: {log.get('action').replace('_', ' ').title()}")
            st.caption(f"{log.get('details', {}).get('message', '')} {log.get('details', {}).get('number', '')}")
            st.divider()
    else:
        st.write("No recent activity found.")

st.sidebar.divider()

# Export Options
st.sidebar.subheader("📥 Export Options")
if st.sidebar.button("Export Current View as CSV", use_container_width=True):
    try:
        # Export the trend data if available
        if 'df_hist' in locals() and not df_hist.empty:
            csv = df_hist.to_csv(index=False)
            st.sidebar.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"metrics_{selected_instance_name}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.sidebar.warning("No data available to export")
    except Exception as e:
        st.sidebar.error(f"Export failed: {e}")

st.sidebar.write("Developed for TV monitoring. High contrast enabled.")
st.sidebar.caption(f"Page loaded: {datetime.now().strftime('%H:%M:%S')}")
