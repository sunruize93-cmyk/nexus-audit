"""语义记忆 — 规则自进化引擎

类比审计师的"经验直觉": 从历史案例中自动提炼检测规则,
并随着新数据不断优化阈值, 实现 Agent 的自改进能力。
"""

from __future__ import annotations

import json
from pathlib import Path

from config import ROOT_DIR


RULES_PATH = ROOT_DIR / "memory" / "learned_rules.json"

DEFAULT_RULES: list[dict] = [
    {
        "id": "R001",
        "name": "凌晨集中下单",
        "description": "凌晨 0:00-5:00 时段, 同一 IP 下单超过阈值",
        "weight": 0.3,
        "threshold": 5,
        "activated_count": 0,
        "precision_estimate": 0.85,
    },
    {
        "id": "R002",
        "name": "共享IP多账户",
        "description": "同一 IP 地址关联 3 个以上不同账户",
        "weight": 0.25,
        "threshold": 3,
        "activated_count": 0,
        "precision_estimate": 0.80,
    },
    {
        "id": "R003",
        "name": "新账户爆发",
        "description": "注册不满 7 天的账户产生大额订单",
        "weight": 0.25,
        "threshold": 7,
        "activated_count": 0,
        "precision_estimate": 0.75,
    },
    {
        "id": "R004",
        "name": "团伙环形关联",
        "description": "账户-设备-IP 形成社区闭环, Louvain 社区 size ≥ 3",
        "weight": 0.2,
        "threshold": 3,
        "activated_count": 0,
        "precision_estimate": 0.90,
    },
]


class SemanticMemory:
    """基于 JSON 文件的规则记忆, 支持自适应权重调整"""

    def __init__(self, rules_path: Path = RULES_PATH) -> None:
        self._rules_path = rules_path
        self._rules = self._load_rules()

    def _load_rules(self) -> list[dict]:
        if self._rules_path.exists():
            with open(self._rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return [r.copy() for r in DEFAULT_RULES]

    def _save_rules(self) -> None:
        self._rules_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._rules_path, "w", encoding="utf-8") as f:
            json.dump(self._rules, f, ensure_ascii=False, indent=2)

    def get_rules(self) -> list[dict]:
        return self._rules

    def get_rule_weights(self) -> dict[str, float]:
        """返回 {rule_id: weight} 映射"""
        return {r["id"]: r["weight"] for r in self._rules}

    def record_activation(self, rule_id: str, was_correct: bool) -> None:
        """记录规则被触发, 并根据反馈调整权重"""
        for rule in self._rules:
            if rule["id"] == rule_id:
                rule["activated_count"] += 1
                if was_correct:
                    rule["weight"] = min(0.5, rule["weight"] * 1.05)
                    rule["precision_estimate"] = min(
                        0.99, rule["precision_estimate"] * 1.02
                    )
                else:
                    rule["weight"] = max(0.05, rule["weight"] * 0.95)
                    rule["precision_estimate"] = max(
                        0.5, rule["precision_estimate"] * 0.98
                    )
                break
        self._normalize_weights()
        self._save_rules()

    def _normalize_weights(self) -> None:
        total = sum(r["weight"] for r in self._rules)
        if total > 0:
            for r in self._rules:
                r["weight"] = round(r["weight"] / total, 4)

    def get_evolution_summary(self) -> str:
        """返回规则进化摘要 (用于 PPT 展示)"""
        lines = ["规则自进化状态:"]
        for r in self._rules:
            lines.append(
                f"  [{r['id']}] {r['name']}: 权重={r['weight']:.2%}, "
                f"触发{r['activated_count']}次, 精度≈{r['precision_estimate']:.1%}"
            )
        return "\n".join(lines)
