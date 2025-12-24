# Debt Collector Python App

A Python application that replicates the logic of the "Debt Collector" Node-RED flow. It automatically fetches client and bill data from IXC Soft ERP, processes debts, and manages an auto-dialer via Asterisk (ARI).

## Structure

- `collector_worker/main.py`: Entry point. Orchestrates the scheduler (Clients, Bills, Reports, Dialer jobs).
- `services/ixc_client.py`: Handles IXC API communication (Auth, Pagination, Rate Limiting).
- `services/processor.py`: Business logic for data normalization, due date calculation, and correlating Bills with Clients.
- `services/report_service.py`: Fetches CDR reports and detailed events from Asterisk/Issabel and stores them in MongoDB.
- `services/dialer.py`: Manages call windows, builds queues, and triggers calls.
- `services/verification.py`: Handles database structure verification and Loguru reporting.
- `database.py`: MongoDB connection and schema definitions.
- `config.py`: Environment configuration.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Copy `.env.example` to `.env` and configure your MongoDB URI.
   ```bash
   cp .env.example .env
   ```
   
   Ensure your MongoDB has an `instance_config` collection with the active instances (as used in the Node-RED flow).

3. **Run**:
   ```bash
   python3 collector_worker/main.py
   ```
   
   **CLI Arguments**:
   You can run specific jobs manually for debugging or one-off execution:
   ```bash
   # Run only the Reports job
   python3 collector_worker/main.py --job reports --debug

   # Run only the Dialer job
   python3 collector_worker/main.py --job dialer

   # Available jobs: clients, bills, dialer, reports, service (default)

   # Run Database Verification (Connection & Indices)
   python3 collector_worker/main.py --verify-db
   ```

## Docker

1. **Build and Run**:
   ```bash
   docker-compose up -d --build
   ```
   This will start the application and a MongoDB database.

2. **Logs**:
   ```bash
   docker-compose logs -f app
   ```

## Features

- **Multi-Instance Support**: Iterates over all active instances found in the database.
- **Resilient Scheduler**: Uses `schedule` library to run tasks at specific times or intervals.
- **Strict Data Integrity**: Enforces unique constraints and performance indices on MongoDB.
- **Rate Limiting**: Respects IXC API limits (100ms delay).
- **Graceful Error Handling**: Logs errors without crashing the main loop.
- **CDR Reports**: Automatically fetches call detail records and event logs from Asterisk.
- **Structured Logging**: Uses `loguru` for beautiful and configurable service logs.
- **Self-Healing DB**: Automatically verifies and fixes database indices and collections on startup.
