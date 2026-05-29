import os

SCHEMA_NAME  = os.environ.get("CLICKZETTA_SCHEMA", "public")
VOLUME_NAME  = os.environ.get("CLICKZETTA_VOLUME", "retail_vol")
VOLUME_PATH  = f"vol://{SCHEMA_NAME}.{VOLUME_NAME}"

retail_schema = "retail"
