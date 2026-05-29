"""
01_clean.py — 数据清洗

UCI Online Retail II 列名：
  Invoice, StockCode, Description, Quantity, InvoiceDate, Price, Customer ID, Country

原始数据问题：
  - 取消订单（Invoice 以 C 开头）
  - 缺失 Customer ID
  - 负数 Quantity（退货）
  - 零或负数 Price
"""

import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent.parent
SAMPLE_PATH = BASE / "data/sample/online_retail_sample.csv"
FULL_PATH   = BASE / "datasets/online_retail_II.xlsx"


def load_data(use_sample=False) -> pd.DataFrame:
    if use_sample:
        return pd.read_csv(SAMPLE_PATH, parse_dates=["InvoiceDate"])
    return pd.concat([
        pd.read_excel(FULL_PATH, sheet_name="Year 2009-2010"),
        pd.read_excel(FULL_PATH, sheet_name="Year 2010-2011"),
    ], ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    print(f"原始行数: {len(df):,}")

    df = df[~df["Invoice"].astype(str).str.startswith("C")]
    print(f"去除取消订单后: {len(df):,}")

    df = df.dropna(subset=["Customer ID"])
    print(f"去除缺失 Customer ID 后: {len(df):,}")

    df = df[df["Quantity"] > 0]
    df = df[df["Price"] > 0]
    print(f"去除异常数量/价格后: {len(df):,}")

    df = df.assign(Revenue=df["Quantity"] * df["Price"])
    df["Customer ID"] = df["Customer ID"].astype(int)

    return df.reset_index(drop=True)


if __name__ == "__main__":
    import time, sys
    use_sample = "--sample" in sys.argv or True  # default sample
    if "--full" in sys.argv:
        use_sample = False

    t = time.time()
    df_raw = load_data(use_sample=use_sample)
    df_clean = clean(df_raw)
    print(f"\n耗时: {time.time()-t:.1f}s")
    print(f"\n清洗后预览:\n{df_clean.head(3).to_string()}")
