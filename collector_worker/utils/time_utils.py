from datetime import datetime

def is_within_operational_window(debug_mode: bool = False) -> bool:
    """
    Checks if the current time is within the allowed operational window.
    
    Rules:
    - Debug mode (config): Always allowed.
    - Sunday: Never allowed.
    - Saturday: 08:00 - 13:00.
    - Weekdays: 08:00 - 19:00.
    """
    if debug_mode:
        return True

    now = datetime.now()
    hour = now.hour
    day = now.weekday() # 0=Mon, 6=Sun

    if day == 6: # Sunday
        return False
        
    if day == 5: # Saturday
        # 8h to 13h
        return 8 <= hour < 13
        
    # Weekdays
    # 8h to 19h
    return 8 <= hour < 19
