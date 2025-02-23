"""Set the schema and prefix by getting the schema from the environment"""

import os

schema = os.getenv("DB_SCHEMA", "").strip()
schema_prefix = f"{schema}." if schema else ""
