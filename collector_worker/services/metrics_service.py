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

    # Default Reverse Map (fallback/base) derived from try2.py logic
    DEFAULT_REVERSE_MAP = {
        'neighborhood': {
            'Tabuleiro dos Martins': ['tabuleiro', 'tabuleiro dos martins', 'tabuleiro do martins', 'martins'],
            'Tabuleiro do Pinto': ['tabuleiro do pinto', 'tabuleiro do pinto ', 'tabuleiro do pinto', 'tabuleiro do pinto.'],
            'Antônio Lins': [
                'antonio lins', 'antónio lins', 'antônio lins de souza', 
                'prefeito antônio lins de souza', 'antonio lins de souza', 
                'pref. antonio lins de souza', 'prefeito antonio lins', 
                'prefeito antonio lins de souza', 'prefeito antonio lins souza' # Added missing variant
            ],
            'Brasil Novo': ['brasil novo', 'complexo brasil novo'],
            'Santos Dumontt': ['santos dumont', 'santos dumontt'],
            'Palmeiras': ['palmeiras', 'recanto das palmeiras'],
            'Cidade Universitária': ['cidade universitária', 'cidade universitaria'],
            'Forene': ['forene', 'forene '],
            'Nova Satuba': ['nova satuba'],
            'Maceió': ['maceió', 'maceio'],
            'Rio Largo': ['rio largo'],
            'Campo dos Palmares': ['campo dos palmares'],
            'Aeroporto': ['aeroporto'],
            'Cambuci': ['cambuci'],
            'Centro': ['centro'],
            'Conjunto Bandeirante': ['conjunto bandeirante', 'conj. bandeirante'],
            'Porto do Milazzo': ['porto do milazzo']
        }
    }

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
            target_keys = ["tipo_cliente", "bairro", "instance_name", "expired_age", "erp_type"]
            
            for key in target_keys:
                # Map key to valid mongo field if needed. 
                # instance_name and erp_type might be consistent across instance, but we can group by them if they exist in document.
                # However, instance_name is likely constant for the instance_full_id scope.
                
                # Use '$' prefix for field reference in $group
                # If key is nested, adjust. For now assume flat or top level.
                field_ref = f"${key}"
                
                pipeline_key = [
                    {"$match": {"instance_full_id": self.instance_full_id}},
                    {"$group": {"_id": field_ref, "count": {"$sum": 1}}}
                ]
                
                # Run aggregation
                results = list(self.db.bills.aggregate(pipeline_key))
                
                # Special Logic for 'bairro' (Neighborhood)
                if key == "bairro":
                    # 1. Fetch Reverse Maps (Default + Instance)
                    default_map = self.DEFAULT_REVERSE_MAP.get('neighborhood', {})
                    instance_map = self.instance.get('erp', {}).get('reverse_map', {}).get('neighborhood', {})
                    
                    # Merge: Instance overrides Default if same correct name, or extends.
                    # We want to build a lookup from BOTH.
                    
                    lookup_map = {}
                    
                    # Helper to populate lookup
                    def populate_lookup(source_map):
                        for correct, variants in source_map.items():
                             if isinstance(variants, list):
                                  for v in variants:
                                      if v:
                                          lookup_map[v.lower().strip()] = correct
                    
                    # Populate Default first
                    populate_lookup(default_map)
                    # Populate Instance second (overrides)
                    populate_lookup(instance_map)
                    
                    # 2. Consolidate Results (Normalization)
                    consolidated = {}
                    for item in results:
                        raw_name = item.get("_id")
                        count = item.get("count", 0)
                        
                        if not raw_name:
                            final_name = "Indefinido"
                        else:
                            norm_name = str(raw_name).lower().strip()
                            # Use stripped raw name for fallback title case
                            final_name = lookup_map.get(norm_name, str(raw_name).strip().title())
                        
                        consolidated[final_name] = consolidated.get(final_name, 0) + count
                    
                    # 3. Assign Dictionary directly (Format: {Name: Count})
                    bill_stats_result[key] = consolidated
                
                # Special Logic for 'tipo_cliente' (Client Type Name) - Same Normalization Pattern
                elif key == "tipo_cliente":
                    # 1. Fetch Client Types from DB for mapping
                    client_types_cursor = self.db.client_types.find({"instance_full_id": self.instance_full_id})
                    type_lookup = {}
                    for ct in client_types_cursor:
                        ct_id = ct.get('id')
                        ct_name = ct.get('tipo_cliente')
                        if ct_id is not None:
                            type_lookup[str(ct_id)] = ct_name
                        if ct_name:
                            type_lookup[ct_name.lower().strip()] = ct_name
                    
                    # 2. Consolidate Results
                    consolidated = {}
                    for item in results:
                        raw_name = item.get("_id")
                        count = item.get("count", 0)
                
                        if not raw_name:
                            final_name = "Indefinido"
                        else:
                            # Normalize and lookup
                            norm_name = str(raw_name).lower().strip()
                            # Try to find name in lookup (by ID or exact name)
                            final_name = type_lookup.get(norm_name, str(raw_name).strip().title())
                        
                        consolidated[final_name] = consolidated.get(final_name, 0) + count
                    
                    # 3. Assign Dictionary
                    bill_stats_result[key] = consolidated

                else:
                    # Default behavior for other keys: List of objects [{_id: ..., count: ...}]
                    bill_stats_result[key] = results

            # 3. Action Log Metrics (Today's activities)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            triggered_calls = self.db.history_action_log.count_documents({
                "instance_full_id": self.instance_full_id,
                "action": "dialer_trigger",
                "occurred_at": {"$gte": today_start}
            })

            # 4. CDR Metrics (from last_reports)
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            pipeline_cdr = [
                {
                    "$match": {
                        "instance_full_id": self.instance_full_id,
                        "date_collected": today_str
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total_calls": {"$sum": 1},
                        "avg_duration": {"$avg": {"$toDouble": "$duration"}},
                        "dispositions": {"$push": "$disposition"}
                    }
                }
            ]
            
            res_cdr = list(self.db.last_reports.aggregate(pipeline_cdr))
            
            cdr_metrics = {
                "dispositions": {},
                "average_duration": 0,
                "total_calls": 0
            }
            
            if res_cdr:
                cdr_data = res_cdr[0]
                cdr_metrics["total_calls"] = cdr_data.get("total_calls", 0)
                cdr_metrics["average_duration"] = round(cdr_data.get("avg_duration", 0) or 0, 2)
                
                # Count dispositions
                for disp in cdr_data.get("dispositions", []):
                    if disp:
                        cdr_metrics["dispositions"][disp] = cdr_metrics["dispositions"].get(disp, 0) + 1

            # 5. Blocked Contracts Metrics
            blocked_metrics = {
                "counts": {},
                "stats": {}
            }
            
            # Fetch all once
            all_blocked = list(self.db.blocked_contracts.find({"instance_full_id": self.instance_full_id}, {"_id": 0}))
            
            # Fields for 'counts' (used for historical tracking)
            target_count_fields = ["status_internet", "status_velocidade", "contrato"]
            for field in target_count_fields:
                field_counts = {}
                for contract in all_blocked:
                    val = contract.get(field) or "N/A"
                    field_counts[val] = field_counts.get(val, 0) + 1
                blocked_metrics["counts"][field] = field_counts

            # Fields for 'stats' (counts for dashboard charts)
            # 5.1 Bairro Normalization
            default_map = self.DEFAULT_REVERSE_MAP.get('neighborhood', {})
            instance_map = self.instance.get('erp', {}).get('reverse_map', {}).get('neighborhood', {})
            lookup_map = {}
            def populate_lookup(source_map):
                for correct, variants in source_map.items():
                    if isinstance(variants, list):
                        for v in variants:
                            if v: lookup_map[v.lower().strip()] = correct
            populate_lookup(default_map)
            populate_lookup(instance_map)

            bairro_stats = {}
            for contract in all_blocked:
                raw_name = contract.get("bairro")
                if not raw_name:
                    final_name = "Indefinido"
                else:
                    norm_name = str(raw_name).lower().strip()
                    final_name = lookup_map.get(norm_name, str(raw_name).strip().title())
                bairro_stats[final_name] = bairro_stats.get(final_name, 0) + 1
            blocked_metrics["stats"]["bairro"] = bairro_stats

            # 5.2 Client Type Normalization
            client_types_cursor = self.db.client_types.find({"instance_full_id": self.instance_full_id})
            type_lookup = {}
            for ct in client_types_cursor:
                ct_id = ct.get('id')
                ct_name = ct.get('tipo_cliente')
                if ct_id is not None: type_lookup[str(ct_id)] = ct_name
                if ct_name: type_lookup[ct_name.lower().strip()] = ct_name

            tipo_stats = {}
            for contract in all_blocked:
                raw_name = contract.get("tipo_cliente")
                if not raw_name:
                    final_name = "Indefinido"
                else:
                    norm_name = str(raw_name).lower().strip()
                    final_name = type_lookup.get(norm_name, str(raw_name).strip().title())
                tipo_stats[final_name] = tipo_stats.get(final_name, 0) + 1
            blocked_metrics["stats"]["tipo_cliente"] = tipo_stats

            # 5.3 Bill Expiry Date (Month/Year)
            vencimento_stats = {}
            for contract in all_blocked:
                dt = contract.get("data_vencimento")
                if dt:
                    if isinstance(dt, str):
                        try:
                            dt = datetime.fromisoformat(dt)
                        except:
                            dt = None
                    if dt:
                        month_year = dt.strftime("%m/%Y")
                        vencimento_stats[month_year] = vencimento_stats.get(month_year, 0) + 1
            blocked_metrics["stats"]["vencimento_mes"] = vencimento_stats

            # 5.4 Expired Age (Days)
            age_stats = {}
            for contract in all_blocked:
                age = contract.get("expired_age")
                if age is not None:
                    try:
                        age_val = int(age)
                        age_key = str(age_val)
                        age_stats[age_key] = age_stats.get(age_key, 0) + 1
                    except:
                        pass
            blocked_metrics["stats"]["expired_age"] = age_stats

            # 6. Construct Metric Document
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
                    "cdr_stats": cdr_metrics,
                    "blocked_contracts": blocked_metrics
                }
            }

            # 6. Save to DB
            self.db.metrics.insert_one(metric_doc)
            logger.info(f"Metrics saved for {self.instance_full_id}")
            
            return metric_doc

        except Exception as e:
            logger.error(f"Failed to collect metrics for {self.instance_full_id}: {e}")
            return None
