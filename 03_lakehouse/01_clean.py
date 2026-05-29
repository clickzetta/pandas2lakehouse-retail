"""
01_clean.py — 数据清洗（ZettaPark 版）

pandas → ZettaPark 对照：
  pd.read_csv(path)                    → session.read.csv("vol://...")
  df[~df.col.str.startswith("C")]      → df.filter(~F.col("Invoice").startswith("C"))
  df.dropna(subset=["Customer ID"])    → df.filter(F.col("Customer ID").is_not_null())
  df[df.Quantity > 0]                  → df.filter(F.col("Quantity") > 0)
  df.assign(Revenue=...)               → df.with_column("Revenue", ...)
  df["Customer ID"].astype(int)        → F.cast(F.col("Customer ID"), IntegerType())
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from clickzetta.zettapark import functions as F
from clickzetta.zettapark.types import IntegerType
from includes.configuration import SCHEMA_NAME, VOLUME_PATH, retail_schema
from includes.helpers import get_session, load_clean


if __name__ == "__main__":
    session = get_session()
    try:
        df = load_clean(session)
        print(f"清洗后行数: {df.count():,}")
        df.show(3)
    finally:
        session.close()
