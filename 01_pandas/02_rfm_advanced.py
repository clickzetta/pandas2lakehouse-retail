"""
02_rfm_advanced.py — 扩展 RFM 分析（pandas 版）

在基础 RFM 之上，增加：
  - 购买间隔统计：P25 / P50 / P75 / 最大间隔（天）
  - 首购到复购天数（second_purchase_gap）
  - 最长断购周期（max_gap）
  - 客户生命周期（days_active = 最后购买 - 首次购买）

这些指标需要对每个客户的订单序列做多次 groupby + sort + shift，
pandas 内存峰值约为数据量的 3-4 倍。
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


def compute_order_level(df: pd.DataFrame) -> pd.DataFrame:
    """聚合到订单级别（每个 Invoice 一行）"""
    return (
        df.groupby(["Customer ID", "Invoice", "InvoiceDate"])
        .agg(OrderRevenue=("Revenue", "sum"), ItemCount=("Quantity", "sum"))
        .reset_index()
        .sort_values(["Customer ID", "InvoiceDate"])
    )


def compute_purchase_gaps(orders: pd.DataFrame) -> pd.DataFrame:
    """
    计算每个客户的购买间隔序列，然后统计：
      - gap_p25 / gap_p50 / gap_p75：间隔天数的四分位数
      - max_gap：最长断购周期
      - second_purchase_gap：首购到复购的天数（-1 表示只购买一次）
      - days_active：客户生命周期（最后购买 - 首次购买）
    """
    orders = orders.copy()
    # 每个客户内，计算相邻订单的间隔天数
    orders["prev_date"] = orders.groupby("Customer ID")["InvoiceDate"].shift(1)
    orders["gap_days"] = (orders["InvoiceDate"] - orders["prev_date"]).dt.days

    # 只保留有间隔的行（第一次购买没有间隔）
    gaps = orders.dropna(subset=["gap_days"])

    gap_stats = gaps.groupby("Customer ID")["gap_days"].agg(
        gap_p25=lambda x: np.percentile(x, 25),
        gap_p50=lambda x: np.percentile(x, 50),
        gap_p75=lambda x: np.percentile(x, 75),
        max_gap="max",
    ).reset_index()

    # 首购到复购天数
    second_purchase = (
        orders.groupby("Customer ID")
        .apply(lambda g: g.sort_values("InvoiceDate").iloc[1]["gap_days"]
               if len(g) >= 2 else -1, include_groups=False)
        .reset_index()
        .rename(columns={0: "second_purchase_gap"})
    )

    # 客户生命周期
    lifecycle = orders.groupby("Customer ID").agg(
        first_purchase=("InvoiceDate", "min"),
        last_purchase=("InvoiceDate", "max"),
        total_orders=("Invoice", "nunique"),
    ).reset_index()
    lifecycle["days_active"] = (
        lifecycle["last_purchase"] - lifecycle["first_purchase"]
    ).dt.days

    result = lifecycle.merge(gap_stats, on="Customer ID", how="left")
    result = result.merge(second_purchase, on="Customer ID", how="left")
    return result


def compute_rfm_advanced(df: pd.DataFrame) -> pd.DataFrame:
    snapshot = df["InvoiceDate"].max()

    # 基础 RFM
    rfm = df.groupby("Customer ID").agg(
        Recency=("InvoiceDate", lambda x: (snapshot - x.max()).days),
        Frequency=("Invoice", "nunique"),
        Monetary=("Revenue", "sum"),
    ).reset_index()

    # 扩展指标
    orders = compute_order_level(df)
    extended = compute_purchase_gaps(orders)

    return rfm.merge(extended, on="Customer ID", how="left")


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    tracemalloc.start()
    t = time.time()

    df = load_clean(use_sample=use_sample)
    result = compute_rfm_advanced(df)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.time() - t

    print(f"耗时: {elapsed:.1f}s  |  客户数: {len(result):,}  |  峰值内存: {peak/1024/1024:.0f} MB")
    print(f"\n列: {result.columns.tolist()}")
    print(result.head(5).to_string())
