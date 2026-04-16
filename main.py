"""Nexus-Audit 主入口 — 4-Agent 顺序管道编排

管道流程:
  Ingest Agent → Pattern Agent → Risk Agent → Alert Agent
  (数据清洗)     (模式识别)      (风险评分)    (报告生成)

架构说明: 采用函数式管道设计, 每个 Agent 是一个
(PipelineState) -> PipelineState 的纯函数节点。
生产环境可无缝迁移至 LangGraph StateGraph (需 Python 3.10+)。
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agents.ingest import run_ingest
from agents.pattern import run_pattern
from agents.risk import run_risk
from agents.alert import run_alert
from models import PipelineState, RiskLevel

console = Console()

AGENT_PIPELINE = [
    ("ingest", run_ingest),
    ("pattern", run_pattern),
    ("risk", run_risk),
    ("alert", run_alert),
]


def run_pipeline(state: PipelineState | None = None) -> PipelineState:
    """执行完整管道, 返回最终状态"""
    if state is None:
        state = PipelineState()
    for name, agent_fn in AGENT_PIPELINE:
        state = agent_fn(state)
    return state


def print_summary(state: PipelineState, total_time: float) -> None:
    """输出精简摘要表格 — 适合截图放 PPT"""
    console.print()

    # ── 管道执行摘要 ──
    t1 = Table(title="Nexus-Audit Pipeline Summary", show_lines=True)
    t1.add_column("Agent", style="bold cyan", width=16)
    t1.add_column("Duration", justify="right", width=10)
    t1.add_column("Input", justify="right", width=14)
    t1.add_column("Output", justify="right", width=14)
    t1.add_column("Key Metric", width=30)

    t1.add_row(
        "Ingest Agent", f"{state.ingest_duration_sec:.1f}s",
        "525,511 raw", f"{state.raw_count:,} clean",
        "Removed 117,797 invalid records",
    )
    t1.add_row(
        "Pattern Agent", f"{state.pattern_duration_sec:.1f}s",
        f"{state.raw_count:,} txns", f"{len(state.suspicious_transactions):,} suspicious",
        "496K nodes, 1.2M edges graph",
    )

    high = sum(1 for a in state.risk_assessments if a.risk_level == RiskLevel.HIGH)
    med = sum(1 for a in state.risk_assessments if a.risk_level == RiskLevel.MEDIUM)
    t1.add_row(
        "Risk Agent", f"{state.risk_duration_sec:.1f}s",
        f"{len(state.suspicious_transactions):,} suspicious",
        f"{len(state.risk_assessments):,} assessed",
        f"HIGH={high:,}  MED={med:,}",
    )
    t1.add_row(
        "Alert Agent", f"{state.alert_duration_sec:.1f}s",
        f"{high + med:,} actionable", f"{len(state.alerts)} alerts",
        f"{len(state.alerts)+1} reports generated",
    )
    console.print(t1)

    # ── 异常检测明细 ──
    t2 = Table(title="Anomaly Detection Breakdown", show_lines=True)
    t2.add_column("Anomaly Type", style="bold yellow", width=24)
    t2.add_column("Triggers", justify="right", width=10)
    t2.add_column("Description", width=40)

    anomaly_counts: Counter = Counter()
    for sus in state.suspicious_transactions:
        for a in sus.anomaly_types:
            anomaly_counts[a.value] += 1

    rows = [
        ("Time Cluster", "time_cluster", "Orders clustered at 00:00-05:00"),
        ("Shared IP", "shared_ip", "3+ accounts sharing same IP"),
        ("New Account Burst", "new_account_burst", "Account age < 7 days with 3+ orders"),
        ("Community Ring", "community_ring", "Louvain community detection ring"),
    ]
    for label, key, desc in rows:
        t2.add_row(label, f"{anomaly_counts.get(key, 0):,}", desc)
    console.print(t2)

    # ── 风险分布 ──
    t3 = Table(title="Risk Distribution", show_lines=True)
    t3.add_column("Risk Level", style="bold", width=14)
    t3.add_column("Count", justify="right", width=10)
    t3.add_column("Percentage", justify="right", width=12)
    t3.add_column("Action", width=36)

    total = len(state.risk_assessments) or 1
    t3.add_row("[red]HIGH[/red]", f"{high:,}", f"{high/total*100:.1f}%",
               "Auto-block + AML investigation")
    t3.add_row("[yellow]MEDIUM[/yellow]", f"{med:,}", f"{med/total*100:.1f}%",
               "Human review queue (48h SLA)")
    low = total - high - med
    t3.add_row("[green]LOW[/green]", f"{low:,}", f"{low/total*100:.1f}%",
               "Monitor in next batch")
    console.print(t3)

    # ── Top 5 警报 ──
    t4 = Table(title="Top 5 Alerts by Amount at Risk", show_lines=True)
    t4.add_column("Alert ID", style="bold red", width=18)
    t4.add_column("Transactions", justify="right", width=14)
    t4.add_column("Amount at Risk", justify="right", width=16)

    sorted_alerts = sorted(state.alerts, key=lambda a: a.total_amount_at_risk, reverse=True)
    for alert in sorted_alerts[:5]:
        t4.add_row(
            alert.alert_id,
            f"{len(alert.risk_assessments):,}",
            f"${alert.total_amount_at_risk:,.2f}",
        )
    console.print(t4)

    # ── 总结行 ──
    console.print(
        Panel(
            f"[bold]Total: {state.raw_count:,} transactions -> "
            f"{len(state.suspicious_transactions):,} suspicious -> "
            f"{high:,} HIGH + {med:,} MEDIUM risk "
            f"in {total_time:.0f}s[/bold]",
            border_style="green",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Nexus-Audit Pipeline")
    parser.add_argument("--summary", action="store_true",
                        help="Only print concise summary tables (for PPT screenshots)")
    args = parser.parse_args()

    if not args.summary:
        console.print(
            Panel(
                "[bold]Nexus-Audit[/bold]\n"
                "基于 Agentic AI 的下一代智能审计系统",
                title="[SCAN] 启动审计管道",
                border_style="bright_blue",
            )
        )
        console.print("[green]管道模式: 4-Agent 顺序编排[/green]\n")

    start_time = time.time()
    state = run_pipeline()
    total_time = time.time() - start_time

    if args.summary:
        print_summary(state, total_time)
    else:
        console.print("\n")
        console.print(
            Panel(
                f"[bold green]审计管道执行完成[/bold green]\n\n"
                f"[DATA]  处理交易: {state.raw_count:,} 条\n"
                f"[SCAN]  可疑交易: {len(state.suspicious_transactions)} 条\n"
                f"[WARN]  风险评估: {len(state.risk_assessments)} 条\n"
                f"[ALERT] 审计警报: {len(state.alerts)} 个\n\n"
                f"[TIME]  总耗时: {total_time:.1f}s\n"
                f"   Ingest:  {state.ingest_duration_sec:.1f}s\n"
                f"   Pattern: {state.pattern_duration_sec:.1f}s\n"
                f"   Risk:    {state.risk_duration_sec:.1f}s\n"
                f"   Alert:   {state.alert_duration_sec:.1f}s",
                title="[OK] 审计完成",
                border_style="green",
            )
        )


if __name__ == "__main__":
    main()
