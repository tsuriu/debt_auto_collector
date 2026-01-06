from datetime import datetime
from loguru import logger
from database import Database
from services.ixc_client import IxcClient

class BlockedContractsService:
    def __init__(self, instance_config):
        self.instance_config = instance_config
        self.instance_name = instance_config.get('instance_name', 'default')
        self.erp_type = instance_config.get('erp', {}).get('type', 'ixc')
        self.instance_full_id = f"{self.instance_name}-{self.erp_type}-{instance_config.get('_id', '')}"
        self.db = Database().get_db()
        self.client = IxcClient(instance_config)

    def _to_int(self, val):
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.strip().isdigit():
            return int(val.strip())
        return val

    def process(self):
        logger.info(f"Starting Blocked Contracts Job for {self.instance_name}")
        
        try:
            # 1. Fetch raw contracts
            raw_contracts = self.client.get_blocked_contracts()
            if not raw_contracts:
                logger.info("No blocked contracts found.")
                # We should still sync (to clear old ones if any)
                pass

            # 2. Fetch all clients for this instance to hydrate data
            # Using find() instead of distinct to get the fields we need
            instance_clients = list(self.db.clients.find({"instance_full_id": self.instance_full_id}))
            client_map = {str(c['id']): c for c in instance_clients} # Map by string ID for safety

            processed_contracts = []
            
            for contract in raw_contracts:
                try:
                    # Required Fields
                    contract_id = self._to_int(contract.get('id'))
                    client_id = self._to_int(contract.get('id_cliente'))
                    
                    if not contract_id or not client_id:
                        continue

                    # Hydration from Client
                    client_data = client_map.get(str(client_id))
                    
                    if not client_data:
                        # Depending on strictness, we might skip or keep with limited data.
                        # Request says "Inject the same metadata keys used in the bills service".
                        # If client not found, we can't inject much.
                        continue
                        
                    processed_item = {
                        "instance_full_id": self.instance_full_id,
                        "instance_name": self.instance_name,
                        "id": contract_id,
                        "id_cliente": client_id,
                        "contrato": contract.get('contrato'),
                        "status": contract.get('status'),
                        "status_internet": contract.get('status_internet'),
                        "status_velocidade": contract.get('status_velocidade'),
                        "pago_ate_data": contract.get('pago_ate_data'), # Keep as string or date? IXC sends string YYYY-MM-DD usually
                        "num_parcelas_atraso": contract.get('num_parcelas_atraso'),
                        "data_inicial_suspensao": contract.get('data_inicial_suspensao'),

                        
                        # Hydrated Data
                        "razao": client_data.get('razao'),
                        "fantasia": client_data.get('fantasia'),
                        "cidade": client_data.get('cidade'),
                        "bairro": client_data.get('bairro'),
                        "endereco": client_data.get('endereco'),
                        "telefone_celular": client_data.get('telefone_celular'),
                        "whatsapp": client_data.get('whatsapp'),
                        
                        "last_updated": datetime.now()
                    }
                    
                    processed_contracts.append(processed_item)
                except Exception as e:
                    logger.warning(f"Error processing contract {contract.get('id')}: {e}")

            # 3. Sync to DB
            if processed_contracts:
                from pymongo import UpdateOne
                ops = []
                valid_ids = []
                for pc in processed_contracts:
                    # Unique by instance + contract ID
                    valid_ids.append(pc['id'])
                    ops.append(
                        UpdateOne(
                            {"instance_full_id": self.instance_full_id, "id": pc['id']},
                            {"$set": pc},
                            upsert=True
                        )
                    )
                
                if ops:
                    self.db.blocked_contracts.bulk_write(ops)
                    logger.info(f"Upserted {len(ops)} blocked contracts.")
                
                # Cleanup: Delete those not in current list
                res = self.db.blocked_contracts.delete_many({
                    "instance_full_id": self.instance_full_id,
                    "id": {"$nin": valid_ids}
                })
                if res.deleted_count > 0:
                    logger.info(f"Removed {res.deleted_count} stale blocked contracts.")
            else:
                # If no contracts returned, clear everything for this instance?
                # Yes, assumes query returns current state.
                res = self.db.blocked_contracts.delete_many({
                    "instance_full_id": self.instance_full_id
                })
                if res.deleted_count > 0:
                    logger.info(f"Cleared {res.deleted_count} blocked contracts (none returned from API).")

            return len(processed_contracts)

        except Exception as e:
            logger.error(f"Error in BlockedContractsService: {e}")
            return 0
