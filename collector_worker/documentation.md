# Collector Worker Documentation

## Overview

The `collector_worker` is a Python-based service designed to automate debt collection processes. It integrates with an external ERP (IXC) and a PABX system (Asterisk/Issabel) to manage clients, bills, automatic dialing, and call reporting. All logging is handled via `loguru`.

## Architecture

The system operates as a daemon or single-run job, connecting to:
1.  **MongoDB**: For data storage (`clients`, `bills`, `history_action_log`, `last_reports`, `metrics`).
2.  **IXC ERP**: Fetches client and billing data via API.
3.  **Asterisk/Issabel**: Triggers calls via ARI (Asterisk REST Interface) and fetches CDRs (Call Detail Records).

### Directory Structure
```
collector_worker/
├── main.py                 # Entry point, scheduler, and job orchestrator
├── config.py               # Configuration and environment variables
├── database.py             # MongoDB connection handler
├── Dockerfile              # Container definition
├── services/
│   ├── ixc_client.py       # API Client for IXC ERP
│   ├── processor.py        # Data processing and business logic
│   ├── dialer.py           # Dialer logic (Queue building & ARI trigger)
│   ├── report_service.py   # Fetches CDRs from Asterisk
│   ├── metrics_service.py  # Calculates and stores data snapshots
│   └── verification.py     # Database structure verification service
└── utils/                  
    └── time_utils.py       # Shared operational window logic
```

## Configuration

The application uses `python-dotenv` to load environment variables.

| Variable | Default | Description |
| :--- | :--- | :--- |
| `MONGO_URI` | `mongodb://localhost:27017/` | MongoDB connection string |
| `DB_NAME` | `debt_collector` | Database name |
| `DEBUG` | `false` | Enable debug logging and bypass window checks |

**Note**: Specific instance configurations (API keys, credentials) are fetched dynamically from the `instances` collection in MongoDB via `database.get_active_instances()`.

## Core Jobs & Workflows

The Service runs on a schedule defined in `main.py`.

### 1. Clients Update (`run_clients_update_job`)
**Schedule**: Daily at 07:00
1.  **Fetch**: Retrieves active clients from IXC (Status: Active, Type: NOT Juridical/Condominium).
2.  **Process**: Validates and formats client data (normalize fields).
3.  **Upsert**: Updates the `clients` collection in MongoDB.
4.  **Sync**: Removes clients from MongoDB that are no longer present in the source fetch.
5.  **Log**: Records stats to `history_action_log`.

### 2. Bills Update (`run_bills_update_job`)
**Schedule**: Every 1 hour
1.  **Fetch**: Retrieves active/open bills from IXC (Due date < Future, > 30 days ago).
2.  **Process**: Calculates `days_until_due`, `expired_age`, and status.
3.  **Merge**: Joins bill data with client data (names, phones) from the local `clients` collection.
4.  **Upsert**: Updates the `bills` collection.
5.  **Sync**: Removes bills from MongoDB not present in the fetch (e.g., if paid or cancelled).

### 3. Dialer (`run_dialer_job`)
**Schedule**: Every 20 minutes (within active window)
**Active Window**: Mon-Fri 08:00-19:00, Sat 08:00-13:00.
1.  **Check Window**: Aborts if outside allowed hours (unless Debug mode).
2.  **Build Queue**:
    *   Finds expired bills (`vencimento_status='expired'`) for the instance.
    *   Filters by `minimum_days_to_charge` (default 7 days).
    *   Groups by Client.
    *   **Priority**: Sorts calls by `expired_age` descending (oldest debt first).
    *   Sanitizes phone numbers.
    *   **Rate Limit**: Enforces strict rules using MongoDB history:
        *   **Max 3 calls per day** per number.
        *   **Min 4 hours interval** between calls.
    *   **Channel Limit**: Limits total calls per run based on `asterisk.num_channel_available` (default 10).
3.  **Trigger Calls**:
    *   Integrates with Asterisk ARI to initiate calls.
    *   CallerID is set to the Bill ID (for tracking) or Client info.
4.  **Log**: Updates `call_history` in `bills` and adds entry to `history_action_log`.

### 4. Reports Update (`run_reports_update_job`)
**Schedule**: Triggered 5 minutes after `run_dialer_job` finishes.
1.  **Login**: Authenticates with the Asterisk/Issabel web interface.
2.  **Fetch**: Retreives Call Detail Records (CDRs) for the current day.
3.  **Enrich**: Fetches detailed events for each CDR (if available).
4.  **Store**: Saves the raw report data to `last_reports` collection.
    
### 5. Metrics Collection (`run_metrics_job`)
**Schedule**: Every 30 minutes
1.  **Aggregate Clients**: Counts total clients, clients with open debt, and clients with expired open debt.
2.  **Aggregate Bills**: Calculates total bills count, total expired bills count, `total_expired_debt_amount`, and `total_intime_debt_amount`.
3.  **Action Logs**: Counts total dialer actions triggered for the current day.
4.  **CDR Analytics**: Fetches the latest report from `last_reports` to compute disposition distribution and average call duration.
5.  **Snapshot**: Saves all metrics into the `metrics` collection with a timestamp.

## Services Breakdown

### `ixc_client.py`
*   **Purpose**: Wrapper for IXC ERP API.
*   **Key Methods**:
    *   `get_clients()`: Fetches customer base.
    *   `get_bills()`: Fetches open invoices.
*   **Features**: Handles pagination, authentication, and rate-limiting.

### `processor.py`
*   **Purpose**: Pure data transformation logic.
*   **Key Methods**:
    *   `process_clients()`: Formats client dictionary.
    *   `process_bills()`: Calculates aging and due dates.
    *   `merge_data()`: Combines Bill + Client data into a flat structure for the Dialer.

### `dialer.py`
*   **Purpose**: Logic for determining WHO to call and HOW.
*   **Key Methods**:
    *   `check_window()`: Validates operating hours.
    *   `build_queue()`: Selection algorithm for calls.
    *   `trigger_call()`: Sends HTTP request to Asterisk.

### `report_service.py`
*   **Purpose**: Scrapes/Fetches reporting data from the PBX.
*   **Key Methods**:
    *   `fetch_cdr_list()`: Gets daily call list.
    *   `fetch_events()`: Gets drill-down details for a call.

### `metrics_service.py`
*   **Purpose**: Strategic data snapshots and performance analytics.
*   **Key Methods**:
    *   `collect_metrics()`: Orchestrates multiple database aggregations (clients, bills, history, reports) to create a historical data point.

### `database.py`
*   **Purpose**: Low-level database operations and schema management.
*   **Key Methods**:
    *   `ping()`: Connectivity check.
    *   `ensure_collections()`: Creates missing collections lazily/explicitly.
    *   `ensure_indices()`: Enforces required performance and unique indices.
    *   `get_indices(collection)`: Introspection of current database state.
    
### `verification.py`
*   **Purpose**: Orchestrates database health checks and provides specialized reporting.
*   **Key Methods**:
    *   `run_full_verification()`: High-level workflow that uses `Database` methods to confirm connectivity, collections, and indices before the app starts.

### `utils/time_utils.py`
*   **Purpose**: Centralized operational window logic.
*   **Key Methods**:
    *   `is_within_operational_window(debug_mode)`: Returns True if current time is allowed for dialing/reporting.

## Maintenance

### Database Auto-Verification
Database verification runs **automatically** on every startup. This process:
1.  **Pings** MongoDB to ensure connectivity.
2.  **Verifies/Creates** all required collections (`clients`, `bills`, etc.).
3.  **Applies** all necessary indices for performance and uniqueness.
4.  **Seeds** the `instance_config` collection if it's empty.

To skip this check (e.g., in a stable environment for faster startup):
```bash
python main.py --no-verify-db
```
This is orchestrated by the `VerificationService` using the low-level API provided by `database.py`. Detailed logs are provided via `loguru`.

## Deployment

### Docker
The service is containerized.
```bash
docker-compose up -d --build
```
Ensure `report_service` (or `collector_worker`) container has network access to both MongoDB and the Asterisk server.

### Manual Run
```bash
# Run service daemon (runs verification by default)
python main.py --job service

# Run without database verification
python main.py --no-verify-db

# Run one-off job (e.g., debug)
python main.py --job dialer --debug

# Run metrics collection manually
python main.py --job metrics --debug
```
