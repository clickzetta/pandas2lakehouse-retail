"""
04_product.py — 产品分析

Top 产品销售额、国家收入分布、月度趋势。
"""

import pandas as pd
from pathlib import Path


def load_clean(use_sample=True) -> pd.DataFrame:
    base = Path(__file__).parent.parent
    path = (base / "data/sample/online_retail_sample.csv") if use_sample \
        else (base / "datasets/online_retail_II.xlsx")
    df = pd.read_csv(path, parse_dates=["InvoiceDate"]) if use_sample \
        else pd.concat([
            pd.read_excel(path, sheet_name="Year 2009-2010"),
            pd.read_excel(path, sheet_name="Year 2010-2011"),
        ], ignore_index=True)
    df = df[~df["InvoiceNo"].astype(str).str.startswith("C")]
    df = df.dropna(subset=["CustomerID"])
    df = df[df["Quantity"] > 0]
    df = df[df["UnitPrice"] > 0]
    df["Revenue"] = df["Quantity"] * df["UnitPrice"]
    df["CustomerID"] = df["CustomerID"].astype(int)
    return df.reset_index(drop=True)


def top_products(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return (
        df.groupby(["StockCode", "Description"])
        .agg(TotalQty=("Quantity", "sum"), TotalRevenue=("Revenue", "sum"),
             OrderCount=("InvoiceNo", "nunique"))
        .reset_index()
        .sort_values("TotalRevenue", ascending=False)
        .head(n)
    )


def country_revenue(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("Country")
        .agg(Revenue=("Revenue", "sum"), Customers=("CustomerID", "nunique"),
             Orders=("InvoiceNo", "nunique"))
        .reset_index()
        .sort_values("Revenue", ascending=False)
    )


def monthly_revenue(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["YearMonth"] = df["InvoiceDate"].dt.to_period("M").astype(str)
    return (
        df.groupby("YearMonth")
        .agg(Revenue=("Revenue", "sum"), Orders=("InvoiceNo", "nunique"))
        .reset_index()
        .sort_values("YearMonth")
    )


if __name__ == "__main__":
    df = load_clean(use_sample=True)
    print("=== Top 10 产品 ===")
    print(top_products(df).to_string(index=False))
    print("\n=== 国家收入分布 ===")
    print(country_revenue(df).head(8).to_string(index=False))
    print("\n=== 月度收入趋势 ===")
    print(monthly_revenue(df).to_string(index=False))
