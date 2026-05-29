"""
04_product.py — 产品分析

Top 产品销售额、国家收入分布、月度趋势。
"""

import pandas as pd, sys, time
from pathlib import Path

BASE = Path(__file__).parent.parent
SAMPLE_PATH = BASE / "data/sample/online_retail_sample.csv"
FULL_PATH   = BASE / "datasets/online_retail_II.xlsx"


def load_clean(use_sample=True) -> pd.DataFrame:
    if use_sample:
        df = pd.read_csv(SAMPLE_PATH, parse_dates=["InvoiceDate"])
    else:
        df = pd.concat([
            pd.read_excel(FULL_PATH, sheet_name="Year 2009-2010"),
            pd.read_excel(FULL_PATH, sheet_name="Year 2010-2011"),
        ], ignore_index=True)
    df = df[~df["Invoice"].astype(str).str.startswith("C")]
    df = df.dropna(subset=["Customer ID"])
    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    df["Revenue"] = df["Quantity"] * df["Price"]
    df["Customer ID"] = df["Customer ID"].astype(int)
    return df.reset_index(drop=True)


def top_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return (
        df.groupby(["StockCode", "Description"])
        .agg(TotalQty=("Quantity", "sum"), TotalRevenue=("Revenue", "sum"),
             OrderCount=("Invoice", "nunique"))
        .reset_index()
        .sort_values("TotalRevenue", ascending=False)
        .head(n)
    )


def country_revenue(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("Country")
        .agg(Revenue=("Revenue", "sum"), Customers=("Customer ID", "nunique"),
             Orders=("Invoice", "nunique"))
        .reset_index()
        .sort_values("Revenue", ascending=False)
    )


def monthly_revenue(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["YearMonth"] = df["InvoiceDate"].dt.to_period("M").astype(str)
    return (
        df.groupby("YearMonth")
        .agg(Revenue=("Revenue", "sum"), Orders=("Invoice", "nunique"))
        .reset_index()
        .sort_values("YearMonth")
    )


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    t = time.time()
    df = load_clean(use_sample=use_sample)
    print(f"耗时: {time.time()-t:.1f}s  |  行数: {len(df):,}")
    print("\n=== Top 10 产品 ===")
    print(top_products(df).to_string(index=False))
    print("\n=== 国家收入分布（Top 8）===")
    print(country_revenue(df).head(8).to_string(index=False))
    print("\n=== 月度收入趋势 ===")
    print(monthly_revenue(df).to_string(index=False))
