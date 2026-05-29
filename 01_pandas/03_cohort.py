"""
03_cohort.py — 同期群（Cohort）留存分析

按客户首次购买**周**分组，追踪后续各周的留存率。
周粒度比月粒度计算量更大（104 个周 × 106 个 CohortIndex），
更适合零售业务的促销周期分析。
"""

import pandas as pd, sys, time
from pathlib import Path

BASE = Path(__file__).parent.parent
SAMPLE_PATH = BASE / "data/sample/online_retail_sample.csv"
FULL_PATH   = BASE / "datasets/online_retail_II.csv"


def load_clean(use_sample=True) -> pd.DataFrame:
    path = SAMPLE_PATH if use_sample else FULL_PATH
    df = pd.read_csv(path, parse_dates=["InvoiceDate"])
    df = df[~df["Invoice"].astype(str).str.startswith("C")]
    df = df.dropna(subset=["Customer ID"])
    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    df["Revenue"] = df["Quantity"] * df["Price"]
    df["Customer ID"] = df["Customer ID"].astype(int)
    return df.reset_index(drop=True)


def compute_cohort(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # 周粒度（Period W）
    df["InvoiceWeek"] = df["InvoiceDate"].dt.to_period("W")

    cohort_map = (
        df.groupby("Customer ID")["InvoiceWeek"]
        .min()
        .rename("CohortWeek")
    )
    df = df.join(cohort_map, on="Customer ID")
    df["CohortIndex"] = (df["InvoiceWeek"] - df["CohortWeek"]).apply(lambda x: x.n)

    cohort_data = (
        df.groupby(["CohortWeek", "CohortIndex"])["Customer ID"]
        .nunique()
        .reset_index()
        .rename(columns={"Customer ID": "Customers"})
    )
    cohort_pivot = cohort_data.pivot_table(
        index="CohortWeek", columns="CohortIndex", values="Customers"
    )
    cohort_size = cohort_pivot.iloc[:, 0]
    return cohort_pivot.divide(cohort_size, axis=0).round(3)


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    t = time.time()
    df = load_clean(use_sample=use_sample)
    retention = compute_cohort(df)
    elapsed = time.time() - t
    print(f"耗时: {elapsed:.1f}s  |  矩阵: {retention.shape[0]} cohorts × {retention.shape[1]} weeks")
    print("\n同期群留存率矩阵（前 5 个 cohort，前 8 周）:")
    print(retention.iloc[:5, :8].to_string())
