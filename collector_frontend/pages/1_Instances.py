import streamlit as st
import pandas as pd
from db import get_db
from bson import ObjectId
from datetime import datetime
from utils import status_badge, export_to_json, confirm_action

st.set_page_config(page_title="Manage Instances", layout="wide")

db = get_db()
instances_col = db.instance_config

st.title("📋 Instance Management")

# Search and Filter
col_search, col_filter = st.columns([3, 1])
with col_search:
    search_term = st.text_input("🔍 Search instances", placeholder="Search by name...")
with col_filter:
    status_filter = st.selectbox("Filter by status", ["All", "Active", "Inactive"])

# --- Helper Functions ---
def get_instances():
    query = {}
    
    # Apply search filter
    if search_term:
        query["instance_name"] = {"$regex": search_term, "$options": "i"}
    
    # Apply status filter
    if status_filter == "Active":
        query["status.active"] = True
    elif status_filter == "Inactive":
        query["status.active"] = False
    
    return list(instances_col.find(query))

# --- UI Layout ---
tab1, tab2, tab3 = st.tabs(["📋 List Instances", "➕ Add New", "📥 Export/Import"])

with tab1:
    st.subheader("Existing Instances")
    instances = get_instances()
    
    if not instances:
        st.info("No instances found matching your criteria.")
    else:
        # Summary metrics
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total Instances", len(instances))
        active_count = sum(1 for i in instances if i.get('status', {}).get('active'))
        col_m2.metric("Active", active_count)
        col_m3.metric("Inactive", len(instances) - active_count)
        
        st.divider()
        
        for inst in instances:
            inst_name = inst.get('instance_name', 'Unknown')
            is_active = inst.get('status', {}).get('active', False)
            
            with st.expander(f"🏢 {inst_name} - {status_badge(is_active)}"):
                # Create tabs for view and edit
                view_tab, edit_tab, actions_tab = st.tabs(["👁️ View", "✏️ Edit", "⚙️ Actions"])
                
                with view_tab:
                    st.json(inst)
                
                with edit_tab:
                    with st.form(f"edit_form_{inst['_id']}"):
                        st.write("**Basic Information**")
                        new_name = st.text_input("Instance Name", value=inst_name)
                        new_active = st.checkbox("Active", value=is_active)
                        
                        st.write("**ERP Configuration**")
                        erp = inst.get('erp', {})
                        new_erp_url = st.text_input("Base URL", value=erp.get('base_url', ''))
                        new_erp_token = st.text_input("User Token", value=erp.get('auth', {}).get('user_token', ''), type="password")
                        
                        st.write("**Asterisk Configuration**")
                        ast = inst.get('asterisk', {})
                        new_ast_host = st.text_input("Host", value=ast.get('host', ''))
                        new_ast_user = st.text_input("Username", value=ast.get('username', ''))
                        new_ast_pass = st.text_input("Password", value=ast.get('password', ''), type="password")
                        
                        if st.form_submit_button("💾 Save Changes", use_container_width=True):
                            update_doc = {
                                "instance_name": new_name,
                                "status.active": new_active,
                                "status.last_sync": datetime.now().isoformat(),
                                "erp.base_url": new_erp_url,
                                "erp.auth.user_token": new_erp_token,
                                "asterisk.host": new_ast_host,
                                "asterisk.username": new_ast_user,
                                "asterisk.password": new_ast_pass,
                                "metadata.updated_at": datetime.now().isoformat()
                            }
                            
                            instances_col.update_one({"_id": inst["_id"]}, {"$set": update_doc})
                            st.success(f"✅ Updated {new_name}")
                            st.rerun()
                
                with actions_tab:
                    st.write("**Quick Actions**")
                    
                    col_a1, col_a2 = st.columns(2)
                    
                    with col_a1:
                        if st.button("🔄 Toggle Active", key=f"toggle_{inst['_id']}", use_container_width=True):
                            new_status = not is_active
                            instances_col.update_one(
                                {"_id": inst["_id"]}, 
                                {"$set": {
                                    "status.active": new_status, 
                                    "status.last_sync": datetime.now().isoformat()
                                }}
                            )
                            st.success(f"Status changed to {'Active' if new_status else 'Inactive'}")
                            st.rerun()
                    
                    with col_a2:
                        # Export single instance
                        inst_json = export_to_json(inst, f"{inst_name}.json")
                        st.download_button(
                            label="📥 Export JSON",
                            data=inst_json,
                            file_name=f"{inst_name}_config.json",
                            mime="application/json",
                            key=f"export_{inst['_id']}",
                            use_container_width=True
                        )
                    
                    st.divider()
                    st.write("**Danger Zone**")
                    
                    confirm_delete = st.checkbox(
                        f"⚠️ I understand this will permanently delete {inst_name}",
                        key=f"confirm_{inst['_id']}"
                    )
                    
                    if st.button("🗑️ Delete Instance", 
                                key=f"del_{inst['_id']}", 
                                disabled=not confirm_delete,
                                type="primary",
                                use_container_width=True):
                        instances_col.delete_one({"_id": inst["_id"]})
                        st.success(f"✅ Deleted {inst_name}")
                        st.rerun()

with tab2:
    st.subheader("Add New Instance Configuration")
    with st.form("new_instance_form"):
        name = st.text_input("Instance Name*", placeholder="e.g. Acme Corp")
        
        st.write("**ERP Configuration (IXC)**")
        erp_url = st.text_input("Base URL*", "https://ixc.sample.com.br/webservice/v1")
        erp_token = st.text_input("User Token*", type="password")
        filial_ids = st.text_input("Filial IDs (comma separated)", "1")
        
        st.write("**Asterisk Configuration**")
        ast_host = st.text_input("Host*", "0.0.0.0")
        ast_user = st.text_input("Username*", "admin")
        ast_pass = st.text_input("Password*", type="password")
        ast_channel = st.text_input("Channel*", "biller-trunk")
        
        submitted = st.form_submit_button("➕ Create Instance", use_container_width=True)
        
        if submitted:
            if not name or not erp_token or not ast_host or not ast_user or not ast_pass:
                st.error("❌ Please fill all required fields (marked with *)")
            else:
                new_doc = {
                    "instance_name": name,
                    "erp": {
                        "type": "ixc",
                        "base_url": erp_url,
                        "auth": {"user_id": "", "user_token": erp_token},
                        "filial_id": [int(x.strip()) for x in filial_ids.split(",") if x.strip().isdigit()],
                        "request_param": {
                            "default_page_size": 600,
                            "max_records": 50000,
                            "delay_between_pages": 150,
                            "safety_limit": 1000
                        }
                    },
                    "charger": {
                        "minimum_days_to_charge": 7,
                        "max_days_to_search": 30,
                        "dial_interval": 4,
                        "dial_per_day": 3
                    },
                    "asterisk": {
                        "host": ast_host,
                        "port": "8088",
                        "username": ast_user,
                        "password": ast_pass,
                        "context": "auto-charger-context",
                        "extension": "start",
                        "channel_type": "SIP",
                        "channel": ast_channel,
                        "num_channel_available": 10,
                        "cdr_host": ast_host,
                        "cdr_port": "80",
                        "cdr_username": ast_user,
                        "cdr_password": ast_pass
                    },
                    "status": {
                        "active": True,
                        "last_sync": datetime.now().isoformat(),
                        "health": "ok"
                    },
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                }
                instances_col.insert_one(new_doc)
                st.success(f"✅ Instance '{name}' created successfully!")
                st.rerun()

with tab3:
    st.subheader("Bulk Export/Import")
    
    col_exp, col_imp = st.columns(2)
    
    with col_exp:
        st.write("**Export All Instances**")
        all_instances = list(instances_col.find({}))
        
        if all_instances:
            all_json = export_to_json(all_instances, "all_instances.json")
            st.download_button(
                label=f"📥 Download All ({len(all_instances)} instances)",
                data=all_json,
                file_name="all_instances_backup.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.info("No instances to export")
    
    with col_imp:
        st.write("**Import Instances**")
        st.warning("⚠️ This will add new instances. Existing ones won't be affected.")
        
        uploaded_file = st.file_uploader("Upload instances JSON", type=['json'])
        
        if uploaded_file is not None:
            try:
                import json
                instances_data = json.load(uploaded_file)
                
                if not isinstance(instances_data, list):
                    instances_data = [instances_data]
                
                st.info(f"Found {len(instances_data)} instance(s) in file")
                
                if st.button("📤 Import Instances", use_container_width=True):
                    imported = 0
                    for inst_data in instances_data:
                        # Remove _id to avoid conflicts
                        if '_id' in inst_data:
                            del inst_data['_id']
                        
                        # Add metadata
                        inst_data['metadata'] = {
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                            "imported": True
                        }
                        
                        instances_col.insert_one(inst_data)
                        imported += 1
                    
                    st.success(f"✅ Successfully imported {imported} instance(s)!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Import failed: {e}")

st.divider()
st.caption("💡 Tip: Use the search and filter options to quickly find specific instances")
