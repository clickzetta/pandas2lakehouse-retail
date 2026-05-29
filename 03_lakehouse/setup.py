#!/usr/bin/env python3
"""
setup.py — 初始化 Lakehouse 环境

1. 创建 Schema（retail）
2. 创建 Volume（retail_vol）
3. 上传 CSV 数据到 Volume
4. 建结果表（空表，由各分析脚本写入）

用法：
  python 03_lakehouse/setup.py                  # 上传 sample（快速验证）
  python 03_lakehouse/setup.py --full           # 上传完整数据集
  python 03_lakehouse/setup.py --skip-upload    # 只建 Schema/Volume，不上传
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(line_buffering=True)

FULL_DATA   = "--full" in sys.argv
SKIP_UPLOAD = "--skip-upload" in sys.argv

try:
    from clickzetta.zettapark.session import Session
except ImportError:
    print("请先安装依赖: pip install clickzetta_zettapark_python python-dotenv")
    sys.exit(1)

from includes.configuration import SCHEMA_NAME, VOLUME_NAME, VOLUME_PATH, retail_schema

REPO_ROOT    = Path(__file__).parent.parent
SAMPLE_FILE  = REPO_ROOT / "data/sample/online_retail_sample.csv"
FULL_FILE    = REPO_ROOT / "datasets/online_retail_II.csv"


def get_session():
    required = ["CLICKZETTA_SERVICE", "CLICKZETTA_INSTANCE", "CLICKZETTA_WORKSPACE",
                "CLICKZETTA_USERNAME", "CLICKZETTA_PASSWORD", "CLICKZETTA_SCHEMA"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] .env 缺少必填项: {', '.join(missing)}")
        sys.exit(1)
    return Session.builder.configs({
        "username":  os.environ["CLICKZETTA_USERNAME"],
        "password":  os.environ["CLICKZETTA_PASSWORD"],
        "service":   os.environ["CLICKZETTA_SERVICE"],
        "instance":  os.environ["CLICKZETTA_INSTANCE"],
        "workspace": os.environ["CLICKZETTA_WORKSPACE"],
        "schema":    SCHEMA_NAME,
        "vcluster":  os.environ.get("CLICKZETTA_VCLUSTER", "default_ap"),
    }).create()


def run(session, stmt, label=""):
    try:
        session.sql(stmt).collect()
        if label:
            print(f"  OK: {label}")
    except Exception as e:
        print(f"  WARN [{label}]: {e}")


def main():
    session = get_session()
    try:
        print("=== 1. 创建 Schema ===")
        run(session, f"CREATE SCHEMA IF NOT EXISTS {retail_schema}", retail_schema)

        print("\n=== 2. 创建 Volume ===")
        run(session, f"CREATE VOLUME IF NOT EXISTS {SCHEMA_NAME}.{VOLUME_NAME}",
            f"{SCHEMA_NAME}.{VOLUME_NAME}")

        if not SKIP_UPLOAD:
            print("\n=== 3. 上传数据到 Volume ===")
            if FULL_DATA:
                if not FULL_FILE.exists():
                    print(f"  [ERROR] 完整数据集不存在: {FULL_FILE}")
                    print("  请先下载：https://archive.ics.uci.edu/dataset/502/online+retail+ii")
                    sys.exit(1)
                files = [FULL_FILE]
            else:
                files = [SAMPLE_FILE]

            for f in files:
                size_kb = f.stat().st_size // 1024
                print(f"  上传 {f.name} ({size_kb} KB)...", end=" ", flush=True)
                session.file.put(str(f), f"{VOLUME_PATH}/raw/", auto_compress=False, overwrite=True)
                print("完成")

    finally:
        session.close()

    print("\n初始化完成。接下来运行：python 03_lakehouse/e2e.py")


if __name__ == "__main__":
    main()
