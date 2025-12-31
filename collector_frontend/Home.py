import streamlit as st
from db import get_db
from utils import test_mongo_connection, format_datetime
from utils_css import apply_light_theme
import os

st.set_page_config(
    page_title="Debt Collector Control Center",
    page_icon="🤖",
    layout="wide"
)

# Apply light theme
apply_light_theme()

st.title("🤖 Debt Collector Control Center")

st.markdown("""
Welcome to the collector management interface. Use the sidebar to navigate between:

- **📋 Instances**: Manage your ERP and Asterisk instance configurations (CRUD).
- **📊 Dashboard**: Visualize collection metrics, debt status, and dialer performance.
- **⚙️ Settings**: Update project-wide environment variables (`.env`).
""")

# System Health Check
db = get_db()
mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DB_NAME", "debt_collector")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🔧 System Status")
    
    # Test database connection
    try:
        db.command('ping')
        st.success("✅ Database: Connected")
        
        # Get collection stats
        collections = db.list_collection_names()
        st.caption(f"Collections: {len(collections)}")
    except Exception as e:
        st.error(f"❌ Database: Disconnected")
        st.caption(f"Error: {str(e)[:50]}...")

with col2:
    st.subheader("📊 Quick Stats")
    
    try:
        # Count active instances
        active_instances = db.instance_config.count_documents({"status.active": True})
        total_instances = db.instance_config.count_documents({})
        st.metric("Active Instances", active_instances, delta=f"{total_instances} total")
        
        # Latest metrics timestamp
        latest_metric = db.metrics.find_one({}, sort=[("timestamp", -1)])
        if latest_metric:
            last_update = format_datetime(latest_metric.get("timestamp"))
            st.caption(f"Last Metrics: {last_update}")
        else:
            st.caption("No metrics collected yet")
            
    except Exception as e:
        st.warning("Unable to fetch stats")

with col3:
    st.subheader("🚀 Quick Actions")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("📋 Instances", use_container_width=True):
            st.switch_page("pages/1_Instances.py")
    
    with col_b:
        if st.button("📊 Dashboard", use_container_width=True):
            st.switch_page("pages/2_Dashboard.py")
    
    if st.button("⚙️ Settings", use_container_width=True):
        st.switch_page("pages/3_Settings.py")

# Recent Activity Preview
st.divider()
st.subheader("⚡ Recent System Activity")

try:
    recent_logs = list(db.history_action_log.find({}).sort("occurred_at", -1).limit(5))
    if recent_logs:
        for log in recent_logs:
            icon = "📞" if "dialer" in log.get("action", "") else "⚙️"
            time_str = format_datetime(log.get("occurred_at"))
            action = log.get("action", "unknown").replace("_", " ").title()
            st.write(f"{icon} **{time_str}** - {action}")
    else:
        st.info("No recent activity found. The worker service may not be running yet.")
except Exception as e:
    st.warning("Unable to load recent activity")

st.divider()
st.caption("💡 Tip: Enable auto-refresh on the Dashboard for TV monitoring mode")
