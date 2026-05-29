import os
from clickzetta.zettapark.session import Session
from clickzetta.zettapark import functions as F
from includes.configuration import SCHEMA_NAME, VOLUME_NAME


def get_session():
    return Session.builder.configs({
        "username":  os.environ["CLICKZETTA_USERNAME"],
        "password":  os.environ["CLICKZETTA_PASSWORD"],
        "service":   os.environ["CLICKZETTA_SERVICE"],
        "instance":  os.environ["CLICKZETTA_INSTANCE"],
        "workspace": os.environ["CLICKZETTA_WORKSPACE"],
        "schema":    SCHEMA_NAME,
        "vcluster":  os.environ.get("CLICKZETTA_VCLUSTER", "default_ap"),
    }).create()


def load_clean(session, filename="online_retail_sample.csv"):
    """从 Volume 读取 CSV，清洗后返回 ZettaPark DataFrame。

    在 SELECT 里直接重命名 'Customer ID'（含空格）为 CustomerID，
    避免后续所有操作都需要用反引号处理含空格列名。
    """
    df = session.sql(f"""
        SELECT
            Invoice,
            StockCode,
            Description,
            Quantity,
            InvoiceDate,
            Price,
            `Customer ID` AS CustomerID,
            Country
        FROM VOLUME {SCHEMA_NAME}.{VOLUME_NAME}
        USING CSV
        OPTIONS ('header' = 'true', 'nullValue' = '')
        FILES ('raw/{filename}')
        WHERE Invoice NOT LIKE 'C%'
          AND `Customer ID` IS NOT NULL
          AND Quantity > 0
          AND Price > 0
    """)

    # 新增 Revenue 列
    df = df.with_column("Revenue", F.col("Quantity") * F.col("Price"))

    return df
