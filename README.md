# Debt Collector Python Ecosystem

A professional, high-fidelity ecosystem for automating debt collection. This project replicates and enhances the logic of the "Debt Collector" Node-RED flow, providing a background worker for data synchronization and a Streamlit-based dashboard for real-time monitoring.

## 🏗️ Architecture

The project is composed of two main Python components and a database:

- **[Collector Worker](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_worker/documentation.md)**: Background service that orchestrates data syncing (IXC ERP), processing (Hydrating client/bill metadata), and metrics generation.
- **[Collector Frontend](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_frontend/documentation.md)**: Interactive Streamlit dashboards (Monitoring, Blocked Contracts, Collection Control) and instance configuration.
- **MongoDB**: Centralized storage for clients, bills, metrics, and configurations.

## 🚀 Quick Start (Docker)

The fastest way to run the entire stack is via Docker Compose:

1. **Setup Environment**:
   ```bash
   cp .env.example .env
   # Configure MONGO_URI if not using the internal compose mongo
   ```

2. **Launch Ecosystem**:
   ```bash
   docker compose up -d --build
   ```

3. **Access Services**:
   - **Dashboard**: `http://localhost:8501`
   - **MongoDB Control**: `http://localhost:27018` (Mapped port)

## ✨ Key Features

### Background Worker (`collector_worker`)
- **Multi-Instance Support**: Parallel processing of multiple ERP/PABX configurations.
- **Smart Dialer**: Priority-based call queue with strict daily and hourly frequency limits.
- **CDR Optimization**: Automatically fetches and optimizes call reports from Asterisk with integrated machine detection (AMD).
- **Metric Snapshots**: Generates periodic data points for deep historical analysis.

### Interactive Dashboard (`collector_frontend`)
- **Real-time Monitoring**: Comprehensive KPIs for active clients, debt volume, and daily collection status.
- **Automated Refresh**: Hardcoded 60-second auto-refresh across all dashboard views for consistent real-time monitoring.
- **Expired Bills Focus**: Specialized view for tracking and analyzing delinquent invoices with aging breakdowns and payment trends.
- **Blocked Contracts Dashboard**: Specialized monitoring for suspended services:
    - **Evolution Tracking**: Trend analysis for connectivity and speed tier states.
    - **Demographic Breakdown**: Distribution by Bairro and Client Type with delay cohort grouping.
    - **Inventory Management**: Prioritized tables for **Curto Prazo (≤ 7 dias)** and **Longo Prazo (> 7 dias)**.
- **Collection Dashboard**: Operational command center for manual recovery:
    - **Trust Unlock (DC) Integration**: Real-time counters and stacked visualizations for "Desbloqueio Confiança" status.
    - **Action List**: Focus on high-priority contacts (8+ days delay) who are already blocked or using their trust unlock.
    - **Quantity-Based Distribution**: Vertical stacked bar charts showing Comum vs. DC counts per due date.
- **Advanced Visualizations**:
    - **CDR Performance**:outcome analysis with high-fidelity daily trend charts.
    - **Color-Coded Analysis**: Unified status colors (**Orange** for short-term, **Red** for critical delays).
- **Robust Configuration**:
    - Multi-ERP support (**ixc**, **rbx**, **altarede**) with specialized reverse mapping for data normalization.
    - Integrated **Form/JSON Toggle** for advanced technical configurations.

## 🛠️ Development

### Manual Setup
1. **Install Dependencies**: `pip install -r collector_worker/requirements.txt && pip install -r collector_frontend/requirements.txt`
2. **Run Worker**: `python3 collector_worker/main.py`
3. **Run Frontend**: `streamlit run collector_frontend/Home.py`

## 📄 Documentation
- Detailed Worker Logic: [collector_worker/documentation.md](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_worker/documentation.md)
- Detailed Frontend & UI: [collector_frontend/documentation.md](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_frontend/documentation.md)
