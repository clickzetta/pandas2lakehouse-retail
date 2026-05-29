"""
03_cohort_advanced.py — 多层窗口函数 Cohort 分析（ZettaPark 版）

pandas → ZettaPark 对照：
  rolling(4).sum()                      → SUM() OVER (ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)
  groupby().rank()                      → DENSE_RANK() OVER (PARTITION BY cohort_week, invoice_week)
  shift(1) + 计算环比                   → LAG(week_revenue) OVER (PARTITION BY customer ORDER BY week)
  多次 groupby + merge                  → 单次 SQL WITH 链

ZettaPark 优势：
  - 所有窗口函数在一次 SQL 扫描中完成
  - pandas 需要 set_index + rolling + reset_index + 多次 merge，内存峰值高
  - 计算量越大，ZettaPark 的优势越明显
"""

import os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent))

from includes.configuration import retail_schema
from includes.helpers import get_session, load_clean


def compute_cohort_advanced(session, df):
    df.create_or_replace_temp_view("retail_clean")

    result = session.sql("""
        WITH customer_week AS (
            -- 每个客户每周的消费汇总
            SELECT
                customerid,
                DATE_TRUNC('week', CAST(invoicedate AS DATE)) AS invoice_week,
                SUM(revenue)            AS week_revenue,
                COUNT(DISTINCT invoice) AS week_orders
            FROM retail_clean
            GROUP BY customerid, DATE_TRUNC('week', CAST(invoicedate AS DATE))
        ),
        with_cohort AS (
            -- 加入首购周（cohort）
            SELECT
                customerid,
                invoice_week,
                week_revenue,
                week_orders,
                MIN(invoice_week) OVER (PARTITION BY customerid) AS cohort_week,
                DATEDIFF(WEEK,
                    MIN(invoice_week) OVER (PARTITION BY customerid),
                    invoice_week
                ) AS cohort_index
            FROM customer_week
        ),
        with_windows AS (
            -- 多层窗口函数：滚动4周、环比、cohort内排名
            SELECT
                customerid,
                invoice_week,
                cohort_week,
                cohort_index,
                week_revenue,
                week_orders,
                -- 滚动 4 周消费金额（rows between 3 preceding and current row）
                SUM(week_revenue) OVER (
                    PARTITION BY customerid
                    ORDER BY invoice_week
                    ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
                ) AS rolling_4w_revenue,
                -- 与上周环比变化率
                ROUND(
                    (week_revenue - LAG(week_revenue) OVER (
                        PARTITION BY customerid ORDER BY invoice_week
                    )) * 1.0 / NULLIF(LAG(week_revenue) OVER (
                        PARTITION BY customerid ORDER BY invoice_week
                    ), 0),
                    3
                ) AS wow_change,
                -- 当周在同 cohort 内的消费排名
                DENSE_RANK() OVER (
                    PARTITION BY cohort_week, invoice_week
                    ORDER BY week_revenue DESC
                ) AS revenue_rank_in_cohort
            FROM with_cohort
        ),
        cohort_stats AS (
            -- 每个 cohort×week 的汇总统计
            SELECT
                cohort_week,
                cohort_index,
                COUNT(DISTINCT customerid)      AS active_customers,
                ROUND(AVG(week_revenue), 2)     AS avg_revenue,
                ROUND(SUM(week_revenue), 2)     AS total_revenue,
                ROUND(AVG(rolling_4w_revenue), 2) AS avg_rolling_4w,
                ROUND(AVG(wow_change), 3)       AS avg_wow_change
            FROM with_windows
            GROUP BY cohort_week, cohort_index
        )
        SELECT
            s.*,
            FIRST_VALUE(s.active_customers) OVER (
                PARTITION BY s.cohort_week ORDER BY s.cohort_index
            ) AS cohort_size,
            ROUND(s.active_customers * 1.0 / FIRST_VALUE(s.active_customers) OVER (
                PARTITION BY s.cohort_week ORDER BY s.cohort_index
            ), 3) AS retention_rate
        FROM cohort_stats s
        ORDER BY cohort_week, cohort_index
    """)
    return result


def save(session, result):
    session.sql(f"CREATE SCHEMA IF NOT EXISTS {retail_schema}").collect()
    result.write.save_as_table(f"{retail_schema}.cohort_advanced", mode="overwrite")
    print(f"已写入 {retail_schema}.cohort_advanced")


if __name__ == "__main__":
    session = get_session()
    try:
        fname = "online_retail_II.csv" if "--full" in sys.argv else "online_retail_sample.csv"
        t = time.time()
        df = load_clean(session, fname)
        result = compute_cohort_advanced(session, df)
        save(session, result)
        cnt = session.sql(f"SELECT COUNT(*) FROM {retail_schema}.cohort_advanced").collect()[0][0]
        print(f"耗时: {time.time()-t:.1f}s  |  {cnt:,} rows")
        session.sql(f"SELECT * FROM {retail_schema}.cohort_advanced LIMIT 5").show()
    finally:
        session.close()
