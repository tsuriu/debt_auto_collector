import requests
import base64
from loguru import logger
from datetime import datetime, timedelta
import re
from database import Database
from utils.time_utils import is_within_operational_window

class Dialer:
    def __init__(self, instance_config):
        self.config = instance_config
        self.pabx = instance_config.get('asterisk', {})
        self.min_days = instance_config.get('charger', {}).get('minimum_days_to_charge', 7)
        self.dial_per_day = instance_config.get('charger', {}).get('dial_per_day', 3)
        self.dial_interval = instance_config.get('charger', {}).get('dial_interval', 4)
        
        # Construct instance_full_id for DB queries
        name = instance_config.get('instance_name', 'default')
        erp_type = instance_config.get('erp', {}).get('type', 'ixc')
        oid = str(instance_config.get('_id', ''))
        self.instance_full_id = f"{name}-{erp_type}-{oid}"
        
        self.db = Database().get_db()

    def check_window(self):
        """Returns True if current time is within allowed call window"""
        return is_within_operational_window(self.config.get('debug_calls', False))

    def can_call_number(self, number):
        """
        Enforce rules:
        1. Max 3 calls per day
        2. Min 4 hours interval between calls
        """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Filter for this number, this instance, and dialer actions
        query = {
            "instance_full_id": self.instance_full_id,
            "action": "dialer_trigger",
            "details.number": number,
            "occurred_at": {"$gte": today_start}
        }
        
        # 1. Check Max Calls per Day
        count_today = self.db.history_action_log.count_documents(query)
        if count_today >= self.dial_per_day:
            logger.debug(f"Blocked {number}: Max {self.dial_per_day} calls reached for today.")
            return False
            
        # 2. Check Interval (4h)
        # Get the most recent call (not just today, but generally? 
        # User constraint: 'at last 4 hours of interval'. 
        # Usually implies 4h from ANY last call.
        # But if we only check today, the first call of day might be < 4h from yesterday's last call.
        # Strict interpretation: check global last call.
        
        last_call = self.db.history_action_log.find_one(
            {
                "instance_full_id": self.instance_full_id,
                "action": "dialer_trigger",
                "details.number": number
            },
            sort=[("occurred_at", -1)]
        )
        
        if last_call:
            last_time = last_call.get('occurred_at')
            if last_time:
                diff = datetime.now() - last_time
                if diff < timedelta(hours=self.dial_interval):
                    logger.debug(f"Blocked {number}: Last call was {diff} ago (<{self.dial_interval}h).")
                    return False
        
        return True

    def build_queue(self, bills):
        if not self.check_window():
            logger.info("Outside call window. Skipping queue build.")
            return [], 0

        # Filter strictly by expired age > min_days (e.g. 7)
        eligible_bills = [b for b in bills if b.get('expired_age', 0) >= self.min_days]
        eligible_count = len(eligible_bills)
        
        # Group by Client to aggregate values
        client_map = {}
        for bill in eligible_bills:
            cid = bill.get('id_cliente')
            if cid not in client_map:
                client_map[cid] = []
            client_map[cid].append(bill)
            
        call_queue = []
        
        # We need to sort by expired_age BEFORE limiting
        # To do that properly, let's first prepare the potential calls list
        potential_calls = []

        for cid, client_bills in client_map.items():
            sample = client_bills[0]
            max_expired_age = max(b.get('expired_age', 0) for b in client_bills)
            total_value = sum(float(b.get('valor', 0)) for b in client_bills)
            client_name = sample.get('razao') or sample.get('fantasia')
            bill_ids = [b.get('full_id') for b in client_bills if b.get('full_id')]
            
            # Extract numbers
            raw_numbers = [
                sample.get('telefone_celular'),
                sample.get('telefone_comercial'),
                sample.get('whatsapp')
            ]
            
            # Sanitization & Deduplication
            unique_numbers = set()
            for num in raw_numbers:
                if num:
                    cleaned = re.sub(r'\D', '', str(num))
                    if len(cleaned) >= 8:
                        unique_numbers.add(cleaned)
            
            # For each client, we might have multiple numbers. 
            # But "never can keep two elements with same full_id" 
            # If we add multiple numbers for SAME client with SAME bills, they share same full_id?
            # Actually, full_id is per bill. 
            # If we add two items to queue for same client (different numbers), 
            # they will BOTH have the same `bill_ids` list.
            # User says: "in queue never can keep two elements with same full_id"
            # This implies if we queue a client, we pick ONE number if multiple are available?
            # Or if we pick multiple numbers, they must be distinct entries, 
            # but then they share the same bills.
            # Let's interpret "never keep two elements with same full_id" as:
            # "No two queue items should represent the same set of bills".
            # Which effectively means one queue item per client (or per unique bill set).
            
            added_for_client = False
            for number in unique_numbers:
                if added_for_client:
                    break # Take only first valid number to avoid "same full_id" in queue
                
                if self.can_call_number(number):
                    potential_calls.append({
                        "client_id": cid,
                        "expired_age": max_expired_age,
                        "contact": number,
                        "client_name": client_name,
                        "total_value": total_value,
                        "bill_ids": bill_ids
                    })
                    added_for_client = True
                else:
                    logger.debug(f"Number {number} for Client {cid} is blocked (rules)")
            
        # Sort by expired_age descending
        potential_calls.sort(key=lambda x: x['expired_age'], reverse=True)

        # Limit by num_channel_available
        limit = self.pabx.get('num_channel_available', 10)
        call_queue = potential_calls[:limit]
            
        return call_queue, eligible_count

    def trigger_call(self, call_data):
        logger.info(f"Triggering call for {call_data}")
        number = call_data['contact']
        client_id = call_data['client_id']
        # total_value = call_data['total_value'] # Unused in ARI payload
        
        # ARI Config
        host = self.pabx.get('host', '127.0.0.1')
        port = self.pabx.get('port', '8088')
        user = self.pabx.get('username', 'admin')
        password = self.pabx.get('password', 'admin')
    
        schema = self.pabx.get('schema', 'http')
        
        channel_type = self.pabx.get('channel_type', 'SIP')
        trunk = self.pabx.get('channel', 'trunk') # Default to 'trunk' if missing, usually provided
        context = self.pabx.get('context', 'from-internal')
        extension = self.pabx.get('extension', '100')
        
        # Construct Endpoint: channel_type/trunk/number
        endpoint = f"{channel_type}/{trunk}/{number}"
        
        url = f"{schema}://{host}:{port}/ari/channels"
        # CallerID format: "ClientID - ClientName"
        # Node-RED: `${clientId} - ${callData.callerId}` where callData.callerId is name?
        # In build_queue, we set 'client_name', so let's use that.
        # UPDATE: User requested "callerId must be full_id from bills document"
        
        bill_ids = call_data.get('bill_ids', [])
        if bill_ids:
            caller_id = str(bill_ids[0])
        else:
             # Fallback if no bill_ids (shouldn't happen given build_queue logic)
            caller_id = f"{client_id} - {call_data['client_name']}"
        
        payload = {
            "endpoint": endpoint,
            "extension": extension,
            "context": context,
            "priority": "1",
            "callerId": f"{caller_id[:80]} <{caller_id[:80]}>" , # Truncate if too long (optional safety)
            "timeout": "30000" # Matching Node-RED flow value
        }
        logger.info(f"Payload: {payload}")
        
        try:
            logger.info(f"Dialing {number} for Client {client_id} via {url}...")
            # Node-RED uses x-www-form-urlencoded
            resp = requests.post(
                url, 
                data=payload,  # data= sends form-urlencoded
                auth=(user, password),
                timeout=5
            )
            resp.raise_for_status()
            
            # Parse Response
            try:
                resp_data = resp.json()
                logger.info(f"Response: {resp_data}")
            except ValueError:
                logger.warning(f"Dialer response from {number} was not JSON: {resp.text}")
                resp_data = {}

            logger.info(f"Call triggered successfully. Status: {resp.status_code}")
            
            # 3. Handle Response & Persistence (Requirement: Map fields and save to last_reports)
            # Mapping:
            # id -> uniqueid
            # name -> channel
            # caller.name -> full_id (Note: caller is object, caller.name is nested)
            
            r_id = resp_data.get("id")
            r_name = resp_data.get("name")
            r_full_id = resp_data.get("caller", {}).get("name")
            
            # The requirement says "persist these mapped values into the last_reports collection".
            # Also later "Change persistence logic ... to upsert ... uniqueid as key".
            # ReportService does this for CDRs. Dialer response acts as "pre-CDR" or "live channel info"?
            # We will follow instruction: "Persist these mapped values into the last_reports collection."
            
            if r_id:
                mapped_doc = {
                    "uniqueid": r_id,
                    "channel": r_name,
                    "full_id": r_full_id, # This effectively links channel to bill/client
                    "instance_full_id": self.instance_full_id, # Good for partitioning
                    "triggered_at": datetime.now(),
                    "source": "dialer_trigger"
                }
                
                self.db.last_reports.update_one(
                    {"uniqueid": r_id},
                    {"$set": mapped_doc},
                    upsert=True
                )
                logger.debug(f"Persisted dialer response to last_reports for uniqueid {r_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger call {number}: {e}")
            return False
