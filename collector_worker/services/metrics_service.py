from datetime import datetime, timedelta
from loguru import logger
from database import Database

class MetricsService:
    def __init__(self, instance):
        self.instance = instance
        # Reuse helper logic to get full id
        name = instance.get('instance_name', 'default')
        erp_type = instance.get('erp', {}).get('type', 'ixc')
        oid = str(instance.get('_id', ''))
        self.instance_full_id = f"{name}-{erp_type}-{oid}"
        self.db = Database().get_db()

    def collect_metrics(self):
        """
        Extracts metrics from database for this specific instance and saves to 'metrics' collection.
        """
        logger.info(f"Collecting metrics for instance: {self.instance_full_id}")
        
        try:
            # 1. Client Metrics
            total_clients = self.db.clients.count_documents({"instance_full_id": self.instance_full_id})
            
            # Clients with any open debt (status 'A')
            clients_with_open_debt = len(self.db.bills.distinct(
                "id_cliente", 
                {"instance_full_id": self.instance_full_id, "status": "A"}
            ))
            
            # Clients with expired open debt
            clients_with_expired_debt = len(self.db.bills.distinct(
                "id_cliente", 
                {"instance_full_id": self.instance_full_id, "vencimento_status": "expired"}
            ))

            # 2. Bill Metrics
            # Count by status/vencimento
            total_bills = self.db.bills.count_documents({"instance_full_id": self.instance_full_id})
            expired_bills = self.db.bills.count_documents({
                "instance_full_id": self.instance_full_id,
                "vencimento_status": "expired"
            })
            
            # Aggregate Total Expired Debt
            pipeline_expired = [
                {"$match": {"instance_full_id": self.instance_full_id, "vencimento_status": "expired"}},
                {"$group": {"_id": None, "total_debt": {"$sum": "$valor_aberto"}}}
            ]
            debt_expired_result = list(self.db.bills.aggregate(pipeline_expired))
            total_expired_debt_amount = debt_expired_result[0]["total_debt"] if debt_expired_result else 0

            # Aggregate Total In-Time Debt
            pipeline_intime = [
                {"$match": {"instance_full_id": self.instance_full_id, "vencimento_status": "current"}},
                {"$group": {"_id": None, "total_debt": {"$sum": "$valor_aberto"}}}
            ]
            debt_intime_result = list(self.db.bills.aggregate(pipeline_intime))
            total_intime_debt_amount = debt_intime_result[0]["total_debt"] if debt_intime_result else 0

            # 3. Action Log Metrics (Today's activities)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            triggered_calls = self.db.history_action_log.count_documents({
                "instance_full_id": self.instance_full_id,
                "action": "dialer_trigger",
                "occurred_at": {"$gte": today_start}
            })

            # 4. CDR Metrics (from last_reports)
            last_report = self.db.last_reports.find_one(
                {"instance_full_id": self.instance_full_id},
                sort=[("last_run_timestamp", -1)]
            )
            
            cdr_metrics = {
                "dispositions": {},
                "average_duration": 0,
                "total_calls": 0
            }
            
            if last_report and "data" in last_report:
                cdrs = last_report["data"]
                cdr_metrics["total_calls"] = len(cdrs)
                
                durations = []
                for cdr in cdrs:
                    disp = cdr.get("disposition", "UNKNOWN")
                    cdr_metrics["dispositions"][disp] = cdr_metrics["dispositions"].get(disp, 0) + 1
                    
                    try:
                        durations.append(float(cdr.get("duration", 0)))
                    except (ValueError, TypeError):
                        pass
                
                if durations:
                    cdr_metrics["average_duration"] = round(sum(durations) / len(durations), 2)

            # 5. Construct Metric Document
            metric_doc = {
                "instance_full_id": self.instance_full_id,
                "instance_name": self.instance.get('instance_name'),
                "timestamp": datetime.now(),
                "data": {
                    "clients": {
                        "total": total_clients,
                        "count_with_open_debt": clients_with_open_debt,
                        "count_with_expired_open_debt": clients_with_expired_debt
                    },
                    "bill": {
                        "total": total_bills,
                        "expired": expired_bills,
                        "total_expired_debt_amount": round(total_expired_debt_amount, 2),
                        "total_intime_debt_amount": round(total_intime_debt_amount, 2)
                    },
                    "actions_today": {
                        "dialer_triggers": triggered_calls
                    },
                    "cdr_stats": cdr_metrics
                }
            }

            # 6. Save to DB
            self.db.metrics.insert_one(metric_doc)
            logger.info(f"Metrics saved for {self.instance_full_id}")
            
            return metric_doc

        except Exception as e:
            logger.error(f"Failed to collect metrics for {self.instance_full_id}: {e}")
            return None
