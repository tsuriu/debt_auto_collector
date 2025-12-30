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
        "clients": {
            "total": 0, 
            "count_with_open_debt": 0,
            "count_pre_force_debt_collection": 0,
            "count_force_debt_collection": 0
        },
        "bill": {
            "total": 0, 
            "expired": 0, 
            "count_pre_force_debt_collection": 0,
            "value_pre_force_debt_collection": 0.0,
            "count_force_debt_collection": 0,
            "value_force_debt_collection": 0.0,
            # Aggregated stats for visualization
            "bill_stats": {} 
        },
        "actions_today": {"dialer_triggers": 0},
        "cdr_stats": {"total_calls": 0, "average_duration": 0}
    }
    
    for inst in instances:
        f_id = f"{inst['instance_name']}-{inst.get('erp',{}).get('type','ixc')}-{str(inst['_id'])}"
        m = get_latest_metrics(f_id)
        if m and "data" in m:
            d = m["data"]
            
            # Clients
            c = d.get("clients", {})
            total_metrics["clients"]["total"] += c.get("total", 0)
            total_metrics["clients"]["count_with_open_debt"] += c.get("count_with_open_debt", 0)
            total_metrics["clients"]["count_pre_force_debt_collection"] += c.get("count_pre_force_debt_collection", 0)
            total_metrics["clients"]["count_force_debt_collection"] += c.get("count_force_debt_collection", 0)

            # Bills
            b = d.get("bill") if "bill" in d else d.get("bills", {})
            total_metrics["bill"]["total"] += b.get("total", 0)
            total_metrics["bill"]["expired"] += b.get("expired", 0)
            total_metrics["bill"]["count_pre_force_debt_collection"] += b.get("count_pre_force_debt_collection", 0)
            total_metrics["bill"]["value_pre_force_debt_collection"] += b.get("value_pre_force_debt_collection", 0.0)
            total_metrics["bill"]["count_force_debt_collection"] += b.get("count_force_debt_collection", 0)
            total_metrics["bill"]["value_force_debt_collection"] += b.get("value_force_debt_collection", 0.0)
            
            # Actions & CDR
            total_metrics["actions_today"]["dialer_triggers"] += d.get("actions_today", {}).get("dialer_triggers", 0)
            total_metrics["cdr_stats"]["total_calls"] += d.get("cdr_stats", {}).get("total_calls", 0)

            # Aggregate Bill Stats (simple merge for visualization)
            # Note: This is an approximation for global view as we can't easily merge overlapping keys without more logic
            # For now, we will skip detailed bill_stats for Global View to keep it clean, or just take the logs
    
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
    
    c_pre = data.get("clients", {}).get("count_pre_force_debt_collection", 0)
    c_force = data.get("clients", {}).get("count_force_debt_collection", 0)
    st.caption(f"Pre-Force: {c_pre} | Force: {c_force}")

with col2:
    st.metric("Expired Bills", data.get("bill", {}).get("expired", 0))
    st.caption(f"Total Bills: {data.get('bill', {}).get('total', 0)}")

with col3:
    # Calculate Total Debt Value from Pre+Force
    val_pre = data.get("bill", {}).get("value_pre_force_debt_collection", 0.0)
    val_force = data.get("bill", {}).get("value_force_debt_collection", 0.0)
    total_val = val_pre + val_force
    
    st.metric("Total Debt Value", f"R$ {total_val:,.2f}")
    st.caption(f"Pre: R$ {val_pre:,.2f} | Force: R$ {val_force:,.2f}")

with col4:
    st.metric("Triggers Today", data.get("actions_today", {}).get("dialer_triggers", 0))
    st.caption(f"CDR Count: {data.get('cdr_stats', {}).get('total_calls', 0)}")

# --- Charts & Activity ---
st.divider()

# Create tabs for different visualizations
tab_trends, tab_stats, tab_logs = st.tabs(["📈 Trends", "🏙️ Neighborhoods", "⚡ Activity Log"])

with tab_trends:
    st.subheader("Financial Evolution")
    # Fetch recent history
    hist = list(db.metrics.find(metrics_query).sort("timestamp", -1).limit(40))
    
    if hist:
        trend_data = []
        for h in hist:
            d_hist = h.get("data", {})
            b_hist = d_hist.get("bill") if "bill" in d_hist else d_hist.get("bills", {})
            
            trend_data.append({
                "Time": h["timestamp"],
                "Pre-Force Value": b_hist.get("value_pre_force_debt_collection", 0),
                "Force Value": b_hist.get("value_force_debt_collection", 0)
            })
            
        df_hist = pd.DataFrame(trend_data)
        
        if not df_hist.empty:
            fig = px.area(
                df_hist, 
                x="Time", 
                y=["Pre-Force Value", "Force Value"],
                color_discrete_map={"Pre-Force Value": "#fb8500", "Force Value": "#d00000"},
                template="plotly_dark"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No numeric data available for trends.")
    else:
        st.info("Insufficient history for trends.")

with tab_stats:
    if selected_instance_name == "🌍 Global (All Active)":
        st.warning("Neighborhood statistics are only available for single instance view.")
    else:
        st.subheader("Top Neighborhoods by Debt (Bills Count)")
        
        bill_stats = data.get("bill", {}).get("bill_stats", {})
        bairro_stats = bill_stats.get("bairro", {})
        
        if bairro_stats:
            # Convert dict to df
            df_bairro = pd.DataFrame(list(bairro_stats.items()), columns=["Neighborhood", "Bills"])
            df_bairro = df_bairro.sort_values("Bills", ascending=False).head(10)
            
            fig_bar = px.bar(
                df_bairro, 
                x="Bills", 
                y="Neighborhood", 
                orientation='h',
                color="Bills",
                template="plotly_dark"
            )
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No neighborhood statistics available.")

with tab_logs:
    st.subheader("Live Activity (Last 15)")
    # Fetch recent history_action_log
    log_query = {}
    if selected_instance_name != "🌍 Global (All Active)":
        log_query = {"instance_full_id": f_id}
    
    recent_logs = list(db.history_action_log.find(log_query).sort("occurred_at", -1).limit(15))
    
    if recent_logs:
        for log in recent_logs:
            col_icon, col_details = st.columns([0.5, 9.5])
            with col_icon:
                st.write("📞" if "dialer" in log.get("action", "") else "⚙️")
            with col_details:
                time_str = log["occurred_at"].strftime("%H:%M")
                action_clean = log.get('action').replace('_', ' ').title()
                st.markdown(f"**{time_str}** - {action_clean}")
                
                details = log.get('details', {})
                msg = details.get('message', '')
                num = details.get('number', '')
                if msg or num:
                    st.caption(f"{msg} {num}")
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
