import sys
import os
from datetime import datetime

# Mocking parts of the system to test Dialer.build_queue
sys.path.append('/Users/tulioamancio/Scripts/tsuriuTech/debt_auto_collector/collector_worker')

def test_build_queue():
    # Patch Database before anything else uses it
    import database
    
    class MockDB:
        def __getattr__(self, name):
            return self
        def count_documents(self, *args, **kwargs):
            return 0
        def find_one(self, *args, **kwargs):
            return None

    class MockDatabase:
        _instance = None
        def __new__(cls):
            if cls._instance is None:
                cls._instance = object.__new__(cls)
                cls._instance.db = MockDB()
            return cls._instance
        def get_db(self):
            return self.db

    # Replace the class in the module
    database.Database = MockDatabase
    
    # Patch Dialer's reference to Database
    import services.dialer
    services.dialer.Database = MockDatabase
    from services.dialer import Dialer

    config = {
        'instance_name': 'test',
        'erp': {'type': 'ixc'},
        'charger': {'minimum_days_to_charge': 5, 'dial_per_day': 3, 'dial_interval': 4},
        'asterisk': {'num_channel_available': 2, 'host': 'localhost'}
    }
    
    dialer = Dialer(config)
    dialer.check_window = lambda: True # Force window open
    
    # Fake bills
    bills = [
        # Client 1: 2 bills, expired 10 and 12 days
        {'id_cliente': 1, 'expired_age': 10, 'valor': 100, 'full_id': 'bill1', 'razao': 'Client 1', 'telefone_celular': '11999999991'},
        {'id_cliente': 1, 'expired_age': 12, 'valor': 150, 'full_id': 'bill2', 'razao': 'Client 1', 'telefone_celular': '11999999991'},
        
        # Client 2: 1 bill, expired 20 days
        {'id_cliente': 2, 'expired_age': 20, 'valor': 200, 'full_id': 'bill3', 'razao': 'Client 2', 'telefone_celular': '11999999992'},
        
        # Client 3: 1 bill, expired 8 days
        {'id_cliente': 3, 'expired_age': 8, 'valor': 300, 'full_id': 'bill4', 'razao': 'Client 3', 'telefone_celular': '11999999993'},
        
        # Client 4: 1 bill, not expired (age 2) - should be ignored
        {'id_cliente': 4, 'expired_age': 2, 'valor': 400, 'full_id': 'bill5', 'razao': 'Client 4', 'telefone_celular': '11999999994'},
    ]
    
    queue, eligible = dialer.build_queue(bills)
    
    print(f"Eligible Count: {eligible}")
    print(f"Queue Size: {len(queue)}")
    for i, item in enumerate(queue):
        print(f"Item {i+1}: Client {item['client_id']}, Max Age {item['expired_age']}, Contact {item['contact']}")

    # Expected:
    # Eligible: 4 (Client 1, 1, 2, 3 have age >= 5)
    # Queue Size: 2 (limit is 2)
    # Item 1: Client 2 (Age 20)
    # Item 2: Client 1 (Age 12)
    
    assert eligible == 4, f"Expected 4 eligible, got {eligible}"
    assert len(queue) == 2, f"Expected 2 items, got {len(queue)}"
    assert queue[0]['client_id'] == 2, f"Expected Client 2 first, got {queue[0]['client_id']}"
    assert queue[1]['client_id'] == 1, f"Expected Client 1 second, got {queue[1]['client_id']}"
    
    print("Verification Passed!")

if __name__ == "__main__":
    try:
        test_build_queue()
    except Exception as e:
        print(f"Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
