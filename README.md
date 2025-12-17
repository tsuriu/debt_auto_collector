# Debt Collector Python App

A Python application that replicates the logic of the "Debt Collector" Node-RED flow. It automatically fetches client and bill data from IXC Soft ERP, processes debts, and manages an auto-dialer via Asterisk (ARI).

## Structure

- `main.py`: Entry point. Orchestrates the scheduler (Clients, Bills, Dialer jobs).
- `services/ixc_client.py`: Handles IXC API communication (Auth, Pagination, Rate Limiting).
- `services/processor.py`: Business logic for data normalization, due date calculation, and correlating Bills with Clients.
- `services/dialer.py`: Manages call windows (business hours), builds call queues based on rules, and triggers calls via Asterisk ARI.
- `database.py`: MongoDB connection and repository functions.
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
   python3 main.py
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
- **Rate Limiting**: Respects IXC API limits (100ms delay).
- **Graceful Error Handling**: Logs errors without crashing the main loop.
