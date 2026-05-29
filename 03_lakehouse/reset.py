#!/usr/bin/env python3
"""
reset.py — 清空所有结果表（保留 Schema 和 Volume）

用法：
  python 03_lakehouse/reset.py
  python 03_lakehouse/reset.py --dry-run
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

DRY_RUN = "--dry-run" in sys.argv

try:
    import clickzetta
except ImportError:
    print("请先安装依赖: pip install clickzetta_zettapark_python python-dotenv")
    sys.exit(1)

from includes.configuration import SCHEMA_NAME, retail_schema

TABLES = [
    f"{retail_schema}.rfm_segments",
    f"{retail_schema}.cohort_retention",
    f"{retail_schema}.top_products",
    f"{retail_schema}.country_revenue",
    f"{retail_schema}.monthly_revenue",
]


def get_conn():
    required = ["CLICKZETTA_SERVICE", "CLICKZETTA_INSTANCE", "CLICKZETTA_WORKSPACE",
                "CLICKZETTA_USERNAME", "CLICKZETTA_PASSWORD", "CLICKZETTA_SCHEMA"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] .env 缺少必填项: {', '.join(missing)}")
        sys.exit(1)
    return clickzetta.connect(
        service=os.environ["CLICKZETTA_SERVICE"],
        instance=os.environ["CLICKZETTA_INSTANCE"],
        workspace=os.environ["CLICKZETTA_WORKSPACE"],
        username=os.environ["CLICKZETTA_USERNAME"],
        password=os.environ["CLICKZETTA_PASSWORD"],
        schema=SCHEMA_NAME,
        vcluster=os.environ.get("CLICKZETTA_VCLUSTER", "default_ap"),
    )


def main():
    if DRY_RUN:
        print("=== DRY RUN — 不会实际删除任何数据 ===\n")

    conn = get_conn()
    cur = conn.cursor()
    try:
        for table in TABLES:
            stmt = f"DROP TABLE IF EXISTS {table}"
            if DRY_RUN:
                print(f"  [DRY] {stmt}")
            else:
                try:
                    cur.execute(stmt)
                    print(f"  OK: {stmt}")
                except Exception as e:
                    print(f"  WARN: {e}")
    finally:
        cur.close()
        conn.close()

    if DRY_RUN:
        print("\n=== DRY RUN 完成 ===")
    else:
        print("\n清空完成。重新跑：python 03_lakehouse/e2e.py --skip-upload")


if __name__ == "__main__":
    main()
