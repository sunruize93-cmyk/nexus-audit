"""异常注入脚本 — 向干净数据中注入 50 条刷单案例

注入的异常特征:
1. 共享 IP: 多个账户使用相同 IP 下单
2. 新账户聚集: 注册不满 7 天的账户凌晨集中下单
3. 凌晨时段爆发: 2:00-4:00 密集订单
4. 团伙环形关联: 账户-设备-IP 形成闭环
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).parent / "processed"

# 固定随机种子保证可复现
random.seed(42)

# ── 异常参数 ─────────────────────────────────────────────────────────
NUM_FRAUD_RINGS = 5
ACCOUNTS_PER_RING = 3
ORDERS_PER_ACCOUNT = 3  # ~= 5 rings × 3 accounts × 3 orders ≈ 45 + 5 solo = 50

SHARED_IPS = [f"192.168.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(5)]
SHARED_DEVICES = [f"DEV-{i:04d}" for i in range(8)]
FRAUD_SKUS = ["FRAUD-SKU-001", "FRAUD-SKU-002", "FRAUD-SKU-003"]
FRAUD_DESCRIPTIONS = [
    "Suspicious Bulk Widget", "Fake Review Product", "Phantom Listing Item"
]


def _random_datetime_night(base_date: datetime) -> datetime:
    """在凌晨 2:00~4:00 之间随机生成时间"""
    hour = random.randint(2, 3)
    minute = random.randint(0, 59)
    return base_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))


def generate_fraud_transactions(existing_df: pd.DataFrame) -> pd.DataFrame:
    """生成 50 条刷单交易并混入原始数据"""

    max_invoice = existing_df["Invoice"].astype(str).str.extract(r"(\d+)")[0].dropna().astype(int).max()
    base_date = datetime(2011, 11, 15)  # 数据集活跃时段

    fraud_rows: list[dict] = []
    invoice_counter = max_invoice + 1

    for ring_id in range(NUM_FRAUD_RINGS):
        ring_ip = SHARED_IPS[ring_id % len(SHARED_IPS)]
        ring_device = SHARED_DEVICES[ring_id % len(SHARED_DEVICES)]

        for acc_idx in range(ACCOUNTS_PER_RING):
            customer_id = f"FRAUD-{ring_id:02d}-{acc_idx:02d}"
            account_age = random.randint(1, 5)

            for _ in range(ORDERS_PER_ACCOUNT):
                order_time = _random_datetime_night(
                    base_date + timedelta(days=random.randint(0, 3))
                )
                qty = random.randint(50, 500)
                price = round(random.uniform(0.5, 5.0), 2)

                fraud_rows.append({
                    "Invoice": str(invoice_counter),
                    "StockCode": random.choice(FRAUD_SKUS),
                    "Description": random.choice(FRAUD_DESCRIPTIONS),
                    "Quantity": qty,
                    "InvoiceDate": order_time,
                    "Price": price,
                    "Customer ID": customer_id,
                    "Country": random.choice(["United Kingdom", "Germany", "France"]),
                    "IP_Address": ring_ip,
                    "Device_ID": ring_device if acc_idx < 2 else SHARED_DEVICES[(ring_id + 3) % len(SHARED_DEVICES)],
                    "Account_Age_Days": account_age,
                    "Is_Fraud": True,
                })
                invoice_counter += 1

    # 5 条独立异常 (非团伙, 但有可疑特征)
    for i in range(5):
        customer_id = f"FRAUD-SOLO-{i:02d}"
        order_time = _random_datetime_night(base_date + timedelta(days=random.randint(0, 2)))
        fraud_rows.append({
            "Invoice": str(invoice_counter),
            "StockCode": random.choice(FRAUD_SKUS),
            "Description": random.choice(FRAUD_DESCRIPTIONS),
            "Quantity": random.randint(200, 1000),
            "InvoiceDate": order_time,
            "Price": round(random.uniform(1.0, 10.0), 2),
            "Customer ID": customer_id,
            "Country": "United Kingdom",
            "IP_Address": SHARED_IPS[random.randint(0, len(SHARED_IPS) - 1)],
            "Device_ID": f"DEV-SOLO-{i:04d}",
            "Account_Age_Days": random.randint(1, 3),
            "Is_Fraud": True,
        })
        invoice_counter += 1

    fraud_df = pd.DataFrame(fraud_rows)

    # 为原始数据添加正常特征列
    normal_df = existing_df.copy()
    normal_df["IP_Address"] = [
        f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"
        for _ in range(len(normal_df))
    ]
    normal_df["Device_ID"] = [
        f"DEV-NORM-{random.randint(10000, 99999)}" for _ in range(len(normal_df))
    ]
    normal_df["Account_Age_Days"] = [
        random.randint(30, 1800) for _ in range(len(normal_df))
    ]
    normal_df["Is_Fraud"] = False

    combined = pd.concat([normal_df, fraud_df], ignore_index=True)
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)

    return combined


def run(input_xlsx: Path | None = None) -> Path:
    """执行异常注入, 返回处理后的 CSV 路径"""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PROCESSED_DIR / "transactions_with_fraud.csv"

    if output_path.exists():
        print(f"[数据层] 已注入数据集已存在: {output_path.name}")
        return output_path

    if input_xlsx is None:
        from data.download_dataset import download
        input_xlsx = download()

    print("[数据层] 读取原始数据集...")
    df = pd.read_excel(input_xlsx, sheet_name=0)
    print(f"[数据层] 原始记录数: {len(df):,}")

    print("[数据层] 注入 50 条刷单异常交易...")
    combined = generate_fraud_transactions(df)
    combined.to_csv(output_path, index=False)

    fraud_count = combined["Is_Fraud"].sum()
    print(f"[数据层] 注入完成: {fraud_count} 条异常 / {len(combined):,} 条总计")
    print(f"[数据层] 输出: {output_path}")

    return output_path


if __name__ == "__main__":
    run()
