import sqlite3
import uuid
from datetime import datetime

# ==================================================================
# SCRIPT STRUCTURE & NAVIGATION
# ==================================================================
# Use the following keywords (Ctrl + F) to jump to specific sections:
#
# Table Creation              : [[TBL_GEN]]
# Triggers                    : [[TRG_GEN]]
# Enumeration & Ref Data      : [[ENUM_REF]]
# Python Supporting Functions : [[PY_API]]
# ==================================================================

def get_connection():
    import os
    try:
        import streamlit as st
        # Try to access secrets
        run_time = st.secrets.get("RUN_TIME", "cloud")
        if run_time == "local":
             db_path = os.path.join("data", "database_dev.sqlite")
        else:
             db_path = st.secrets.get("DB_FILE_PATH", os.path.join("data", "database.sqlite"))
    except Exception:
        # Fallback for local execution without streamlit secrets
        db_path = os.path.join("data", "database_dev.sqlite")
    
    return sqlite3.connect(db_path)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Enable foreign keys
    c.execute('PRAGMA foreign_keys = ON;')
    
    # [[TBL_GEN]]
    # ------------------------------------------------------------------
    # Table Generation SQL statements:
    # 0.  TBL_CORE_GEOMETRY (System Geometry) 
    #     -> Centralized store for spatial objects (point, polygon, linestring [optional])
    #     -> linked via UUIDs on buildings and addresses
    # 1.  TBL_SYS_USERS (Users)
    # 2.  TBL_CORE_PROPERTY (Property)
    # 3.  TBL_CORE_LEGAL_OWNERSHIP (Legal Ownership)
    # 4.  TBL_CORE_BUILDING (Building)
    # 5.  TBL_CORE_INSPECTION (Building Inspection)
    # 6.  TBL_CORE_INSPECTION_MEDIA (Inspection Media)
    # 7.  TBL_CORE_SUITABILITY (Suitability)
    # 8.  TBL_CORE_OCCUPANCY (Occupancy)
    # 9.  TBL_CORE_SAFETY (Safety)
    # 10. TBL_CORE_LANDPLOT (Landplot)
    # 11. TBL_CORE_ALLOCATION (Allocation)
    # 12. TBL_CORE_GOVERNANCE (Governance)
    # 13. TBL_SYS_EXT_SYSTEMS (External Systems Master) 
    #     -> Registry of external sources (Commission reports, Cadastre, Ministry, etc.) 
    #     -> for sync tracking.
    # 14. TBL_LINK_ALLOCATION (Allocation External Links) 
    #     -> Maps building allocations to external system records.
    # 15. TBL_LINK_GOVERNANCE (Governance External Links) 
    #     -> Maps property governance records to external system counterparts.
    # 16. TBL_CORE_ADDRESS (Property Address / Postal)
    # 17. TBL_LINK_ADDRESS_ADMIN_REGION (Admin Boundary Mapping)
    # 18. TBL_REF_ENUM (Reference Data - Enum Master)
    # 19. TBL_REF_ENUM_I18N (Reference Data - Translations)
    # ------------------------------------------------------------------

    # 0. System Geometry Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_GEOMETRY (
            GEOM_ID TEXT PRIMARY KEY,               -- UUID, referenced by other tables
            GEOM_TYPE TEXT NOT NULL,                -- POINT | POLYGON | LINESTRING
            GEOM_WKT TEXT,                          -- Geometry in WKT format, NULL until created
            CRS_EPSG INTEGER DEFAULT 4326,          -- Coordinate reference system (WGS84 default)
            SOURCE TEXT,                            -- e.g. Field survey, OSM, Satellite, Admin data
            CAPTURE_METHOD TEXT,                    -- GPS, Digitised, Imported
            CREATED_AT TEXT NOT NULL,               -- ISO timestamp
            CREATED_BY TEXT,                        -- User or system
            UPDATED_AT TEXT                         -- Last update timestamp
        )
    ''')

    # 1. Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_SYS_USERS (
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
        CREATE TABLE IF NOT EXISTS TBL_CORE_PROPERTY (
            SYS_PROPERTY_ID TEXT PRIMARY KEY,
            ID_ADMIN_UNIT TEXT,
            ID_CADASTRAL_NO TEXT,
            ID_COMPLEX_FLAG INTEGER DEFAULT 0,
            GEOM_PROP_CREATED INTEGER DEFAULT 0,
            ID_PROPERTY_GEOM TEXT,              -- FK to TBL_CORE_GEOMETRY (POLYGON)
            FOREIGN KEY (ID_PROPERTY_GEOM) REFERENCES TBL_CORE_GEOMETRY (GEOM_ID)
        )
    ''')
    
    # 3. Legal Ownership Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_LEGAL_OWNERSHIP (
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
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_CORE_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 4. Building Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_BUILDING (
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
            ID_BUILDING_GEOM TEXT,              -- FK to TBL_CORE_GEOMETRY (POLYGON)
            GEOM_BLD_CREATED INTEGER DEFAULT 0,
            GEOM_ENTR_CREATED INTEGER DEFAULT 0, -- Track building entrance pin
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_CORE_PROPERTY (SYS_PROPERTY_ID),
            FOREIGN KEY (ID_BUILDING_GEOM) REFERENCES TBL_CORE_GEOMETRY (GEOM_ID)
        )
    ''')
    
    # 5. Building Inspection Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_INSPECTION (
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
            FOREIGN KEY (FK_BLD_ID) REFERENCES TBL_CORE_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 6. Inspection Media Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_INSPECTION_MEDIA (
            SYS_MEDIA_ID TEXT PRIMARY KEY,
            FK_INSPECTION_ID TEXT NOT NULL,
            MEDIA_TYPE TEXT,
            MEDIA_URI TEXT,
            MEDIA_DESCRIPTION TEXT,
            MEDIA_TIMESTAMP TEXT,
            MEDIA_SOURCE TEXT,
            FOREIGN KEY (FK_INSPECTION_ID) REFERENCES TBL_CORE_INSPECTION (SYS_INSPECTION_ID)
        )
    ''')
    
    # 7. Suitability Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_SUITABILITY (
            SYS_SUIT_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            SUIT_IDP_YES INTEGER DEFAULT 0,
            SUIT_AFTER_RECON INTEGER DEFAULT 0,
            SUIT_AFTER_REFIT INTEGER DEFAULT 0,
            SUIT_UNSUITABLE INTEGER DEFAULT 0,
            SUIT_FURTHER_INSP INTEGER DEFAULT 0,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_CORE_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 8. Occupancy Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_OCCUPANCY (
            SYS_OCC_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            OCC_CURRENT_USE TEXT,
            OCC_VACANCY_DUR REAL,
            OCC_NUM_CURRENT INTEGER,
            OCC_FREE_PLACES INTEGER,
            OCC_LEGAL_BASIS TEXT,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_CORE_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 9. Safety Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_SAFETY (
            SYS_SAFE_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            SAFE_PWD_ACCESS INTEGER DEFAULT 0,
            SAFE_FIRE INTEGER DEFAULT 0,
            SAFE_SANITARY INTEGER DEFAULT 0,
            SAFE_CIVIL_DEF INTEGER DEFAULT 0,
            SAFE_HAZARD_ZONE TEXT,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_CORE_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 10. Landplot Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_LANDPLOT (
            SYS_LAND_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            LAND_SIZE REAL,
            LAND_CATEGORY TEXT,
            LAND_INTENDED_USE TEXT,
            LAND_FACTUAL_USE TEXT,
            LAND_VEGETATION TEXT,
            LAND_TEMP_STRUCT INTEGER DEFAULT 0,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_CORE_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 11. Allocation Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_ALLOCATION (
            SYS_ALLOC_ID TEXT PRIMARY KEY,
            FK_BUILDING_ID TEXT NOT NULL,
            ALLOC_NUM_IDPS INTEGER,
            ALLOC_APPLICATIONS INTEGER,
            ALLOC_HOUSEHOLD TEXT,
            ALLOC_VULNERABILITY TEXT,
            ALLOC_PENSION_NOTIF INTEGER DEFAULT 0,
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_CORE_BUILDING (SYS_BLD_ID)
        )
    ''')
    
    # 12. Governance Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_GOVERNANCE (
            SYS_GOV_ID TEXT PRIMARY KEY,
            FK_PROPERTY_ID TEXT NOT NULL,
            GOV_COMMISSION_DEC TEXT,
            GOV_DECISION_DATE TEXT,
            GOV_IAS_ENTRY TEXT,
            GOV_DISCLOSURE INTEGER DEFAULT 0,
            GOV_FUNDING TEXT,
            GOV_DREAM_SIDAR TEXT,
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_CORE_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')
    
    # 13. External Systems Table (Master registry)
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_SYS_EXT_SYSTEMS (
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
        CREATE TABLE IF NOT EXISTS TBL_LINK_ALLOCATION (
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
            FOREIGN KEY (FK_BUILDING_ID) REFERENCES TBL_CORE_BUILDING (SYS_BLD_ID),
            FOREIGN KEY (EXT_SYSTEM_NAME) REFERENCES TBL_SYS_EXT_SYSTEMS (SYSTEM_CODE)
        )
    ''')
    
    # 15. Governance Link Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_LINK_GOVERNANCE (
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
            FOREIGN KEY (FK_PROPERTY_ID) REFERENCES TBL_CORE_PROPERTY (SYS_PROPERTY_ID),
            FOREIGN KEY (EXT_SYSTEM_NAME) REFERENCES TBL_SYS_EXT_SYSTEMS (SYSTEM_CODE)
        )
    ''')

    # 16. Property Address Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_CORE_ADDRESS (
        SYS_ADDR_ID TEXT PRIMARY KEY,
        FK_PROPERTY_ID TEXT NOT NULL,

        -- Address semantics
        ADDR_TYPE TEXT,                     -- e.g. 'PHYSICAL', 'CORRESPONDENCE'
        ADDR_LINE1 TEXT,
        ADDR_LINE2 TEXT,
        POSTCODE TEXT,
        CITY TEXT,

        -- Human-entered administrative context (postal / legal)
        ADMIN_UNIT TEXT,                    -- e.g. 'Île-de-France', 'Kyiv Oblast'
        COUNTRY TEXT,

        -- Geometry linkage (optional, derived later)
        ID_ADDR_GEOM TEXT,                  -- FK to address-point geometry
        ADDR_GEOM_CREATED INTEGER DEFAULT 0,

        FOREIGN KEY (FK_PROPERTY_ID)
            REFERENCES TBL_CORE_PROPERTY (SYS_PROPERTY_ID)
        )
    ''')

    # 17. Mapping the ADDRESS to ADMIN_REGION Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_LINK_ADDRESS_ADMIN_REGION (
        SYS_ADDR_ADMIN_ID TEXT PRIMARY KEY,

        -- Link to address
        FK_SYS_ADDR_ID TEXT NOT NULL,

        -- Administrative hierarchy
        ADMIN_LEVEL INTEGER NOT NULL,        -- 0=country, 1=oblast/province, 2=raion, 3=hromada
        ADMIN_LEVEL_NAME TEXT NOT NULL,       -- Human-readable name
        ADMIN_CODE TEXT,                     -- World Bank / ISO / GADM code

        -- Provenance & audit
        ADMIN_SOURCE TEXT DEFAULT 'external_source',
        RESOLVED_FROM_GEOM TEXT,              -- 'address_point' | 'cadastral_polygon'
        RESOLVED_AT INTEGER,                  -- unix timestamp

        FOREIGN KEY (FK_SYS_ADDR_ID)
            REFERENCES TBL_CORE_ADDRESS (SYS_ADDR_ID)
        )
    ''')

    # 18. Enum Master Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_REF_ENUM (
            SYS_ENUM_ID TEXT PRIMARY KEY,
            ENUM_GROUP  TEXT NOT NULL,
            ENUM_CODE   TEXT NOT NULL,
            IS_ACTIVE   INTEGER DEFAULT 1,
            SORT_ORDER  INTEGER DEFAULT 0,
            UNIQUE (ENUM_GROUP, ENUM_CODE)
        )
    ''')

    # 19. Enum Translation Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS TBL_REF_ENUM_I18N (
            SYS_ENUM_I18N_ID TEXT PRIMARY KEY,
            FK_ENUM_ID       TEXT NOT NULL,
            LANGUAGE_CODE    TEXT NOT NULL,
            ENUM_LABEL       TEXT NOT NULL,
            ENUM_DESCRIPTION TEXT,
            UNIQUE (FK_ENUM_ID, LANGUAGE_CODE),
            FOREIGN KEY (FK_ENUM_ID) REFERENCES TBL_REF_ENUM (SYS_ENUM_ID)
        )
    ''')

# [[TRG_GEN]]
    # Triggers & Business Logic SQL
    # ------------------------------------------------------------------
    # Trigger firing sequence for a new property:
    #   add_property() in Python orchestrates the insert order:
    #   1. INSERT TBL_CORE_PROPERTY        -> trg_after_property_insert fires
    #   2. INSERT TBL_CORE_BUILDING        -> trg_after_building_insert fires
    #   3. INSERT TBL_CORE_ADDRESS         -> trg_after_address_insert fires
    #   4. INSERT TBL_CORE_LEGAL_OWNERSHIP -> no trigger, Python only
    #
    #   Future:
    #   5. INSERT TBL_CORE_INSPECTION  -> trg_after_inspection_insert fires (add_inspection())
    #      which creates TBL_CORE_SUITABILITY placeholder
    # ------------------------------------------------------------------

    # Fired by: add_property() step 1
    # Creates: POLYGON geometry placeholder for the property boundary
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_after_property_insert
        AFTER INSERT ON TBL_CORE_PROPERTY
        BEGIN
            INSERT INTO TBL_CORE_GEOMETRY (GEOM_ID, GEOM_TYPE, CREATED_AT, CREATED_BY)
            VALUES (NEW.ID_PROPERTY_GEOM, 'POLYGON', datetime('now'), 'SYSTEM');
        END;
    ''')

    # Fired by: add_property() step 2
    # Creates: TWO placeholders (Polygon for footprint, Point for entrance)
    # The entrance point uses the SYS_BLD_ID (Implicit ID)
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_after_building_insert
        AFTER INSERT ON TBL_CORE_BUILDING
        BEGIN
            -- 1. Create Footprint Placeholder (Polygon)
            INSERT INTO TBL_CORE_GEOMETRY (GEOM_ID, GEOM_TYPE, CREATED_AT, CREATED_BY)
            VALUES (NEW.ID_BUILDING_GEOM, 'POLYGON', datetime('now'), 'SYSTEM');
            
            -- 2. Create Entrance Placeholder (Point) using SYS_BLD_ID
            INSERT INTO TBL_CORE_GEOMETRY (GEOM_ID, GEOM_TYPE, CREATED_AT, CREATED_BY)
            VALUES (NEW.SYS_BLD_ID, 'POINT', datetime('now'), 'SYSTEM');
        END;
    ''')

    # Fired by: add_property() step 3
    # Creates: POINT geometry placeholder for the address location
    c.execute('''
        CREATE TRIGGER IF NOT EXISTS trg_after_address_insert
        AFTER INSERT ON TBL_CORE_ADDRESS
        BEGIN
            INSERT INTO TBL_CORE_GEOMETRY (GEOM_ID, GEOM_TYPE, CREATED_AT, CREATED_BY)
            VALUES (NEW.ID_ADDR_GEOM, 'POINT', datetime('now'), 'SYSTEM');
        END;
    ''')

    # Fired by: add_inspection() step 1 — NOT YET IMPLEMENTED
    # Creates: SUITABILITY placeholder linked to the building
    # NOTE: SYS_SUIT_ID UUID must be generated in add_inspection() before insert,
    #       as SQLite triggers cannot generate Python UUIDs.
    #       This trigger is a placeholder for future implementation.
    # c.execute('''
    #     CREATE TRIGGER IF NOT EXISTS trg_after_inspection_insert
    #     AFTER INSERT ON TBL_CORE_INSPECTION
    #     BEGIN
    #         -- UUID generation handled in add_inspection() Python function
    #     END;
    # ''')
    # ------------------------------------------------------------------

    conn.commit()
    conn.close()

# [[ENUM_REF]]

from db_enums import _ENUM_SEED


def seed_enums():
    """
    Populate TBL_REF_ENUM and TBL_REF_ENUM_I18N with the authoritative enum values.
    """
    conn = get_connection()
    c = conn.cursor()

    for group, code, sort_order, label, description, is_active in _ENUM_SEED:
        enum_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{group}.{code}"))
        c.execute('''
            INSERT OR IGNORE INTO TBL_REF_ENUM
                (SYS_ENUM_ID, ENUM_GROUP, ENUM_CODE, IS_ACTIVE, SORT_ORDER)
            VALUES (?, ?, ?, ?, ?)
        ''', (enum_id, group, code, is_active, sort_order))

        i18n_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{group}.{code}.en"))
        c.execute('''
            INSERT OR IGNORE INTO TBL_REF_ENUM_I18N
                (SYS_ENUM_I18N_ID, FK_ENUM_ID, LANGUAGE_CODE, ENUM_LABEL, ENUM_DESCRIPTION)
            VALUES (?, ?, 'en', ?, ?)
        ''', (i18n_id, enum_id, label, description))

    conn.commit()
    conn.close()


# ------------------------------------------------------------------
# [[PY_API]]
# DESIGN PATTERN: The 'Skeleton Management' Pattern
# Many modules follow this pattern:
# 1. API: High-level 'orchestration' functions (like add_property) 
#    that create the relational structure across multiple tables.
# 2. UPDATERS: Focused functions (update_*) that handle specific forms.
# 3. TRIGGERS: SQL-level logic for automatic dependent data (like geometry).
# ------------------------------------------------------------------
def get_enum_options(group: str, lang: str = "en") -> list:
    """
    Returns a list of (ENUM_CODE, ENUM_LABEL) tuples for a given group and language.
    Falls back to ENUM_CODE if no translation exists for the requested language.

    Usage in Streamlit:
        options = get_enum_options("BLD_TYPE")
        codes = [o[0] for o in options]
        labels = [o[1] for o in options]
        selected_code = codes[st.selectbox("Building Type", range(len(labels)), format_func=lambda i: labels[i])]
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT e.ENUM_CODE, COALESCE(i.ENUM_LABEL, e.ENUM_CODE) AS LABEL
        FROM TBL_REF_ENUM e
        LEFT JOIN TBL_REF_ENUM_I18N i
            ON i.FK_ENUM_ID = e.SYS_ENUM_ID
           AND i.LANGUAGE_CODE = ?
        WHERE e.ENUM_GROUP = ?
          AND e.IS_ACTIVE = 1
        ORDER BY e.SORT_ORDER, e.ENUM_CODE
    ''', (lang, group))
    rows = c.fetchall()
    conn.close()
    return rows

def add_user(email, password_hash, role):
    conn = get_connection()
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    try:
        c.execute('''
            INSERT INTO TBL_SYS_USERS (USER_ID, EMAIL, PASSWORD_HASH, ROLE, CREATED_AT)
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
    c.execute('SELECT EMAIL, PASSWORD_HASH, ROLE, FIRST_LOGIN_FLAG FROM TBL_SYS_USERS')
    users = c.fetchall()
    conn.close()
    return users

def delete_user(email):
    conn = get_connection()
    c = conn.cursor()
    try:
        # Prevent deleting the last admin or the dev user if possible, 
        # but for now, just perform the delete.
        c.execute('DELETE FROM TBL_SYS_USERS WHERE EMAIL = ?', (email,))
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
        c.execute('UPDATE TBL_SYS_USERS SET PASSWORD_HASH = ?, FIRST_LOGIN_FLAG = 0 WHERE EMAIL = ?', (new_hash, email))
        conn.commit()
        return True
    finally:
        conn.close()

def clear_first_login_flag(email):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE TBL_SYS_USERS SET FIRST_LOGIN_FLAG = 0 WHERE EMAIL = ?', (email,))
        conn.commit()
        return True
    finally:
        conn.close()

# Add property:
def add_property(admin_unit, cadastral_no, created_by='SYSTEM'):
    """
    MASTER ORCHESTRATOR: Creates a full property 'skeleton'.
    
    This function handles the 'Genesis' of a property, ensuring that 
    the property record and its mandatory related placeholders 
    (Building, Address, Legal, Governance, Landplot) are created 
    together in a single transaction.
    
    SQL triggers in [[TRG_GEN]] automatically create the geometry placeholders
    during these inserts.
    """
    conn = get_connection()
    c = conn.cursor()

    try:
        # Generate all UUIDs upfront to maintain relational integrity
        property_id  = str(uuid.uuid4())
        prop_geom_id = str(uuid.uuid4())
        bld_id       = str(uuid.uuid4())
        bld_geom_id  = str(uuid.uuid4())
        addr_id      = str(uuid.uuid4())
        addr_geom_id = str(uuid.uuid4())
        legal_id     = str(uuid.uuid4())
        gov_id       = str(uuid.uuid4())
        land_id      = str(uuid.uuid4())

        # 1. Insert property (triggers plot polygon)
        c.execute("""
            INSERT INTO TBL_CORE_PROPERTY (
                SYS_PROPERTY_ID, ID_ADMIN_UNIT, ID_CADASTRAL_NO,
                ID_PROPERTY_GEOM
            ) VALUES (?, ?, ?, ?)
        """, (property_id, admin_unit, cadastral_no, prop_geom_id))

        # 2. Insert building (triggers footprint polygon)
        c.execute("""
            INSERT INTO TBL_CORE_BUILDING (
                SYS_BLD_ID, FK_PROPERTY_ID, ID_BUILDING_GEOM,
                BLD_TYPE, BLD_STRUCT_COND, BLD_LOAD_STATUS
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (bld_id, property_id, bld_geom_id,
              'UNKNOWN', 'UNKNOWN', 'UNKNOWN'))

        # 3. Insert address (triggers location point)
        c.execute("""
            INSERT INTO TBL_CORE_ADDRESS (
                SYS_ADDR_ID, FK_PROPERTY_ID, ID_ADDR_GEOM,
                ADDR_TYPE
            ) VALUES (?, ?, ?, ?)
        """, (addr_id, property_id, addr_geom_id, 'UNKNOWN'))

        # 4. Insert legal placeholder (Owned/Admin data)
        c.execute("""
            INSERT INTO TBL_CORE_LEGAL_OWNERSHIP (
                SYS_LegalOwner_ID, FK_PROPERTY_ID, OWN_TYPE, OWN_ENTITY
            ) VALUES (?, ?, ?, ?)
        """, (legal_id, property_id, 'UNKNOWN', 'UNKNOWN'))

        # 5. Insert governance placeholder (Commission/Disclosure data)
        c.execute("""
            INSERT INTO TBL_CORE_GOVERNANCE (
                SYS_GOV_ID, FK_PROPERTY_ID
            ) VALUES (?, ?)
        """, (gov_id, property_id))

        # 6. Insert landplot placeholder (Cadastral/Vegetation data)
        c.execute("""
            INSERT INTO TBL_CORE_LANDPLOT (
                SYS_LAND_ID, FK_PROPERTY_ID
            ) VALUES (?, ?)
        """, (land_id, property_id))

        conn.commit()
        return property_id

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
### End Add

# Delete property:
def delete_property(property_id):
    """
    Fully removes a property and all linked records across all tables.
    Cascade order respects FK constraints — children first, parent last.
    Geometry records cleaned up after parent records are removed.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Collect all geometry IDs before deleting anything
        c.execute("""
            SELECT ID_PROPERTY_GEOM, ID_ADDRESS_GEOM 
            FROM TBL_CORE_PROPERTY 
            WHERE SYS_PROPERTY_ID = ?
        """, (property_id,))
        prop_row = c.fetchone()

        c.execute("""
            SELECT ID_BUILDING_GEOM 
            FROM TBL_CORE_BUILDING 
            WHERE FK_PROPERTY_ID = ?
        """, (property_id,))
        bld_geom_rows = c.fetchall()

        c.execute("""
            SELECT ID_ADDR_GEOM 
            FROM TBL_CORE_ADDRESS 
            WHERE FK_PROPERTY_ID = ?
        """, (property_id,))
        addr_row = c.fetchone()

        # 2. Get building IDs for deeper cascade
        c.execute("""
            SELECT SYS_BLD_ID 
            FROM TBL_CORE_BUILDING 
            WHERE FK_PROPERTY_ID = ?
        """, (property_id,))
        bld_ids = [r[0] for r in c.fetchall()]

        # 3. Get inspection IDs for media cascade
        for bld_id in bld_ids:
            c.execute("""
                SELECT SYS_INSPECTION_ID 
                FROM TBL_CORE_INSPECTION 
                WHERE FK_BLD_ID = ?
            """, (bld_id,))
            insp_ids = [r[0] for r in c.fetchall()]

            # 4. Delete inspection media
            for insp_id in insp_ids:
                c.execute("DELETE FROM TBL_CORE_INSPECTION_MEDIA WHERE FK_INSPECTION_ID = ?", (insp_id,))

            # 5. Delete inspections
            c.execute("DELETE FROM TBL_CORE_INSPECTION  WHERE FK_BLD_ID = ?", (bld_id,))

            # 6. Delete building linked tables
            c.execute("DELETE FROM TBL_CORE_SUITABILITY WHERE FK_BUILDING_ID = ?", (bld_id,))
            c.execute("DELETE FROM TBL_CORE_OCCUPANCY   WHERE FK_BUILDING_ID = ?", (bld_id,))
            c.execute("DELETE FROM TBL_CORE_SAFETY      WHERE FK_BUILDING_ID = ?", (bld_id,))
            c.execute("DELETE FROM TBL_CORE_ALLOCATION  WHERE FK_BUILDING_ID = ?", (bld_id,))
            c.execute("DELETE FROM TBL_LINK_ALLOCATION  WHERE FK_BUILDING_ID = ?", (bld_id,))

        # 7. Delete address admin region links
        c.execute("""
            DELETE FROM TBL_LINK_ADDRESS_ADMIN_REGION 
            WHERE FK_SYS_ADDR_ID IN (
                SELECT SYS_ADDR_ID FROM TBL_CORE_ADDRESS 
                WHERE FK_PROPERTY_ID = ?
            )
        """, (property_id,))

        # 8. Delete property-level records
        c.execute("DELETE FROM TBL_CORE_BUILDING       WHERE FK_PROPERTY_ID = ?", (property_id,))
        c.execute("DELETE FROM TBL_CORE_ADDRESS        WHERE FK_PROPERTY_ID = ?", (property_id,))
        c.execute("DELETE FROM TBL_CORE_LEGAL_OWNERSHIP WHERE FK_PROPERTY_ID = ?", (property_id,))
        c.execute("DELETE FROM TBL_CORE_LANDPLOT       WHERE FK_PROPERTY_ID = ?", (property_id,))
        c.execute("DELETE FROM TBL_CORE_GOVERNANCE     WHERE FK_PROPERTY_ID = ?", (property_id,))
        c.execute("DELETE FROM TBL_LINK_GOVERNANCE     WHERE FK_PROPERTY_ID = ?", (property_id,))

        # 9. Delete property
        c.execute("DELETE FROM TBL_CORE_PROPERTY WHERE SYS_PROPERTY_ID = ?", (property_id,))

        # 10. Clean up orphaned geometry records
        geom_ids = []
        if prop_row:
            if prop_row[0]: geom_ids.append(prop_row[0])
            if prop_row[1]: geom_ids.append(prop_row[1])
        for row in bld_geom_rows:
            if row[0]: geom_ids.append(row[0])
        if addr_row and addr_row[0]:
            geom_ids.append(addr_row[0])

        for geom_id in geom_ids:
            c.execute("DELETE FROM TBL_CORE_GEOMETRY WHERE GEOM_ID = ?", (geom_id,))

        conn.commit()
        print(f"✅ Property {property_id} and all linked records deleted.")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Error deleting property: {e}")
        return False
    finally:
        conn.close()
### End Delete

### Updates to different tables
def update_complex_flag(property_id, is_complex):
    """Updates the complex/multi-building flag on the property record."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_PROPERTY
            SET ID_COMPLEX_FLAG = ?
            WHERE SYS_PROPERTY_ID = ?
        """, (int(is_complex), property_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating complex flag: {e}")
        return False
    finally:
        conn.close()

def add_building(property_id):
    """
    Creates a new building record for a property.
    Triggers will automatically create the geometry placeholders.
    """
    import uuid
    bld_id = str(uuid.uuid4())
    bld_geom_id = str(uuid.uuid4())

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO TBL_CORE_BUILDING (
                SYS_BLD_ID, FK_PROPERTY_ID, ID_BUILDING_GEOM,
                BLD_TYPE, BLD_STRUCT_COND, BLD_LOAD_STATUS
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (bld_id, property_id, bld_geom_id,
              'UNKNOWN', 'UNKNOWN', 'UNKNOWN'))
        conn.commit()
        return bld_id
    except Exception as e:
        conn.rollback()
        print(f"Error adding building: {e}")
        return None
    finally:
        conn.close()

def delete_building(building_id):
    """
    Deletes a specific building and all its related records (inspections, geometry, etc.).
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Get geometry IDs for this building
        c.execute("SELECT ID_BUILDING_GEOM FROM TBL_CORE_BUILDING WHERE SYS_BLD_ID = ?", (building_id,))
        row = c.fetchone()
        bld_geom_id = row[0] if row else None
        
        # 2. Delete inspection media
        c.execute("""
            DELETE FROM TBL_CORE_INSPECTION_MEDIA 
            WHERE FK_INSPECTION_ID IN (
                SELECT SYS_INSPECTION_ID FROM TBL_CORE_INSPECTION WHERE FK_BLD_ID = ?
            )
        """, (building_id,))
        
        # 3. Delete inspections
        c.execute("DELETE FROM TBL_CORE_INSPECTION WHERE FK_BLD_ID = ?", (building_id,))
        
        # 4. Delete building linked tables
        c.execute("DELETE FROM TBL_CORE_SUITABILITY WHERE FK_BUILDING_ID = ?", (building_id,))
        c.execute("DELETE FROM TBL_CORE_OCCUPANCY   WHERE FK_BUILDING_ID = ?", (building_id,))
        c.execute("DELETE FROM TBL_CORE_SAFETY      WHERE FK_BUILDING_ID = ?", (building_id,))
        c.execute("DELETE FROM TBL_CORE_ALLOCATION  WHERE FK_BUILDING_ID = ?", (building_id,))
        c.execute("DELETE FROM TBL_LINK_ALLOCATION  WHERE FK_BUILDING_ID = ?", (building_id,))
        
        # 5. Delete the building itself
        c.execute("DELETE FROM TBL_CORE_BUILDING WHERE SYS_BLD_ID = ?", (building_id,))
        
        # 6. Delete geometry records (Footprint and Entrance)
        # Note: Entrance uses SYS_BLD_ID as GEOM_ID
        if bld_geom_id:
            c.execute("DELETE FROM TBL_CORE_GEOMETRY WHERE GEOM_ID = ?", (bld_geom_id,))
        c.execute("DELETE FROM TBL_CORE_GEOMETRY WHERE GEOM_ID = ?", (building_id,))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        print(f"Error deleting building {building_id}: {e}")
        return False
    finally:
        conn.close()

def update_legal_ownership(property_id, own_type, own_entity, doc_exist, consent, encumbrances):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_LEGAL_OWNERSHIP
            SET OWN_TYPE = ?, OWN_ENTITY = ?, LEG_DOC_EXIST = ?, OWN_CONSENT = ?, ENCUMBRANCES = ?
            WHERE FK_PROPERTY_ID = ?
        """, (own_type, own_entity, int(doc_exist), int(consent), encumbrances, property_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def update_property_address(property_id, line1, line2, city, postcode, 
                            country=None, addr_type='UNKNOWN'):
    """
    Updates address text fields for a given property.
    addr_type defaults to UNKNOWN if not provided.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_ADDRESS
            SET ADDR_LINE1 = ?, ADDR_LINE2 = ?, CITY = ?, POSTCODE = ?, 
            COUNTRY = ?, ADDR_TYPE  = ?
            WHERE FK_PROPERTY_ID = ?
        """, (line1, line2, city, postcode, country, addr_type, property_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def get_address_geometry(geom_id):
    """
    Returns latitude and longitude from TBL_CORE_GEOMETRY WKT.
    Assumes POINT(longitude latitude) format.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT GEOM_WKT FROM TBL_CORE_GEOMETRY WHERE GEOM_ID = ?", (geom_id,))
        row = c.fetchone()
        if row and row[0]:
            wkt = row[0]
            # Simple POINT extraction
            import re
            match = re.search(r"POINT\(([-\d\.]+) ([-\d\.]+)\)", wkt)
            if match:
                return {
                    "longitude": float(match.group(1)),
                    "latitude": float(match.group(2))
                }
        return None
    finally:
        conn.close()

def update_address_geometry(addr_geom_id, latitude, longitude, resolved_address, updated_by='SYSTEM'):
    """
    Updates the geometry WKT and marks ADDR_GEOM_CREATED as 1.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        wkt = f"POINT({longitude} {latitude})"
        now = datetime.now().isoformat()
        
        # 1. Update Geometry Table
        c.execute("""
            UPDATE TBL_CORE_GEOMETRY
            SET GEOM_TYPE      = 'POINT',
                GEOM_WKT       = ?, 
                UPDATED_AT     = ?, 
                SOURCE         = 'Geocoding', 
                CAPTURE_METHOD = 'API'
            WHERE GEOM_ID = ?
        """, (wkt, now, addr_geom_id))
        
        # 2. Update Address Table flag
        c.execute("""
            UPDATE TBL_CORE_ADDRESS
            SET ADDR_GEOM_CREATED = 1
            WHERE ID_ADDR_GEOM = ?
        """, (addr_geom_id,))

        # 3. Cascading Reset: Building Footprints
        # Find the property associated with this address geometry
        c.execute("""
            SELECT FK_PROPERTY_ID FROM TBL_CORE_ADDRESS WHERE ID_ADDR_GEOM = ?
        """, (addr_geom_id,))
        prop_row = c.fetchone()
        if prop_row:
            prop_id = prop_row[0]
            # Reset validation status for all buildings on this property
            c.execute("""
                UPDATE TBL_CORE_BUILDING
                SET GEOM_BLD_CREATED = 0
                WHERE FK_PROPERTY_ID = ?
            """, (prop_id,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating geometry: {e}")
        return False
    finally:
        conn.close()
    
def reset_address_geometry(addr_geom_id, updated_by='SYSTEM'):
    """
    Clears geometry WKT and resets ADDR_GEOM_CREATED flag to 0.
    Called when user rejects a geocoded location.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        now = datetime.now().isoformat()

        # 1. Clear geometry record back to placeholder state
        c.execute("""
            UPDATE TBL_CORE_GEOMETRY
            SET GEOM_WKT = NULL, SOURCE = NULL, CAPTURE_METHOD = NULL,
                UPDATED_AT = ?, CREATED_BY = ?
            WHERE GEOM_ID = ?
        """, (now, updated_by, addr_geom_id))

        # 2. Reset address flag
        c.execute("""
            UPDATE TBL_CORE_ADDRESS
            SET ADDR_GEOM_CREATED = 0
            WHERE ID_ADDR_GEOM = ?
        """, (addr_geom_id,))

        conn.commit()
        return True
    except Exception as e:
        print(f"Error resetting geometry: {e}")
        return False
    finally:
        conn.close()

def update_landplot(property_id, size, category, intended_use):
    """
    Updates land plot characteristics for a given property.
    Factual use and other Stage 2 fields are not updated here.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_LANDPLOT
            SET LAND_SIZE         = ?,
                LAND_CATEGORY     = ?,
                LAND_INTENDED_USE = ?
            WHERE FK_PROPERTY_ID = ?
        """, (size, category, intended_use, property_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating landplot: {e}")
        return False
    finally:
        conn.close()

def update_governance(property_id, commission_dec, decision_date, disclosure):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_GOVERNANCE
            SET GOV_COMMISSION_DEC = ?, GOV_DECISION_DATE = ?, GOV_DISCLOSURE = ?
            WHERE FK_PROPERTY_ID = ?
        """, (commission_dec, decision_date, int(disclosure), property_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()

def update_building_geom_flag(bld_geom_id, is_accepted):
    """
    Updates the GEOM_BLD_CREATED flag on the building record.
    - 1: outline accepted (OSM or field captured)
    - 0: outline rejected or not found — geometry record remains empty
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_BUILDING
            SET GEOM_BLD_CREATED = ?
            WHERE ID_BUILDING_GEOM = ?
        """, (int(is_accepted), bld_geom_id))  # ← was is_complex
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating building geom flag: {e}")
        return False
    finally:
        conn.close()

def update_building_geometry(bld_geom_id, geometry, updated_by='SYSTEM'):
    """
    Updates the building footprint geometry in TBL_CORE_GEOMETRY.
    Accepts either a WKT string or a shapely geometry object.
    GEOM_TYPE is always POLYGON for building footprints.
    """
    if not bld_geom_id:
        return False
        
    wkt = None
    if isinstance(geometry, str):
        wkt = geometry
    elif hasattr(geometry, 'wkt'):
        wkt = geometry.wkt
        
    if not wkt:
        return False

    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_GEOMETRY 
            SET GEOM_WKT = ?, UPDATED_AT = ?, CREATED_BY = ?
            WHERE GEOM_ID = ?
        """, (wkt, datetime.now().isoformat(), updated_by, bld_geom_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating building geometry: {e}")
        return False
    finally:
        conn.close()

def update_building_entr_flag(bld_id, is_accepted):
    """
    Updates the GEOM_ENTR_CREATED flag on the building record.
    - 1: entrance pin accepted
    - 0: entrance pin rejected or not set
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE TBL_CORE_BUILDING 
            SET GEOM_ENTR_CREATED = ? 
            WHERE SYS_BLD_ID = ?
        """, (1 if is_accepted else 0, bld_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating building entrance flag: {e}")
        return False
    finally:
        conn.close()

def update_building_entrance_geometry(bld_id, latitude, longitude, updated_by='SYSTEM'):
    """
    Updates the building entrance point geometry in TBL_CORE_GEOMETRY.
    Uses SYS_BLD_ID as the GEOM_ID (Implicit ID).
    Uses REPLACE INTO to handle cases where the placeholder might be missing.
    """
    wkt = f"POINT({longitude} {latitude})"
    now = datetime.now().isoformat()
    
    conn = get_connection()
    c = conn.cursor()
    try:
        # Check if it exists to preserve CREATED_AT if possible, or just REPLACE
        # For simplicity and standardisation, we use REPLACE INTO for this specific implicit-ID case
        c.execute("""
            INSERT INTO TBL_CORE_GEOMETRY (GEOM_ID, GEOM_TYPE, GEOM_WKT, UPDATED_AT, CREATED_BY, CREATED_AT)
            VALUES (?, 'POINT', ?, ?, ?, ?)
            ON CONFLICT(GEOM_ID) DO UPDATE SET
                GEOM_WKT = excluded.GEOM_WKT,
                UPDATED_AT = excluded.UPDATED_AT,
                CREATED_BY = excluded.CREATED_BY
        """, (bld_id, wkt, now, updated_by, now))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating building entrance geometry: {e}")
        return False
    finally:
        conn.close()

def get_geometry_data(geom_id):
    """
    Retrieves the GEOM_TYPE and GEOM_WKT for a given geometry ID.
    Returns a dictionary or None.
    """
    if not geom_id:
        return None
        
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT GEOM_TYPE, GEOM_WKT 
            FROM TBL_CORE_GEOMETRY 
            WHERE GEOM_ID = ?
        """, (geom_id,))
        row = c.fetchone()
        if row:
            return {"type": row[0], "wkt": row[1]}
        return None
    except Exception as e:
        print(f"Error fetching geometry data: {e}")
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully with UUID-based schema.")
