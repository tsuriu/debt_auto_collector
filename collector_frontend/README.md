# Collector Frontend Documentation

## Overview

The `collector_frontend` is a Streamlit-based web application that provides a centralized dashboard for monitoring and managing the debt collection operation. it serves as the user interface for the `collector_worker`, allowing for real-time data visualization and instance configuration.

## Architecture

The application is structured using Streamlit's multi-page feature.

### Directory Structure
```
collector_frontend/
├── Home.py                 # Landing page and navigation
├── db.py                   # MongoDB shared connection handler
├── utils.py                # Formatting and data helpers
├── utils_css.py            # Theme and custom CSS definitions
├── requirements.txt        # Frontend dependencies
├── Dockerfile              # Container definition
└── pages/
    ├── 1_Instances.py      # Instance Management (CRUD & Config)
    ├── 2_Expired_Bills.py  # Monitoring of Open and Expired Invoices
    ├── 3_Blocked_Contracts.py # Monitoring of Suspended Services
    ├── 4_Collection_Dashboard.py # Operational Control for Manual Recovery
    └── 5_Settings.py       # Global system settings
```

## Key Features

### 1. Expired Bills Overview (`2_Expired_Bills.py`)
Provides a comprehensive overview of the operation with a focus on delinquent invoices:
- **Clients**: Total active clients vs. clients with open debt. Features specialized horizontal stack charts and centralized KPI cards.
- **Bills Overview**: 
    - **Proportional Layout**: Expanded center area for the Bill Counts bar graph.
    - **Stacked Breakdown**: Pre-Debt and Debt Collector value cards are vertically stacked for optimal readability.
    - **Single-Line Format**: Primary expired KPIs (Total and Value) use a streamlined horizontal `LABEL : VALUE` format.
- **CDR Overview**: Telephony performance metrics for the **Current Day**:
    - **Daily Filter**: All metrics and historical trends are automatically filtered to show data only for the current calendar day (from 00:00:00).
    - **Disposition Redesign**: Outcome counts are displayed in color-coded, single-line horizontal boxes with the format `DISPOSITION : VALUE`.
    - **Disposition Trend**: A high-fidelity Stacked Area Chart (ECharts) visualizing outcome trends throughout the day.
- **Auto-Refresh**: The dashboard is hardcoded to refresh every **60 seconds**, ensuring real-time relevance without manual configuration.

### 2. Blocked Contracts Dashboard (`3_Blocked_Contracts.py`)
Monitoring and analysis of customers with suspended services:
- **Optimized Performance**: Directly consumes aggregated counts from the `metrics` collection, ensuring fast load times even for thousands of contracts.
- **Vertical Alignment**: Top section features a balanced 4-column layout where counters are vertically stretched to match the height of evolution charts.
- **Distribution Analysis**:
    - **Bairro & Tipo Cliente**: Vertical stacked bar charts with delay-based grouping (**Orange** for ≤ 7 days, **Red** for > 7 days).
    - **Dívida por Atraso**: Stacked bar chart showing the breakdown of debt age, highlighting operational groups.
- **Evolution Tracking**: Historical Stacked Area and Bar charts for connectivity and speed tier trends.
- **Detailed Inventory**: Bill-centric tables separated into **Curto Prazo (≤ 7 dias)** and **Longo Prazo (> 7 dias)**, displaying essential columns like `ID Fatura`, `Cliente`, `Valor`, `Vencimento`, and `Status Bloqueio`.
    - **Status Bloqueio Interpretation**:
        - **🌐 (Internet)**: Connectivity state from IXC (e.g., *Bloqueio Automático*, *Financeiro em Atraso*).
        - **🚀 (Velocidade)**: Speed tier state (*Normal* or *Reduzida*).
        - **✅ Ativo / Não Bloqueado**: Bill is expired but no technical restriction has been applied to the contract yet.
- **Auto-Refresh**: Synchronized with the 60-second system-wide refresh for real-time monitoring.

### 3. Collection Dashboard (`4_Collection_Dashboard.py`)
Operational command center focused on high-priority manual recovery:
- **Trust Unlock (DC) Integration**: 
    - Dedicated KPI for active "Desbloqueio Confiança" contracts.
    - Vertical stacked bar charts showing the breakdown between Comum and DC contracts sorted by due date.
- **Action List**: A highly focused list of clients requiring manual contact:
    - **Filtering**: Specifically includes clients with 8+ days of delay who are either blocked or have an active trust unlock.
    - **Categorization**: Primary list for immediate contact and an expander for all other overdue items.
- **Dynamic Context**: Sidebar allows filtering by Instance and Due Date for specialized operational focus.

### 4. Instance Management (`1_Instances.py`)
Allows for granular control over individual customer instances:
- **Categorized Form**: UI organized into logical sections (General, ERP, Asterisk/AMI, CDR Database, Collection Rules). Dashboard-specific controls are globally managed and removed from instance forms.
- **ERP Type Support**: Dropdown selection for multiple ERP integrations (**ixc**, **rbx**, **altarede**).
- **JSON Editor Toggle**: Advanced users can switch between the form view and a raw JSON editor for bulk configuration changes.
- **Instance Creation**: Standardized form for onboarding new instances with all required technical and business parameters.
- **Danger Zone**: Protected area for instance deletion.

### 3. Professional Theme (`utils_css.py`)
- **Organic Light Theme**: A customized, high-fidelity UI that maintains a professional look even in dark mode.
- **Design System**: Uses custom CSS for KPI cards, section headers, and data tables to ensure consistency across pages.

## Technical Details

- **ECharts Integration**: Uses `streamlit-echarts` for complex visualizations (Stacked Area, Nightingale Rose, etc.).
- **MongoDB Integration**: Directly queries the `metrics`, `instance_config`, and `client_types` collections.
- **Data Merging**: Implements complex logic in the dashboard to sum and average metrics from multiple documents in Global mode.

## Configuration

The application uses `python-dotenv` for configuration.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MONGO_URI` | `mongodb://localhost:27017/` | MongoDB connection string |
| `TZ` | `America/Maceio` | Timezone for reporting timestamps |

## Deployment

### Docker
The frontend is fully containerized and integrated into the project's Docker Compose.
```bash
docker compose up -d --build
```
Port `8501` is exposed by default. Live-mounting of the `./collector_frontend` directory is enabled for development environments.
