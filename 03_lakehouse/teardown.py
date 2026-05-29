#!/usr/bin/env python3
"""
teardown.py — 完整清理：删除 Schema 和 Volume

用法：
  python 03_lakehouse/teardown.py
  python 03_lakehouse/teardown.py --dry-run
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN = "--dry-run" in sys.argv

try:
    from clickzetta.zettapark.session import Session
except ImportError:
    print("请先安装依赖: pip install clickzetta_zettapark_python python-dotenv")
    sys.exit(1)

from includes.configuration import SCHEMA_NAME, VOLUME_NAME, retail_schema


def execute(session, stmt, label=""):
    if DRY_RUN:
        print(f"  [DRY] {stmt}")
        return
    try:
        session.sql(stmt).collect()
        print(f"  OK: {label or stmt[:80]}")
    except Exception as e:
        print(f"  WARN [{label}]: {e}")


def main():
    if DRY_RUN:
        print("=== DRY RUN — 不会实际删除任何对象 ===\n")

    session = Session.builder.configs({
        "username":  os.environ["CLICKZETTA_USERNAME"],
        "password":  os.environ["CLICKZETTA_PASSWORD"],
        "service":   os.environ["CLICKZETTA_SERVICE"],
        "instance":  os.environ["CLICKZETTA_INSTANCE"],
        "workspace": os.environ["CLICKZETTA_WORKSPACE"],
        "schema":    SCHEMA_NAME,
        "vcluster":  os.environ.get("CLICKZETTA_VCLUSTER", "default_ap"),
    }).create()

    try:
        print(f"删除 Volume {SCHEMA_NAME}.{VOLUME_NAME} ...")
        execute(session, f"DROP VOLUME IF EXISTS {SCHEMA_NAME}.{VOLUME_NAME}",
                f"{SCHEMA_NAME}.{VOLUME_NAME}")

        print(f"删除 Schema {retail_schema} (CASCADE) ...")
        execute(session, f"DROP SCHEMA IF EXISTS {retail_schema} CASCADE", retail_schema)
    finally:
        session.close()

    if DRY_RUN:
        print("\n=== DRY RUN 完成 ===")
    else:
        print("\n完整清理完成。重新初始化：python 03_lakehouse/setup.py")


if __name__ == "__main__":
    main()
