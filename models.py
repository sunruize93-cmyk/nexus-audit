"""Pydantic 数据模型 — Agent 间标准化数据传递"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Ingest Agent 输出 ────────────────────────────────────────────────

class CleanTransaction(BaseModel):
    """清洗后的标准化交易记录"""
    invoice_no: str
    stock_code: str
    description: str
    quantity: int
    invoice_date: datetime
    unit_price: float
    customer_id: str
    country: str
    # 注入的跨境特征
    ip_address: Optional[str] = None
    device_id: Optional[str] = None
    account_age_days: Optional[int] = None
    total_amount: float = 0.0


# ── Pattern Agent 输出 ───────────────────────────────────────────────

class AnomalyType(str, Enum):
    TIME_CLUSTER = "time_cluster"
    SHARED_IP = "shared_ip"
    NEW_ACCOUNT_BURST = "new_account_burst"
    COMMUNITY_RING = "community_ring"


class SuspiciousTransaction(BaseModel):
    """被标记为可疑的交易"""
    transaction: CleanTransaction
    anomaly_types: list[AnomalyType] = Field(default_factory=list)
    anomaly_score: float = Field(ge=0.0, le=1.0, description="综合异常分 0~1")
    related_transactions: list[str] = Field(
        default_factory=list, description="关联交易的 invoice_no 列表"
    )
    community_id: Optional[int] = None


# ── Risk Agent 输出 ──────────────────────────────────────────────────

class RiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskAssessment(BaseModel):
    """风险评估结果"""
    transaction: SuspiciousTransaction
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="LLM 的 CoT 推理链")
    recommended_action: str = ""


# ── Alert Agent 输出 ─────────────────────────────────────────────────

class AuditAlert(BaseModel):
    """审计警报"""
    alert_id: str
    risk_assessments: list[RiskAssessment]
    community_summary: Optional[str] = None
    total_amount_at_risk: float = 0.0
    report_markdown: str = ""


# ── Pipeline 状态 ────────────────────────────────────────────────────

class PipelineState(BaseModel):
    """LangGraph 状态: 在 Agent 之间传递的全局状态"""
    raw_count: int = 0
    clean_transactions: list[CleanTransaction] = Field(default_factory=list)
    suspicious_transactions: list[SuspiciousTransaction] = Field(default_factory=list)
    risk_assessments: list[RiskAssessment] = Field(default_factory=list)
    alerts: list[AuditAlert] = Field(default_factory=list)
    # 统计指标
    ingest_duration_sec: float = 0.0
    pattern_duration_sec: float = 0.0
    risk_duration_sec: float = 0.0
    alert_duration_sec: float = 0.0
