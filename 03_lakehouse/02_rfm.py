"""
02_rfm.py — RFM 客户分层分析（ZettaPark 版）

pandas → ZettaPark 对照：
  df.groupby("Customer ID").agg(...)   → df.group_by("Customer ID").agg(...)
  lambda x: (snapshot - x.max()).days  → F.datediff("day", F.max("InvoiceDate"), F.lit(snapshot))
  df["col"].nunique()                  → F.count_distinct("Invoice")
  df.assign(Segment=df.apply(...))     → df.with_column("Segment", F.when(...).otherwise(...))
  df.sort_values("Monetary")           → df.sort(F.col("Monetary").desc())
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


def compute_rfm(session, df):
    snapshot = df.agg(F.max("InvoiceDate")).collect()[0][0]

    rfm = df.group_by("Customer ID").agg(
        F.datediff("day", F.max("InvoiceDate"), F.lit(snapshot)).alias("Recency"),
        F.count_distinct("Invoice").alias("Frequency"),
        F.round(F.sum("Revenue"), 2).alias("Monetary"),
    )
    return rfm, snapshot


def score_rfm(session, rfm):
    """用 NTILE(4) 窗口函数打分，替代 pandas 的 qcut。"""
    from clickzetta.zettapark.window import Window

    w_r = Window.order_by(F.col("Recency").asc())
    w_f = Window.order_by(F.col("Frequency").asc())
    w_m = Window.order_by(F.col("Monetary").asc())

    rfm = rfm.with_column("R_rank", F.ntile(4).over(w_r))
    rfm = rfm.with_column("F_rank", F.ntile(4).over(w_f))
    rfm = rfm.with_column("M_rank", F.ntile(4).over(w_m))

    # R 分反转：rank=1（最小 Recency）→ score=4
    rfm = rfm.with_column("R_score", F.lit(5) - F.col("R_rank"))
    rfm = rfm.with_column("F_score", F.col("F_rank"))
    rfm = rfm.with_column("M_score", F.col("M_rank"))

    # 客户分层
    rfm = rfm.with_column("Segment",
        F.when((F.col("R_score") >= 3) & (F.col("F_score") >= 3), F.lit("Champions"))
         .when(F.col("R_score") >= 3, F.lit("Recent Customers"))
         .when(F.col("F_score") >= 3, F.lit("At Risk"))
         .otherwise(F.lit("Lost"))
    )
    return rfm


def save_rfm(session, rfm):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    rfm.write.save_as_table(f"{retail_schema}.rfm_segments", mode="overwrite")
    print(f"已写入 {retail_schema}.rfm_segments")


if __name__ == "__main__":
    session = get_session()
    try:
        df = load_clean(session)
        rfm, snapshot = compute_rfm(session, df)
        rfm = score_rfm(session, rfm)
        save_rfm(session, rfm)

        print(f"\n客户分层分布:")
        rfm.group_by("Segment").agg(F.count("*").alias("Count")) \
           .sort(F.col("Count").desc()).show()
    finally:
        session.close()
