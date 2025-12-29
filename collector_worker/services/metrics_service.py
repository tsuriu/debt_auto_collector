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
            
            # Clients Classification
            clients_pre_force = len(self.db.bills.distinct(
                "id_cliente",
                {"instance_full_id": self.instance_full_id, "collection_rule": "pre_force_debt_collection"}
            ))
            
            clients_force = len(self.db.bills.distinct(
                "id_cliente",
                {"instance_full_id": self.instance_full_id, "collection_rule": "force_debt_collection"}
            ))

            # 2. Bill Metrics
            # Count by status/vencimento
            total_bills = self.db.bills.count_documents({"instance_full_id": self.instance_full_id})
            expired_bills = self.db.bills.count_documents({
                "instance_full_id": self.instance_full_id,
                "vencimento_status": "expired"
            })
            
            # Bill Classification Counters & Sums
            
            # Pre-Force Debt Collection
            pipeline_pre_force = [
                {"$match": {"instance_full_id": self.instance_full_id, "collection_rule": "pre_force_debt_collection"}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "total_value": {"$sum": "$valor_aberto"}}}
            ]
            res_pre_force = list(self.db.bills.aggregate(pipeline_pre_force))
            pre_force_data = res_pre_force[0] if res_pre_force else {"count": 0, "total_value": 0}

            # Force Debt Collection
            pipeline_force = [
                {"$match": {"instance_full_id": self.instance_full_id, "collection_rule": "force_debt_collection"}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "total_value": {"$sum": "$valor_aberto"}}}
            ]
            res_force = list(self.db.bills.aggregate(pipeline_force))
            force_data = res_force[0] if res_force else {"count": 0, "total_value": 0}

            # Bill Stats - Aggregated by specific keys
            bill_stats_result = {}
            target_keys = ["id_condominio", "bairro", "instance_name", "data_vencimento", "erp_type"]
            
            for key in target_keys:
                # Map key to valid mongo field if needed. 
                # instance_name and erp_type might be consistent across instance, but we can group by them if they exist in document.
                # However, instance_name is likely constant for the instance_full_id scope.
                
                # Use '$' prefix for field reference in $group
                # If key is nested, adjust. For now assume flat or top level.
                field_ref = f"${key}"
                if key == "erp_type":
                     # In some docs it might be flat, in others nested? 
                     # Processor adds 'erp_type' at root level.
                     pass 
                
                pipeline_key = [
                    {"$match": {"instance_full_id": self.instance_full_id}},
                    {"$group": {"_id": field_ref, "count": {"$sum": 1}}}
                ]
                
                # Run aggregation
                results = list(self.db.bills.aggregate(pipeline_key))
                
                # Format Result: key -> value -> count? 
                # Or just list of objects? 
                # Request says: data.bill.bill_stats must be based in...
                # db.bills.aggregate([{ $group: { _id: "$key", count: { $sum: 1 } } }])
                # This implies the result for ONE key.
                # Since we have multiple keys, we likely want a dictionary where keys are the field names.
                # ex: bill_stats: { "bairro": [{"_id": "Centro", "count": 10}, ...], "endereco": ... }
                
                bill_stats_result[key] = results

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
                        # New counters
                        "count_pre_force_debt_collection": clients_pre_force,
                        "count_force_debt_collection": clients_force
                    },
                    "bill": {
                        "total": total_bills,
                        "expired": expired_bills,
                        # New counters & Sums
                        "count_pre_force_debt_collection": pre_force_data["count"],
                        "value_pre_force_debt_collection": round(pre_force_data["total_value"], 2),
                        "count_force_debt_collection": force_data["count"],
                        "value_force_debt_collection": round(force_data["total_value"], 2),
                        "bill_stats": bill_stats_result
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
