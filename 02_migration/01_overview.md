# 迁移概述

## 整体结论

你不需要重新学一套新工具，也不需要推倒重写现有脚本。pandas 代码直接作为迁移蓝图——分析逻辑、指标定义、分层规则全部保留，只替换数据读取方式和少数 API。

| 指标 | pandas | ZettaPark |
|------|--------|-----------|
| 扩展 RFM（购买间隔分析） | 8.2s，峰值 203MB | 3.2s，本地内存 0 |
| 周粒度同期群留存 | 9.4s，峰值 236MB | 5.9s，本地内存 0 |
| 多窗口 Cohort（滚动4周+环比+排名） | 2.4s，峰值 203MB | 3.1s，本地内存 0 |

数据规模：UCI Online Retail II，106 万行原始数据，清洗后 80.5 万行，5,878 个客户。

## 迁移前后对比

| 层 | pandas 实现 | ZettaPark 实现 |
|----|-------------|----------------|
| 数据读取 | `pd.read_csv(path)` | `FROM VOLUME ... USING CSV OPTIONS` |
| 清洗过滤 | `df[condition]` | `WHERE` 子句（在 SQL 里完成） |
| 列重命名 | `df.rename(columns=...)` | `SELECT col AS new_name`（在初始 SQL 里处理含空格列名） |
| 窗口函数 | `groupby().apply(shift())` | `LAG() OVER (PARTITION BY ... ORDER BY ...)` |
| 滚动聚合 | `rolling(4).sum()` | `SUM() OVER (ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)` |
| 百分位数 | `np.percentile(x, 25)` | `PERCENTILE(col, 0.25)` |
| 结果写出 | `df.to_csv()` / `df.to_parquet()` | `df.write.save_as_table(...)` |

## 必须修改的地方

### 1. 数据读取方式

pandas 直接读本地文件；ZettaPark 从 Volume 读取，且不支持 `inferSchema`。

```python
# pandas
df = pd.read_csv("online_retail_II.csv", parse_dates=["InvoiceDate"])

# ZettaPark — 用 session.sql + FROM VOLUME
df = session.sql("""
    SELECT Invoice, StockCode, Quantity, InvoiceDate, Price,
           `Customer ID` AS CustomerID, Country
    FROM VOLUME schema.vol_name
    USING CSV OPTIONS ('header' = 'true', 'nullValue' = '')
    FILES ('raw/online_retail_II.csv')
""")
```

### 2. 含空格的列名

原始数据有 `Customer ID`（含空格）。pandas 自动处理；ZettaPark 需要在初始 SQL 里用反引号引用并重命名，否则后续所有操作都需要反引号。

```python
# ZettaPark — 在 SELECT 里一次性重命名
`Customer ID` AS CustomerID
```

### 3. 窗口函数替代 groupby().apply()

pandas 用 `shift()` 计算相邻订单间隔；ZettaPark 用 `LAG()` 窗口函数，在一次 SQL 扫描中完成，无需多次 merge。

```python
# pandas — 需要 sort + shift + merge
orders["prev_date"] = orders.groupby("Customer ID")["InvoiceDate"].shift(1)
orders["gap_days"] = (orders["InvoiceDate"] - orders["prev_date"]).dt.days

# ZettaPark — 单次 SQL
LAG(order_date) OVER (PARTITION BY customerid ORDER BY order_date)
DATEDIFF(DAY, LAG(order_date) OVER (...), order_date) AS gap_days
```

### 4. 百分位数函数

```python
# pandas
np.percentile(x, 25)

# ZettaPark
PERCENTILE(gap_days, 0.25)
# 注意：不是 PERCENTILE_CONT，不是 APPROX_PERCENTILE
```

### 5. 滚动窗口

```python
# pandas — 需要 set_index + rolling + reset_index
cust_week.set_index("InvoiceWeek")
.groupby("Customer ID")["WeekRevenue"]
.transform(lambda x: x.rolling(4, min_periods=1).sum())

# ZettaPark — 标准 SQL 窗口帧
SUM(week_revenue) OVER (
    PARTITION BY customerid ORDER BY invoice_week
    ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
)
```

## 完全兼容的部分（无需修改）

分析逻辑本身不需要改动：

- 过滤条件（退货单、空客户、负数量）
- RFM 指标定义（Recency/Frequency/Monetary）
- Cohort 分析逻辑（首购周、留存率计算）
- 分层规则（Champions/At Risk/Lost 等）
- 所有聚合逻辑（SUM、COUNT DISTINCT、AVG）

## 迁移工作量估算

| 文件 | 改动类型 | 工作量 |
|------|---------|--------|
| `load_clean()` | 替换 read_csv → session.sql + FROM VOLUME | 约 15 行 |
| `compute_rfm_advanced()` | groupby+apply → session.sql CTE | 约 50 行 SQL |
| `compute_cohort_advanced()` | rolling+rank → session.sql CTE | 约 60 行 SQL |
| `save()` | to_csv → write.save_as_table | 约 3 行 |

总计：约 2 小时完成迁移，分析逻辑零改动。
