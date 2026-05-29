"""
02_rfm.py — RFM 客户分层分析

RFM 三个维度：
  - Recency:   距最后一次购买的天数（越小越好）
  - Frequency: 购买次数（越大越好）
  - Monetary:  总消费金额（越大越好）

打分逻辑：各维度按四分位数分为 1-4 分，R 分越小得分越高。
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


def compute_rfm(df: pd.DataFrame) -> pd.DataFrame:
    snapshot = df["InvoiceDate"].max()
    rfm = df.groupby("CustomerID").agg(
        Recency=("InvoiceDate", lambda x: (snapshot - x.max()).days),
        Frequency=("InvoiceNo", "nunique"),
        Monetary=("Revenue", "sum"),
    ).reset_index()
    return rfm


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    rfm = rfm.copy()
    rfm["R_score"] = pd.qcut(rfm["Recency"], q=4, labels=[4, 3, 2, 1])
    rfm["F_score"] = pd.qcut(rfm["Frequency"].rank(method="first"), q=4, labels=[1, 2, 3, 4])
    rfm["M_score"] = pd.qcut(rfm["Monetary"].rank(method="first"), q=4, labels=[1, 2, 3, 4])

    def segment(row):
        r, f = int(row["R_score"]), int(row["F_score"])
        if r >= 3 and f >= 3:   return "Champions"
        elif r >= 3:             return "Recent Customers"
        elif f >= 3:             return "At Risk"
        else:                    return "Lost"

    rfm["Segment"] = rfm.apply(segment, axis=1)
    return rfm


if __name__ == "__main__":
    df = load_clean(use_sample=True)
    rfm = score_rfm(compute_rfm(df))
    print(rfm.head(10).to_string())
    print(f"\n客户分层分布:\n{rfm['Segment'].value_counts()}")
