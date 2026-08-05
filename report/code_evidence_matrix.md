# 代码证据矩阵

本索引面向 `intelligence_collection_agent_report.pdf`。行号基于 2026-07-15 当前工作树；
文件内容本身是权威证据，行号仅用于快速定位。

| 报告结论 | 当前代码证据 | 解释 |
|---|---|---|
| 采集与构图解耦 | `AGENTS.md`；`backend/common/topics.py:1-5` | `common` 只共享主题；`intel_agent` 与 `ctinexus_kg` 通过持久化 DTO 交接。 |
| 18 个 Core、15 个 Extended | `backend/common/topics.py:11-52` | Core 驱动覆盖；Extended 仅可搜索/标注，不驱动 legacy 配额。 |
| full 永远走 legacy 配额路径 | `backend/intel_agent/engine/controller.py:109` | `adaptive` 只在 `IncrementalCollectionMode` 且策略为 `adaptive` 时为真。 |
| full legacy 默认每个 Core 配额 3 | `backend/intel_agent/analysis.py:26-27,63-64,179-195` | 这是 item count 口径，不等于有效证据质量。 |
| 相关性三层门控 | `backend/intel_agent/relevance.py:31-35,154-205,312-318` | rule 阈值 0.75/0.20；embedding 阈值 0.62/0.42；中间区间交给 LLM。 |
| legacy 缺少相关性元数据时按 0.5 兜底 | `backend/intel_agent/analysis.py:26,78-82` | 有标签时只有 `relevant` 被计数；无标签时 score >= 0.5。 |
| 初始启发式分数最低从 0.45 起 | `backend/intel_agent/sources.py:537-540` | `0.45 + topic_bonus + token_bonus`，因此禁用相关性管线时存在过纳入风险。 |
| 四源和证据通道映射 | `backend/intel_agent/engine/gaps.py:28-43` | arXiv=research；NVD/OSV=advisory；CISA=exploitation。 |
| 来源信任系数 | `backend/intel_agent/engine/gaps.py:34-38` | arXiv 0.72、NVD 0.90、OSV 0.84、CISA 0.92。 |
| 34 个自适应覆盖单元 | `backend/intel_agent/engine/gaps.py:51,56-62` | 18 个 research + 除 jailbreak/model backdoor 外 16 个 advisory。 |
| 主题 credit 守恒 | `backend/intel_agent/engine/gaps.py:77-100` | 多主题 score 总和超过 1 时归一化，防止一条 item 被重复全额计入。 |
| 事件级去重与多源佐证 | `backend/intel_agent/engine/gaps.py:103-137` | CVE/GHSA/PYSEC/RUSTSEC 精确锚定；首证据 1、异源佐证 0.5、同源重复 0。 |
| 新鲜度半衰期 | `backend/intel_agent/engine/gaps.py:45-50,139-145` | 权重下限 0.5；research/exploitation 365 天，advisory 730 天。 |
| 有效证据公式 | `backend/intel_agent/engine/gaps.py:147-176` | credit × relevance × trust × uniqueness × freshness 后求和。 |
| gap 优先级 | `backend/intel_agent/engine/gaps.py:177-208` | `0.6 coverage + 0.2 diversity + 0.2 freshness`，截断到 1。 |
| UCB arm 定义 | `backend/intel_agent/engine/bandit.py:12-29` | topic/channel/source/intent/operator signature。 |
| UCB 效用 | `backend/intel_agent/engine/bandit.py:32-67` | 期望 gap reduction + 探索项 - noise/duplicate 惩罚。 |
| portfolio 预算 | `backend/intel_agent/engine/bandit.py:70-101` | 每批最多 4；discovery 20%；confirmation 10%。 |
| reward 归因 | `backend/intel_agent/engine/bandit.py:104-127` | gap reduction、发现/确认奖励与噪声、重复、调用成本共同决定，范围 [-1,1]。 |
| 新主题确定性门控 | `backend/intel_agent/engine/gaps.py:337-447` | residual、余弦聚类 0.82、>=3 事件、>=2 来源、burst>=1.5 后才交给结构化 LLM 命名。 |
| 内存 playbook 衰减 | `backend/intel_agent/memory/playbook.py:74-88,184-239` | 未使用奖励乘 0.9；连续低于 0.1 可 deprecated；召回同时看语义与 reward。 |
| SDK 不可用时降级 | `backend/intel_agent/engine/controller.py:273-320,611-693` | adaptive 会记录 fallback 并转 legacy；full 每轮也可用确定性 fallback。 |
| 自适应停止由安全阀决定 | `backend/intel_agent/engine/controller.py:704-793` | max rounds/budget/timeout/saturated 为权威；critic 在该路径主要解释，不覆盖硬停止条件。 |
| legacy 停止允许 critic 判断 | `backend/intel_agent/engine/controller.py:795-877` | 仍受 max rounds、stall、open gaps 等规则保护。 |
| 内建工具禁用、MCP 白名单 | `backend/intel_agent/runtime/client.py:149-164`；`backend/intel_agent/tools/server.py:14-47` | `tools=[]`、`setting_sources=[]`，只允许本地明确列出的 MCP 工具。 |
| source tool 二次校验 | `backend/intel_agent/tools/source_tools.py:90-208` | 候选、源/通道、时间窗、预算、分页、去重全部在 Python 侧重新校验。 |
| hooks 是本地预算闸门 | `backend/intel_agent/hooks.py:32-178` | PreToolUse 拒绝越界，PostToolUse 审计，失败写 RunGap。 |
| full 每轮新 SDK 会话；adaptive 连续会话 | `backend/intel_agent/agent/loop.py:97-224,275-388` | full 隔离轮次；adaptive 尝试 resume，再 fresh session，最后 controller fallback。 |
| context 只给摘要 | `backend/intel_agent/engine/context.py:18-97` | digest 有长度上限，不把 raw document 全量注入 agent。 |
| Mongo 全局 item 去重 | `backend/intel_agent/mongo_store.py:67-132,192-253` | `_id=item_id`，`run_ids` 保存溯源；run 文档与 item 文档分开。 |
| JSON 原子写入 | `backend/intel_agent/persistence.py:40-103` | 临时文件替换并维护 latest；仅在未启用 Mongo 时作为主存储。 |
| trace 可审计 | `backend/intel_agent/observability.py:34-116` | JSONL + console 回调，记录 round/tool/result/critic/session 等事件。 |
| item-KG 失败隔离 | `backend/ctinexus_kg/pipeline.py`；`scripts/smoke_pipeline.py` | 采集与构图通过 DTO/持久化交接，冒烟验证 fake KG 流程不污染采集。 |
| 当前测试基线 | 2026-07-15 命令输出；`report/runtime_snapshot.json` | 86 passed；smoke pipeline 通过。 |

## 需要谨慎解释的实现语义

1. `summary.core_gap_count` 是开放的 `CorpusGap` 数量，不是 legacy quota gap 数量。
   full/bootstrap 不计算 `CorpusGap`，因此它可能显示 0，同时仍有 15 个 legacy gap。
2. `trace.tool_call` 包括记忆、状态和 summary 工具；不能当作外部源 API 调用数。
3. `uncertain` 是分类结果，不是健康覆盖。当前 `item_is_relevant` 在有标签时会排除它；
   但禁用相关性管线后，0.5 的 legacy score fallback 可能把启发式高分误当成 relevant。
4. OSV API 本身是 package/commit/version 查询，当前实现的开放式主题检索是遍历固定的
   15 个 AI package 清单；它不是通用语义搜索。
5. `.env.example` 中仍出现 `INTEL_ENGINE=rules`，但当前 controller/CLI 主路径不读取该变量；
   这是配置文档漂移，不应写成现行切换开关。

