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
    ├── 2_Dashboard.py      # Main Metrics and CDR Overview
    └── 3_Settings.py       # Global system settings
```

## Key Features

### 1. Unified Dashboard (`2_Dashboard.py`)
Provides a comprehensive overview of the operation across three main domains:
- **Clients**: Total active clients vs. clients with open debt, using interactive horizontal stack charts.
- **Bills Overview**: Detailed breakdown of expired bill counts and values, categorized by collection rules (Pre-Debt vs. Debt Collector).
- **Categorized Charts**: Vertical bar graphs for **Client Type**, **Neighborhood**, and **Debt Aging (Expired Age)**, limited to the top 8 elements for clarity.
- **CDR Overview**: Real-time telephony performance metrics:
    - **KPIs**: Total calls and average duration (seconds).
    - **Disposition Trend**: A high-fidelity Stacked Area Chart (ECharts) visualizing call outcomes (ANSWERED, BUSY, FAILED, NO ANSWER, CONGESTION) over time.
- **Global View**: Automatically aggregates and merges metrics from all active instances into a single unified workspace.

### 2. Instance Management (`1_Instances.py`)
Allows for granular control over individual customer instances:
- **Categorized Form**: UI organized into logical sections (General, ERP, Asterisk/AMI, CDR Database, Collection Rules).
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
