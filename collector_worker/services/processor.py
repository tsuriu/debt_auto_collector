from datetime import datetime
from loguru import logger

class Processor:
    def __init__(self, instance_config):
        self.config = instance_config
        self.instance_name = instance_config.get('instance_name', 'default')
        self.erp_type = instance_config.get('erp', {}).get('type', 'ixc')
        self.instance_pre_id = f"{self.instance_name}-{self.erp_type}"
        self.min_days = instance_config.get('charger', {}).get('minimum_days_to_charge', 0)

    def _to_int(self, val):
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return val

    def _to_date(self, date_str):
        if not date_str:
            return None
        if isinstance(date_str, datetime):
            return date_str
        try:
            # Try ISO format (YYYY-MM-DD)
            if '-' in date_str:
                return datetime.strptime(date_str, "%Y-%m-%d")
            # Try BR format (DD/MM/YYYY)
            elif '/' in date_str:
                return datetime.strptime(date_str, "%d/%m/%Y")
        except Exception:
            pass
        return None

    def _get_tipo_pessoa(self, client):
        # Try direct fields
        val = client.get('tipo_pessoa') or client.get('pessoa')
        if val:
            return val
            
        # Try deriving from CNPJ/CPF -> REMOVED
        # doc = client.get('cnpj_cpf', '')
        # if not doc:
        #    return 'F' 
            
        # Clean digits
        # digits = ''.join(c for c in str(doc) if c.isdigit())
        
        # if len(digits) > 11:
        #    return 'J' 
        return 'F' # Default fallback

    def validate_client(self, client):
        if not client.get('id') or not client.get('razao'):
            return False
        return True

    def process_clients(self, raw_clients):
        processed = []
        for client in raw_clients:
            if not self.validate_client(client):
                continue
            
            processed.append({
                "id": self._to_int(client.get('id')),
                "razao": client.get('razao'),
                "fantasia": client.get('fantasia'),
                "data_cadastro": self._to_date(client.get('data_cadastro')),
                "endereco": client.get('endereco'),
                "bairro": client.get('bairro'),
                "cidade": client.get('cidade'),
                "estado": client.get('estado'),
                "cep": client.get('cep'),
                "email": client.get('email'),
                "telefone_celular": client.get('telefone_celular'),
                "telefone_comercial": client.get('telefone_comercial'),
                "ramal": client.get('ramal'),
                "id_condominio": self._to_int(client.get('id_condominio')),
                "whatsapp": client.get('whatsapp'),
                "participa_pre_cobranca": client.get('participa_pre_cobranca'),
                "ativo": client.get('ativo'),
                "tipo_pessoa": self._get_tipo_pessoa(client),
                "id_tipo_cliente": self._to_int(client.get('id_tipo_cliente')),
                "data_ultima_alteracao": datetime.now()
            })
        return processed

    def calculate_days_until_due(self, due_date_obj):
        if not due_date_obj:
            return None
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            due = due_date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            delta = (due - today).days
            return delta
        except Exception:
            return None

    def process_bills(self, raw_bills):
        processed = []
        for bill in raw_bills:
            try:
                # Convert values
                valor = float(bill.get('valor', 0))
                valor_aberto = float(bill.get('valor_aberto', 0)) or valor
                
                # Parse dates first
                d_vencimento = self._to_date(bill.get('data_vencimento'))
                d_emissao = self._to_date(bill.get('data_emissao'))
                d_pagamento = self._to_date(bill.get('pagamento_data')) # if exists

                days_until_due = self.calculate_days_until_due(d_vencimento)
                
                processed_bill = {
                    "id": self._to_int(bill.get('id')),
                    "nn_boleto": bill.get('nn_boleto'),
                    "status": bill.get('status'),
                    "pagamento_data": d_pagamento,
                    "data_emissao": d_emissao,
                    "data_vencimento": d_vencimento,
                    "valor": valor,
                    "valor_aberto": valor_aberto,
                    "id_contrato": self._to_int(bill.get('id_contrato')),
                    "id_cliente": self._to_int(bill.get('id_cliente')),
                    "dias_vencimento": days_until_due,
                    "vencimento_status": 'expired' if days_until_due is not None and days_until_due < 0 else 'current',
                    "expired_age": abs(days_until_due) if days_until_due is not None and days_until_due < 0 else 0,
                    "data_processamento": datetime.now()
                }
                
                processed.append(processed_bill)
            except Exception as e:
                logger.warning(f"Skipping invalid bill: {e}")
                
        return processed

    def merge_data(self, bills, clients, client_types=None):
        # Index clients by ID for fast lookup
        # Ensure ID keys are strings for matching if clients came from DB (where they might depend on how they were stored)
        # But we just enforced ints in process_clients.
        # If 'clients' comes from MongoDB find(), and we stored them as Int, they are Int.
        client_map = {str(c['id']): c for c in clients}
        
        # Index client types by ID
        type_map = {}
        if client_types:
            for t in client_types:
                # Ensure we map from INT (as stored) or match types
                tid = t.get('id')
                name = t.get('tipo_cliente')
                if tid and name:
                    type_map[str(tid)] = name

        merged_charges = []
        
        for bill in bills:
            # Filter: only if expired_age > 0 (expired)
            if bill.get('expired_age', 0) <= 0:
                continue
                
            # Filter: only if expired_age > 0 (expired) OR status is 'R' (Paid)
            # We want to catch payments (R) even if not "expired" in our logic, so we can update DB and eventually delete.
            # But the user logic "if bill already exist in db and status if different of A must be updated"
            # implies we should pass everything that IS NOT 'A' (Open) + everything that IS expired?
            # actually, simplest is: pass everything that is relevant. 
            # If we want to UPDATE status to 'R', we must pass 'R'.
            
            # The original logic skipped R. Now we allow it.
            # We also skip if expired_age <= 0 UNLESS it is paid?
            # User requirement: "if bill already exist in db and status if different of A must be updated"
            
            # Let's relax filters.
            # if bill.get('status') == 'R': continue  <-- REMOVED

            client_id = str(bill.get('id_cliente'))
            client = client_map.get(client_id)
            
            if not client:
                continue

            # Additional keys from client
            merged_bill = bill.copy()
            # Resolve Client Type Name
            type_id = client.get('id_tipo_cliente')
            type_name = type_map.get(str(type_id), type_id) if type_id else ''

            merged_bill.update({
                "telefone_celular": client.get('telefone_celular', ''),
                "telefone_comercial": client.get('telefone_comercial', ''),
                "whatsapp": client.get('whatsapp', ''),
                "razao": client.get('razao', ''),
                "fantasia": client.get('fantasia', ''),
                "bairro": client.get('bairro', ''),
                "endereco": client.get('endereco', ''),
                "tipo_cliente": type_name, # Mapped to name
                "ativo": client.get('ativo', ''),
                "participa_pre_cobranca": client.get('participa_pre_cobranca', ''),
                "tipo_pessoa": client.get('tipo_pessoa') or client.get('pessoa') or '',
            })
            
            # Unique ID
            merged_bill['full_id'] = f"{self.instance_pre_id}-{client_id}-{bill['id']}"
            merged_bill['instance_name'] = self.instance_name
            merged_bill['erp_type'] = self.erp_type
            merged_bill['last_updated'] = datetime.now()
            
            # Classification Rule
            expired_age = merged_bill.get('expired_age', 0)
            if expired_age <= self.min_days:
                merged_bill['collection_rule'] = 'pre_force_debt_collection'
            else:
                merged_bill['collection_rule'] = 'force_debt_collection'

            merged_charges.append(merged_bill)
            
        return merged_charges

    def process_client_types(self, raw_types):
        processed = []
        for t in raw_types:
            try:
                processed.append({
                    "id": self._to_int(t.get('id')),
                    "tipo_cliente": t.get('tipo_cliente')
                })
            except Exception as e:
                logger.warning(f"Skipping invalid client type: {e}")
        return processed
