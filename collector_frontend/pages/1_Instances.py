import streamlit as st
import pandas as pd
from db import get_db
from bson import ObjectId
from datetime import datetime
from utils import status_badge, export_to_json, confirm_action, safe_get
from utils_css import apply_light_theme

st.set_page_config(page_title="Gerenciar Instâncias", layout="wide")

# Apply light theme
apply_light_theme()

db = get_db()
instances_col = db.instance_config

st.title("📋 Gerenciamento de Instâncias")

# Busca e Filtro
col_search, col_filter = st.columns([3, 1])
with col_search:
    search_term = st.text_input("🔍 Buscar instâncias", placeholder="Buscar por nome...")
with col_filter:
    status_filter = st.selectbox("Filtrar por status", ["Todos", "Ativos", "Inativos"])

# --- Helper Functions ---
def get_instances():
    query = {}
    
    # Apply search filter
    if search_term:
        query["instance_name"] = {"$regex": search_term, "$options": "i"}
    
    # Aplicar filtro de status
    if status_filter == "Ativos":
        query["status.active"] = True
    elif status_filter == "Inativos":
        query["status.active"] = False
    
    return list(instances_col.find(query))

# --- Layout da UI ---
tab1, tab2, tab3 = st.tabs(["📋 Listar Instâncias", "➕ Adicionar Nova", "📥 Exportar/Importar"])

with tab1:
    st.subheader("Instâncias Existentes")
    instances = get_instances()
    
    if not instances:
        st.info("Nenhuma instância encontrada com os critérios informados.")
    else:
        # Métricas de resumo
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Total de Instâncias", len(instances))
        active_count = sum(1 for i in instances if i.get('status', {}).get('active'))
        col_m2.metric("Ativas", active_count)
        col_m3.metric("Inativas", len(instances) - active_count)
        
        st.divider()
        
        for inst in instances:
            inst_name = inst.get('instance_name', 'Desconhecida')
            is_active = inst.get('status', {}).get('active', False)
            
            with st.expander(f"🏢 {inst_name} - {status_badge(is_active)}"):
                # Alternar Modo de Visualização
                view_mode = st.radio("Modo de Visualização", ["📝 Formulário Categorizado", "{} Editor JSON"], key=f"mode_{inst['_id']}", horizontal=True, label_visibility="collapsed")
                st.divider()

                if view_mode == "📝 Formulário Categorizado":
                    with st.form(f"edit_form_{inst['_id']}"):
                        # --- CATEGORIA: Geral ---
                        st.markdown("#### ⚙️ Configurações Gerais")
                        g_col1, g_col2 = st.columns(2)
                        with g_col1:
                            new_name = st.text_input("Nome da Instância", value=inst.get('instance_name', ''))
                        with g_col2:
                            new_active = st.toggle("Instância Ativa", value=inst.get('status', {}).get('active', False))
                        
                        # --- CATEGORIA: ERP (IXC) ---
                        st.markdown("#### 🔌 Configuração do ERP")
                        erp = inst.get('erp', {})
                        e_col1, e_col2 = st.columns([3, 1])
                        with e_col1:
                            new_erp_url = st.text_input("URL Base", value=erp.get('base_url', ''))
                        with e_col2:
                            current_type = erp.get('type', 'ixc')
                            type_options = ["ixc", "rbx", "altarede"]
                            # Encontrar índice para o valor atual, padrão 0
                            try:
                                type_idx = type_options.index(current_type)
                            except ValueError:
                                type_idx = 0
                            new_erp_type = st.selectbox("Tipo", options=type_options, index=type_idx)
                        
                        e_col3, e_col4 = st.columns(2)
                        with e_col3:
                            new_erp_token = st.text_input("Token do Usuário", value=erp.get('auth', {}).get('user_token', ''), type="password")
                        with e_col4:
                            # Converter lista para string separada por vírgula para edição
                            filial_ids_val = ", ".join(map(str, erp.get('filial_id', [])))
                            new_filial_ids = st.text_input("IDs das Filiais (separados por vírgula)", value=filial_ids_val)
                        
                        # --- CATEGORIA: Asterisk (AMI) ---
                        st.markdown("#### 📞 Configuração Asterisk / AMI")
                        ast = inst.get('asterisk', {})
                        a_col1, a_col2, a_col3 = st.columns(3)
                        with a_col1:
                            new_ast_host = st.text_input("Host AMI", value=ast.get('host', ''))
                        with a_col2:
                            new_ast_port = st.text_input("Porta AMI", value=ast.get('port', '8088'))
                        with a_col3:
                            new_ast_user = st.text_input("Usuário AMI", value=ast.get('username', ''))
                        
                        a_col4, a_col5, a_col6 = st.columns(3)
                        with a_col4:
                            new_ast_pass = st.text_input("Senha AMI", value=ast.get('password', ''), type="password")
                        with a_col5:
                            new_ast_context = st.text_input("Contexto", value=ast.get('context', 'auto-charger-context'))
                        with a_col6:
                            new_ast_ext = st.text_input("Extensão", value=ast.get('extension', 'start'))
                        
                        a_col7, a_col8, a_col9 = st.columns(3)
                        with a_col7:
                            new_ast_ch_type = st.text_input("Tipo de Canal", value=ast.get('channel_type', 'SIP'))
                        with a_col8:
                            new_ast_channel = st.text_input("Nome do Tronco/Canal", value=ast.get('channel', ''))
                        with a_col9:
                            new_ast_ch_avail = st.number_input("Canais Máximos", value=ast.get('num_channel_available', 10), min_value=1)

                        # --- CATEGORIA: Banco de Dados CDR ---
                        st.markdown("#### 📊 Banco de Dados CDR")
                        c_col1, c_col2, c_col3, c_col4 = st.columns(4)
                        with c_col1:
                            new_cdr_host = st.text_input("Host CDR", value=ast.get('cdr_host', ''))
                        with c_col2:
                            new_cdr_port = st.text_input("Porta CDR", value=ast.get('cdr_port', '80'))
                        with c_col3:
                            new_cdr_user = st.text_input("Usuário CDR", value=ast.get('cdr_username', ''))
                        with c_col4:
                            new_cdr_pass = st.text_input("Senha CDR", value=ast.get('cdr_password', ''), type="password")

                        # --- CATEGORIA: Regras de Cobrança ---
                        st.markdown("#### ⚖️ Regras de Cobrança / Charger")
                        chg = inst.get('charger', {})
                        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                        with r_col1:
                            new_min_days = st.number_input("Dias Mínimos para Cobrar", value=chg.get('minimum_days_to_charge', 7))
                        with r_col2:
                            new_max_days = st.number_input("Máximo de Dias para Busca", value=chg.get('max_days_to_search', 30))
                        with r_col3:
                            new_dial_int = st.number_input("Intervalo de Discagem (min)", value=chg.get('dial_interval', 4))
                        with r_col4:
                            new_dial_day = st.number_input("Discagens por Dia", value=safe_get(chg, 'dial_per_day', 3))

                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("💾 Salvar Alterações de Configuração", use_container_width=True, type="primary"):
                            # Preparar atualização
                            update_doc = {
                                "instance_name": new_name,
                                "status.active": new_active,
                                "erp.type": new_erp_type,
                                "erp.base_url": new_erp_url,
                                "erp.auth.user_token": new_erp_token,
                                "erp.filial_id": [int(x.strip()) for x in new_filial_ids.split(",") if x.strip().isdigit()],
                                "asterisk.host": new_ast_host,
                                "asterisk.port": new_ast_port,
                                "asterisk.username": new_ast_user,
                                "asterisk.password": new_ast_pass,
                                "asterisk.context": new_ast_context,
                                "asterisk.extension": new_ast_ext,
                                "asterisk.channel_type": new_ast_ch_type,
                                "asterisk.channel": new_ast_channel,
                                "asterisk.num_channel_available": new_ast_ch_avail,
                                "asterisk.cdr_host": new_cdr_host,
                                "asterisk.cdr_port": new_cdr_port,
                                "asterisk.cdr_username": new_cdr_user,
                                "asterisk.cdr_password": new_cdr_pass,
                                "charger.minimum_days_to_charge": new_min_days,
                                "charger.max_days_to_search": new_max_days,
                                "charger.dial_interval": new_dial_int,
                                "charger.dial_per_day": new_dial_day,
                                "metadata.updated_at": datetime.now().isoformat()
                            }
                            
                            instances_col.update_one({"_id": inst["_id"]}, {"$set": update_doc})
                            st.success(f"✅ Configuração para {new_name} atualizada!")
                            st.rerun()
                
                else:
                    # Editor YAML/JSON
                    import json
                    st.markdown("#### 🛠️ Editor JSON Bruto")
                    st.caption("Edite o documento de configuração bruto abaixo. Tenha cuidado com a estrutura.")
                    
                    # Convert ObjectId and other non-serializable fields for Editor
                    serializable_inst = json.loads(json.dumps(inst, default=str))
                    
                    # Tool to remove _id for editing if desired, but we need it for update.
                    # Usually better to exclude _id from text area to avoid tampering.
                    edit_inst = serializable_inst.copy()
                    if "_id" in edit_inst: del edit_inst["_id"]

                    json_str = st.text_area("Conteúdo JSON", value=json.dumps(edit_inst, indent=4), height=500, key=f"json_edit_{inst['_id']}")
                    
                    c_col1, c_col2 = st.columns(2)
                    with c_col1:
                        if st.button("💾 Salvar Alterações JSON", key=f"save_json_{inst['_id']}", use_container_width=True, type="primary"):
                            try:
                                updated_data = json.loads(json_str)
                                # Manter o ID original
                                instances_col.replace_one({"_id": inst["_id"]}, updated_data)
                                st.success("✅ Configuração JSON atualizada!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ JSON Inválido: {e}")
                    
                    with c_col2:
                        # Exportar instância única
                        inst_json_dl = json.dumps(inst, indent=4, default=str)
                        st.download_button(
                            label="📥 Baixar Backup JSON",
                            data=inst_json_dl,
                            file_name=f"{inst_name}_config.json",
                            mime="application/json",
                            key=f"dl_json_{inst['_id']}",
                            use_container_width=True
                        )

                # Zona de Perigo fora das abas mas dentro do expander
                st.divider()
                with st.expander("🗑️ Zona de Perigo"):
                    st.write(f"Tem certeza que deseja excluir **{inst_name}**?")
                    if st.button("🗑️ Excluir Permanentemente", key=f"del_{inst['_id']}", type="primary", use_container_width=True):
                        instances_col.delete_one({"_id": inst["_id"]})
                        st.success(f"✅ {inst_name} excluído!")
                        st.rerun()

with tab2:
    st.subheader("Adicionar Nova Configuração de Instância")
    with st.form("new_instance_form"):
        # --- CATEGORIA: Geral ---
        st.markdown("#### ⚙️ Configurações Gerais")
        g_col1, g_col2 = st.columns(2)
        with g_col1:
            name = st.text_input("Nome da Instância*", placeholder="ex: Minha Empresa")
        with g_col2:
            active = st.toggle("Instância Ativa", value=True)
            
        # --- CATEGORIA: ERP ---
        st.markdown("#### 🔌 Configuração do ERP")
        erp_col1, erp_col2 = st.columns([3, 1])
        with erp_col1:
            erp_url = st.text_input("URL Base*", "https://ixc.sample.com.br/webservice/v1")
        with erp_col2:
            erp_type = st.selectbox("Tipo*", ["ixc", "rbx", "altarede"])
            
        e_col3, e_col4 = st.columns(2)
        with e_col3:
            erp_token = st.text_input("Token do Usuário*", type="password")
        with e_col4:
            filial_ids = st.text_input("IDs das Filiais (separados por vírgula)", "1")
        
        # --- CATEGORIA: Asterisk (AMI) ---
        st.markdown("#### 📞 Configuração Asterisk / AMI")
        a_col1, a_col2, a_col3 = st.columns(3)
        with a_col1:
            ast_host = st.text_input("Host AMI*", "0.0.0.0")
        with a_col2:
            ast_port = st.text_input("Porta AMI*", "8088")
        with a_col3:
            ast_user = st.text_input("Usuário AMI*", "admin")
        
        a_col4, a_col5, a_col6 = st.columns(3)
        with a_col4:
            ast_pass = st.text_input("Senha AMI*", type="password")
        with a_col5:
            ast_context = st.text_input("Contexto", "auto-charger-context")
        with a_col6:
            ast_ext = st.text_input("Extensão", "start")
        
        a_col7, a_col8, a_col9 = st.columns(3)
        with a_col7:
            ast_ch_type = st.text_input("Tipo de Canal", "SIP")
        with a_col8:
            ast_channel = st.text_input("Nome do Tronco/Canal*", "trunk-name")
        with a_col9:
            ast_ch_avail = st.number_input("Canais Máximos", value=10, min_value=1)

        # --- CATEGORIA: Banco de Dados CDR ---
        st.markdown("#### 📊 Banco de Dados CDR")
        c_col1, c_col2, c_col3, c_col4 = st.columns(4)
        with c_col1:
            cdr_host = st.text_input("Host CDR*", "0.0.0.0 (geralmente o Host AMI)")
        with c_col2:
            cdr_port = st.text_input("Porta CDR*", "80")
        with c_col3:
            cdr_user = st.text_input("Usuário CDR*", "admin")
        with c_col4:
            cdr_pass = st.text_input("Senha CDR*", type="password")

        # --- CATEGORIA: Regras de Cobrança ---
        st.markdown("#### ⚖️ Regras de Cobrança / Charger")
        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
        with r_col1:
            min_days = st.number_input("Dias Mínimos para Cobrar", value=7)
        with r_col2:
            max_days = st.number_input("Máximo de Dias para Busca", value=30)
        with r_col3:
            dial_int = st.number_input("Intervalo de Discagem (min)", value=4)
        with r_col4:
            dial_day = st.number_input("Discagens por Dia", value=3)

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("➕ Criar Instância", use_container_width=True, type="primary")
        
        if submitted:
            if not name or not erp_token or not ast_host or not ast_user or not ast_pass or not ast_channel:
                st.error("❌ Por favor, preencha todos os campos obrigatórios (marcados com *)")
            else:
                new_doc = {
                    "instance_name": name,
                    "erp": {
                        "type": erp_type,
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
                        "minimum_days_to_charge": min_days,
                        "max_days_to_search": max_days,
                        "dial_interval": dial_int,
                        "dial_per_day": dial_day
                    },
                    "asterisk": {
                        "host": ast_host,
                        "port": ast_port,
                        "username": ast_user,
                        "password": ast_pass,
                        "context": ast_context,
                        "extension": ast_ext,
                        "channel_type": ast_ch_type,
                        "channel": ast_channel,
                        "num_channel_available": ast_ch_avail,
                        "cdr_host": cdr_host,
                        "cdr_port": cdr_port,
                        "cdr_username": cdr_user,
                        "cdr_password": cdr_pass
                    },
                    "status": {
                        "active": active,
                        "last_sync": datetime.now().isoformat(),
                        "health": "ok"
                    },
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat()
                    }
                }
                instances_col.insert_one(new_doc)
                st.success(f"✅ Instância '{name}' criada com sucesso!")
                st.rerun()

with tab3:
    st.subheader("Exportação/Importação em Massa")
    
    col_exp, col_imp = st.columns(2)
    
    with col_exp:
        st.write("**Exportar Todas as Instâncias**")
        all_instances = list(instances_col.find({}))
        
        if all_instances:
            all_json = export_to_json(all_instances, "all_instances.json")
            st.download_button(
                label=f"📥 Baixar Todas ({len(all_instances)} instâncias)",
                data=all_json,
                file_name="all_instances_backup.json",
                mime="application/json",
                use_container_width=True
            )
        else:
            st.info("Nenhuma instância para exportar")
    
    with col_imp:
        st.write("**Importar Instâncias**")
        st.warning("⚠️ Isso adicionará novas instâncias. As existentes não serão afetadas.")
        
        uploaded_file = st.file_uploader("Carregar JSON de instâncias", type=['json'])
        
        if uploaded_file is not None:
            try:
                import json
                instances_data = json.load(uploaded_file)
                
                if not isinstance(instances_data, list):
                    instances_data = [instances_data]
                
                st.info(f"Encontrada(s) {len(instances_data)} instância(s) no arquivo")
                
                if st.button("📤 Importar Instâncias", use_container_width=True):
                    imported = 0
                    for inst_data in instances_data:
                        # Remover _id para evitar conflitos
                        if '_id' in inst_data:
                            del inst_data['_id']
                        
                        # Adicionar metadados
                        inst_data['metadata'] = {
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat(),
                            "imported": True
                        }
                        
                        instances_col.insert_one(inst_data)
                        imported += 1
                    
                    st.success(f"✅ Sucesso ao importar {imported} instância(s)!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Falha na importação: {e}")

st.divider()
st.caption("💡 Dica: Use as opções de busca e filtro para encontrar instâncias específicas rapidamente")
