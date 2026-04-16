"""下载 UCI Online Retail II 数据集"""

from __future__ import annotations

import urllib.request
from pathlib import Path

DATA_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
RAW_DIR = Path(__file__).parent / "raw"


def download() -> Path:
    """下载并解压数据集，返回 Excel 文件路径"""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / "online_retail_ii.zip"

    xlsx_candidates = list(RAW_DIR.glob("*.xlsx"))
    if xlsx_candidates:
        print(f"[数据层] 数据集已存在: {xlsx_candidates[0].name}")
        return xlsx_candidates[0]

    print("[数据层] 正在下载 UCI Online Retail II 数据集...")
    urllib.request.urlretrieve(DATA_URL, zip_path)
    print(f"[数据层] 下载完成: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")

    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(RAW_DIR)
    zip_path.unlink()

    xlsx_files = list(RAW_DIR.glob("*.xlsx"))
    if not xlsx_files:
        raise FileNotFoundError("解压后未找到 .xlsx 文件")

    print(f"[数据层] 解压完成: {xlsx_files[0].name}")
    return xlsx_files[0]


if __name__ == "__main__":
    download()
