"""
04_product.py — 产品分析（ZettaPark 版）

pandas → ZettaPark 对照：
  df.groupby(["StockCode","Description"]).agg(...)  → df.group_by(...).agg(...)
  df.sort_values("TotalRevenue", ascending=False)   → df.sort(F.col("TotalRevenue").desc())
  df.head(n)                                        → df.limit(n)
  df["YearMonth"] = df.dt.to_period("M").astype(str)→ F.date_format(F.col("InvoiceDate"), "yyyy-MM")
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from clickzetta.zettapark.session import Session
from clickzetta.zettapark import functions as F
from includes.configuration import SCHEMA_NAME, retail_schema
from includes.helpers import get_session, load_clean


def top_products(df, n=10):
    return (
        df.group_by("StockCode", "Description")
        .agg(
            F.sum("Quantity").alias("TotalQty"),
            F.round(F.sum("Revenue"), 2).alias("TotalRevenue"),
            F.count_distinct("Invoice").alias("OrderCount"),
        )
        .sort(F.col("TotalRevenue").desc())
        .limit(n)
    )


def country_revenue(df):
    return (
        df.group_by("Country")
        .agg(
            F.round(F.sum("Revenue"), 2).alias("Revenue"),
            F.count_distinct("CustomerID").alias("Customers"),
            F.count_distinct("Invoice").alias("Orders"),
        )
        .sort(F.col("Revenue").desc())
    )


def monthly_revenue(df):
    df = df.with_column("YearMonth",
        F.date_format(F.col("InvoiceDate").cast("date"), "yyyy-MM"))
    return (
        df.group_by("YearMonth")
        .agg(
            F.round(F.sum("Revenue"), 2).alias("Revenue"),
            F.count_distinct("Invoice").alias("Orders"),
        )
        .sort("YearMonth")
    )


def save_all(session, df):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    top_products(df).write.save_as_table(f"{retail_schema}.top_products", mode="overwrite")
    country_revenue(df).write.save_as_table(f"{retail_schema}.country_revenue", mode="overwrite")
    monthly_revenue(df).write.save_as_table(f"{retail_schema}.monthly_revenue", mode="overwrite")
    print("已写入 top_products / country_revenue / monthly_revenue")


if __name__ == "__main__":
    session = get_session()
    try:
        df = load_clean(session)
        save_all(session, df)
        print("\n=== Top 10 产品 ===")
        top_products(df).show()
        print("\n=== 国家收入（Top 8）===")
        country_revenue(df).limit(8).show()
        print("\n=== 月度趋势 ===")
        monthly_revenue(df).show()
    finally:
        session.close()
