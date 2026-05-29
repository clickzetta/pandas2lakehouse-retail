"""
04_market_basket.py — 商品关联分析（ZettaPark 版）

pandas → ZettaPark 对照：
  invoice_products.merge(invoice_products, on="Invoice")  → SQL self-join
  groupby().size()                                         → GROUP BY ... COUNT(*)
  多次 merge 计算 support/lift                             → 单次 SQL WITH 链

ZettaPark 优势：
  - self-join 的中间结果在服务端处理，不落本地内存
  - pandas 峰值内存 2203MB（1M 行），ZettaPark 本地内存 0
  - 数据量翻倍时 pandas 直接 OOM，ZettaPark 不受影响
"""

import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from includes.configuration import retail_schema
from includes.helpers import get_session, load_clean


def compute_market_basket(session, df, min_support: int = 10):
    df.create_or_replace_temp_view("retail_clean")

    result = session.sql(f"""
        WITH invoice_products AS (
            -- 每个 invoice 包含哪些商品（去重）
            SELECT DISTINCT invoice, stockcode
            FROM retail_clean
        ),
        total AS (
            SELECT COUNT(DISTINCT invoice) AS total_invoices
            FROM retail_clean
        ),
        pairs AS (
            -- self-join：找同一 invoice 里的商品对
            -- 中间结果在服务端处理，不占本地内存
            SELECT
                a.stockcode AS stockcode_a,
                b.stockcode AS stockcode_b,
                COUNT(*)    AS co_count
            FROM invoice_products a
            JOIN invoice_products b
              ON a.invoice = b.invoice
             AND a.stockcode < b.stockcode
            GROUP BY a.stockcode, b.stockcode
            HAVING COUNT(*) >= {min_support}
        ),
        product_freq AS (
            -- 每个商品出现在多少个 invoice 中
            SELECT stockcode, COUNT(DISTINCT invoice) AS freq
            FROM invoice_products
            GROUP BY stockcode
        )
        SELECT
            p.stockcode_a,
            p.stockcode_b,
            p.co_count,
            ROUND(p.co_count * 1.0 / t.total_invoices, 4) AS support,
            ROUND(
                (p.co_count * 1.0 / t.total_invoices)
                / (fa.freq * 1.0 / t.total_invoices)
                / (fb.freq * 1.0 / t.total_invoices),
                2
            ) AS lift
        FROM pairs p
        CROSS JOIN total t
        JOIN product_freq fa ON p.stockcode_a = fa.stockcode
        JOIN product_freq fb ON p.stockcode_b = fb.stockcode
        ORDER BY lift DESC
        LIMIT 100
    """)
    return result


def save(session, result):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    result.write.save_as_table(f"{retail_schema}.market_basket", mode="overwrite")
    print(f"已写入 {retail_schema}.market_basket")


if __name__ == "__main__":
    session = get_session()
    try:
        fname = "online_retail_II.csv" if "--full" in sys.argv else "online_retail_sample.csv"
        t = time.time()
        df = load_clean(session, fname)
        result = compute_market_basket(session, df)
        save(session, result)
        print(f"耗时: {time.time()-t:.1f}s")
        session.sql(f"SELECT * FROM {retail_schema}.market_basket LIMIT 5").show()
    finally:
        session.close()
