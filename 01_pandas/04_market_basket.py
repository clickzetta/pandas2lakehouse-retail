"""
04_market_basket.py — 商品关联分析（Market Basket Analysis，pandas 版）

找出同一订单中经常一起购买的商品对，计算：
  - co_count：共同出现次数
  - support：在所有订单中出现的比例
  - lift：提升度（> 1 表示正相关，越高越强）

核心瓶颈：invoice_products 自连接（self-join）。
  - 800k 行数据中有约 19k 个唯一 invoice，每个 invoice 平均 ~20 个商品
  - self-join 产生的中间结果约 20 * 20 * 19k = 760 万行
  - pandas 需要把这 760 万行全部加载到内存，峰值内存极高
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


def compute_market_basket(df: pd.DataFrame, min_support: int = 10) -> pd.DataFrame:
    # 1. 每个 invoice 包含哪些商品（去重）
    invoice_products = (
        df[["Invoice", "StockCode"]]
        .drop_duplicates()
    )

    total_invoices = invoice_products["Invoice"].nunique()

    # 2. self-join：找同一 invoice 里的商品对
    #    这是内存瓶颈：中间结果行数 = sum(n_products_per_invoice^2)
    pairs = invoice_products.merge(invoice_products, on="Invoice", suffixes=("_a", "_b"))
    pairs = pairs[pairs["StockCode_a"] < pairs["StockCode_b"]]  # 去重，避免 (A,B) 和 (B,A)

    # 3. 统计共现次数
    pair_counts = (
        pairs.groupby(["StockCode_a", "StockCode_b"])
        .size()
        .reset_index(name="co_count")
    )
    pair_counts = pair_counts[pair_counts["co_count"] >= min_support]

    # 4. 每个商品的出现频次
    product_freq = (
        invoice_products.groupby("StockCode")["Invoice"]
        .nunique()
        .reset_index(name="freq")
    )

    # 5. 计算 support 和 lift
    pair_counts = pair_counts.merge(
        product_freq.rename(columns={"StockCode": "StockCode_a", "freq": "freq_a"}),
        on="StockCode_a"
    )
    pair_counts = pair_counts.merge(
        product_freq.rename(columns={"StockCode": "StockCode_b", "freq": "freq_b"}),
        on="StockCode_b"
    )

    pair_counts["support"] = (pair_counts["co_count"] / total_invoices).round(4)
    pair_counts["lift"] = (
        pair_counts["support"]
        / (pair_counts["freq_a"] / total_invoices)
        / (pair_counts["freq_b"] / total_invoices)
    ).round(2)

    return pair_counts.sort_values("lift", ascending=False).head(100)


if __name__ == "__main__":
    use_sample = "--full" not in sys.argv
    tracemalloc.start()
    t = time.time()

    df = load_clean(use_sample=use_sample)
    result = compute_market_basket(df, min_support=10)

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.time() - t

    print(f"耗时: {elapsed:.1f}s  |  商品对数: {len(result):,}  |  峰值内存: {peak/1024/1024:.0f} MB")
    print(f"\nTop 5 关联商品对（按 lift 排序）:")
    print(result[["StockCode_a", "StockCode_b", "co_count", "support", "lift"]].head(5).to_string(index=False))
