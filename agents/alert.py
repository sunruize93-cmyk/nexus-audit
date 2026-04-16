"""Alert Agent — 审计报告生成与团伙图谱输出

痛点: 审计报告撰写耗时, 格式不统一, 关键信息容易遗漏。
方案: 自动聚合风险评估结果, 按社区/团伙分组生成结构化 Markdown 报告,
      附带关联网络可视化图谱。
效果: 报告生成从人工 2 小时 → 自动 10 秒, 格式标准化, 可追溯。
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from rich.console import Console

from config import OUTPUT_DIR
from graph.network import visualize_graph
from models import (
    AuditAlert,
    PipelineState,
    RiskAssessment,
    RiskLevel,
)

console = Console()


def _group_by_community(
    assessments: list[RiskAssessment],
) -> dict[int | None, list[RiskAssessment]]:
    groups: dict[int | None, list[RiskAssessment]] = defaultdict(list)
    for a in assessments:
        groups[a.transaction.community_id].append(a)
    return dict(groups)


def _generate_report_markdown(
    alert: AuditAlert, community_assessments: list[RiskAssessment]
) -> str:
    """生成单个审计警报的 Markdown 报告"""
    lines = [
        f"# 审计警报报告 {alert.alert_id}",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 风险概览",
        f"- **涉及交易数**: {len(alert.risk_assessments)}",
        f"- **风险金额合计**: ${alert.total_amount_at_risk:,.2f}",
        "",
        "| 风险等级 | 数量 |",
        "|---------|------|",
    ]

    level_counts = defaultdict(int)
    for a in alert.risk_assessments:
        level_counts[a.risk_level.value] += 1
    for level in ["high", "medium", "low"]:
        lines.append(f"| {level.upper()} | {level_counts.get(level, 0)} |")

    lines.extend(["", "## 高风险交易详情", ""])

    high_risk = [a for a in community_assessments if a.risk_level == RiskLevel.HIGH]
    for a in high_risk[:10]:
        txn = a.transaction.transaction
        lines.extend([
            f"### 发票 {txn.invoice_no}",
            f"- **客户**: {txn.customer_id} | **国家**: {txn.country}",
            f"- **金额**: ${txn.total_amount:,.2f} | **时间**: {txn.invoice_date}",
            f"- **IP**: {txn.ip_address} | **设备**: {txn.device_id}",
            f"- **账户年龄**: {txn.account_age_days} 天",
            f"- **异常类型**: {', '.join(a.value for a in a.transaction.anomaly_types)}",
            f"- **风险评分**: {a.risk_score:.2f}",
            f"- **AI推理**: {a.reasoning}",
            f"- **建议措施**: {a.recommended_action}",
            "",
        ])

    if alert.community_summary:
        lines.extend(["## 团伙分析", "", alert.community_summary, ""])

    lines.extend([
        "## 审计建议",
        "",
        "1. 对高风险交易立即冻结相关账户",
        "2. 对关联社区内所有账户进行交叉审查",
        "3. 将共享IP和设备加入黑名单",
        "4. 更新风控规则, 降低凌晨时段大额交易阈值",
        "",
        "---",
        "*本报告由 Nexus-Audit AI 系统自动生成*",
    ])

    return "\n".join(lines)


def run_alert(state: PipelineState) -> PipelineState:
    """Alert Agent 入口"""
    console.print("\n[bold red]═══ Alert Agent 启动 ═══[/bold red]")
    start = time.time()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assessments = state.risk_assessments

    actionable = [a for a in assessments if a.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM)]
    console.print(f"  需处置: {len(actionable)} 笔 (高+中风险)")

    groups = _group_by_community(actionable)

    alerts: list[AuditAlert] = []
    # 限制报告数量: 按团伙大小排序, 取 top 20
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)[:20]
    for comm_id, group_assessments in sorted_groups:
        alert_id = f"ALERT-{uuid.uuid4().hex[:8].upper()}"
        total_risk = sum(
            a.transaction.transaction.total_amount for a in group_assessments
        )

        community_summary = None
        if comm_id is not None:
            customers = set()
            ips = set()
            devices = set()
            for a in group_assessments:
                t = a.transaction.transaction
                customers.add(t.customer_id)
                if t.ip_address:
                    ips.add(t.ip_address)
                if t.device_id:
                    devices.add(t.device_id)
            community_summary = (
                f"**团伙 #{comm_id}**: {len(customers)} 个账户共享 "
                f"{len(ips)} 个IP和 {len(devices)} 台设备, "
                f"总涉案金额 ${total_risk:,.2f}"
            )

        alert = AuditAlert(
            alert_id=alert_id,
            risk_assessments=group_assessments,
            community_summary=community_summary,
            total_amount_at_risk=total_risk,
        )
        alert.report_markdown = _generate_report_markdown(alert, group_assessments)
        alerts.append(alert)

        report_path = OUTPUT_DIR / f"{alert_id}.md"
        report_path.write_text(alert.report_markdown, encoding="utf-8")

    # 生成网络图可视化
    G = state.__dict__.get("_graph")
    partition = state.__dict__.get("_partition")
    if G and partition:
        graph_path = str(OUTPUT_DIR / "network_graph.png")
        visualize_graph(G, partition, output_path=graph_path)
        console.print(f"  [green]团伙关系图谱已保存: {graph_path}[/green]")

    # 生成汇总报告
    summary_lines = [
        "# Nexus-Audit 审计汇总报告",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 管道运行统计",
        f"- 原始交易数: {state.raw_count:,}",
        f"- 可疑交易数: {len(state.suspicious_transactions)}",
        f"- 警报数: {len(alerts)}",
        "",
        "## 耗时统计",
        f"- Ingest: {state.ingest_duration_sec:.1f}s",
        f"- Pattern: {state.pattern_duration_sec:.1f}s",
        f"- Risk: {state.risk_duration_sec:.1f}s",
        f"- Alert: {time.time() - start:.1f}s",
        f"- **总计**: {state.ingest_duration_sec + state.pattern_duration_sec + state.risk_duration_sec + (time.time() - start):.1f}s",
        "",
        "## 风险分布",
    ]
    high = sum(1 for a in assessments if a.risk_level == RiskLevel.HIGH)
    med = sum(1 for a in assessments if a.risk_level == RiskLevel.MEDIUM)
    low = sum(1 for a in assessments if a.risk_level == RiskLevel.LOW)
    summary_lines.extend([
        f"- 高风险: {high}",
        f"- 中风险: {med}",
        f"- 低风险: {low}",
        "",
        "## 各警报详情",
    ])
    for alert in alerts:
        summary_lines.append(
            f"- [{alert.alert_id}] 涉案 ${alert.total_amount_at_risk:,.2f}, "
            f"{len(alert.risk_assessments)} 笔交易"
        )

    summary_path = OUTPUT_DIR / "SUMMARY_REPORT.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    elapsed = time.time() - start
    state.alerts = alerts
    state.alert_duration_sec = round(elapsed, 2)

    console.print(
        f"[bold red]✓ Alert 完成[/bold red]: "
        f"生成 {len(alerts)} 个警报, {len(alerts)+1} 份报告, "
        f"耗时 {elapsed:.1f}s"
    )
    console.print(f"  [green]报告输出目录: {OUTPUT_DIR}[/green]")
    return state
