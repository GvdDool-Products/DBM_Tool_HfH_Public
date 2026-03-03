import sqlite3
from datetime import datetime
from db_core import get_connection

def lock_property(property_id, user_id):
    """Marks a property as locked for fieldwork."""
    conn = get_connection()
    c = conn.cursor()
    locked_at = datetime.now().isoformat()
    try:
        c.execute('''
            UPDATE TBL_PROPERTY 
            SET IS_LOCKED = 1, LOCKED_BY = ?, LOCKED_AT = ?
            WHERE ID_PROPERTY = ? AND IS_LOCKED = 0
        ''', (user_id, locked_at, property_id))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()

def unlock_property(property_id):
    """Releases the lock on a property."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            UPDATE TBL_PROPERTY 
            SET IS_LOCKED = 0, LOCKED_BY = NULL, LOCKED_AT = NULL
            WHERE ID_PROPERTY = ?
        ''', (property_id,))
        conn.commit()
        return True
    finally:
        conn.close()

    return False, None

def get_all_properties_with_lock_status():
    """
    Returns a DataFrame with ID_PROPERTY, Address, IS_LOCKED, LOCKED_BY, LOCKED_AT.
    """
    import pandas as pd
    conn = get_connection()
    try:
        query = '''
            SELECT 
                p.ID_PROPERTY, 
                p.Address_Street || ', ' || p.Address_City as Full_Address,
                p.IS_LOCKED,
                p.LOCKED_BY,
                p.LOCKED_AT
            FROM TBL_PROPERTY p
        '''
        df = pd.read_sql_query(query, conn)
        return df
    finally:
        conn.close()

def toggle_lock(property_id, user_id, current_lock_status):
    """
    Toggles the lock status. 
    If locked (1), attempts to unlock (only if locked by user).
    If unlocked (0), attempts to lock.
    """
    if current_lock_status:
        # User wants to unlock
        return unlock_property(property_id)
    else:
        # User wants to lock
        return lock_property(property_id, user_id)
