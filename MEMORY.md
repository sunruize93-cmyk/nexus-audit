# Nexus-Audit 项目记忆

## 项目目标
德勤 2026 Digital Camp 比赛 - 基于 Agentic AI 的智能审计系统，用于跨境电商刷单风险检测。

## 技术架构
- **Agent 编排**: 纯函数式管道 (Python 3.9 兼容, 生产可迁移至 LangGraph)
- **图分析**: NetworkX + Louvain 社区发现
- **LLM**: OpenAI GPT-4o (含规则引擎回退)
- **记忆系统**: 工作记忆(dict) + 情景记忆(SQLite) + 语义记忆(JSON 规则自进化)
- **Demo**: Streamlit Dashboard
- **数据**: UCI Online Retail II (52.5万条) + 50 条注入异常

## 当前进展
| 模块 | 状态 | 备注 |
|------|------|------|
| 项目结构 | 已完成 | |
| 全局 Skill | 已完成 | .cursor/skills/deloitte-competition-SKILL.md |
| 数据准备 | 已完成 | 52.5万+50条异常 |
| Ingest Agent | 已完成 | 23s 处理 52.5万条 |
| Pattern Agent | 已完成 | 49.6万节点图, 19263笔可疑 |
| Risk Agent | 已完成 | 5038高+14225中风险 |
| Alert Agent | 已完成 | 20个警报, 21份报告 |
| 三层记忆 | 已完成 | 规则自进化已验证 |
| Streamlit UI | 已完成 | 待运行截图 |
| 端到端测试 | 已通过 | 总耗时 919.5s |
| PPT Markdown | 已完成 | ppt/presentation.md |

## 已知问题
- Python 3.9 不支持 LangGraph, 使用顺序管道回退
- 图可视化中文字体需 Microsoft YaHei
- Risk Agent 逐条评估 19263 笔耗时 524s, 可通过批量评估优化
- 社区发现参数可能过于激进 (19263 笔可疑), 可调 LOUVAIN_RESOLUTION 和 MIN_COMMUNITY_SIZE

## 关键决策
- 用纯函数管道替代 LangGraph (Python 3.9 兼容性)
- NetworkX+Louvain 替代 RGCN (5天内可交付)
- Streamlit 替代飞书/Obsidian
- LLM 不可用时自动回退规则引擎

## 实测运行数据 (用于 PPT)
- Ingest: 23.2s, 525,511 → 407,714 条
- Pattern: 357.6s, 496,217 节点, 1,221,818 边
- Risk: 524.2s, 5038 高 + 14225 中
- Alert: 14.5s, 20 个警报, 21 份报告
- 总耗时: 919.5s

## 最后更新
2026-04-16 - 全部模块开发完成, 端到端测试通过
