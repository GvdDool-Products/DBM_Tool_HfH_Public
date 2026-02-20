"""
enum_definitions.py — Authoritative seed data for the IDP Housing Database Enums.

This file contains the master list of enums used to populate TBL_ENUM and TBL_ENUM_I18N.
Separating this from db_core.py improves maintainability and prepares the system for 
expanded translations (i18n).

Format: (ENUM_GROUP, ENUM_CODE, SORT_ORDER, ENUM_LABEL, ENUM_DESCRIPTION)
"""

_ENUM_SEED = [
    # ROLE
    ("ROLE", "ADMIN",       1, "Administrator", "Full access to the system"),
    ("ROLE", "SURVEYOR",    2, "Surveyor",       "Field data collection"),
    ("ROLE", "INSPECTOR",   3, "Inspector",      "Building inspections"),
    
    # BLD_TYPE
    ("BLD_TYPE", "RES",     1, "Residential",    "Housing building"),
    ("BLD_TYPE", "COM",     2, "Commercial",     "Shops, offices"),
    ("BLD_TYPE", "IND",     3, "Industrial",     "Factory / warehouse"),
    
    # BLD_STRUCT_COND
    ("BLD_STRUCT_COND", "GOOD", 1, "Good",       "No structural issues"),
    ("BLD_STRUCT_COND", "FAIR", 2, "Fair",       "Minor damage, requires monitoring"),
    ("BLD_STRUCT_COND", "POOR", 3, "Poor",       "Major damage, unsafe"),
    
    # BLD_LOAD_STATUS
    ("BLD_LOAD_STATUS", "OK",       1, "OK",       "Load-bearing capacity normal"),
    ("BLD_LOAD_STATUS", "CRITICAL", 2, "Critical", "Structural risk present"),
    
    # SAFE_HAZARD_ZONE
    ("SAFE_HAZARD_ZONE", "NONE",          1, "No Hazard",      "No known hazard"),
    ("SAFE_HAZARD_ZONE", "ARMED_CONFLICT",2, "Armed Conflict", "Active war zone"),
    ("SAFE_HAZARD_ZONE", "FLOOD",         3, "Flood",          "Flood-prone area"),
    ("SAFE_HAZARD_ZONE", "LANDSLIDE",     4, "Landslide",      "Landslide-prone area"),
    ("SAFE_HAZARD_ZONE", "EARTHQUAKE",    5, "Earthquake",     "Seismic risk zone"),
    ("SAFE_HAZARD_ZONE", "ROCKFALL",      6, "Rockfall",       "Rockfall hazard area"),
    
    # OCC_CURRENT_USE
    ("OCC_CURRENT_USE", "RES",      1, "Residential", "Currently used for housing"),
    ("OCC_CURRENT_USE", "SCHOOL",   2, "School",      "Educational use"),
    ("OCC_CURRENT_USE", "HOSPITAL", 3, "Hospital",    "Healthcare facility"),
    
    # ALLOC_VULNERABILITY
    ("ALLOC_VULNERABILITY", "ELDERLY",  1, "Elderly",  "Vulnerable population: elderly"),
    ("ALLOC_VULNERABILITY", "CHILD",    2, "Child",    "Vulnerable population: children"),
    ("ALLOC_VULNERABILITY", "DISABLED", 3, "Disabled", "Vulnerable population: mobility impaired"),
    
    # SYSTEM_TYPE
    ("SYSTEM_TYPE", "MONITORING",  1, "Monitoring",  "Data collection & assessment system"),
    ("SYSTEM_TYPE", "ALLOCATION",  2, "Allocation",  "Allocation management system"),
    ("SYSTEM_TYPE", "GOVERNANCE",  3, "Governance",  "Policy / decision support system"),
    ("SYSTEM_TYPE", "FINANCIAL",   4, "Financial",   "Budget / payments system"),
    
    # SYNC_METHOD
    ("SYNC_METHOD", "API",         1, "API",         "Automated API integration"),
    ("SYNC_METHOD", "FILE_IMPORT", 2, "File Import", "Manual import of data files"),
    ("SYNC_METHOD", "MANUAL",      3, "Manual",      "Manual entry or processing"),
    ("SYNC_METHOD", "WEBHOOK",     4, "Webhook",     "Event-driven integration"),
]
