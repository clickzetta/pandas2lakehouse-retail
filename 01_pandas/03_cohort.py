"""
03_cohort.py — 同期群（Cohort）留存分析

按客户首次购买月份分组，追踪后续各月的留存率。
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


def compute_cohort(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["InvoiceMonth"] = df["InvoiceDate"].dt.to_period("M")

    cohort_map = (
        df.groupby("CustomerID")["InvoiceMonth"]
        .min()
        .rename("CohortMonth")
    )
    df = df.join(cohort_map, on="CustomerID")
    df["CohortIndex"] = (df["InvoiceMonth"] - df["CohortMonth"]).apply(lambda x: x.n)

    cohort_data = (
        df.groupby(["CohortMonth", "CohortIndex"])["CustomerID"]
        .nunique()
        .reset_index()
        .rename(columns={"CustomerID": "Customers"})
    )

    cohort_pivot = cohort_data.pivot_table(
        index="CohortMonth", columns="CohortIndex", values="Customers"
    )
    cohort_size = cohort_pivot.iloc[:, 0]
    retention = cohort_pivot.divide(cohort_size, axis=0).round(3)
    return retention


if __name__ == "__main__":
    df = load_clean(use_sample=True)
    retention = compute_cohort(df)
    print("同期群留存率矩阵（前 6 个月）:")
    print(retention.iloc[:, :6].to_string())
