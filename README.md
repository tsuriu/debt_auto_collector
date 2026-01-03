# Debt Collector Python Ecosystem

A professional, high-fidelity ecosystem for automating debt collection. This project replicates and enhances the logic of the "Debt Collector" Node-RED flow, providing a background worker for data synchronization and a Streamlit-based dashboard for real-time monitoring.

## 🏗️ Architecture

The project is composed of two main Python components and a database:

- **[Collector Worker](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_worker/documentation.md)**: Background service that orchestrates data syncing (IXC ERP), call triggers (Asterisk ARI), and metrics generation.
- **[Collector Frontend](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_frontend/documentation.md)**: Interactive Streamlit dashboard for data visualization and instance configuration.
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
- **Automated Refresh**: Hardcoded 60-second auto-refresh for consistent real-time monitoring.
- **Daily Focus**: All historical charts and trends are automatically filtered to show metrics for the **current day**.
- **Advanced Visualizations**:
    - **CDR Overview**: Redesigned disposition grid with color-coded horizontal stats and daily trend charts.
    - **Categorized Charts**: Vertical Bar graphs for demographic and debt aging analysis.
- **Robust Configuration**:
    - A categorized form-based editor for instance management.
    - Dropdown support for multiple ERP types (**ixc**, **rbx**, **altarede**).
    - Integrated **Form/JSON Toggle** for technical configuration flexibility.

## 🛠️ Development

### Manual Setup
1. **Install Dependencies**: `pip install -r collector_worker/requirements.txt && pip install -r collector_frontend/requirements.txt`
2. **Run Worker**: `python3 collector_worker/main.py`
3. **Run Frontend**: `streamlit run collector_frontend/Home.py`

## 📄 Documentation
- Detailed Worker Logic: [collector_worker/documentation.md](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_worker/documentation.md)
- Detailed Frontend & UI: [collector_frontend/documentation.md](file:///Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_frontend/documentation.md)
