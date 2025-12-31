"""Shared CSS styling for the Streamlit frontend - Light Theme."""
import streamlit as st

def apply_light_theme():
    """Apply consistent organic light theme across all pages."""
    st.markdown("""
    <style>
        /* Force Light Theme Backgrounds - More aggressive */
        [data-testid="stAppViewContainer"],
        [data-testid="stHeader"], 
        [data-testid="stToolbar"],
        .main,
        .stApp {
            background-color: #f8fafc !important;
        }
        
        /* Sidebar - Elegant Dark */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
        }
        [data-testid="stSidebar"] *,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label {
            color: #f8fafc !important;
        }
        [data-testid="stSidebar"] .stButton > button {
            background-color: #334155 !important;
            color: #f8fafc !important;
            border: 1px solid #475569 !important;
            border-radius: 8px !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background-color: #475569 !important;
            border-color: #64748b !important;
        }
        
        /* Main Content - Force all text to be dark */
        .main .block-container,
        .main [data-testid="stMarkdownContainer"] p,
        .main [data-testid="stMarkdownContainer"] h1,
        .main [data-testid="stMarkdownContainer"] h2,
        .main [data-testid="stMarkdownContainer"] h3,
        .main [data-testid="stMarkdownContainer"] h4,
        .main [data-testid="stMarkdownContainer"] h5,
        .main [data-testid="stMarkdownContainer"] h6,
        .main h1, .main h2, .main h3, .main h4, .main h5, .main h6,
        .main p, .main span, .main div,
        .main label,
        [data-testid="stMarkdownContainer"] {
            color: #0f172a !important;
        }
        
        /* Buttons - Primary (Blue gradient) */
        .stButton > button[kind="primary"],
        .stButton > button[kind="primaryFormSubmit"],
        button[kind="primary"] {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.5rem 1.5rem !important;
            font-weight: 600 !important;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3) !important;
        }
        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4) !important;
        }
        
        /* Secondary Buttons */
        .stButton > button[kind="secondary"],
        .stButton > button:not([kind="primary"]) {
            background-color: white !important;
            color: #0f172a !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 8px !important;
            padding: 0.5rem 1.5rem !important;
            font-weight: 600 !important;
        }
        .stButton > button[kind="secondary"]:hover,
        .stButton > button:not([kind="primary"]):hover {
            background-color: #f8fafc !important;
            border-color: #cbd5e1 !important;
        }
        
        /* Download Buttons */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
        }
        
        /* Metrics - Soft Cards */
        [data-testid="stMetric"] {
            background: white !important;
            padding: 1rem !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
            border: 1px solid #e2e8f0 !important;
        }
        [data-testid="stMetricValue"] {
            color: #0f172a !important;
            font-weight: 700 !important;
        }
        [data-testid="stMetricLabel"] {
            color: #64748b !important;
            font-weight: 600 !important;
        }
        
        /* Success/Info/Warning/Error Messages */
        .stSuccess,
        [data-testid="stNotificationContentSuccess"] {
            background-color: #f0fdf4 !important;
            border-left: 4px solid #22c55e !important;
            color: #166534 !important;
        }
        .stInfo,
        [data-testid="stNotificationContentInfo"] {
            background-color: #eff6ff !important;
            border-left: 4px solid #3b82f6 !important;
            color: #1e40af !important;
        }
        .stWarning,
        [data-testid="stNotificationContentWarning"] {
            background-color: #fffbeb !important;
            border-left: 4px solid #f59e0b !important;
            color: #92400e !important;
        }
        .stError,
        [data-testid="stNotificationContentError"] {
            background-color: #fef2f2 !important;
            border-left: 4px solid #ef4444 !important;
            color: #991b1b !important;
        }
        
        /* Forms - Clean inputs - CRITICAL FIX */
        input[type="text"],
        input[type="password"],
        input[type="number"],
        input[type="email"],
        textarea,
        [data-baseweb="input"] input,
        [data-baseweb="textarea"] textarea,
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stNumberInput > div > div > input {
            background-color: white !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 8px !important;
            color: #0f172a !important;
            padding: 0.5rem !important;
        }
        
        /* Select boxes */
        [data-baseweb="select"] > div,
        .stSelectbox > div > div {
            background-color: white !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 8px !important;
        }
        [data-baseweb="select"] span,
        .stSelectbox span {
            color: #0f172a !important;
        }
        
        /* Focus states */
        input:focus,
        textarea:focus,
        [data-baseweb="input"]:focus-within,
        [data-baseweb="textarea"]:focus-within {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
            outline: none !important;
        }
        
        /* Expanders - Soft shadows */
        [data-testid="stExpander"] {
            background-color: white !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 12px !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
        }
        [data-testid="stExpander"] summary {
            color: #0f172a !important;
            font-weight: 600 !important;
        }
        
        /* Tables */
        .dataframe,
        [data-testid="stTable"] {
            background-color: white !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 8px !important;
            overflow: hidden !important;
        }
        .dataframe thead tr th {
            background-color: #f8fafc !important;
            color: #64748b !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.05em !important;
            border-bottom: 2px solid #e2e8f0 !important;
        }
        .dataframe tbody tr {
            background-color: white !important;
        }
        .dataframe tbody tr:hover {
            background-color: #f1f5f9 !important;
        }
        .dataframe tbody tr td {
            color: #0f172a !important;
        }
        
        /* Tabs */
        [data-baseweb="tab-list"] {
            background-color: white !important;
            border-radius: 12px !important;
            padding: 0.25rem !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06) !important;
        }
        [data-baseweb="tab"] {
            border-radius: 8px !important;
            color: #64748b !important;
            font-weight: 600 !important;
        }
        [data-baseweb="tab"][aria-selected="true"] {
            background-color: #3b82f6 !important;
            color: white !important;
        }
        
        /* Checkboxes */
        [data-testid="stCheckbox"] label {
            color: #0f172a !important;
        }
        
        /* File Uploader */
        [data-testid="stFileUploader"] {
            background-color: white !important;
            border: 2px dashed #e2e8f0 !important;
            border-radius: 8px !important;
        }
        [data-testid="stFileUploader"] label {
            color: #64748b !important;
        }
        
        /* Dividers */
        hr {
            border-color: #e2e8f0 !important;
            margin: 2rem 0 !important;
        }
        
        /* Hide Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Custom card class for consistent styling */
        .custom-card {
            background-color: white !important;
            border-radius: 12px !important;
            padding: 1.5rem !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08) !important;
            border: 1px solid #e2e8f0 !important;
            margin-bottom: 1.5rem !important;
        }
    </style>
    """, unsafe_allow_html=True)
