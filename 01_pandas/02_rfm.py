"""
02_rfm.py — RFM 客户分层分析

RFM 三个维度：
  - Recency:   距最后一次购买的天数（越小越好）
  - Frequency: 购买次数（越大越好）
  - Monetary:  总消费金额（越大越好）

打分逻辑：各维度按四分位数分为 1-4 分，R 分越小得分越高。
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


def compute_rfm(df: pd.DataFrame) -> pd.DataFrame:
    snapshot = df["InvoiceDate"].max()
    return df.groupby("Customer ID").agg(
        Recency=("InvoiceDate", lambda x: (snapshot - x.max()).days),
        Frequency=("Invoice", "nunique"),
        Monetary=("Revenue", "sum"),
    ).reset_index()


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    rfm = rfm.copy()
    # rank 后 qcut 保证 4 个 bin 都有数据
    rfm["R_score"] = pd.qcut(rfm["Recency"].rank(method="first", ascending=False),
                              q=4, labels=[4, 3, 2, 1])
    rfm["F_score"] = pd.qcut(rfm["Frequency"].rank(method="first"), q=4, labels=[1, 2, 3, 4])
    rfm["M_score"] = pd.qcut(rfm["Monetary"].rank(method="first"),  q=4, labels=[1, 2, 3, 4])

    def segment(row):
        r, f = int(row["R_score"]), int(row["F_score"])
        if r >= 3 and f >= 3:  return "Champions"
        elif r >= 3:           return "Recent Customers"
        elif f >= 3:           return "At Risk"
        else:                  return "Lost"

    rfm["Segment"] = rfm.apply(segment, axis=1)
    return rfm


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    t = time.time()
    df = load_clean(use_sample=use_sample)
    rfm = score_rfm(compute_rfm(df))
    print(f"耗时: {time.time()-t:.1f}s  |  客户数: {len(rfm):,}")
    print(rfm.head(10).to_string())
    print(f"\n客户分层分布:\n{rfm['Segment'].value_counts()}")
