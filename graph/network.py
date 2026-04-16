"""图网络分析 — 构建异构交易关系图 + Louvain 社区发现

节点类型: Customer / Device / IP_Address
边类型: customer→device (使用), customer→ip (来源), device→ip (关联)

通过 Louvain 社区发现算法识别紧密关联的刷单团伙。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import community as community_louvain  # python-louvain
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import networkx as nx
import numpy as np

# 尝试使用系统中文字体
for font_name in ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "sans-serif"]:
    if any(font_name.lower() in f.name.lower() for f in fm.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [font_name]
        plt.rcParams["axes.unicode_minus"] = False
        break

from config import LOUVAIN_RESOLUTION, MIN_COMMUNITY_SIZE
from models import CleanTransaction


def build_transaction_graph(
    transactions: list[CleanTransaction],
) -> nx.Graph:
    """从交易记录构建异构关系图"""
    G = nx.Graph()

    for txn in transactions:
        cust_node = f"C:{txn.customer_id}"
        G.add_node(cust_node, node_type="customer")

        if txn.ip_address:
            ip_node = f"IP:{txn.ip_address}"
            G.add_node(ip_node, node_type="ip")
            if G.has_edge(cust_node, ip_node):
                G[cust_node][ip_node]["weight"] += 1
            else:
                G.add_edge(cust_node, ip_node, weight=1, edge_type="uses_ip")

        if txn.device_id:
            dev_node = f"D:{txn.device_id}"
            G.add_node(dev_node, node_type="device")
            if G.has_edge(cust_node, dev_node):
                G[cust_node][dev_node]["weight"] += 1
            else:
                G.add_edge(cust_node, dev_node, weight=1, edge_type="uses_device")

            if txn.ip_address:
                ip_node = f"IP:{txn.ip_address}"
                if G.has_edge(dev_node, ip_node):
                    G[dev_node][ip_node]["weight"] += 1
                else:
                    G.add_edge(dev_node, ip_node, weight=1, edge_type="device_ip")

    return G


def detect_communities(G: nx.Graph) -> dict[str, int]:
    """Louvain 社区发现, 返回 {node: community_id}"""
    if len(G) == 0:
        return {}
    partition = community_louvain.best_partition(
        G, resolution=LOUVAIN_RESOLUTION, random_state=42
    )
    return partition


def get_suspicious_communities(
    partition: dict[str, int],
) -> dict[int, list[str]]:
    """筛选出 size ≥ 阈值 的可疑社区"""
    communities: dict[int, list[str]] = defaultdict(list)
    for node, comm_id in partition.items():
        communities[comm_id].append(node)

    return {
        cid: members
        for cid, members in communities.items()
        if len(members) >= MIN_COMMUNITY_SIZE
    }


def get_community_stats(
    G: nx.Graph, partition: dict[str, int]
) -> list[dict[str, Any]]:
    """返回每个可疑社区的统计信息"""
    suspicious = get_suspicious_communities(partition)
    stats = []
    for cid, members in suspicious.items():
        subgraph = G.subgraph(members)
        customers = [n for n in members if n.startswith("C:")]
        ips = [n for n in members if n.startswith("IP:")]
        devices = [n for n in members if n.startswith("D:")]
        stats.append({
            "community_id": cid,
            "size": len(members),
            "customers": len(customers),
            "ips": len(ips),
            "devices": len(devices),
            "edges": subgraph.number_of_edges(),
            "density": nx.density(subgraph) if len(subgraph) > 1 else 0,
            "member_list": members,
        })
    return sorted(stats, key=lambda x: x["density"], reverse=True)


def visualize_graph(
    G: nx.Graph,
    partition: dict[str, int],
    output_path: str = "output/network_graph.png",
    title: str = "交易关联网络 — 团伙社区发现",
) -> str:
    """生成网络图可视化, 返回文件路径"""
    suspicious = get_suspicious_communities(partition)
    suspicious_nodes = set()
    for members in suspicious.values():
        suspicious_nodes.update(members)

    if not suspicious_nodes:
        suspicious_nodes = set(list(G.nodes())[:50])

    # 限制可视化节点数, 避免大图内存爆炸
    MAX_VIS_NODES = 200
    if len(suspicious_nodes) > MAX_VIS_NODES:
        sorted_comms = sorted(suspicious.items(), key=lambda x: len(x[1]), reverse=True)
        suspicious_nodes = set()
        for _, members in sorted_comms:
            suspicious_nodes.update(members)
            if len(suspicious_nodes) >= MAX_VIS_NODES:
                break

    sub_G = G.subgraph(suspicious_nodes)

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))

    color_map = {
        "customer": "#FF6B6B",
        "ip": "#4ECDC4",
        "device": "#FFE66D",
    }
    node_colors = [
        color_map.get(sub_G.nodes[n].get("node_type", ""), "#CCCCCC")
        for n in sub_G.nodes()
    ]

    comm_colors_raw = plt.cm.Set3(np.linspace(0, 1, max(len(suspicious), 1)))
    edge_colors = []
    for u, v in sub_G.edges():
        u_comm = partition.get(u, -1)
        v_comm = partition.get(v, -1)
        if u_comm == v_comm and u_comm in suspicious:
            idx = list(suspicious.keys()).index(u_comm) % len(comm_colors_raw)
            edge_colors.append(comm_colors_raw[idx])
        else:
            edge_colors.append((0.7, 0.7, 0.7, 0.3))

    pos = nx.kamada_kawai_layout(sub_G) if len(sub_G) < 100 else nx.shell_layout(sub_G)
    nx.draw_networkx_edges(sub_G, pos, edge_color=edge_colors, width=1.5, ax=ax)
    nx.draw_networkx_nodes(
        sub_G, pos, node_color=node_colors, node_size=200, alpha=0.9, ax=ax
    )

    labels = {}
    for n in sub_G.nodes():
        if n.startswith("C:") and "FRAUD" in n:
            labels[n] = n.replace("C:", "")
        elif n.startswith("IP:") and any(
            n in members for members in suspicious.values()
        ):
            labels[n] = n.replace("IP:", "")
    nx.draw_networkx_labels(sub_G, pos, labels, font_size=7, ax=ax)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF6B6B",
               markersize=10, label="Customer"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#4ECDC4",
               markersize=10, label="IP Address"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#FFE66D",
               markersize=10, label="Device"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()
    from pathlib import Path as P
    P(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()

    return output_path
