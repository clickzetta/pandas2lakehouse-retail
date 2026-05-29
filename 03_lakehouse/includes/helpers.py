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

    ZettaPark 不支持 inferSchema，用 session.sql + USING CSV OPTIONS 读取。
    列名和类型由 Lakehouse 根据 header 自动推断。
    """
    df = session.sql(f"""
        SELECT *
        FROM VOLUME {SCHEMA_NAME}.{VOLUME_NAME}
        USING CSV
        OPTIONS ('header' = 'true', 'nullValue' = '')
        FILES ('raw/{filename}')
    """)

    # 去除取消订单（Invoice 以 C 开头）
    df = df.filter(~F.col("Invoice").cast("string").startswith("C"))

    # 去除缺失 Customer ID
    df = df.filter(F.col("Customer ID").is_not_null())

    # 去除异常数量和价格
    df = df.filter(F.col("Quantity") > 0)
    df = df.filter(F.col("Price") > 0)

    # 新增 Revenue 列
    df = df.with_column("Revenue", F.col("Quantity") * F.col("Price"))

    return df
