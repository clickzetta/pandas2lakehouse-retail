"""
01_clean.py — 数据清洗

原始数据问题：
  - 取消订单（InvoiceNo 以 C 开头）
  - 缺失 CustomerID
  - 负数 Quantity（退货）
  - 零或负数 UnitPrice
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "datasets"
SAMPLE_DIR = Path(__file__).parent.parent / "data" / "sample"


def load_data(use_sample=False) -> pd.DataFrame:
    if use_sample:
        path = SAMPLE_DIR / "online_retail_sample.csv"
        df = pd.read_csv(path, encoding="utf-8", parse_dates=["InvoiceDate"])
    else:
        path = DATA_DIR / "online_retail_II.xlsx"
        df = pd.concat([
            pd.read_excel(path, sheet_name="Year 2009-2010"),
            pd.read_excel(path, sheet_name="Year 2010-2011"),
        ], ignore_index=True)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    print(f"原始行数: {len(df):,}")

    # 去除取消订单
    df = df[~df["InvoiceNo"].astype(str).str.startswith("C")]
    print(f"去除取消订单后: {len(df):,}")

    # 去除缺失 CustomerID
    df = df.dropna(subset=["CustomerID"])
    print(f"去除缺失 CustomerID 后: {len(df):,}")

    # 去除异常数量和价格
    df = df[df["Quantity"] > 0]
    df = df[df["UnitPrice"] > 0]
    print(f"去除异常数量/价格后: {len(df):,}")

    # 新增销售额列
    df = df.assign(Revenue=df["Quantity"] * df["UnitPrice"])

    # 统一 CustomerID 类型
    df["CustomerID"] = df["CustomerID"].astype(int)

    return df.reset_index(drop=True)


if __name__ == "__main__":
    df_raw = load_data(use_sample=True)
    df_clean = clean(df_raw)
    print(f"\n清洗后数据预览:")
    print(df_clean.head())
    print(f"\n数据类型:\n{df_clean.dtypes}")
