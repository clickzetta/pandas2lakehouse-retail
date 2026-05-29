"""
03_cohort.py — 同期群留存分析（ZettaPark 版）

按客户首次购买**周**分组，追踪后续各周的留存率。

pandas → ZettaPark 对照：
  df["InvoiceDate"].dt.to_period("W")  → F.date_trunc("week", F.col("InvoiceDate"))
  df.groupby().min()                   → df.group_by().agg(F.min(...))
  df.join(cohort_map, on=...)          → df.join(cohort_map, "CustomerID")
  (period_a - period_b).n             → F.datediff("week", cohort_week, invoice_week)
  df.groupby().nunique()               → df.group_by().agg(F.count_distinct(...))
  cohort_pivot.divide(cohort_size)     → FIRST_VALUE 窗口函数取 index=0 作分母
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from clickzetta.zettapark.session import Session
from clickzetta.zettapark import functions as F
from clickzetta.zettapark.window import Window
from includes.configuration import SCHEMA_NAME, retail_schema
from includes.helpers import get_session, load_clean


def compute_cohort(session, df):
    """
    周粒度同期群分析。

    ZettaPark DataFrame API 对列名大小写不敏感（统一转小写），
    含复杂 self-join 的场景改用 session.sql 更可靠。
    """
    # 把 DataFrame 注册为临时视图，再用 SQL 完成计算
    df.create_or_replace_temp_view("retail_clean")

    cohort_data = session.sql("""
        WITH with_week AS (
            SELECT
                customerid,
                DATE_TRUNC('week', CAST(invoicedate AS DATE)) AS invoice_week
            FROM retail_clean
        ),
        cohort_map AS (
            SELECT customerid, MIN(invoice_week) AS cohort_week
            FROM with_week
            GROUP BY customerid
        ),
        with_index AS (
            SELECT
                w.customerid,
                w.invoice_week,
                c.cohort_week,
                DATEDIFF(WEEK, c.cohort_week, w.invoice_week) AS cohort_index
            FROM with_week w
            JOIN cohort_map c ON w.customerid = c.customerid
        ),
        cohort_counts AS (
            SELECT
                cohort_week,
                cohort_index,
                COUNT(DISTINCT customerid) AS customers
            FROM with_index
            GROUP BY cohort_week, cohort_index
        )
        SELECT
            cohort_week,
            cohort_index,
            customers,
            FIRST_VALUE(customers) OVER (
                PARTITION BY cohort_week ORDER BY cohort_index
            ) AS cohort_size,
            ROUND(customers * 1.0 / FIRST_VALUE(customers) OVER (
                PARTITION BY cohort_week ORDER BY cohort_index
            ), 3) AS retention_rate
        FROM cohort_counts
        ORDER BY cohort_week, cohort_index
    """)
    return cohort_data


def save_cohort(session, cohort_data):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    cohort_data.write.save_as_table(f"{retail_schema}.cohort_retention", mode="overwrite")
    print(f"已写入 {retail_schema}.cohort_retention")


if __name__ == "__main__":
    import time
    session = get_session()
    try:
        fname = "online_retail_II.csv" if "--full" in sys.argv else "online_retail_sample.csv"
        t = time.time()
        df = load_clean(session, fname)
        cohort_data = compute_cohort(session, df)
        save_cohort(session, cohort_data)
        row_cnt = cohort_data.count()
        cohort_cnt = cohort_data.select("cohort_week").distinct().count()
        print(f"耗时: {time.time()-t:.1f}s  |  {cohort_cnt} cohorts, {row_cnt} rows")
        print("\n前 10 行（从结果表读取）:")
        session.sql(f"SELECT * FROM {retail_schema}.cohort_retention LIMIT 10").show()
    finally:
        session.close()
