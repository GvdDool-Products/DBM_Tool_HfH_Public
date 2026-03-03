"""
enum_definitions.py — Authoritative seed data for the IDP Housing Database Enums.

This file contains the master list of enums used to populate TBL_ENUM and TBL_ENUM_I18N.
Separating this from db_core.py improves maintainability and prepares the system for 
expanded translations (i18n).

Format: (ENUM_GROUP, ENUM_CODE, SORT_ORDER, ENUM_LABEL, ENUM_DESCRIPTION, IS_ACTIVE)
"""

_ENUM_SEED = [
    # ROLE
    ("ROLE", "ADMIN", 1, "Administrator", "Full access to the system", 1),
    ("ROLE", "EXPERT", 2, "Expert", "Expert-level user with limited admin privileges", 1),
    ("ROLE", "SURVEYOR", 3, "Surveyor", "Field data collection", 1),
    ("ROLE", "INSPECTOR", 4, "Inspector", "Building inspections", 1),
    
    # BLD_TYPE
    ("BLD_TYPE", "UNKNOWN", 99, "Unknown", "Default enumeration for standardisation", 1),
    ("BLD_TYPE", "RES", 1, "Residential", "Housing building", 1),
    ("BLD_TYPE", "COM", 2, "Commercial", "Shops, offices", 1),
    ("BLD_TYPE", "IND", 3, "Industrial", "Factory / warehouse", 1),
    
    # BLD_STRUCT_COND
    ("BLD_STRUCT_COND", "UNKNOWN", 99, "Unknown", "Default enumeration for standardisation", 1),
    ("BLD_STRUCT_COND", "GOOD", 1, "Good", "No structural issues", 1),
    ("BLD_STRUCT_COND", "FAIR", 2, "Fair", "Minor damage, requires monitoring", 1),
    ("BLD_STRUCT_COND", "POOR", 3, "Poor", "Major damage, unsafe", 1),
    
    # BLD_LOAD_STATUS
    ("BLD_LOAD_STATUS", "UNKNOWN", 99, "Unknown", "Default enumeration for standardisation", 1),
    ("BLD_LOAD_STATUS", "OK", 1, "OK", "Load-bearing capacity normal", 1),
    ("BLD_LOAD_STATUS", "CRITICAL", 2, "Critical", "Structural risk present", 1),

    # ADDR_TYPE
    ("ADDR_TYPE", "UNKNOWN", 99, "Unknown", "Default enumeration for standardisation", 1),
    ("ADDR_TYPE", "PHYSICAL", 1, "Physical", "Actual on-ground location of the property", 1),
    ("ADDR_TYPE", "POSTAL", 2, "Postal", "Official mailing address", 1),
    ("ADDR_TYPE", "LEGAL", 3, "Legal", "Registered administrative address", 1),
    ("ADDR_TYPE", "CORRESPONDENCE", 4, "Correspondence", "Address for communications", 0),
    ("ADDR_TYPE", "TEMPORARY", 5, "Temporary", "Interim or displaced address", 0),
    ("ADDR_TYPE", "HISTORICAL", 6, "Historical", "Previous address, pre-renaming", 0),

    # OWN_TYPE
    ("OWN_TYPE", "UNKNOWN", 99, "Unknown", "Default enumeration for standardisation", 1),
    ("OWN_TYPE", "STATE", 1, "State", "State-owned property", 1),
    ("OWN_TYPE", "MUNICIPAL", 2, "Municipal", "Municipally owned property", 1),
    ("OWN_TYPE", "PRIVATE", 3, "Private", "Privately owned property", 1),
    ("OWN_TYPE", "COMMUNAL", 4, "Communal", "Communal ownership form", 1),
    ("OWN_TYPE", "MIXED", 5, "Mixed", "Mixed ownership", 1),

    # OWN_ENTITY
    ("OWN_ENTITY", "UNKNOWN", 99, "Unknown", "Default enumeration for standardisation", 1),
    ("OWN_ENTITY", "CENTRAL_GOV", 1, "Central Government", "Ministry or state body", 1),
    ("OWN_ENTITY", "LOCAL_GOV", 2, "Local Government", "Hromada or municipal authority", 1),
    ("OWN_ENTITY", "STATE_ENTERPRISE", 3, "State Enterprise", "State-owned company or utility", 1),
    ("OWN_ENTITY", "PRIVATE_PERSON", 4, "Private Person", "Individual private owner", 1),
    ("OWN_ENTITY", "PRIVATE_COMPANY", 5, "Private Company", "Privately owned legal entity", 1),
    ("OWN_ENTITY", "RELIGIOUS", 6, "Religious Organisation", "Church or religious body", 1),
    ("OWN_ENTITY", "NGO", 7, "NGO", "Non-governmental organisation", 1),

    # SAFE_HAZARD_ZONE
    ("SAFE_HAZARD_ZONE", "NONE",          1, "No Hazard",      "No known hazard", 1),
    ("SAFE_HAZARD_ZONE", "ARMED_CONFLICT",2, "Armed Conflict", "Active war zone", 1),
    ("SAFE_HAZARD_ZONE", "FLOOD",         3, "Flood",          "Flood-prone area", 1),
    ("SAFE_HAZARD_ZONE", "LANDSLIDE",     4, "Landslide",      "Landslide-prone area", 1),
    ("SAFE_HAZARD_ZONE", "EARTHQUAKE",    5, "Earthquake",     "Seismic risk zone", 1),
    ("SAFE_HAZARD_ZONE", "ROCKFALL",      6, "Rockfall",       "Rockfall hazard area", 1),
    
    # OCC_CURRENT_USE
    ("OCC_CURRENT_USE", "RES",      1, "Residential", "Currently used for housing", 1),
    ("OCC_CURRENT_USE", "SCHOOL",   2, "School",      "Educational use", 1),
    ("OCC_CURRENT_USE", "HOSPITAL", 3, "Hospital",    "Healthcare facility", 1),
    
    # ALLOC_VULNERABILITY
    ("ALLOC_VULNERABILITY", "ELDERLY",  1, "Elderly",  "Vulnerable population: elderly", 1),
    ("ALLOC_VULNERABILITY", "CHILD",    2, "Child",    "Vulnerable population: children", 1),
    ("ALLOC_VULNERABILITY", "DISABLED", 3, "Disabled", "Vulnerable population: mobility impaired", 1),
    
    # SYSTEM_TYPE
    ("SYSTEM_TYPE", "MONITORING",  1, "Monitoring",  "Data collection & assessment system", 1),
    ("SYSTEM_TYPE", "ALLOCATION",  2, "Allocation",  "Allocation management system", 1),
    ("SYSTEM_TYPE", "GOVERNANCE",  3, "Governance",  "Policy / decision support system", 1),
    ("SYSTEM_TYPE", "FINANCIAL",   4, "Financial",   "Budget / payments system", 1),
    
    # SYNC_METHOD
    ("SYNC_METHOD", "API",         1, "API",         "Automated API integration", 1),
    ("SYNC_METHOD", "FILE_IMPORT", 2, "File Import", "Manual import of data files", 1),
    ("SYNC_METHOD", "MANUAL",      3, "Manual",      "Manual entry or processing", 1),
    ("SYNC_METHOD", "WEBHOOK",     4, "Webhook",     "Event-driven integration", 1),
]
