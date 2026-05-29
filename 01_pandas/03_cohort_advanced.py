"""
03_cohort_advanced.py — 多层窗口函数 Cohort 分析（pandas 版）

在基础周粒度 cohort 之上，增加：
  1. 每个客户每周的消费金额（customer_week_revenue）
  2. 滚动 4 周消费金额（rolling_4w_revenue）—— rolling window
  3. 当周在同 cohort 内的消费排名（revenue_rank_in_cohort）—— window rank
  4. 与上周消费的环比变化率（wow_change）—— lag + 计算
  5. 每个 cohort 每周的活跃客户数和平均消费（cohort_week_stats）

pandas 实现需要：
  - 多次 groupby + merge（内存翻倍）
  - rolling() 需要先 sort + set_index（额外内存）
  - rank() 在大 groupby 下很慢
"""

import pandas as pd
import numpy as np
import sys
import time
import tracemalloc
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


def compute_cohort_advanced(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. 周截断
    df["InvoiceWeek"] = df["InvoiceDate"].dt.to_period("W").dt.start_time

    # 2. 每个客户每周的消费金额
    cust_week = (
        df.groupby(["Customer ID", "InvoiceWeek"])
        .agg(WeekRevenue=("Revenue", "sum"), WeekOrders=("Invoice", "nunique"))
        .reset_index()
        .sort_values(["Customer ID", "InvoiceWeek"])
    )

    # 3. 滚动 4 周消费金额（需要 set_index + rolling）
    cust_week = cust_week.set_index("InvoiceWeek")
    cust_week["Rolling4wRevenue"] = (
        cust_week.groupby("Customer ID")["WeekRevenue"]
        .transform(lambda x: x.rolling(4, min_periods=1).sum())
    )
    cust_week = cust_week.reset_index()

    # 4. 与上周的环比变化率
    cust_week["PrevWeekRevenue"] = (
        cust_week.groupby("Customer ID")["WeekRevenue"].shift(1)
    )
    cust_week["WoWChange"] = (
        (cust_week["WeekRevenue"] - cust_week["PrevWeekRevenue"])
        / cust_week["PrevWeekRevenue"].replace(0, np.nan)
    ).round(3)

    # 5. 首购周（cohort）
    cohort_map = (
        cust_week.groupby("Customer ID")["InvoiceWeek"]
        .min()
        .rename("CohortWeek")
    )
    cust_week = cust_week.join(cohort_map, on="Customer ID")
    cust_week["CohortIndex"] = (
        (cust_week["InvoiceWeek"] - cust_week["CohortWeek"])
        .dt.days // 7
    )

    # 6. 当周在同 cohort 内的消费排名（计算量最大的步骤）
    cust_week["RevenueRankInCohort"] = (
        cust_week.groupby(["CohortWeek", "InvoiceWeek"])["WeekRevenue"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    # 7. 每个 cohort×week 的汇总统计
    cohort_stats = (
        cust_week.groupby(["CohortWeek", "CohortIndex"])
        .agg(
            ActiveCustomers=("Customer ID", "nunique"),
            AvgRevenue=("WeekRevenue", "mean"),
            TotalRevenue=("WeekRevenue", "sum"),
            AvgRolling4w=("Rolling4wRevenue", "mean"),
        )
        .reset_index()
    )

    # 8. 留存率
    cohort_size = cohort_stats[cohort_stats["CohortIndex"] == 0][
        ["CohortWeek", "ActiveCustomers"]
    ].rename(columns={"ActiveCustomers": "CohortSize"})
    cohort_stats = cohort_stats.merge(cohort_size, on="CohortWeek", how="left")
    cohort_stats["RetentionRate"] = (
        cohort_stats["ActiveCustomers"] / cohort_stats["CohortSize"]
    ).round(3)

    return cohort_stats, cust_week


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    tracemalloc.start()
    t = time.time()

    df = load_clean(use_sample=use_sample)
    cohort_stats, cust_week = compute_cohort_advanced(df)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.time() - t

    print(f"耗时: {elapsed:.1f}s  |  峰值内存: {peak/1024/1024:.0f} MB")
    print(f"cohort_stats: {cohort_stats.shape}  cust_week: {cust_week.shape}")
    print(f"\ncohort_stats 前 5 行:")
    print(cohort_stats.head(5).to_string())
    print(f"\ncust_week 前 5 行（含滚动窗口和排名）:")
    print(cust_week[["Customer ID", "InvoiceWeek", "WeekRevenue",
                      "Rolling4wRevenue", "WoWChange", "RevenueRankInCohort"]].head(5).to_string())
