import sqlite3
import uuid
import json
from datetime import datetime
import os

# Authoritative list of available auxiliary datasets
AVAILABLE_DATASETS = [
    {
        "id": "worldbank_uk_adm1",
        "name": "World Bank - Ukraine ADM1 (Oblasts)",
        "source": "World Bank",
        "type": "Administrative Boundaries",
        "description": "Level 1 administrative boundaries for Ukraine."
    },
    {
        "id": "worldbank_uk_adm2",
        "name": "World Bank - Ukraine ADM2 (Raions)",
        "source": "World Bank",
        "type": "Administrative Boundaries",
        "description": "Level 2 administrative boundaries for Ukraine."
    }
]

class AuxiliaryDataImporter:
    def __init__(self, db_connection_factory):
        self.get_connection = db_connection_factory
        self.table_name = "TBL_REF_ADMIN_BOUNDARIES"

    def ensure_table_exists(self):
        """Creates the auxiliary table if it doesn't already exist."""
        conn = self.get_connection()
        c = conn.cursor()
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                SYS_ADMIN_ID TEXT PRIMARY KEY,
                DATASET_ID TEXT NOT NULL,
                ADMIN_LEVEL INTEGER,
                ADMIN_NAME TEXT,
                ADMIN_CODE TEXT,
                GEOM_WKT TEXT,
                PROPERTIES_JSON TEXT,
                CREATED_AT TEXT
            )
        ''')
        # Index for faster dataset identification
        c.execute(f"CREATE INDEX IF NOT EXISTS idx_dataset_id ON {self.table_name} (DATASET_ID)")
        conn.commit()
        conn.close()

    def get_available_datasets(self):
        """Returns the list of datasets supported by this importer."""
        return AVAILABLE_DATASETS

    def is_dataset_loaded(self, dataset_id):
        """Checks if a specific dataset has already been loaded into the database."""
        self.ensure_table_exists()
        conn = self.get_connection()
        c = conn.cursor()
        c.execute(f"SELECT COUNT(*) FROM {self.table_name} WHERE DATASET_ID = ?", (dataset_id,))
        count = c.fetchone()[0]
        conn.close()
        return count > 0

    def ingest_dataset(self, dataset_id, overwrite=False):
        """
        Loads the selected dataset into the database.
        In this initial version, we simulate the data load or look for local files.
        For now, we'll provide a placeholder logic that can be expanded with GeoJSON parsers.
        """
        self.ensure_table_exists()
        
        if self.is_dataset_loaded(dataset_id) and not overwrite:
            return False, f"Dataset '{dataset_id}' is already loaded. Use overwrite=True."

        conn = self.get_connection()
        c = conn.cursor()

        try:
            if overwrite:
                c.execute(f"DELETE FROM {self.table_name} WHERE DATASET_ID = ?", (dataset_id,))

            # Simulation of data ingestion
            # In a real scenario, this would load a GeoJSON/Shapefile
            # and iterate through features.
            
            sample_data = self._get_sample_data(dataset_id)
            
            created_at = datetime.now().isoformat()
            for feature in sample_data:
                sys_id = str(uuid.uuid4())
                c.execute(f'''
                    INSERT INTO {self.table_name} 
                    (SYS_ADMIN_ID, DATASET_ID, ADMIN_LEVEL, ADMIN_NAME, ADMIN_CODE, GEOM_WKT, PROPERTIES_JSON, CREATED_AT)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sys_id,
                    dataset_id,
                    feature['level'],
                    feature['name'],
                    feature['code'],
                    feature['wkt'],
                    json.dumps(feature['properties']),
                    created_at
                ))

            conn.commit()
            return True, f"Successfully ingested {len(sample_data)} records for {dataset_id}."
        except Exception as e:
            conn.rollback()
            return False, f"Ingestion failed: {str(e)}"
        finally:
            conn.close()

    def _get_sample_data(self, dataset_id):
        """
        Mock data for demonstration. 
        In production, this would read from external sources or uploaded files.
        """
        if "adm1" in dataset_id:
            return [
                {
                    "level": 1,
                    "name": "Kyiv City",
                    "code": "UA-30",
                    "wkt": "POLYGON((30.4 50.4, 30.6 50.4, 30.6 50.6, 30.4 50.6, 30.4 50.4))",
                    "properties": {"population": 2800000}
                },
                {
                    "level": 1,
                    "name": "Lviv Oblast",
                    "code": "UA-46",
                    "wkt": "POLYGON((23.0 49.5, 25.0 49.5, 25.0 50.5, 23.0 50.5, 23.0 49.5))",
                    "properties": {"population": 2500000}
                }
            ]
        elif "adm2" in dataset_id:
             return [
                {
                    "level": 2,
                    "name": "Kyiv Raion",
                    "code": "UA-30-01",
                    "wkt": "POLYGON((30.45 50.45, 30.55 50.45, 30.55 50.55, 30.45 50.55, 30.45 50.45))",
                    "properties": {"parent": "Kyiv City"}
                }
            ]
        return []