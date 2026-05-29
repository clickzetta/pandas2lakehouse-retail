# pandas → ZettaPark API 对照

## 数据读取

| pandas | ZettaPark | 说明 |
|--------|-----------|------|
| `pd.read_csv(path)` | `session.sql("SELECT ... FROM VOLUME ... USING CSV OPTIONS ...")` | ZettaPark 不支持 inferSchema，必须用 SQL 读取 |
| `pd.read_csv(path, parse_dates=["col"])` | `CAST(col AS DATE)` 或 `CAST(col AS TIMESTAMP)` | 日期解析在 SQL 里完成 |
| `df.rename(columns={"Customer ID": "CustomerID"})` | `` `Customer ID` AS CustomerID `` | 含空格列名在初始 SELECT 里重命名 |

## 数据清洗

| pandas | ZettaPark | 说明 |
|--------|-----------|------|
| `df[~df["Invoice"].str.startswith("C")]` | `WHERE Invoice NOT LIKE 'C%'` | 过滤退货单 |
| `df.dropna(subset=["Customer ID"])` | `WHERE \`Customer ID\` IS NOT NULL` | 过滤空客户 |
| `df[df["Quantity"] > 0]` | `WHERE Quantity > 0` | 过滤负数量 |
| `df["Revenue"] = df["Quantity"] * df["Price"]` | `df.with_column("Revenue", F.col("Quantity") * F.col("Price"))` | 新增计算列 |

## 聚合与分组

| pandas | ZettaPark | 说明 |
|--------|-----------|------|
| `df.groupby("col").agg({"col2": "sum"})` | `df.group_by("col").agg(F.sum("col2"))` | 基础聚合 |
| `df.groupby("col")["col2"].nunique()` | `F.count_distinct("col2")` | 去重计数 |
| `df.groupby("col")["col2"].min()` | `F.min("col2")` | 最小值 |
| `df.groupby("col").apply(lambda g: ...)` | `session.sql("... WITH cte AS (...) SELECT ...")` | 复杂逻辑改用 SQL CTE |

## 窗口函数

| pandas | ZettaPark SQL | 说明 |
|--------|---------------|------|
| `df.groupby("id")["date"].shift(1)` | `LAG(date, 1) OVER (PARTITION BY id ORDER BY date)` | 取上一行值 |
| `df.groupby("id")["val"].rank(method="dense", ascending=False)` | `DENSE_RANK() OVER (PARTITION BY id ORDER BY val DESC)` | 排名 |
| `df.groupby("id")["val"].transform(lambda x: x.rolling(4, min_periods=1).sum())` | `SUM(val) OVER (PARTITION BY id ORDER BY week ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)` | 滚动聚合 |
| `df.groupby("id")["val"].shift(1)` 然后计算差值 | `LAG(val) OVER (PARTITION BY id ORDER BY week)` | 环比计算 |
| `df.groupby("id")["date"].transform("min")` | `MIN(date) OVER (PARTITION BY id)` | 分组内最小值（不聚合行数） |

## 百分位数

| pandas | ZettaPark | 说明 |
|--------|-----------|------|
| `np.percentile(x, 25)` | `PERCENTILE(col, 0.25)` | P25 |
| `np.percentile(x, 50)` | `PERCENTILE(col, 0.50)` | 中位数 |
| `np.percentile(x, 75)` | `PERCENTILE(col, 0.75)` | P75 |
| `x.quantile(0.5)` | `PERCENTILE(col, 0.50)` | 同上 |

> ⚠️ **注意**：ZettaPark 用 `PERCENTILE`，不是 `PERCENTILE_CONT`，也不是 `APPROX_PERCENTILE`。

## 日期操作

| pandas | ZettaPark SQL | 说明 |
|--------|---------------|------|
| `df["date"].dt.to_period("W").dt.start_time` | `DATE_TRUNC('week', CAST(col AS DATE))` | 截断到周 |
| `(date_a - date_b).dt.days` | `DATEDIFF(DAY, date_b, date_a)` | 日期差（天） |
| `(week_a - week_b).dt.days // 7` | `DATEDIFF(WEEK, week_b, week_a)` | 日期差（周） |
| `df["date"].max()` | `MAX(col)` | 最大日期 |

> ⚠️ **注意**：`DATEDIFF(WEEK, ...)` 中 `WEEK` 不加引号；`DATE_TRUNC('week', ...)` 中 `'week'` 加引号。两者语法不同。

## 结果写出

| pandas | ZettaPark | 说明 |
|--------|-----------|------|
| `df.to_csv("output.csv")` | `df.write.save_as_table("schema.table", mode="overwrite")` | 写入 Lakehouse 表 |
| `df.to_parquet("output.parquet")` | `df.write.save_as_table(...)` | 同上，格式由平台管理 |

## 条件逻辑

| pandas | ZettaPark | 说明 |
|--------|-----------|------|
| `np.where(cond, a, b)` | `F.when(cond, a).otherwise(b)` | 条件赋值 |
| `df["col"].fillna(0)` | `F.coalesce(F.col("col"), F.lit(0))` | 空值填充 |

## 已知陷阱

### COUNT(DISTINCT) 与 ORDER BY 不能共存

在同一个 `GROUP BY` 里同时使用 `COUNT(DISTINCT ...)` 和带 `ORDER BY` 的聚合（如 `PERCENTILE`）会报错。解决方法：拆成两个 CTE。

```sql
-- 错误：COUNT(DISTINCT) 和 PERCENTILE 在同一 GROUP BY
SELECT customerid,
       COUNT(DISTINCT invoice) AS total_orders,
       PERCENTILE(gap_days, 0.5) AS gap_p50  -- 报错
FROM ...
GROUP BY customerid

-- 正确：拆成两个 CTE
customer_stats AS (
    SELECT customerid, COUNT(DISTINCT invoice) AS total_orders
    FROM ... GROUP BY customerid
),
gap_percentiles AS (
    SELECT customerid, PERCENTILE(gap_days, 0.5) AS gap_p50
    FROM ... WHERE gap_days IS NOT NULL GROUP BY customerid
)
```

### DataFrame API 的列名大小写

ZettaPark 将所有列名转为小写。原始数据的 `Customer ID` 在 DataFrame 里变成 `customer id`（含空格且小写），直接使用会报错。在初始 SQL 的 `SELECT` 里重命名是最简单的解法。

### session.sql 返回的 DataFrame 二次操作

对 `session.sql(...)` 返回的 DataFrame 调用 `.show()` 有时会失败。改用：

```python
session.sql("SELECT * FROM table LIMIT 10").show()
```

或先 `create_or_replace_temp_view`，再查询临时视图。
