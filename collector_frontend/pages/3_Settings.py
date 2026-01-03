import streamlit as st
import os
from dotenv import load_dotenv, set_key
from utils import test_mongo_connection, export_to_json
from utils_css import apply_light_theme
import json

st.set_page_config(page_title="Configurações", layout="wide")

# Aplicar tema claro
apply_light_theme()

# Caminho para o .env na raiz
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

st.title("⚙️ Configurações Globais")
st.write(f"Gerenciando configurações em: `{dotenv_path}`")

# Carregar valores atuais
load_dotenv(dotenv_path, override=True)

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
db_name = os.getenv("DB_NAME", "debt_collector")
debug_mode = os.getenv("DEBUG", "false").lower() == "true"

# Seção de Teste de Conexão
st.subheader("🔌 Teste de Conexão com o Banco")
col_test1, col_test2 = st.columns([3, 1])

with col_test1:
    test_uri = st.text_input("URI do MongoDB para Teste", mongo_uri, key="test_uri")
    test_db = st.text_input("Nome do Banco para Teste", db_name, key="test_db")

with col_test2:
    st.write("")  # Espaçador
    st.write("")  # Espaçador
    if st.button("🧪 Testar Conexão", use_container_width=True):
        with st.spinner("Testando conexão..."):
            success, message = test_mongo_connection(test_uri, test_db)
            if success:
                st.success(message)
            else:
                st.error(message)

st.divider()

# Formulário de Configuração
st.subheader("💾 Configuração de Ambiente")

with st.form("settings_form"):
    new_mongo_uri = st.text_input("URI do MongoDB", mongo_uri, 
                                   help="Formato: mongodb://[usuario:senha@]host[:porta]/")
    new_db_name = st.text_input("Nome do Banco de Dados", db_name,
                                help="Nome do banco de dados MongoDB a ser usado")
    new_debug = st.checkbox("Modo Debug", value=debug_mode,
                           help="Habilita logs detalhados no serviço worker")
    
    col_save, col_export = st.columns(2)
    
    with col_save:
        submitted = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)
    
    if submitted:
        # Validar entradas
        if not new_mongo_uri or not new_db_name:
            st.error("URI do MongoDB e Nome do Banco de Dados são obrigatórios!")
        else:
            try:
                # Garantir que o arquivo existe
                if not os.path.exists(dotenv_path):
                    open(dotenv_path, 'a').close()
                
                set_key(dotenv_path, "MONGO_URI", new_mongo_uri)
                set_key(dotenv_path, "DB_NAME", new_db_name)
                set_key(dotenv_path, "DEBUG", str(new_debug).lower())
                
                st.success("✅ Configuração atualizada com sucesso!")
                st.info("⚠️ Nota: O serviço worker e este aplicativo precisam ser reiniciados para aplicar as alterações.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Falha ao salvar configurações: {e}")

# Exportar/Importar Configuração
st.divider()
st.subheader("📦 Backup e Restauração")

col_exp, col_imp = st.columns(2)

with col_exp:
    st.write("**Exportar Configurações**")
    config_data = {
        "MONGO_URI": os.getenv("MONGO_URI"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DEBUG": os.getenv("DEBUG")
    }
    
    json_data = export_to_json(config_data, "config.json")
    st.download_button(
        label="📥 Baixar Configuração .env",
        data=json_data,
        file_name="collector_config.json",
        mime="application/json",
        use_container_width=True
    )

with col_imp:
    st.write("**Importar Configurações**")
    uploaded_file = st.file_uploader("Carregar JSON de configuração", type=['json'])
    
    if uploaded_file is not None:
        try:
            config = json.load(uploaded_file)
            
            if st.button("📤 Aplicar Configuração Importada", use_container_width=True):
                for key, value in config.items():
                    if key in ["MONGO_URI", "DB_NAME", "DEBUG"]:
                        set_key(dotenv_path, key, str(value))
                
                st.success("✅ Configuração importada com sucesso!")
                st.rerun()
        except Exception as e:
            st.error(f"❌ Arquivo de configuração inválido: {e}")

# Exibição do Ambiente Atual
st.divider()
st.subheader("📋 Variáveis de Ambiente Atuais")

env_display = {
    "MONGO_URI": os.getenv("MONGO_URI", "Não definido"),
    "DB_NAME": os.getenv("DB_NAME", "Não definido"),
    "DEBUG": os.getenv("DEBUG", "false")
}

st.json(env_display)

st.caption("💡 Dica: Sempre teste a conexão antes de salvar para evitar erros de configuração")
