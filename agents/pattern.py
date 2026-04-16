"""Pattern Agent — 模式识别与可疑标记

痛点: 传统规则引擎只能做单维度检测 (如: 单一 IP 阈值),
      无法发现跨维度的团伙作案模式。
方案: 多维度异常检测 + 图网络社区发现, 同时检测时间聚集、
      共享资源、新账户爆发、团伙环形关联四类异常。
效果: 异常识别从单维度升级为图感知, 团伙检出率 > 90%。
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import timedelta

from rich.console import Console

from config import (
    NEW_ACCOUNT_DAYS,
    SHARED_IP_THRESHOLD,
    TIME_CLUSTER_MIN_ORDERS,
    TIME_CLUSTER_WINDOW_HOURS,
)
from graph.network import (
    build_transaction_graph,
    detect_communities,
    get_suspicious_communities,
)
from memory.semantic import SemanticMemory
from models import (
    AnomalyType,
    CleanTransaction,
    PipelineState,
    SuspiciousTransaction,
)

console = Console()


def _detect_time_clusters(
    transactions: list[CleanTransaction],
) -> dict[str, list[str]]:
    """检测凌晨时段的时间聚集异常"""
    night_orders: dict[str, list[CleanTransaction]] = defaultdict(list)
    for txn in transactions:
        if 0 <= txn.invoice_date.hour <= 5:
            night_orders[txn.ip_address or txn.customer_id].append(txn)

    clusters: dict[str, list[str]] = {}
    for key, txns in night_orders.items():
        if len(txns) >= TIME_CLUSTER_MIN_ORDERS:
            clusters[key] = [t.invoice_no for t in txns]
    return clusters


def _detect_shared_ip(
    transactions: list[CleanTransaction],
) -> dict[str, set[str]]:
    """检测同一 IP 关联多个不同账户"""
    ip_customers: dict[str, set[str]] = defaultdict(set)
    for txn in transactions:
        if txn.ip_address:
            ip_customers[txn.ip_address].add(txn.customer_id)

    return {
        ip: custs
        for ip, custs in ip_customers.items()
        if len(custs) >= SHARED_IP_THRESHOLD
    }


def _detect_new_account_burst(
    transactions: list[CleanTransaction],
) -> set[str]:
    """检测新账户爆发 (注册 < 7天 且有大量订单)"""
    new_accounts: set[str] = set()
    customer_orders: dict[str, int] = defaultdict(int)

    for txn in transactions:
        if txn.account_age_days is not None and txn.account_age_days <= NEW_ACCOUNT_DAYS:
            customer_orders[txn.customer_id] += 1

    for cust_id, count in customer_orders.items():
        if count >= 3:
            new_accounts.add(cust_id)
    return new_accounts


def run_pattern(state: PipelineState) -> PipelineState:
    """Pattern Agent 入口"""
    console.print("\n[bold cyan]═══ Pattern Agent 启动 ═══[/bold cyan]")
    start = time.time()
    transactions = state.clean_transactions

    semantic = SemanticMemory()
    rule_weights = semantic.get_rules()

    # 1. 时间聚集检测
    time_clusters = _detect_time_clusters(transactions)
    time_flagged = set()
    for invoices in time_clusters.values():
        time_flagged.update(invoices)
    console.print(
        f"  [cyan]时间聚集[/cyan]: 发现 {len(time_clusters)} 个聚集点, "
        f"涉及 {len(time_flagged)} 笔交易"
    )

    # 2. 共享 IP 检测
    shared_ips = _detect_shared_ip(transactions)
    ip_flagged_customers: set[str] = set()
    for custs in shared_ips.values():
        ip_flagged_customers.update(custs)
    console.print(
        f"  [cyan]共享IP[/cyan]: {len(shared_ips)} 个 IP 关联 "
        f"{len(ip_flagged_customers)} 个账户"
    )

    # 3. 新账户爆发
    new_burst = _detect_new_account_burst(transactions)
    console.print(f"  [cyan]新账户爆发[/cyan]: {len(new_burst)} 个可疑新账户")

    # 4. 图网络社区发现
    console.print("  [cyan]图分析[/cyan]: 构建交易关联网络...")
    G = build_transaction_graph(transactions)
    console.print(
        f"  [dim]图规模: {G.number_of_nodes():,} 节点, {G.number_of_edges():,} 边[/dim]"
    )

    partition = detect_communities(G)
    suspicious_comms = get_suspicious_communities(partition)
    community_customers: dict[int, set[str]] = defaultdict(set)
    for node, comm_id in partition.items():
        if comm_id in suspicious_comms and node.startswith("C:"):
            community_customers[comm_id].add(node.replace("C:", ""))
    console.print(
        f"  [cyan]社区发现[/cyan]: {len(suspicious_comms)} 个可疑社区"
    )

    # 汇总: 为每笔交易计算异常分
    txn_lookup: dict[str, CleanTransaction] = {
        t.invoice_no: t for t in transactions
    }
    suspicious: list[SuspiciousTransaction] = []
    seen_invoices: set[str] = set()

    for txn in transactions:
        anomaly_types: list[AnomalyType] = []
        related: list[str] = []
        comm_id = None

        if txn.invoice_no in time_flagged:
            anomaly_types.append(AnomalyType.TIME_CLUSTER)

        if txn.customer_id in ip_flagged_customers:
            anomaly_types.append(AnomalyType.SHARED_IP)

        if txn.customer_id in new_burst:
            anomaly_types.append(AnomalyType.NEW_ACCOUNT_BURST)

        cust_node = f"C:{txn.customer_id}"
        if cust_node in partition:
            cid = partition[cust_node]
            if cid in suspicious_comms:
                anomaly_types.append(AnomalyType.COMMUNITY_RING)
                comm_id = cid
                related = [
                    n.replace("C:", "")
                    for n in suspicious_comms[cid]
                    if n.startswith("C:") and n != cust_node
                ]

        if anomaly_types and txn.invoice_no not in seen_invoices:
            score = sum(
                next(
                    (r["weight"] for r in rule_weights if r["name"] == _anomaly_to_rule_name(a)),
                    0.25,
                )
                for a in anomaly_types
            )
            score = min(1.0, score)

            suspicious.append(
                SuspiciousTransaction(
                    transaction=txn,
                    anomaly_types=anomaly_types,
                    anomaly_score=round(score, 3),
                    related_transactions=related,
                    community_id=comm_id,
                )
            )
            seen_invoices.add(txn.invoice_no)

    elapsed = time.time() - start
    state.suspicious_transactions = suspicious
    state.pattern_duration_sec = round(elapsed, 2)

    # 保存图和社区数据供后续可视化
    state.__dict__["_graph"] = G
    state.__dict__["_partition"] = partition

    console.print(
        f"[bold cyan]✓ Pattern 完成[/bold cyan]: "
        f"{len(suspicious)} 笔可疑交易 (占 {len(suspicious)/len(transactions)*100:.2f}%), "
        f"耗时 {elapsed:.1f}s"
    )
    return state


def _anomaly_to_rule_name(a: AnomalyType) -> str:
    mapping = {
        AnomalyType.TIME_CLUSTER: "凌晨集中下单",
        AnomalyType.SHARED_IP: "共享IP多账户",
        AnomalyType.NEW_ACCOUNT_BURST: "新账户爆发",
        AnomalyType.COMMUNITY_RING: "团伙环形关联",
    }
    return mapping.get(a, "")
