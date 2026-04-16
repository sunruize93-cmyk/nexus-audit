"""Nexus-Audit 全局配置 — 所有可调参数集中管理"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── Paths ────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
DATA_RAW_DIR = ROOT_DIR / "data" / "raw"
DATA_PROCESSED_DIR = ROOT_DIR / "data" / "processed"
OUTPUT_DIR = ROOT_DIR / "output"
DB_PATH = ROOT_DIR / "nexus_audit.db"

# ── OpenAI ───────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── Ingest Agent 参数 ────────────────────────────────────────────────
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))

# ── Pattern Agent 参数 ───────────────────────────────────────────────
TIME_CLUSTER_WINDOW_HOURS = float(os.getenv("TIME_CLUSTER_WINDOW_HOURS", "2"))
TIME_CLUSTER_MIN_ORDERS = int(os.getenv("TIME_CLUSTER_MIN_ORDERS", "5"))
SHARED_IP_THRESHOLD = int(os.getenv("SHARED_IP_THRESHOLD", "3"))
NEW_ACCOUNT_DAYS = int(os.getenv("NEW_ACCOUNT_DAYS", "7"))

# ── Risk Agent 参数 ──────────────────────────────────────────────────
RISK_HIGH_THRESHOLD = float(os.getenv("RISK_HIGH_THRESHOLD", "0.8"))
RISK_MEDIUM_THRESHOLD = float(os.getenv("RISK_MEDIUM_THRESHOLD", "0.5"))

# ── Graph 参数 ───────────────────────────────────────────────────────
LOUVAIN_RESOLUTION = float(os.getenv("LOUVAIN_RESOLUTION", "1.0"))
MIN_COMMUNITY_SIZE = int(os.getenv("MIN_COMMUNITY_SIZE", "3"))
