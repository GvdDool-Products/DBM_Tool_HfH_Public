import sqlite3
import uuid
from datetime import datetime

def get_connection():
    import os
    # Ensure we look in the data directory relative to the project root
    # Assuming the app is run from the project root
    db_path = os.path.join("data", "database.sqlite")
    return sqlite3.connect(db_path)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute('PRAGMA foreign_keys = ON;')
    
    # 1. Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_USERS (
            USER_ID TEXT PRIMARY KEY,
            EMAIL TEXT UNIQUE NOT NULL,
            PASSWORD_HASH TEXT NOT NULL,
            ROLE TEXT NOT NULL,
            FIRST_LOGIN_FLAG INTEGER DEFAULT 1,
            CREATED_AT TEXT NOT NULL
        )
    ''')
    
    # 2. Property Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_PROPERTY (
            SYS_PROPERTY_ID TEXT PRIMARY KEY,
            ID_ADDRESS TEXT,
            ID_ADMIN_UNIT TEXT,
            ID_CADASTRAL_NO TEXT,
            ID_GIS_GEOM TEXT,
            ID_COMPLEX_FLAG INTEGER DEFAULT 0
        )
    ''')
    
    # 3. Legal Ownership Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_LegalOwnership (
            SYS_LegalOwner_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            OWN_TYPE TEXT,
            OWN_ENTITY TEXT,
            LEG_DOC_EXIST INTEGER DEFAULT 0,
            OWN_CONSENT INTEGER DEFAULT 0,
            ENCUMBRANCES TEXT,
            REGISTRY_SOURCE TEXT,
            REGISTRATION_DATE TEXT,
            LAND_USE_DESIG TEXT,
            LAND_OWN_FORM TEXT,
            LAND_TITLE_DOC TEXT,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 4. Building Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_BUILDING (
            SYS_BLD_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            BLD_TYPE TEXT,
            BLD_NC_CODE TEXT,
            BLD_FLOORS INTEGER,
            BLD_TOTAL_AREA REAL,
            BLD_LIVING_AREA REAL,
            BLD_FREE_AREA REAL,
            BLD_STRUCT_COND TEXT,
            BLD_LOAD_STATUS TEXT,
            BLD_ENG_SYS INTEGER DEFAULT 0,
            BLD_ENG_SYS_COND TEXT,
            BLD_ENERGY_METERS INTEGER DEFAULT 0,
            BLD_WINDOWS TEXT,
            BLD_FURNITURE INTEGER DEFAULT 0,
            BLD_MEDIA INTEGER DEFAULT 0,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 5. Building Inspection Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_BUILDING_INSPECTION (
            SYS_INSPECTION_ID TEXT PRIMARY KEY,
            FK_BLD_ID TEXT NOT NULL,
            INSP_OVERALL_COND TEXT,
            INSP_ROUTINE_REPAIR INTEGER DEFAULT 0,
            INSP_MAJOR_REPAIR INTEGER DEFAULT 0,
            INSP_RECONSTRUCTION INTEGER DEFAULT 0,
            INSP_REFITTING INTEGER DEFAULT 0,
            INSP_STRUCT_RISK TEXT,
            INSP_ADDITIONAL_REQ INTEGER DEFAULT 0,
            INSP_DATE TEXT,
            INSP_COMMISSION TEXT,
            FOREIGN KEY (FK_BLD_ID) REFERENCES TBL_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 6. Inspection Media Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_INSPECTION_MEDIA (
            SYS_MEDIA_ID TEXT PRIMARY KEY,
            FK_INSPECTION_ID TEXT NOT NULL,
            MEDIA_TYPE TEXT,
            MEDIA_URI TEXT,
            MEDIA_DESCRIPTION TEXT,
            MEDIA_TIMESTAMP TEXT,
            MEDIA_SOURCE TEXT,
            FOREIGN KEY (FK_INSPECTION_ID) REFERENCES TBL_BUILDING_INSPECTION (SYS_INSPECTION_ID)
        )
    ''')
    
    # 7. Suitability Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_SUITABILITY (
            SYS_SUIT_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            SUIT_IDP_YES INTEGER DEFAULT 0,
            SUIT_AFTER_RECON INTEGER DEFAULT 0,
            SUIT_AFTER_REFIT INTEGER DEFAULT 0,
            SUIT_UNSUITABLE INTEGER DEFAULT 0,
            SUIT_FURTHER_INSP INTEGER DEFAULT 0,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 8. Occupancy Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_OCCUPANCY (
            SYS_OCC_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            OCC_CURRENT_USE TEXT,
            OCC_VACANCY_DUR REAL,
            OCC_NUM_CURRENT INTEGER,
            OCC_FREE_PLACES INTEGER,
            OCC_LEGAL_BASIS TEXT,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 9. Safety Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_SAFETY (
            SYS_SAFE_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            SAFE_PWD_ACCESS INTEGER DEFAULT 0,
            SAFE_FIRE INTEGER DEFAULT 0,
            SAFE_SANITARY INTEGER DEFAULT 0,
            SAFE_CIVIL_DEF INTEGER DEFAULT 0,
            SAFE_HAZARD_ZONE TEXT,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 10. Landplot Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_LANDPLOT (
            SYS_LAND_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            LAND_SIZE REAL,
            LAND_CATEGORY TEXT,
            LAND_INTENDED_USE TEXT,
            LAND_FACTUAL_USE TEXT,
            LAND_VEGETATION TEXT,
            LAND_TEMP_STRUCT INTEGER DEFAULT 0,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 11. Allocation Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_ALLOCATION (
            SYS_ALLOC_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            ALLOC_NUM_IDPS INTEGER,
            ALLOC_APPLICATIONS INTEGER,
            ALLOC_HOUSEHOLD TEXT,
            ALLOC_VULNERABILITY TEXT,
            ALLOC_PENSION_NOTIF INTEGER DEFAULT 0,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 12. Governance Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_GOVERNANCE (
            SYS_GOV_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            GOV_COMMISSION_DEC TEXT,
            GOV_DECISION_DATE TEXT,
            GOV_IAS_ENTRY TEXT,
            GOV_DISCLOSURE INTEGER DEFAULT 0,
            GOV_FUNDING TEXT,
            GOV_DREAM_SIDAR TEXT,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 13. External Systems Table (Master registry)
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_EXTERNAL_SYSTEMS (
            SYS_EXT_SYS_ID TEXT PRIMARY KEY,
            SYSTEM_CODE TEXT UNIQUE NOT NULL,
            SYSTEM_NAME TEXT,
            SYSTEM_TYPE TEXT,
            SYSTEM_OWNER TEXT,
            API_ENDPOINT TEXT,
            SYNC_METHOD TEXT,
            SYNC_FREQUENCY TEXT,
            IS_ACTIVE INTEGER DEFAULT 1,
            LAST_HEALTH_CHECK TEXT
        )
    ''')
    
    # 14. Allocation Link Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_ALLOCATION_LINK (
            SYS_ALLOC_LINK_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            EXT_SYSTEM_NAME TEXT NOT NULL,
            EXT_RECORD_ID TEXT,
            EXT_SYNC_DATE TEXT,
            EXT_SYNC_STATUS TEXT,
            EXT_DATA_SNAPSHOT TEXT,
            LINK_TYPE TEXT,
            LINK_CREATED_DATE TEXT,
            LINK_CREATED_BY TEXT,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_BUILDING (SYS_BLD_ID),
            FOREIGN KEY (EXT_SYSTEM_NAME) REFERENCES TBL_EXTERNAL_SYSTEMS (SYSTEM_CODE)
        )
    ''')
    
    # 15. Governance Link Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_GOVERNANCE_LINK (
            SYS_GOV_LINK_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            EXT_SYSTEM_NAME TEXT NOT NULL,
            EXT_RECORD_ID TEXT,
            EXT_SYNC_DATE TEXT,
            EXT_SYNC_STATUS TEXT,
            EXT_DATA_SNAPSHOT TEXT,
            LINK_TYPE TEXT,
            LINK_CREATED_DATE TEXT,
            LINK_CREATED_BY TEXT,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_PROPERTY (SYS_PROPERTY_ID),
            FOREIGN KEY (EXT_SYSTEM_NAME) REFERENCES TBL_EXTERNAL_SYSTEMS (SYSTEM_CODE)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(email, password_hash, role):
    conn = get_connection()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT INTO TBL_USERS (USER_ID, EMAIL, PASSWORD_HASH, ROLE, CREATED_AT)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, email, password_hash, role, created_at))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_users():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT EMAIL, PASSWORD_HASH, ROLE, FIRST_LOGIN_FLAG FROM TBL_USERS')
    users = c.fetchall()
    conn.close()
    return users

def delete_user(email):
    conn = get_connection()
    c = conn.cursor()
    try:
        # Prevent deleting the last admin or the dev user if possible, 
        # but for now, just perform the delete.
        c.execute('DELETE FROM TBL_USERS WHERE EMAIL = ?', (email,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def update_user_password(email, new_hash):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE TBL_USERS SET PASSWORD_HASH = ?, FIRST_LOGIN_FLAG = 0 WHERE EMAIL = ?', (new_hash, email))
        conn.commit()
        return True
    finally:
        conn.close()

def clear_first_login_flag(email):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE TBL_USERS SET FIRST_LOGIN_FLAG = 0 WHERE EMAIL = ?', (email,))
        conn.commit()
        return True
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with UUID-based schema.")
