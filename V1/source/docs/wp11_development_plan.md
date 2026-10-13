# WP1-1 开发计划

本文档重写 WP1-1 的开发计划，遵循 Phase 0 已确定的原则：WP1-1 不做狭义 MVP，而是在完整系统边界下，按阶段逐步启用能力。开发过程中允许弱实现，但不允许把 schema、state、接口、handoff contract 做窄或做死。

## 1. 开发总目标

WP1-1 的目标是构建一个长期运行的智能情报采集与分析系统，形成从公开 source 到结构化攻击情报、覆盖率分析、弱信号发现和告警输出的完整闭环。

完整目标边界包括：
- 多源情报采集
- 统一标准化与结构化抽取
- 多级去重与攻击归并
- AI BOM 组件解析
- query telemetry 与 search reflection
- multi-dimensional coverage gap fill
- alert generation 与 review queue

## 2. 开发原则

### 2.1 一次设计到位

以下内容从第一阶段开始就必须按完整系统设计：
- LangGraph state schema
- 节点 handoff contract
- source abstraction
- query telemetry 结构
- coverage gap 数据模型
- 输出对象 schema
- `artifact_ref` 优先的状态传递原则

### 2.2 分阶段启用

以下内容允许先用基础实现，再逐步增强：
- 首批 source 数量
- query rewrite 策略强度
- dedup / rerank 模型强度
- 向量检索索引规模与召回策略强度
- coverage ROI 策略
- 告警审查策略精度

### 2.3 稳定优先

- 先做可持续运行的骨架，再堆算法复杂度
- 先打通 telemetry 和审计链路，再做更聪明的调度与 reflection
- 先保证节点边界稳定，再优化单点算法

## 3. 阶段划分

## 3.1 Phase 1：运行骨架与基础契约

目标：搭建 WP1-1 的可运行基线，让图可以稳定执行，状态和节点边界固定下来。

核心任务：
- 实现 LangGraph 主流程骨架
- 定义 `WP11GraphState` 与各节点 DTO
- 实现 runtime context、checkpoint、trace_id、run_id 机制
- 统一 handoff contract，明确 `raw_id`、`attack_id`、`query_run_id`、`artifact_ref`
- 约束状态传递只保留引用、摘要和统计，不跨节点传大正文

建议交付物：
- graph skeleton
- state schema
- node input/output schema
- error handling / retry / checkpoint 机制

完成标准：
- 图可以空跑或用 stub source 跑通
- 每个节点有清晰输入输出
- 失败可恢复，状态可追踪

## 3.2 Phase 2：首批 source 接入与原始记录入库

目标：让首批 source 稳定进入系统，形成统一的 raw record 输入层。

首批启用 source 建议：
- NVD
- GitHub Security Advisories
- arXiv
- Reddit
- Hacker News
- CISA KEV
- MITRE ATT&CK

后续扩展 source：
- GitHub Discussions / Issues
- 厂商安全公告
- HuggingFace

核心任务：
- 建立 source registry
- 为每类 source 实现 collector adapter
- 支持 cursor 或 time window 增量抓取
- 实现速率限制、失败重试、失败审计
- 把原始结果统一映射为 raw record
- 将每条记录绑定到 `query run`

建议交付物：
- source fetch adapters
- source scheduler 基础版
- raw ingest flow
- source failure / retry policy

完成标准：
- 首批 source 可稳定抓取
- 原始记录可统一入库
- source 成功率、失败率、抓取延迟可观测

## 3.3 Phase 3：标准化、结构化抽取与攻击对象生成

目标：把 heterogeneous raw records 转成统一攻击情报对象。

核心任务：
- raw content 清洗
- 标题、摘要、正文、元数据标准化
- 抽取攻击对象字段
- 提取 taxonomy 候选、CVSS hint、BOM mentions
- 生成 STIX payload
- 为每条标准化结果保留证据引用和 extraction reason

建议交付物：
- StandardizerAgent
- parsing / normalization tools
- standardized intel schema

完成标准：
- 首批 source 都能生成统一结构化对象
- 标准化结果可被后续 dedup / bom / scoring 直接消费

## 3.4 Phase 4：多级去重、攻击归并与审计

目标：把重复或高度相似的情报压缩成稳定攻击知识单元。

核心任务：
- content hash 去重
- SimHash / MinHash 近重复识别
- 向量数据库语义召回
- embedding retrieval
- rerank 与结构化约束检查
- 产出 `new / merge / review` 决策
- 对每个决策保留 `reason`、相似度和 BOM 差异说明

推荐架构：
- Level 1: `content hash` exact dedup
- Level 2: `SimHash / MinHash` near-duplicate filtering
- Level 3: 向量数据库 semantic recall
- Level 4: rerank
- Level 5: taxonomy / CVE / BOM 结构化裁决
- Level 6: `new / merge / review` 审计决策

向量数据库建议：
- 使用 `Qdrant` 作为 Phase 4 的 attack signature memory
- 当前工程约定优先采用 `Qdrant` 本地嵌入式模式（`QdrantClient(path=...)`），不要求 Docker
- `Qdrant` 在当前项目中承担“语义召回层”，不直接替代最终结构化裁决
- 用于存储 standardized attack object 的语义签名
- 用于 top-k semantic candidate retrieval，而不是直接替代最终裁决逻辑
- 最终合并决策仍必须保留 BOM-aware / taxonomy-aware / CVE-aware 审查

设计要求：
- 去重逻辑必须兼容“叙事相似但 BOM 不同”的场景
- 决策必须能审计
- merge 后要保留证据链接和来源覆盖情况
- 语义相似度高但 BOM 差异显著时，优先进入 `review`，不能直接 merge

新增审查层：
- 在 `semantic_dedup_and_merge` 后增加 `DedupAdjudicatorAgent`
- 该智能体不负责第一轮召回，而负责二次审查系统对 `new / merge / review` 的判断是否合理
- 输入包括：
  - top-k semantic candidates
  - rerank score
  - taxonomy overlap
  - CVE overlap
  - BOM delta
  - evidence refs
- 输出包括：
  - 是否同意系统决策
  - 修正后的决策建议
  - 审查理由与风险说明

建议交付物：
- DedupMergeAgent
- DedupAdjudicatorAgent
- vector memory / attack signature memory
- dedup decision schema
- merge audit records

完成标准：
- 能稳定区分 new / merge / review
- 不因去重而错误吞掉组件差异信息
- 语义召回层与结构化裁决层职责清晰分离

## 3.5 Phase 5：AI BOM 解析与置信度评分

目标：把攻击情报与组件、版本、供应商上下文关联起来，并形成统一评分。

核心任务：
- alias normalization
- exact / alias / trigram / embedding matching
- vendor-aware rerank
- version constraint normalization
- unresolved queue 处理
- 增加 `BomResolutionReviewerAgent` 对解析结果进行二次审查
- 计算 source trust、extraction confidence、dedup certainty、bom resolution confidence、evidence density、source diversity bonus

新增审查层：
- 在 `resolve_ai_bom` 后增加 `BomResolutionReviewerAgent`
- 用于判断系统对 AI BOM 的解析是否正确
- 重点检查：
  - alias 归一化是否误配
  - vendor 识别是否错误
  - 版本约束是否合理
  - 多候选组件是否需要 `review`
- 输出包括：
  - accept / revise / review_queue
  - 修正后的 component suggestion
  - 解析理由与歧义说明

建议交付物：
- BomMapperAgent
- BomResolutionReviewerAgent
- component resolution pipeline
- confidence / novelty scoring service

完成标准：
- 组件解析具备稳定主路径和 unresolved fallback
- 评分结果可用于后续 alert 与 coverage 分析
- 高风险或高歧义组件解析具备二次智能审查能力

## 3.6 Phase 6：Query Telemetry 与 Search Reflection

目标：让 WP1-1 不是固定检索，而是能根据结果自动调整检索策略。

核心任务：
- 定义 `query run` 与 `query telemetry`
- 记录 `query_text`、`query_intent`、`rewrite_round`、`result_count`、`parsed_count`、`duplicate_count`、`novelty_yield`、`noise_ratio`
- 实现 `assess_collection_yield`
- 实现 `reflect_search_strategy`
- 支持 broader / narrower / source-specific rewrite
- 限制 reflection budget 和停止条件

Phase 6 设计调整：
- `SearchReflectionAgent` 必须采用 LLM-primary 方案，而不是规则主判
- `assess_collection_yield` 负责生成结构化 telemetry / summary / source diagnostics，作为反思输入，不负责最终 rewrite 决策
- LLM 负责综合判断：当前 query 是 recall 不足、precision 不足、source mismatch，还是已接近收益上限
- 规则只保留为约束与护栏：
  - reflection budget
  - 最大 rewrite 轮数
  - source-specific query 语法约束
  - 禁止危险或无意义 rewrite
  - LLM 失败时的显式 degraded fallback 与审计

推荐实现方式：
- 引入 `LangChainLlmSearchReflectionAgent` ，使用 structured output 产出 rewrite decision
- 输出应至少包含：
  - `should_retry`
  - `stop_reason`
  - `diagnosis`（low_recall / high_noise / source_mismatch / saturated / uncertain）
  - `recommended_actions`
  - `rewritten_queries`
  - `expected_gain_dimension`（recall / precision / novelty）
  - `confidence`
  - `evidence_summary`
  - `fallback_reason`
- `rewritten_queries` 应支持：
  - broader rewrite
  - narrower rewrite
  - source-specific rewrite
  - corroboration query
  - component-anchored query
  - taxonomy-anchored query

设计原则：
- reflection 的核心价值是 agentic strategy adaptation，而不是阈值触发器
- telemetry 是 LLM 的观察窗口，不是最终决策器
- rewrite 必须保留前后版本关系、触发原因、模型判断与预期收益方向
- `llm_required` 时，反思失败必须显式失败或进入可审计降级路径，不能静默继续

后续增强方向：
- bandit / online learning
- source-specific query template ranking
- learned rewrite policy

建议交付物：
- SearchReflectionAgent
- LLM reflection decision schema / audit schema
- query feedback memory
- source-specific query templates

完成标准：
- query rewrite 有 telemetry 支撑
- query rewrite 由 LLM 主导生成，并保留结构化审计
- 反思环路可提升 recall、precision 或 novelty 中至少一项

## 3.7 Phase 7：Coverage Gap Fill

目标：让系统按真实覆盖盲区执行 targeted collection，而不是均匀抓取。

核心任务：
- 建立 `attack taxonomy x source x component family` 多维 coverage 视图
- 建立 `mainstream ai vendor / model family x source x attack taxonomy` 多维 coverage 视图
- 计算 `gap_score`、`source_diversity_gap`、`component_coverage_gap`、`corroboration_gap`
- 生成 `recommended_sources`、`recommended_queries`、`expected_evidence_type`
- 引入 `estimated_gap_fill_roi`
- 支持 gap fill 回流到 dispatch / collect 环节

coverage 设计拆分为两条主线：

### 攻击类型覆盖率
- 关注不同攻击类型是否被充分覆盖
- 重点维度：
  - `taxonomy coverage`
  - `attack family coverage`
  - `source diversity`
  - `corroboration density`

### 主流厂商 / 主流模型覆盖率
- 关注主流 AI 厂商、模型家族、框架、代理栈是否被系统覆盖
- 建议纳入的覆盖对象：
  - OpenAI
  - Anthropic
  - Google
  - Meta
  - Mistral
  - Alibaba / Qwen
  - DeepSeek
  - HuggingFace 重点模型生态
  - LangChain / LlamaIndex / agent runtime / plugin ecosystem
- 重点不是只看“是否出现过”，而是看：
  - 是否有攻击记录
  - 是否有高危记录
  - 是否有跨 source corroboration
  - 是否有组件 / 版本层影响映射

初始弱实现建议：
- 用规则分数和阈值判断是否回流

后续增强方向：
- ROI 预测模型
- per-source 收益学习
- contextual bandit 调度

建议交付物：
- CoverageAnalystAgent
- gap scoring service
- gap-fill loop
- vendor/model coverage read model

完成标准：
- coverage 分析可驱动新的 targeted collection
- gap fill 不再是机械回流，而是带 ROI 判断的策略执行
- 攻击类型覆盖率与主流厂商 / 主流模型覆盖率都可独立分析和追踪

## 3.8 Phase 8：运营化、评测与长期运行能力

目标：让系统具备可观测、可回放、可优化、可长期运行的工程能力。

核心任务：
- 统一 tracing 与 metrics
- 建 dashboard：source success、query yield、rewrite gain、coverage growth、alert precision
- 建 replay 机制：按 run、source、query 回放
- 建评测集：dedup、BOM、query rewrite、alert review
- 明确运维手册和异常处理策略

建议交付物：
- runtime dashboard
- replay tooling
- evaluation datasets and scripts

完成标准：
- 系统具备持续运行和持续优化能力
- 核心指标可被长期跟踪

## 4. 跨阶段必须持续维护的事项

这些工作不是单独阶段，而是从开发开始就要持续维护。

### 4.1 可观测性
- trace_id 全链路传播
- source / query / node 级 metrics
- 失败原因结构化记录

### 4.2 审计性
- 所有自动决策都保留 `reason`
- merge、review、alert 必须可解释
- query rewrite 必须保留前后版本关系

### 4.3 数据与状态边界
- 节点间只传引用、摘要和统计
- 正文尽快持久化
- 避免 state 膨胀

### 4.4 回归验证
- 每完成一阶段，都要补对应回归验证
- 不能等全部做完再统一评测

## 5. 推荐执行顺序

建议实际实施时按下面顺序推进：

1. 先完成 Phase 1，定稳 graph、state、contract
2. 再完成 Phase 2，接通首批 source 和 ingest
3. 再完成 Phase 3 与 Phase 4，形成结构化 attack 主链路
4. 再完成 Phase 5，保证组件语义和评分闭环
5. 再完成 Phase 6 与 Phase 7，构建搜索反思与 coverage gap fill 的智能闭环
6. 最后完成 Phase 8，提升系统长期运行能力

## 6. 风险与控制点

### 6.1 最容易返工的点
- state schema 设计过窄
- handoff contract 不稳定
- telemetry 前期没记全
- coverage 只按单一 taxonomy 建模

### 6.2 最容易失控的点
- source 越接越多但没有收益评估
- query rewrite 没有停止条件
- dedup 把组件差异吞掉
- 弱信号噪声过大导致告警失真

### 6.3 控制原则
- 所有阶段都优先保护 schema 和 contract 稳定性
- 所有增强策略都必须建立在 telemetry 之上
- 所有智能化决策都必须保留审计信息

## 7. 开发计划的最终要求

WP1-1 的开发不是“先做一个小爬虫再慢慢堆功能”，而是：

- 先建立完整边界下的稳定架构
- 再逐阶段启用 source、算法和策略
- 保证每一阶段都能直接继承前一阶段成果
- 避免因为前期缩窄设计而在中后期进行系统性返工

本文件作为 WP1-1 的重写开发计划，应与 `docs/wp11_phase0_preparation.md` 配套使用。
