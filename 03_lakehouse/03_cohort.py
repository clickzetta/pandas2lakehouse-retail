"""
03_cohort.py — 同期群留存分析（ZettaPark 版）

pandas → ZettaPark 对照：
  df["InvoiceDate"].dt.to_period("M")  → F.date_trunc("month", F.col("InvoiceDate"))
  df.groupby().min()                   → df.group_by().agg(F.min(...))
  df.join(cohort_map, on=...)          → df.join(cohort_map, "Customer ID")
  cohort_data.pivot_table(...)         → session.sql("SELECT ... PIVOT ...")  或手动 CASE WHEN
  cohort_pivot.divide(cohort_size)     → 窗口函数 FIRST_VALUE 取 index=0 的值做分母
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
    # 月份截断
    df = df.with_column("InvoiceMonth",
        F.date_trunc("month", F.col("InvoiceDate").cast("date")))

    # 每个客户的首购月份
    cohort_map = df.group_by("Customer ID").agg(
        F.min("InvoiceMonth").alias("CohortMonth")
    )
    df = df.join(cohort_map, "Customer ID")

    # 距首购的月数
    df = df.with_column("CohortIndex",
        F.months_between(F.col("InvoiceMonth"), F.col("CohortMonth")).cast("int"))

    # 每个 cohort × index 的活跃客户数
    cohort_data = df.group_by("CohortMonth", "CohortIndex").agg(
        F.count_distinct("Customer ID").alias("Customers")
    )

    # 计算留存率：用窗口函数取 index=0 的 cohort size 作分母
    from clickzetta.zettapark.window import Window
    w = Window.partition_by("CohortMonth").order_by("CohortIndex")
    cohort_data = cohort_data.with_column("CohortSize",
        F.first_value("Customers").over(w))
    cohort_data = cohort_data.with_column("RetentionRate",
        F.round(F.col("Customers") / F.col("CohortSize"), 3))

    return cohort_data.sort("CohortMonth", "CohortIndex")


def save_cohort(session, cohort_data):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    cohort_data.write.save_as_table(f"{retail_schema}.cohort_retention", mode="overwrite")
    print(f"已写入 {retail_schema}.cohort_retention")


if __name__ == "__main__":
    session = get_session()
    try:
        df = load_clean(session)
        cohort_data = compute_cohort(session, df)
        save_cohort(session, cohort_data)
        print("\n同期群留存率（前 10 行）:")
        cohort_data.show(10)
    finally:
        session.close()
