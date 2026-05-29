"""
02_rfm_advanced.py — 扩展 RFM 分析（ZettaPark 版）

pandas → ZettaPark 对照：
  df.groupby().agg(lambda: percentile)  → PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY gap)
  df.groupby().apply(lambda g: g.iloc[1])→ LEAD/LAG 窗口函数
  df.sort_values + shift()              → LAG(date, 1) OVER (PARTITION BY customer ORDER BY date)
  多次 merge                            → 单次 SQL WITH 链，无额外内存

ZettaPark 优势：所有窗口函数在一次 SQL 扫描中完成，
pandas 需要多次 groupby + merge，内存峰值约为数据量的 3-4 倍。
"""

import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from clickzetta.zettapark import functions as F
from includes.configuration import retail_schema
from includes.helpers import get_session, load_clean


def compute_rfm_advanced(session, df):
    """
    用 session.sql + 临时视图完成所有计算。
    所有窗口函数在一次 SQL 扫描中完成，无需多次 merge。
    """
    df.create_or_replace_temp_view("retail_clean")

    result = session.sql("""
        WITH order_level AS (
            -- 聚合到订单级别
            SELECT
                customerid,
                invoice,
                CAST(invoicedate AS DATE) AS order_date,
                SUM(revenue) AS order_revenue
            FROM retail_clean
            GROUP BY customerid, invoice, CAST(invoicedate AS DATE)
        ),
        with_gaps AS (
            -- 计算相邻订单间隔（LAG 窗口函数）
            SELECT
                customerid,
                invoice,
                order_date,
                order_revenue,
                LAG(order_date) OVER (
                    PARTITION BY customerid ORDER BY order_date
                ) AS prev_order_date,
                DATEDIFF(DAY,
                    LAG(order_date) OVER (PARTITION BY customerid ORDER BY order_date),
                    order_date
                ) AS gap_days,
                ROW_NUMBER() OVER (
                    PARTITION BY customerid ORDER BY order_date
                ) AS order_seq
            FROM order_level
        ),
        customer_stats AS (
            -- 每个客户的汇总统计，分两步避免 DISTINCT + ORDER BY 冲突
            SELECT
                customerid,
                MIN(order_date)                                    AS first_purchase,
                MAX(order_date)                                    AS last_purchase,
                COUNT(DISTINCT invoice)                            AS total_orders,
                DATEDIFF(DAY, MIN(order_date), MAX(order_date))    AS days_active,
                MAX(CASE WHEN order_seq = 2 THEN gap_days END)     AS second_purchase_gap
            FROM with_gaps
            GROUP BY customerid
        ),
        gap_percentiles AS (
            -- 单独计算间隔百分位（只对有间隔的行）
            SELECT
                customerid,
                PERCENTILE(gap_days, 0.25) AS gap_p25,
                PERCENTILE(gap_days, 0.50) AS gap_p50,
                PERCENTILE(gap_days, 0.75) AS gap_p75,
                MAX(gap_days)              AS max_gap
            FROM with_gaps
            WHERE gap_days IS NOT NULL
            GROUP BY customerid
        ),
        rfm AS (
            SELECT
                customerid,
                DATEDIFF(DAY, MAX(CAST(invoicedate AS DATE)),
                    MAX(MAX(CAST(invoicedate AS DATE))) OVER ()
                ) AS recency,
                COUNT(DISTINCT invoice)  AS frequency,
                ROUND(SUM(revenue), 2)   AS monetary
            FROM retail_clean
            GROUP BY customerid
        )
        SELECT
            r.customerid,
            r.recency,
            r.frequency,
            r.monetary,
            s.first_purchase,
            s.last_purchase,
            s.total_orders,
            s.days_active,
            ROUND(p.gap_p25, 1)  AS gap_p25,
            ROUND(p.gap_p50, 1)  AS gap_p50,
            ROUND(p.gap_p75, 1)  AS gap_p75,
            p.max_gap,
            COALESCE(s.second_purchase_gap, -1) AS second_purchase_gap
        FROM rfm r
        JOIN customer_stats s ON r.customerid = s.customerid
        LEFT JOIN gap_percentiles p ON r.customerid = p.customerid
        ORDER BY r.customerid
    """)
    return result


def save(session, result):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    result.write.save_as_table(f"{retail_schema}.rfm_advanced", mode="overwrite")
    print(f"已写入 {retail_schema}.rfm_advanced")


if __name__ == "__main__":
    import time
    session = get_session()
    try:
        fname = "online_retail_II.csv" if "--full" in sys.argv else "online_retail_sample.csv"
        t = time.time()
        df = load_clean(session, fname)
        result = compute_rfm_advanced(session, df)
        save(session, result)
        cnt = session.sql(f"SELECT COUNT(*) FROM {retail_schema}.rfm_advanced").collect()[0][0]
        print(f"耗时: {time.time()-t:.1f}s  |  客户数: {cnt:,}")
        session.sql(f"SELECT * FROM {retail_schema}.rfm_advanced LIMIT 3").show()
    finally:
        session.close()
