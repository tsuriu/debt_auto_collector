import time, sys, json
import schedule
from datetime import datetime
from loguru import logger
from config import Config
from database import Database, get_active_instances
from services.ixc_client import IxcClient
from services.processor import Processor
from services.dialer import Dialer
from services.report_service import ReportService
from services.verification import VerificationService
from services.metrics_service import MetricsService

def _get_instance_full_id(instance):
    name = instance.get('instance_name', 'default')
    erp_type = instance.get('erp', {}).get('type', 'ixc')
    oid = str(instance.get('_id', ''))
    return f"{name}-{erp_type}-{oid}"

def run_clients_update_job():
    logger.info("Starting Job: CLIENTS UPDATE")
    instances = get_active_instances()
    
    for instance in instances:
        try:
            start_time = time.time()
            instance_full_id = _get_instance_full_id(instance)
            logger.info(f"Processing instance: {instance.get('instance_name')} (ID: {instance_full_id})")
            
            client = IxcClient(instance)
            processor = Processor(instance)
            db = Database().get_db()

            # Snapshot Before
            start_count = db.clients.count_documents({"instance_full_id": instance_full_id})
            
            # Fetch
            raw_clients = client.get_clients()
            logger.info(f"Fetched {len(raw_clients)} clients")
            
            # Process
            processed_clients = processor.process_clients(raw_clients)
            
            if processed_clients:
                from pymongo import UpdateOne
                ops = []
                for c in processed_clients:
                    c['instance_full_id'] = instance_full_id
                    # Key by instance + client ID to ensure uniqueness per instance
                    ops.append(
                        UpdateOne(
                            {"instance_full_id": instance_full_id, "id": c['id']},
                            {"$set": c},
                            upsert=True
                        )
                    )
                
                if ops:
                    res = db.clients.bulk_write(ops)
                    logger.info(f"Saved/Updated {len(ops)} clients to 'clients' collection")
                    
                    upserted_count = res.upserted_count
                    modified_count = res.modified_count
                    matched_count = res.matched_count
                else:
                    upserted_count = 0
                    modified_count = 0
                    matched_count = 0

                # SYNC: Delete clients that are NOT in the current processed list for this instance
                # This ensures clients filtered out (e.g. tipo_pessoa != J) or inactive are removed.
                valid_ids = [c['id'] for c in processed_clients]
                sync_result = db.clients.delete_many({
                    "instance_full_id": instance_full_id,
                    "id": {"$nin": valid_ids}
                })
                
                deleted_count = sync_result.deleted_count
                if deleted_count > 0:
                    logger.info(f"Synced/Removed {deleted_count} clients from DB (Not in current valid set)")
                    
                    # Removed intermediate log for cleanup stats to avoid noise
                    pass
                
                # Update Metadata
                db.data_reference.update_one(
                    {"instance_full_id": instance_full_id},
                    {"$set": {
                        "instance_full_id": instance_full_id,
                        "instance_name": instance.get('instance_name'),
                        "last_clients_update": datetime.now().isoformat()
                    }},
                    upsert=True
                )
            
            # Snapshot After
            end_count = db.clients.count_documents({"instance_full_id": instance_full_id})
            delta = end_count - start_count
            elapsed_time = round(time.time() - start_time, 2)

            # Log Execution Summary
            db.history_action_log.insert_one({
                "instance_full_id": instance_full_id,
                "action": "job_clients_execution",
                "occurred_at": datetime.now(),
                "details": {
                    "start_count": start_count,
                    "end_count": end_count,
                    "delta": delta,
                    "elapsed_time_seconds": elapsed_time,
                    "fetched": len(raw_clients),
                    "upserted": locals().get('upserted_count', 0),
                    "modified": locals().get('modified_count', 0),
                    "matched": locals().get('matched_count', 0),
                    "deleted": locals().get('deleted_count', 0)
                }
            })
                
            logger.info(f"Instance {instance.get('instance_name')} - Clients Job Finished. Delta: {delta}, Time: {elapsed_time}s")
            
        except Exception as e:
            logger.error(f"Error in Clients Job for {instance.get('instance_name')}: {e}")

def run_bills_update_job():
    logger.info("Starting Job: BILLS UPDATE")
    instances = get_active_instances()
    
    for instance in instances:
        try:
            start_time = time.time()
            instance_full_id = _get_instance_full_id(instance)
            logger.info(f"Processing instance: {instance.get('instance_name')}")
            
            client = IxcClient(instance)
            processor = Processor(instance)
            db = Database().get_db()
            
            # Snapshot Before
            start_count = db.bills.count_documents({"instance_full_id": instance_full_id})

            # Fetch Bills
            raw_bills = client.get_bills()
            processed_bills = processor.process_bills(raw_bills)
            
            # Fetch Clients from 'clients' collection
            # We need all clients for this instance to merge data
            # To avoid memory issues with huge sets, we might need optimization later, 
            # but for now fetching instance clients (e.g. 20k) is okay in 2025 python.
            instance_clients = list(db.clients.find({"instance_full_id": instance_full_id}))
            
            if not instance_clients:
                logger.warning(f"No clients found in 'clients' collection for {instance_full_id}. Skipping merge.")
            
            # Merge / Create Charges
            charges = processor.merge_data(processed_bills, instance_clients)
            
            upserted_count = 0
            modified_count = 0
            matched_count = 0
            deleted_count = 0

            if charges:
                # We no longer filter by "paid_days". All data returned by processor is considered valid for sync.
                # If IXC stops returning it (e.g. date range), sync will remove it.
                
                valid_ids = []
                from pymongo import UpdateOne
                ops = []
                for charge in charges:
                    charge['instance_full_id'] = instance_full_id
                    valid_ids.append(charge['full_id'])
                    ops.append(
                        UpdateOne(
                            {"full_id": charge["full_id"]},
                            {"$set": charge},
                            upsert=True
                        )
                    )
                
                if ops:
                    res = db.bills.bulk_write(ops)
                    logger.info(f"Saved/Updated {len(ops)} valid bills to 'bills' collection")
                    
                    upserted_count = res.upserted_count
                    modified_count = res.modified_count
                    matched_count = res.matched_count
                else:
                    upserted_count = 0
                    modified_count = 0
                    matched_count = 0

            # SYNC: Delete bills that are NOT in the valid_ids list for this instance
            sync_result = db.bills.delete_many({
                "instance_full_id": instance_full_id,
                "full_id": {"$nin": valid_ids}
            })
            
            deleted_count = sync_result.deleted_count
            if deleted_count > 0:
                logger.info(f"Synced/Removed {deleted_count} bills from DB (Not in current valid set)")

            # Log Stats - REMOVED intermediate log to prevent double entries
            # db.history_action_log.insert_one({...})

            db.data_reference.update_one(
                {"instance_full_id": instance_full_id},
                {"$set": {
                    "instance_full_id": instance_full_id,
                    "last_bills_update": datetime.now().isoformat()
                }},
                upsert=True
            )
                    
            # Snapshot After
            end_count = db.bills.count_documents({"instance_full_id": instance_full_id})
            delta = end_count - start_count
            elapsed_time = round(time.time() - start_time, 2)

            # Log Execution Summary
            db.history_action_log.insert_one({
                "instance_full_id": instance_full_id,
                "action": "job_bills_execution",
                "occurred_at": datetime.now(),
                "details": {
                    "start_count": start_count,
                    "end_count": end_count,
                    "delta": delta,
                    "elapsed_time_seconds": elapsed_time,
                    "fetched": len(processed_bills),
                    "upserted": upserted_count,
                    "modified": modified_count,
                    "matched": matched_count,
                    "deleted": deleted_count
                }
            })
                    
            logger.info(f"Instance {instance.get('instance_name')} - Bills Job Finished. Delta: {delta}, Time: {elapsed_time}s")

        except Exception as e:
            logger.error(f"Error in Bills Job for {instance.get('instance_name')}: {e}")

def run_dialer_job():
    logger.info("Starting Job: DIALER")
    instances = get_active_instances()
    
    for instance in instances:
        try:
            instance_full_id = _get_instance_full_id(instance)
            
            # Inject debug config if global debug is on
            if Config.DEBUG:
                instance['debug_calls'] = True
                
            dialer = Dialer(instance)
            db = Database().get_db()
            
            if not dialer.check_window():
                logger.info(f"Skipping dialer for {instance.get('instance_name')} (Outside Window)")
                continue
            
            # Fetch bills from 'bills' collection
            # Query: instance_full_id AND vencimento_status='expired'
            # Note: expired_age logic is also filtered in build_queue, but efficient query helps
            query = {
                "instance_full_id": instance_full_id,
                "vencimento_status": "expired"
            }
            
            bills = list(db.bills.find(query))
            
            if not bills:
                logger.info(f"No expired bills found for {instance.get('instance_name')}")
                continue

            queue, eligible_count = dialer.build_queue(bills)
            
            logger.info(f"Dialer for {instance.get('instance_name')}: {eligible_count} eligible, queuing {len(queue)} calls.")
            
            count = 0
            
            for call in [queue[0]]:
                # Check 4h window again (just in case multiple numbers for same client in queue)
                # Although queue builder handles it now with the added_for_client flag.
                
                if dialer.trigger_call(call):
                    count += 1
                    
                    # Add History to Bills and Action Log
                    bill_ids = call.get('bill_ids', [])
                    if bill_ids:
                        occurred_at = datetime.now()
                        
                        # 1. Update Bill History (Legacy/Embedded)
                        history_entry = {
                            "occurred_at": occurred_at,
                            "number": call['contact'],
                            "status": "triggered"
                        }
                        db.bills.update_many(
                            {"full_id": {"$in": bill_ids}},
                            {"$push": {"call_history": history_entry}}
                        )
                        
                        # 2. Insert into Action Log (New)
                        # We create one log entry per bill involved
                        log_entries = []
                        for bid in bill_ids:
                            log_entries.append({
                                "full_id": bid,
                                "action": "dialer_trigger",
                                "occurred_at": occurred_at,
                                "instance_full_id": instance_full_id,
                                "details": {
                                    "number": call['contact'],
                                    "client_name": call['client_name'],
                                    "status": "success"
                                }
                            })
                        
                        if log_entries:
                            db.history_action_log.insert_many(log_entries)
                        
                        logger.debug(f"Logged action for {len(bill_ids)} bills.")
                        
                    time.sleep(1)
            
            logger.info(f"Triggered {count} calls for {instance.get('instance_name')}")
            
            # Log Stats
            db.history_action_log.insert_one({
                "instance_full_id": instance_full_id,
                "action": "job_dialer_stats",
                "occurred_at": datetime.now(),
                "details": {
                    "eligible": eligible_count,
                    "queue_size": len(queue),
                    "triggered": count
                }
            })

        except Exception as e:
            logger.error(f"Error in Dialer Job for {instance.get('instance_name')}: {e}")

    # Schedule deferred report execution (5 minutes after dialer finishes)
    def _run_report_once():
        run_reports_update_job()
        return schedule.CancelJob
        
    schedule.every(5).minutes.do(_run_report_once)
    logger.info("Scheduled Reports Job to run in 5 minutes.")

def run_reports_update_job():
    logger.info("Starting Job: REPORTS UPDATE")
    instances = get_active_instances()
    
    for instance in instances:
        try:
            instance_full_id = _get_instance_full_id(instance)
            logger.info(f"Processing reports for instance: {instance.get('instance_name')}")
            
            # Inject debug config if global debug is on
            if Config.DEBUG:
                instance['debug_calls'] = True
            
            service = ReportService(instance)
            count = service.process() or 0
            
            # Log Stats
            Database().get_db().history_action_log.insert_one({
                "instance_full_id": instance_full_id,
                "action": "job_reports_stats",
                "occurred_at": datetime.now(),
                "details": {
                    "fetched": count
                }
            })
            
            logger.info(f"Report job finished for {instance.get('instance_name')}")
        except Exception as e:
            logger.error(f"Error in Report Job for {instance.get('instance_name')}: {e}")

def run_metrics_job():
    logger.info("Starting Job: METRICS")
    instances = get_active_instances()
    
    for instance in instances:
        try:
            service = MetricsService(instance)
            service.collect_metrics()
        except Exception as e:
            logger.error(f"Error in Metrics Job for {instance.get('instance_name')}: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Debt Collector Service")
    parser.add_argument(
        "--job", 
        choices=["clients", "bills", "dialer", "reports", "service", "metrics"], 
        default="service",
        help="Run a specific job manually (once) or start the long-running service (default)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug logging and behavior"
    )
    parser.add_argument(
        "--no-verify-db", 
        action="store_true",
        help="Skip database verification on startup"
    )
    args = parser.parse_args()

    # Configure Loguru
    logger.remove() # Remove default handler
    is_debug = args.debug or Config.DEBUG
    log_level = "DEBUG" if is_debug else "INFO"
    
    # Production Format: Simple and concise
    # Debug Format: Includes module, function, and line
    if is_debug:
        log_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    else:
        log_format = "[{time:YYYY-MM-DD HH:mm:ss}] <level>{level: <7}</level>: {message}"

    logger.add(sys.stderr, level=log_level, format=log_format)
    
    if args.debug:
        Config.DEBUG = True
        logger.debug("Debug mode enabled via CLI")

    logger.info(f"Starting application in mode: {args.job.upper()}")

    # Ensure DB Structure (Collections & Indices) ALWAYS on startup
    # This prevents running jobs against a broken or empty DB
    if not args.no_verify_db: 
        logger.info("Initializing database verification...")
        verifier = VerificationService()
        if verifier.run_full_verification(exit_on_failure=not Config.DEBUG):
            logger.info("Database structure confirmed.")
        else:
            logger.error("Database initialization failed.")
            if not Config.DEBUG:
                sys.exit(1)

    if args.job == "clients":
        run_clients_update_job()
        return

    if args.job == "bills":
        run_bills_update_job()
        return

    if args.job == "dialer":
        run_dialer_job()
        return

    if args.job == "reports":
        run_reports_update_job()
        return

    if args.job == "metrics":
        run_metrics_job()
        return


    # Service / Scheduler Mode
    if args.job == "service":
        logger.info("Auto Debt Collector Service Started (Daemon Mode)")
        
        # Schedule definitions
        schedule.every().day.at("07:00").do(run_clients_update_job)
        schedule.every(1).hours.do(run_bills_update_job)
        # Reports are now triggered 5min after dialer job ends
        # schedule.every(5).minutes.do(run_reports_update_job)
        
        # Metrics: every 6 hours
        schedule.every(30).minutes.do(run_metrics_job)

        # Dialer: every 20 minutes between 8-18 (handled by check_window inside job)
        schedule.every(20).minutes.do(run_dialer_job)
        
        # Run immediately on startup for debug/verification if debug is ON
        if args.debug or Config.DEBUG:
            logger.warning("DEBUG MODE: Running all jobs immediately for verification")
            try:
                run_clients_update_job()
                run_bills_update_job()
                run_reports_update_job()
                run_dialer_job()
            except Exception as e:
                logger.critical(f"Startup jobs failed: {e}")
                sys.exit(1)
        
        while True:
            schedule.run_pending()
            time.sleep(10)

if __name__ == "__main__":
    main()
