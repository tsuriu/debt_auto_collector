import streamlit as st
import os
from dotenv import load_dotenv, set_key
from utils import test_mongo_connection, export_to_json
from utils_css import apply_light_theme
import json

st.set_page_config(page_title="Settings", layout="wide")

# Apply light theme
apply_light_theme()

# Path to root .env
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

st.title("⚙️ Global Settings")
st.write(f"Managing configuration in: `{dotenv_path}`")

# Load current values
load_dotenv(dotenv_path, override=True)

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DB_NAME", "debt_collector")
debug_mode = os.getenv("DEBUG", "false").lower() == "true"

# Test Connection Section
st.subheader("🔌 Database Connection Test")
col_test1, col_test2 = st.columns([3, 1])

with col_test1:
    test_uri = st.text_input("Test MongoDB URI", mongo_uri, key="test_uri")
    test_db = st.text_input("Test Database Name", db_name, key="test_db")

with col_test2:
    st.write("")  # Spacer
    st.write("")  # Spacer
    if st.button("🧪 Test Connection", use_container_width=True):
        with st.spinner("Testing connection..."):
            success, message = test_mongo_connection(test_uri, test_db)
            if success:
                st.success(message)
            else:
                st.error(message)

st.divider()

# Configuration Form
st.subheader("💾 Environment Configuration")

with st.form("settings_form"):
    new_mongo_uri = st.text_input("MongoDB URI", mongo_uri, 
                                   help="Format: mongodb://[username:password@]host[:port]/")
    new_db_name = st.text_input("Database Name", db_name,
                                help="Name of the MongoDB database to use")
    new_debug = st.checkbox("Debug Mode", value=debug_mode,
                           help="Enable verbose logging in the worker service")
    
    col_save, col_export = st.columns(2)
    
    with col_save:
        submitted = st.form_submit_button("💾 Save Changes", use_container_width=True)
    
    if submitted:
        # Validate inputs
        if not new_mongo_uri or not new_db_name:
            st.error("MongoDB URI and Database Name are required!")
        else:
            try:
                # Ensure file exists
                if not os.path.exists(dotenv_path):
                    open(dotenv_path, 'a').close()
                
                set_key(dotenv_path, "MONGO_URI", new_mongo_uri)
                set_key(dotenv_path, "DB_NAME", new_db_name)
                set_key(dotenv_path, "DEBUG", str(new_debug).lower())
                
                st.success("✅ Configuration updated successfully!")
                st.info("⚠️ Note: The worker service and this app need to be restarted to apply changes.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Failed to save settings: {e}")

# Export/Import Configuration
st.divider()
st.subheader("📦 Backup & Restore")

col_exp, col_imp = st.columns(2)

with col_exp:
    st.write("**Export Configuration**")
    config_data = {
        "MONGO_URI": os.getenv("MONGO_URI"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DEBUG": os.getenv("DEBUG")
    }
    
    json_data = export_to_json(config_data, "config.json")
    st.download_button(
        label="📥 Download .env Config",
        data=json_data,
        file_name="collector_config.json",
        mime="application/json",
        use_container_width=True
    )

with col_imp:
    st.write("**Import Configuration**")
    uploaded_file = st.file_uploader("Upload config JSON", type=['json'])
    
    if uploaded_file is not None:
        try:
            config = json.load(uploaded_file)
            
            if st.button("📤 Apply Imported Config", use_container_width=True):
                for key, value in config.items():
                    if key in ["MONGO_URI", "DB_NAME", "DEBUG"]:
                        set_key(dotenv_path, key, str(value))
                
                st.success("✅ Configuration imported successfully!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Invalid configuration file: {e}")

# Current Environment Display
st.divider()
st.subheader("📋 Current Environment Variables")

env_display = {
    "MONGO_URI": os.getenv("MONGO_URI", "Not set"),
    "DB_NAME": os.getenv("DB_NAME", "Not set"),
    "DEBUG": os.getenv("DEBUG", "false")
}

st.json(env_display)

st.caption("💡 Tip: Always test the connection before saving to avoid configuration errors")
