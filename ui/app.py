"""Nexus-Audit Streamlit Dashboard

交互式审计仪表盘, 支持:
- 一键运行完整管道
- 风险分布可视化
- 交易网络图谱展示
- 审计报告查看
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_DIR, DATA_PROCESSED_DIR
from models import PipelineState, RiskLevel

st.set_page_config(
    page_title="Nexus-Audit | 智能审计系统",
    page_icon="🔍",
    layout="wide",
)


def run_pipeline() -> PipelineState:
    """执行完整管道"""
    from agents.ingest import run_ingest
    from agents.pattern import run_pattern
    from agents.risk import run_risk
    from agents.alert import run_alert

    state = PipelineState()
    with st.spinner("Ingest Agent 数据清洗中..."):
        state = run_ingest(state)
    with st.spinner("Pattern Agent 模式识别中..."):
        state = run_pattern(state)
    with st.spinner("Risk Agent 风险评估中..."):
        state = run_risk(state)
    with st.spinner("Alert Agent 报告生成中..."):
        state = run_alert(state)
    return state


def render_header():
    st.title("🔍 Nexus-Audit")
    st.markdown("**基于 Agentic AI 的下一代智能审计系统及主动风险防御体系**")
    st.markdown("---")


def render_metrics(state: PipelineState):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📊 总交易", f"{state.raw_count:,}")
    col2.metric("🔎 可疑交易", f"{len(state.suspicious_transactions)}")

    high = sum(1 for a in state.risk_assessments if a.risk_level == RiskLevel.HIGH)
    med = sum(1 for a in state.risk_assessments if a.risk_level == RiskLevel.MEDIUM)

    col3.metric("🔴 高风险", str(high))
    col4.metric("🟡 中风险", str(med))

    total_time = (
        state.ingest_duration_sec
        + state.pattern_duration_sec
        + state.risk_duration_sec
        + state.alert_duration_sec
    )
    col5.metric("⏱ 总耗时", f"{total_time:.1f}s")


def render_risk_distribution(state: PipelineState):
    st.subheader("风险分布")
    col1, col2 = st.columns(2)

    with col1:
        levels = [a.risk_level.value for a in state.risk_assessments]
        df = pd.DataFrame({"risk_level": levels})
        counts = df["risk_level"].value_counts().reindex(["high", "medium", "low"], fill_value=0)
        fig = px.pie(
            names=["高风险", "中风险", "低风险"],
            values=counts.values,
            color_discrete_sequence=["#FF4444", "#FFB347", "#77DD77"],
            title="风险等级分布",
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        scores = [a.risk_score for a in state.risk_assessments]
        fig = px.histogram(
            x=scores,
            nbins=20,
            title="风险评分分布",
            labels={"x": "风险评分", "y": "数量"},
            color_discrete_sequence=["#4ECDC4"],
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)


def render_anomaly_breakdown(state: PipelineState):
    st.subheader("异常类型分析")
    from collections import Counter
    all_anomalies = []
    for sus in state.suspicious_transactions:
        all_anomalies.extend([a.value for a in sus.anomaly_types])

    counter = Counter(all_anomalies)
    labels_map = {
        "time_cluster": "凌晨集中下单",
        "shared_ip": "共享IP多账户",
        "new_account_burst": "新账户爆发",
        "community_ring": "团伙环形关联",
    }
    fig = px.bar(
        x=[labels_map.get(k, k) for k in counter.keys()],
        y=list(counter.values()),
        title="各类异常触发次数",
        labels={"x": "异常类型", "y": "触发次数"},
        color_discrete_sequence=["#FF6B6B", "#4ECDC4", "#FFE66D", "#C9B1FF"],
    )
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


def render_pipeline_timing(state: PipelineState):
    st.subheader("管道耗时分析")
    fig = go.Figure(go.Bar(
        x=[state.ingest_duration_sec, state.pattern_duration_sec,
           state.risk_duration_sec, state.alert_duration_sec],
        y=["Ingest Agent", "Pattern Agent", "Risk Agent", "Alert Agent"],
        orientation="h",
        marker_color=["#4ECDC4", "#45B7D1", "#FFB347", "#FF6B6B"],
    ))
    fig.update_layout(
        title="各 Agent 执行耗时 (秒)",
        xaxis_title="耗时 (s)",
        height=300,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_network_graph():
    st.subheader("交易关联网络 — 团伙社区发现")
    graph_path = OUTPUT_DIR / "network_graph.png"
    if graph_path.exists():
        st.image(str(graph_path), use_container_width=True)
    else:
        st.info("运行管道后将在此显示团伙关联网络图")


def render_high_risk_table(state: PipelineState):
    st.subheader("高风险交易明细")
    high_risk = [a for a in state.risk_assessments if a.risk_level == RiskLevel.HIGH]
    if not high_risk:
        st.info("未发现高风险交易")
        return

    rows = []
    for a in high_risk:
        txn = a.transaction.transaction
        rows.append({
            "发票号": txn.invoice_no,
            "客户ID": txn.customer_id,
            "国家": txn.country,
            "金额": f"${txn.total_amount:,.2f}",
            "时间": txn.invoice_date.strftime("%Y-%m-%d %H:%M"),
            "IP": txn.ip_address or "-",
            "风险评分": f"{a.risk_score:.2f}",
            "异常类型": ", ".join(at.value for at in a.transaction.anomaly_types),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=400)


def render_reports():
    st.subheader("审计报告")
    reports = list(OUTPUT_DIR.glob("ALERT-*.md"))
    summary = OUTPUT_DIR / "SUMMARY_REPORT.md"

    if summary.exists():
        with st.expander("📋 汇总报告", expanded=True):
            st.markdown(summary.read_text(encoding="utf-8"))

    for report in reports:
        with st.expander(f"📄 {report.stem}"):
            st.markdown(report.read_text(encoding="utf-8"))


def main():
    render_header()

    if "pipeline_state" not in st.session_state:
        st.session_state.pipeline_state = None

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("▶ 运行审计管道", type="primary", use_container_width=True):
            start = time.time()
            state = run_pipeline()
            st.session_state.pipeline_state = state
            st.success(f"管道执行完成! 耗时 {time.time()-start:.1f}s")
            st.rerun()

    state = st.session_state.pipeline_state

    if state is None:
        st.info("👆 点击上方按钮启动审计管道")

        csv_path = DATA_PROCESSED_DIR / "transactions_with_fraud.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, nrows=100)
            st.subheader("数据预览 (前100行)")
            st.dataframe(df, use_container_width=True)
        return

    render_metrics(state)
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 风险分析", "🌐 网络图谱", "📋 审计报告", "⏱ 性能统计"]
    )

    with tab1:
        render_risk_distribution(state)
        render_anomaly_breakdown(state)
        render_high_risk_table(state)

    with tab2:
        render_network_graph()

    with tab3:
        render_reports()

    with tab4:
        render_pipeline_timing(state)

        st.subheader("ROI 对比估算")
        col1, col2 = st.columns(2)
        total_time = (
            state.ingest_duration_sec + state.pattern_duration_sec
            + state.risk_duration_sec + state.alert_duration_sec
        )
        with col1:
            st.markdown("### 传统人工审计")
            st.markdown(f"- 数据清洗: ~2 小时")
            st.markdown(f"- 交易审查: ~4 小时 ({state.raw_count:,} 条)")
            st.markdown(f"- 报告撰写: ~2 小时")
            st.markdown(f"- **总计: ~8 小时/批次**")

        with col2:
            st.markdown("### Nexus-Audit AI 审计")
            st.markdown(f"- Ingest: {state.ingest_duration_sec:.1f}s")
            st.markdown(f"- Pattern: {state.pattern_duration_sec:.1f}s")
            st.markdown(f"- Risk: {state.risk_duration_sec:.1f}s")
            st.markdown(f"- Alert: {state.alert_duration_sec:.1f}s")
            st.markdown(f"- **总计: {total_time:.1f}s**")

        speedup = (8 * 3600) / max(total_time, 1)
        st.metric("效率提升", f"{speedup:.0f}x", f"从 8 小时 → {total_time:.0f} 秒")


if __name__ == "__main__":
    main()
