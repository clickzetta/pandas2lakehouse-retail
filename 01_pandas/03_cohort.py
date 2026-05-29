"""
03_cohort.py — 同期群（Cohort）留存分析

按客户首次购买月份分组，追踪后续各月的留存率。
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


def compute_cohort(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["InvoiceMonth"] = df["InvoiceDate"].dt.to_period("M")

    cohort_map = (
        df.groupby("Customer ID")["InvoiceMonth"]
        .min()
        .rename("CohortMonth")
    )
    df = df.join(cohort_map, on="Customer ID")
    df["CohortIndex"] = (df["InvoiceMonth"] - df["CohortMonth"]).apply(lambda x: x.n)

    cohort_data = (
        df.groupby(["CohortMonth", "CohortIndex"])["Customer ID"]
        .nunique()
        .reset_index()
        .rename(columns={"Customer ID": "Customers"})
    )
    cohort_pivot = cohort_data.pivot_table(
        index="CohortMonth", columns="CohortIndex", values="Customers"
    )
    cohort_size = cohort_pivot.iloc[:, 0]
    return cohort_pivot.divide(cohort_size, axis=0).round(3)


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    t = time.time()
    df = load_clean(use_sample=use_sample)
    retention = compute_cohort(df)
    print(f"耗时: {time.time()-t:.1f}s")
    print("同期群留存率矩阵（前 6 个月）:")
    print(retention.iloc[:, :6].to_string())
