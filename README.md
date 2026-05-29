# pandas2lakehouse-retail

> pandas → ZettaPark 迁移示例，以 UCI Online Retail 数据集为载体，展示如何将本地 pandas 分析脚本扩展到大规模数据。

数据来源：[UCI Online Retail II Dataset](https://archive.ics.uci.edu/dataset/502/online+retail+ii)（英国零售商 2009–2011 年真实交易记录，约 100 万行）。

---

## 迁移总结

### 整体结论

**ZettaPark DataFrame API 与 pandas 高度相似，核心操作几乎一一对应。** 迁移的本质不是重写业务逻辑，而是把计算从本地内存移到 Lakehouse 引擎——同样的代码，从处理 10 万行变成处理 1000 万行。

### API 对照

| pandas | ZettaPark | 兼容性 |
|--------|-----------|--------|
| `pd.read_csv(path)` | `session.read.csv("vol://schema.vol/path")` | 路径格式不同，其余一致 |
| `df.rename(columns={...})` | `df.with_column_renamed(old, new)` | snake_case 命名风格 |
| `df[df.col > 0]` | `df.filter(F.col("col") > 0)` | 语义一致，语法略有差异 |
| `df.groupby("col").agg(...)` | `df.group_by("col").agg(...)` | 下划线分隔，其余一致 |
| `df.merge(other, on="key")` | `df.join(other, "key")` | 方法名不同，语义一致 |
| `df.assign(new=expr)` | `df.with_column("new", expr)` | 方法名不同 |
| `df.sort_values("col")` | `df.sort("col")` | 方法名不同 |
| `df.drop_duplicates()` | `df.distinct()` | 方法名不同 |
| `df.to_csv(path)` | `df.write.save_as_table("schema.table")` | 直接写入 Lakehouse 表 |
| `df.shape[0]` | `df.count()` | 触发计算方式不同 |

### 分析场景

| 场景 | 说明 |
|------|------|
| 数据清洗 | 去除取消订单、空 CustomerID、负数 Quantity |
| RFM 分析 | 按客户计算 Recency / Frequency / Monetary，分层打标 |
| 同期群分析 | 按首购月份分组，追踪各月留存率 |
| 产品分析 | Top 产品销售额、退货率、国家分布 |

---

## 项目结构

```
pandas2lakehouse-retail/
├── 01_pandas/                   # 原始 pandas 代码（本地运行）
│   ├── 01_clean.py              #   数据清洗
│   ├── 02_rfm.py                #   RFM 分析
│   ├── 03_cohort.py             #   同期群分析
│   └── 04_product.py            #   产品分析
├── 02_migration/                # 迁移说明
│   ├── 01_overview.md           #   迁移策略与 API 对照
│   └── 02_api_mapping.md        #   完整 API 对照表
├── 03_lakehouse/                # ✅ ZettaPark 迁移后代码
│   ├── includes/configuration.py
│   ├── 01_clean.py
│   ├── 02_rfm.py
│   ├── 03_cohort.py
│   ├── 04_product.py
│   ├── setup.py                 #   初始化 Schema、Volume，上传数据
│   ├── e2e.py                   #   端到端验证
│   ├── reset.py                 #   清空表
│   └── teardown.py              #   完整清理
├── data/
│   └── sample/                  #   1000 行 sample 数据（git 提交）
├── datasets/                    #   完整数据集（.gitignore，运行时下载）
└── .env.sample
```

---

## 快速开始

### 前置条件

- Python 3.10+
- ClickZetta Lakehouse 账号（[免费注册](https://www.yunqi.tech)）

```bash
pip install clickzetta_zettapark_python pandas python-dotenv openpyxl
cp .env.sample .env
# 编辑 .env 填写连接信息

cd 03_lakehouse
python setup.py        # 建 Schema、Volume、表，上传 sample 数据
python e2e.py          # 端到端验证
```

### 运行原始 pandas 代码

```bash
pip install pandas openpyxl matplotlib seaborn
# 下载完整数据集到 datasets/ 后：
python 01_pandas/01_clean.py
python 01_pandas/02_rfm.py
python 01_pandas/03_cohort.py
python 01_pandas/04_product.py
```

---

## 数据集

- 来源：[UCI Machine Learning Repository - Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- 格式：Excel（.xlsx），两个 sheet（2009-2010 / 2010-2011）
- 字段：`InvoiceNo, StockCode, Description, Quantity, InvoiceDate, UnitPrice, CustomerID, Country`
- 规模：约 100 万行，4000+ 客户，38 个国家
- License：CC BY 4.0
