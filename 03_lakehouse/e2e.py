#!/usr/bin/env python3
"""
e2e.py — 端到端验证

流程：上传数据 → 清洗 → RFM → 同期群 → 产品分析 → 断言检查

EXPECTED 值来自 01_pandas/ 在完整数据集（106 万行）上的实际输出。
sample 模式下只验证行数和结构，不验证具体数值。

用法：
  python 03_lakehouse/e2e.py                  # sample 模式（快速）
  python 03_lakehouse/e2e.py --full           # 完整数据集（需先上传）
  python 03_lakehouse/e2e.py --skip-upload    # 跳过上传
  python 03_lakehouse/e2e.py --reset          # 先清空再跑
"""

import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(line_buffering=True)

FULL_DATA   = "--full" in sys.argv
SKIP_UPLOAD = "--skip-upload" in sys.argv
DO_RESET    = "--reset" in sys.argv

try:
    from clickzetta.zettapark.session import Session
    from clickzetta.zettapark import functions as F
    from clickzetta.zettapark.window import Window
except ImportError:
    print("请先安装依赖: pip install clickzetta_zettapark_python python-dotenv")
    sys.exit(1)

from includes.configuration import SCHEMA_NAME, VOLUME_NAME, VOLUME_PATH, retail_schema
from includes.helpers import get_session, load_clean

REPO_ROOT = Path(__file__).parent.parent

# Ground truth from pandas on CSV dataset (1,067,371 rows)
EXPECTED_FULL = {
    "clean_rows":        805549,
    "customer_count":    5878,
    "country_top":       "United Kingdom",
    "monthly_rows":      25,        # 25 months of data (2009-12 to 2011-12)
}

passed = failed = 0


def check(label, actual, expected):
    global passed, failed
    if actual == expected:
        print(f"  ✓ {label}: {actual}")
        passed += 1
    else:
        print(f"  ✗ {label}: got {actual!r}, expected {expected!r}")
        failed += 1


def sql(session, stmt):
    return session.sql(stmt).collect()


def main():
    t_total = time.time()
    session = get_session()

    try:
        if DO_RESET:
            print("=== 清空结果表 ===")
            for t in ["rfm_segments", "cohort_retention", "top_products",
                      "country_revenue", "monthly_revenue"]:
                try:
                    sql(session, f"DROP TABLE IF EXISTS {retail_schema}.{t}")
                    print(f"  dropped {retail_schema}.{t}")
                except Exception:
                    pass

        if not SKIP_UPLOAD:
            print("\n=== 上传数据 ===")
            fname = "online_retail_II.csv" if FULL_DATA else "online_retail_sample.csv"
            src = REPO_ROOT / ("datasets" if FULL_DATA else "data/sample") / fname
            print(f"  上传 {fname}...", end=" ", flush=True)
            session.file.put(str(src), f"{VOLUME_PATH}/raw/", auto_compress=False, overwrite=True)
            print("完成")

        fname = "online_retail_II.csv" if FULL_DATA else "online_retail_sample.csv"

        print("\n=== 数据清洗 ===")
        t = time.time()
        df = load_clean(session, fname)
        clean_cnt = df.count()
        print(f"  清洗后行数: {clean_cnt:,}  ({time.time()-t:.1f}s)")

        print("\n=== RFM 分析 ===")
        t = time.time()
        snapshot = df.agg(F.max("InvoiceDate")).collect()[0][0]
        rfm = df.group_by("CustomerID").agg(
            F.datediff("day", F.max("InvoiceDate"), F.lit(snapshot)).alias("Recency"),
            F.count_distinct("Invoice").alias("Frequency"),
            F.round(F.sum("Revenue"), 2).alias("Monetary"),
        )
        w_r = Window.order_by(F.col("Recency").asc())
        w_f = Window.order_by(F.col("Frequency").asc())
        w_m = Window.order_by(F.col("Monetary").asc())
        rfm = rfm.with_column("R_score", F.lit(5) - F.ntile(4).over(w_r))
        rfm = rfm.with_column("F_score", F.ntile(4).over(w_f))
        rfm = rfm.with_column("M_score", F.ntile(4).over(w_m))
        rfm = rfm.with_column("Segment",
            F.when((F.col("R_score") >= 3) & (F.col("F_score") >= 3), F.lit("Champions"))
             .when(F.col("R_score") >= 3, F.lit("Recent Customers"))
             .when(F.col("F_score") >= 3, F.lit("At Risk"))
             .otherwise(F.lit("Lost"))
        )
        sql(session, f"CREATE SCHEMA IF NOT EXISTS {retail_schema}")
        rfm.write.save_as_table(f"{retail_schema}.rfm_segments", mode="overwrite")
        customer_cnt = rfm.count()
        seg_counts = {r[0]: r[1] for r in
                      rfm.group_by("Segment").agg(F.count("*").alias("n")).collect()}
        print(f"  客户数: {customer_cnt:,}  ({time.time()-t:.1f}s)")
        print(f"  分层: {seg_counts}")

        print("\n=== 产品分析 ===")
        t = time.time()
        top = (df.group_by("StockCode", "Description")
               .agg(F.round(F.sum("Revenue"), 2).alias("TotalRevenue"))
               .sort(F.col("TotalRevenue").desc()).limit(1).collect())
        top_code = top[0][0] if top else None

        country = (df.group_by("Country")
                   .agg(F.round(F.sum("Revenue"), 2).alias("Revenue"))
                   .sort(F.col("Revenue").desc()).limit(1).collect())
        top_country = country[0][0] if country else None

        monthly = (df.with_column("YearMonth",
                       F.date_format(F.col("InvoiceDate").cast("date"), "yyyy-MM"))
                   .group_by("YearMonth")
                   .agg(F.round(F.sum("Revenue"), 2).alias("Revenue"))
                   .sort("YearMonth"))
        monthly_cnt = monthly.count()
        print(f"  Top 产品: {top_code}  Top 国家: {top_country}  月份数: {monthly_cnt}  ({time.time()-t:.1f}s)")

        print("\n=== 断言检查 ===")
        if FULL_DATA:
            check("清洗后行数",   clean_cnt,    EXPECTED_FULL["clean_rows"])
            check("客户数",       customer_cnt, EXPECTED_FULL["customer_count"])
            check("分层总和=客户数", sum(seg_counts.values()), customer_cnt)
            check("Top 国家",     top_country,  EXPECTED_FULL["country_top"])
            check("月份数",       monthly_cnt,  EXPECTED_FULL["monthly_rows"])
        else:
            # sample 模式：只验证结构
            check("清洗后有数据",  clean_cnt > 0,    True)
            check("客户数 > 0",    customer_cnt > 0, True)
            check("有 Champions",  "Champions" in seg_counts, True)
            check("Top 国家非空",  top_country is not None, True)
            check("月份数 > 0",    monthly_cnt > 0, True)

    finally:
        session.close()

    total = passed + failed
    print(f"\n{'='*40}")
    print(f"验证结果：{passed}/{total} 通过  总耗时: {time.time()-t_total:.1f}s")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
