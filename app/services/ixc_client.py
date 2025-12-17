import requests
import time
import base64
import json
from loguru import logger
from datetime import datetime, timedelta

class IxcClient:
    def __init__(self, instance_config):
        self.config = instance_config
        self.erp = instance_config.get('erp', {})
        self.base_url = self.erp.get('base_url')
        self.auth = self.erp.get('auth', {})
        self.user_id = self.auth.get('user_id')
        self.token = self.auth.get('user_token')
        self.default_page_size = self.erp.get('request_param', {}).get('default_page_size', 20)
        
        self.last_request_time = 0
        self.min_delay = 0.1  # 100ms

    def _get_headers(self):
        credentials = f"{self.user_id}:{self.token}"
        encoded_auth = base64.b64encode(credentials.encode()).decode()
        return {
            "ixcsoft": "listar",
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json"
        }

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def fetch_all(self, endpoint, query_params):
        all_records = []
        page = 1
        total_records = None
        
        while True:
            query_params['page'] = str(page)
            query_params['rp'] = str(self.default_page_size)
            
            self._rate_limit()
            
            url = f"{self.base_url}/{endpoint}"
            logger.info(f"Fetching {endpoint} page {page}...")
            
            try:
                response = requests.post(url, headers=self._get_headers(), json=query_params)
                response.raise_for_status()
                data = response.json()
                
                records = data.get('registros', [])
                if not records:
                    break
                    
                all_records.extend(records)
                
                total = int(data.get('total', 0))
                if total_records is None:
                    total_records = total
                    logger.info(f"Total records expecting: {total_records}")
                
                if len(all_records) >= total_records:
                    break
                
                page += 1
                
            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break
                
        return all_records

    def get_clients(self):
        # topic === "update_clients" logic
        query_params = {
            "qtype": "cliente.ativo",
            "query": "S",
            "oper": "=",
            "sortname": "cliente.id",
            "sortorder": "asc",
            "grid_param": json.dumps([
                {"TB": "cliente.id", "OP": "!=", "P": "1"},
                {"TB": "cliente.filial_id", "OP": "!=", "P": "3"}
            ])
        }
        return self.fetch_all("cliente", query_params)

    def get_bills(self):
        # topic === "update_bills" logic
        today = datetime.now()
        future_date = today
        past_date = today - timedelta(days=30)
        
        format_date = lambda d: d.strftime("%d/%m/%Y")
        
        query_params = {
            "qtype": "fn_areceber.data_vencimento",
            "query": format_date(future_date),
            "oper": "<",
            "sortname": "fn_areceber.data_vencimento",
            "sortorder": "asc",
            "grid_param": json.dumps([
                {"TB": "fn_areceber.liberado", "OP": "=", "P": "S"},
                {"TB": "fn_areceber.status", "OP": "=", "P": "A"},
                {"TB": "fn_areceber.filial_id", "OP": "!=", "P": "3"},
                {"TB": "fn_areceber.data_vencimento", "OP": ">", "P": format_date(past_date)}
            ])
        }
        return self.fetch_all("fn_areceber", query_params)
