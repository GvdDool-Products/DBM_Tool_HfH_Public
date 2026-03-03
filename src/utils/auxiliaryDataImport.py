# src/utils/auxiliaryDataImport.py

import sqlite3
import uuid
import json
import zipfile
import tempfile
import os
from datetime import datetime, timezone
from io import BytesIO

# ---------------------------------------------------------------------------
# Authoritative list of available auxiliary datasets
# "admin_level": 0 = Country
# "admin_level": 1 = State/Province
# "admin_level": 2 = County/District
# "admin_level": 3 = City/Town
# ---------------------------------------------------------------------------
AVAILABLE_DATASETS = [
    {
        "id": "hdx_ukr_adm1",
        "name": "HDX COD-AB - Ukraine ADM1 (Oblasts)",
        "source": "HDX/OCHA",
        "source_org": "OCHA",
        "type": "Administrative Boundaries",
        "admin_level": 1,
        "country_code": "UA",
        "description": "Level 1 administrative boundaries for Ukraine (27 Oblasts). Source: State Scientific Production Enterprise Kartographia, April 2024.",
        "url": "https://data.humdata.org/dataset/1b604491-04f9-4d1e-bb10-781a8b3f05a3/resource/628889fd-2e32-4659-a342-5053ae4e342a/download/ukr_admbnd_sspe_20240416_em_gdb.gdb.zip",
        "layer": "ukr_admbnda_adm1_sspe_20240416_em",
        "valid_on": "2024-04-16"
    },
    {
        "id": "hdx_ukr_adm2",
        "name": "HDX COD-AB - Ukraine ADM2 (Raions)",
        "source": "HDX/OCHA",
        "source_org": "OCHA",
        "type": "Administrative Boundaries",
        "admin_level": 2,
        "country_code": "UA",
        "description": "Level 2 administrative boundaries for Ukraine (139 Raions). Source: State Scientific Production Enterprise Kartographia, April 2024.",
        "url": "https://data.humdata.org/dataset/1b604491-04f9-4d1e-bb10-781a8b3f05a3/resource/628889fd-2e32-4659-a342-5053ae4e342a/download/ukr_admbnd_sspe_20240416_em_gdb.gdb.zip",
        "layer": "ukr_admbnda_adm2_sspe_20240416_em",
        "valid_on": "2024-04-16"
    },
    {
        "id": "hdx_ukr_adm3",
        "name": "HDX COD-AB - Ukraine ADM3 (Hromadas)",
        "source": "HDX/OCHA",
        "source_org": "OCHA",
        "type": "Administrative Boundaries",
        "admin_level": 3,
        "country_code": "UA",
        "description": "Level 3 administrative boundaries for Ukraine (1769 Hromadas). Source: State Scientific Production Enterprise Kartographia, April 2024.",
        "url": "https://data.humdata.org/dataset/1b604491-04f9-4d1e-bb10-781a8b3f05a3/resource/628889fd-2e32-4659-a342-5053ae4e342a/download/ukr_admbnd_sspe_20240416_em_gdb.gdb.zip",
        "layer": "ukr_admbnda_adm3_sspe_20240416_em",
        "valid_on": "2024-04-16"
    },
]


# ---------------------------------------------------------------------------
# Helper: download GDB zip and extract to a temp directory
# ---------------------------------------------------------------------------
def _download_and_extract_gdb(url: str) -> str:
    """Downloads a zipped GDB and extracts it to a temp directory. Returns the GDB path."""
    import requests
    response = requests.get(url, timeout=120)
    response.raise_for_status()

    tmp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(BytesIO(response.content)) as z:
        z.extractall(tmp_dir)

    for entry in os.listdir(tmp_dir):
        if entry.endswith(".gdb"):
            return os.path.join(tmp_dir, entry)

    raise FileNotFoundError("No .gdb folder found in zip archive.")


# ---------------------------------------------------------------------------
# Main importer class
# ---------------------------------------------------------------------------
class AuxiliaryDataImporter:

    BOUNDARIES_TABLE = "TBL_REF_ADMIN_BOUNDARIES"
    METADATA_TABLE   = "TBL_REF_DATASET_METADATA"

    def __init__(self, db_connection_factory):
        self.get_connection = db_connection_factory

    # ------------------------------------------------------------------
    # Table creation
    # ------------------------------------------------------------------
    def ensure_tables_exist(self):
        """Creates TBL_REF_ADMIN_BOUNDARIES and TBL_REF_DATASET_METADATA if they don't exist."""
        conn = self.get_connection()
        c = conn.cursor()

        # Reference dataset metadata — one row per dataset load
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.METADATA_TABLE} (
                DATASET_ID       TEXT PRIMARY KEY,  -- matches id in AVAILABLE_DATASETS
                DATASET_NAME     TEXT NOT NULL,
                SOURCE_URL       TEXT,
                SOURCE_ORG       TEXT,
                DESCRIPTION      TEXT,
                COUNTRY_CODE     TEXT,
                VALID_ON         TEXT,              -- date from the dataset itself
                LOADED_AT        TEXT,              -- UTC ISO timestamp
                LOADED_BY        TEXT,              -- FK to TBL_SYS_USERS (nullable)
                RECORD_COUNT     INTEGER,
                PROPERTIES_JSON  TEXT,              -- schema/column list describing JSON_DATA fields
                NOTES            TEXT
            )
        ''')

        # Reference boundary features — one row per administrative unit
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.BOUNDARIES_TABLE} (
                SYS_ADMIN_ID  TEXT PRIMARY KEY,
                DATASET_ID    TEXT NOT NULL,        -- FK to TBL_REF_DATASET_METADATA
                ADMIN_LEVEL   INTEGER,              -- 1=oblast, 2=raion, 3=hromada
                ADMIN_NAME    TEXT,                 -- English name (ADM1_EN / ADM2_EN etc.)
                ADMIN_CODE    TEXT,                 -- P-code (UA80, UA8036 etc.)
                GEOM_WKT      TEXT,                 -- geometry in WKT format
                CRS_EPSG      INTEGER DEFAULT 4326, -- coordinate reference system
                JSON_DATA     TEXT,                 -- per-feature attribute values
                FOREIGN KEY (DATASET_ID) REFERENCES {self.METADATA_TABLE} (DATASET_ID)
            )
        ''')

        c.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_ref_admin_dataset_id
            ON {self.BOUNDARIES_TABLE} (DATASET_ID)
        ''')
        c.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_ref_admin_level
            ON {self.BOUNDARIES_TABLE} (ADMIN_LEVEL)
        ''')
        c.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_ref_admin_code
            ON {self.BOUNDARIES_TABLE} (ADMIN_CODE)
        ''')

        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_available_datasets(self):
        """Returns the list of datasets supported by this importer."""
        return AVAILABLE_DATASETS

    def is_dataset_loaded(self, dataset_id: str) -> bool:
        """Checks if a dataset has already been loaded into the database."""
        self.ensure_tables_exist()
        conn = self.get_connection()
        c = conn.cursor()
        c.execute(
            f"SELECT COUNT(*) FROM {self.METADATA_TABLE} WHERE DATASET_ID = ?",
            (dataset_id,)
        )
        count = c.fetchone()[0]
        conn.close()
        return count > 0

    def get_loaded_datasets(self):
        """Returns metadata rows for all datasets currently in the database."""
        self.ensure_tables_exist()
        conn = self.get_connection()
        import pandas as pd
        df = pd.read_sql(
            f"SELECT * FROM {self.METADATA_TABLE} ORDER BY LOADED_AT DESC", conn
        )
        conn.close()
        return df

    def ingest_dataset(self, dataset_id: str, overwrite: bool = False, loaded_by: str = None):
        """Dispatcher — routes to the correct ingestion method based on dataset type."""
        self.ensure_tables_exist()

        config = next((d for d in AVAILABLE_DATASETS if d["id"] == dataset_id), None)
        if not config:
            return False, f"Unknown dataset id: '{dataset_id}'"

        if self.is_dataset_loaded(dataset_id) and not overwrite:
            return False, f"Dataset '{dataset_id}' already loaded. Pass overwrite=True to reload."

        match config["type"]:
            # From the list of available datasets
            case "Administrative Boundaries":
                return self._ingest_admin_boundaries(config, overwrite, loaded_by)
            case "Population":
                return self._ingest_population(config, overwrite, loaded_by)
            case _:
                return False, f"No ingestion method implemented for type: '{config['type']}'"

    # ------------------------------------------------------------------
    # Private ingestion methods
    # The following methods are dataset dependent, so we need to implement a method for each dataset
    # Currently available:
    # - Administrative Boundaries: functional, and used for point-in-polygon lookups
    # - Population: as placeholder, not implemented yet
    # ------------------------------------------------------------------
    def _ingest_admin_boundaries(self, config: dict, overwrite: bool, loaded_by: str):
        """Handles GDB-based administrative boundary datasets from HDX."""
        import geopandas as gpd
        conn = self.get_connection()
        c = conn.cursor()

        try:
            # Clean up existing records if overwriting
            if overwrite:
                c.execute(f"DELETE FROM {self.BOUNDARIES_TABLE} WHERE DATASET_ID = ?", (config["id"],))
                c.execute(f"DELETE FROM {self.METADATA_TABLE}   WHERE DATASET_ID = ?", (config["id"],))

            # Download and extract GDB
            print(f"Downloading {config['name']}...")
            gdb_path = _download_and_extract_gdb(config["url"])

            # Read the specific admin level layer
            print(f"Reading layer: {config['layer']}")
            gdf = gpd.read_file(gdb_path, layer=config["layer"])
            gdf = gdf.to_crs(epsg=4326)

            record_count = len(gdf)
            loaded_at    = datetime.now(timezone.utc).isoformat()
            admin_level  = config["admin_level"]
            level_str    = f"ADM{admin_level}"

            # Columns stored explicitly — exclude from JSON_DATA
            core_cols = {
                "geometry",
                f"{level_str}_EN",
                f"{level_str}_PCODE",
                "Shape_Length",
                "Shape_Area"
            }

            # PROPERTIES_JSON on metadata: schema describing what's in JSON_DATA
            json_data_keys = [col for col in gdf.columns if col not in core_cols]
            properties_schema = json.dumps(json_data_keys)

            # Write metadata row
            c.execute(f'''
                INSERT INTO {self.METADATA_TABLE}
                (DATASET_ID, DATASET_NAME, SOURCE_URL, SOURCE_ORG, DESCRIPTION,
                 COUNTRY_CODE, VALID_ON, LOADED_AT, LOADED_BY, RECORD_COUNT,
                 PROPERTIES_JSON, NOTES)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                config["id"],
                config["name"],
                config["url"],
                config["source_org"],
                config["description"],
                config["country_code"],
                config["valid_on"],
                loaded_at,
                loaded_by,
                record_count,
                properties_schema,
                None
            ))

            # Write one boundary row per feature
            print(f"Inserting {record_count} features...")
            for _, row in gdf.iterrows():
                sys_id     = str(uuid.uuid4())
                admin_name = row.get(f"{level_str}_EN")
                admin_code = row.get(f"{level_str}_PCODE")
                geom_wkt   = row.geometry.wkt

                # Per-feature attribute values (everything except core cols)
                json_data = {
                    col: str(row[col])
                    for col in gdf.columns
                    if col not in core_cols and row[col] is not None
                }

                c.execute(f'''
                    INSERT INTO {self.BOUNDARIES_TABLE}
                    (SYS_ADMIN_ID, DATASET_ID, ADMIN_LEVEL, ADMIN_NAME, ADMIN_CODE,
                     GEOM_WKT, CRS_EPSG, JSON_DATA)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sys_id,
                    config["id"],
                    admin_level,
                    admin_name,
                    admin_code,
                    geom_wkt,
                    4326,
                    json.dumps(json_data)
                ))

            conn.commit()
            return True, f"Successfully ingested {record_count} records for '{config['id']}'."

        except Exception as e:
            conn.rollback()
            return False, f"Ingestion failed: {str(e)}"
        finally:
            conn.close()

    def _ingest_population(self, config: dict, overwrite: bool, loaded_by: str):
        """Handles population datasets — to be implemented."""
        raise NotImplementedError("Population ingestion not yet implemented.")


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
# Reverse Geocoding
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

geolocator = Nominatim(user_agent="habitat_ukraine_refit")

def geocode_address(a_dict):
    """
    Attempts to geocode an address from TBL_CORE_ADDRESS data.
    Tries full address string first, falls back to structured components.
    
    Args:
        a_dict: address dictionary from get_property_address()
    
    Returns:
        dict with 'latitude', 'longitude', 'resolved_address' or None if failed
    """
    
    # 1. Try full address string
    full_address = ", ".join(filter(None, [
        a_dict.get('ADDR_LINE1'),
        a_dict.get('ADDR_LINE2'),
        a_dict.get('CITY'),
        a_dict.get('POSTCODE'),
        a_dict.get('ADMIN_UNIT'),
        a_dict.get('COUNTRY'),
    ]))

    if full_address:
        try:
            location = geolocator.geocode(full_address, timeout=10)
            if location:
                return {
                    "latitude":         location.latitude,
                    "longitude":        location.longitude,
                    "resolved_address": location.address
                }
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Full address geocoding failed: {e}")

    # 2. Fallback to structured components only
    structured = ", ".join(filter(None, [
        a_dict.get('ADDR_LINE1'),
        a_dict.get('CITY'),
        a_dict.get('COUNTRY'),
    ]))

    if structured:
        try:
            location = geolocator.geocode(structured, timeout=10)
            if location:
                return {
                    "latitude":         location.latitude,
                    "longitude":        location.longitude,
                    "resolved_address": location.address
                }
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"Structured geocoding failed: {e}")

    return None

# OpenStreetMap
import osmnx as ox
from shapely.geometry import Point

def fetch_osm_footprint(latitude, longitude):
    """
    Attempts to retrieve a building footprint from OpenStreetMap using osmnx.
    
    Assumes the input point is located within a physical building structure 
    mapped in OSM. The function queries a 50m radius and returns the geometry 
    of the specific polygon that spatially contains the provided coordinates.
    """
    try:
        # Fetch features tagged as 'building' within 50 meters of the point
        gdf = ox.features_from_point((latitude, longitude), tags={'building': True}, dist=50)
        
        if gdf.empty:
            return None
            
        # Define the search point (note: shapely uses x, y -> lon, lat)
        search_point = Point(longitude, latitude)
        
        # Filter the results for the building that contains the point
        containing_buildings = gdf[gdf.geometry.contains(search_point)]
        
        if not containing_buildings.empty:
            # Return the geometry of the first unambiguous match
            return containing_buildings.iloc[0].geometry
            
        return None
        
    except Exception:
        # Handles cases where no results are found or API request fails
        return None