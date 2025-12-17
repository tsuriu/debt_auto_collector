import requests
import base64
from loguru import logger
from datetime import datetime, timedelta
import re

class Dialer:
    def __init__(self, instance_config):
        self.config = instance_config
        self.pabx = instance_config.get('asterisk', {})
        self.min_days = instance_config.get('charger', {}).get('minimum_days_to_charge', 7)
        
        # In-memory state (should be persisted in production but keeping simpler for now as per plan)
        # Ideally this should be in Redis or Mongo to survive restarts
        self.number_last_called = {} 
        self.client_attempts = {} 
        self.retry_queue = []

    def check_window(self):
        """Returns True if current time is within allowed call window"""
        now = datetime.now()
        hour = now.hour
        day = now.weekday() # 0=Mon, 6=Sun
        
        if self.config.get('debug_calls', False):
            return True

        if day == 6: # Sunday
            return False
            
        if day == 5: # Saturday
            # 8h to 13h
            if 8 <= hour < 13:
                return True
            return False
            
        # Weekdays
        # 8h to 19h
        if 8 <= hour < 19:
            return True
            
        return False

    def can_call_number(self, number):
        last_time = self.number_last_called.get(number)
        if not last_time:
            return True
        
        # 4 hours block
        cutoff = datetime.now() - timedelta(hours=4)
        return last_time < cutoff

    def build_queue(self, bills):
        if not self.check_window():
            logger.info("Outside call window. Skipping queue build.")
            return []

        # Filter strictly by expired age > min_days (e.g. 7)
        eligible_bills = [b for b in bills if b.get('expired_age', 0) >= self.min_days]
        
        # Group by Client to aggregate values (optional but good for context)
        # But we technically just need to trigger calls for the client.
        client_map = {}
        for bill in eligible_bills:
            cid = bill.get('id_cliente')
            if cid not in client_map:
                client_map[cid] = []
            client_map[cid].append(bill)
            
        call_queue = []
        
        for cid, client_bills in client_map.items():
            sample = client_bills[0]
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
            
            # Check availability for EACH number
            for number in unique_numbers:
                if self.can_call_number(number):
                    call_queue.append({
                        "client_id": cid,
                        "contact": number,
                        "client_name": client_name,
                        "total_value": total_value,
                        "bill_ids": bill_ids
                    })
                else:
                    logger.debug(f"Number {number} for Client {cid} is blocked (4h rule)")
            
        return call_queue

    def trigger_call(self, call_data):
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
        caller_id = f"{client_id} - {call_data['client_name']}"
        
        payload = {
            "endpoint": endpoint,
            "extension": extension,
            "context": context,
            "priority": "1",
            "callerId": caller_id[:80], # Truncate if too long (optional safety)
            "timeout": "30000" # Matching Node-RED flow value
        }
        
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
            logger.info(f"Call triggered successfully. Status: {resp.status_code}")
            
            # Record last call time
            self.number_last_called[number] = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"Failed to trigger call {number}: {e}")
            return False
