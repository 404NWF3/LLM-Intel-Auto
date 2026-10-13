# WP1-1 架构、目录结构与接口签名

## 1. 推荐目录结构

```text
backend/
  agents/
    intel_agents/
      __init__.py

      orchestrator/
        graph.py
        state.py
        nodes.py
        router.py
        runtime.py

      crews/
        source_collection_crew.py
        standardization_crew.py

      agents/
        supervisor_agent.py
        search_reflection_agent.py
        cve_collector_agent.py
        code_security_collector_agent.py
        paper_collector_agent.py
        community_signal_collector_agent.py
        standardizer_agent.py
        dedup_merge_agent.py
        dedup_adjudicator_agent.py
        bom_mapper_agent.py
        bom_resolution_reviewer_agent.py
        coverage_analyst_agent.py
        alert_reviewer_agent.py

      tools/
        source_fetch_tools.py
        parsing_tools.py
        taxonomy_tools.py
        cvss_tools.py
        vector_memory_tools.py
        bom_tools.py
        coverage_tools.py
        db_bridge_tools.py

      skills/
        source_query_expansion.md
        search_reflection_playbook.md
        attack_standardization_playbook.md
        dedup_adjudication_playbook.md
        ai_bom_resolution_playbook.md
        coverage_gap_fill_playbook.md
        high_risk_alert_review.md

      memory/
        qdrant_store.py
        embedding_provider.py
        collections.py

      schemas/
        plan.py
        query.py
        intel.py
        dedup.py
        alert.py

      services/
        source_registry.py
        source_scheduler.py
        query_strategy_service.py
        query_feedback_service.py
        novelty_service.py
        burst_service.py
        quality_scoring_service.py
        rerank_service.py

      prompts/
        search_reflection_prompts.py
        standardization_prompts.py
        review_prompts.py

      runners/
        bootstrap_runner.py
        incremental_runner.py
        scheduler_runner.py
```

## 2. 模块职责

### `orchestrator/`
- LangGraph 状态机
- 节点路由
- checkpoint 恢复
- runtime context 加载

### `agents/`
- 真正有自主性的业务 Agent

### `tools/`
- LangChain tools
- 供 Agent 调用的稳定能力

### `skills/`
- 可复用工作流说明
- 适合用 OpenCode / Claude Code 风格封装

### `memory/`
- Qdrant collection 管理（本地嵌入式模式）
- embedding 生成
- 语义检索

### `services/`
- 纯 Python 算法与调度逻辑
- 不一定暴露成 LangChain tool
- 包括 query feedback、gap fill ROI、source scheduling 等闭环策略

## 3. Agent 接口签名

### 3.1 SupervisorAgent

```python
class SupervisorAgent:
    def plan_run(
        self,
        runtime_context: dict,
        coverage_snapshot: list[dict],
        source_quality_rows: list[dict],
        query_feedback_rows: list[dict] | None = None,
    ) -> dict:
        """Return CollectionPlan."""
```

### 3.2 SearchReflectionAgent

```python
class SearchReflectionAgent:
    def reflect(
        self,
        source_runs: list[dict],
        query_telemetry: list[dict],
        collection_goals: dict,
    ) -> dict:
        """Return LLM-judged rewritten queries, stop/continue decision, audit fields, and rationale."""
```

### 3.3 CveCollectorAgent

```python
class CveCollectorAgent:
    def collect(self, plan: dict) -> list[dict]:
        """Collect from NVD / KEV / ATT&CK-like structured sources."""
```

### 3.4 CodeSecurityCollectorAgent

```python
class CodeSecurityCollectorAgent:
    def collect(self, plan: dict) -> list[dict]:
        """Collect advisories, PoC clues, issue/discussion evidence from GitHub-like sources."""
```

### 3.5 PaperCollectorAgent

```python
class PaperCollectorAgent:
    def collect(self, plan: dict) -> list[dict]:
        """Collect papers, reports, model cards, and technical analyses."""
```

### 3.6 CommunitySignalCollectorAgent

```python
class CommunitySignalCollectorAgent:
    def collect(self, plan: dict) -> list[dict]:
        """Collect Reddit / HN / public discussion posts."""
```

### 3.7 StandardizerAgent

```python
class StandardizerAgent:
    def standardize_batch(self, raw_items: list[dict]) -> list[dict]:
        """Normalize raw items into StandardizedIntel objects."""
```

### 3.8 DedupMergeAgent

```python
class DedupMergeAgent:
    def dedup_and_merge(self, items: list[dict]) -> list[dict]:
        """Return DedupDecision for each item and execute merge policy."""
```

### 3.9 DedupAdjudicatorAgent

```python
class DedupAdjudicatorAgent:
    def review_decisions(self, candidates: list[dict], decisions: list[dict]) -> list[dict]:
        """Review new / merge / review decisions with semantic and BOM-aware evidence."""
```

### 3.10 BomMapperAgent

```python
class BomMapperAgent:
    def map_bom(self, attack_records: list[dict]) -> list[dict]:
        """Resolve or enqueue AI BOM mentions."""
```

### 3.11 BomResolutionReviewerAgent

```python
class BomResolutionReviewerAgent:
    def review_resolution(self, attack_records: list[dict], bom_results: list[dict]) -> list[dict]:
        """Review AI BOM resolution quality and return accept / revise / review_queue outputs."""
```

### 3.12 CoverageAnalystAgent

```python
class CoverageAnalystAgent:
    def analyze(
        self,
        coverage_rows: list[dict],
        source_quality_rows: list[dict],
        component_risk_rows: list[dict],
        vendor_model_rows: list[dict],
        recent_attacks: list[dict],
    ) -> list[dict]:
        """Return attack-taxonomy and vendor/model coverage gaps with targeted recommendations."""
```

### 3.13 AlertReviewerAgent

```python
class AlertReviewerAgent:
    def review(self, attack_candidates: list[dict]) -> list[dict]:
        """Return final alert candidates."""
```

## 4. LangGraph 节点接口签名

```python
def load_runtime_context_node(state: dict) -> dict: ...
def supervisor_plan_node(state: dict) -> dict: ...
def dispatch_collection_node(state: dict) -> dict: ...
def collect_from_sources_node(state: dict) -> dict: ...
def store_raw_records_node(state: dict) -> dict: ...
def assess_collection_yield_node(state: dict) -> dict: ...
def reflect_search_strategy_node(state: dict) -> dict: ...
def parse_and_standardize_node(state: dict) -> dict: ...
def semantic_dedup_and_merge_node(state: dict) -> dict: ...
def dedup_adjudication_node(state: dict) -> dict: ...
def resolve_ai_bom_node(state: dict) -> dict: ...
def review_bom_resolution_node(state: dict) -> dict: ...
def score_confidence_and_novelty_node(state: dict) -> dict: ...
def refresh_coverage_view_node(state: dict) -> dict: ...
def coverage_gap_analysis_node(state: dict) -> dict: ...
def generate_alerts_node(state: dict) -> dict: ...
def finalize_run_node(state: dict) -> dict: ...
```

## 5. Qdrant 设计

建议使用本地嵌入式 `Qdrant` collections：

### `raw_intel_fingerprint`
用途：
- 原始文本近重复检测
- 低成本 recall 去重和 query failure 分析辅助

metadata：
- `source_name`
- `source_uri`
- `published_at`
- `content_hash`
- `taxonomy_guess`
- `component_names`

### `attack_signature_memory`
用途：
- 标准化攻击对象相似检索
- merge/new/review 决策支持
- 支撑“叙事相似但组件不同”的二级裁决
- 作为 `semantic_dedup_and_merge` 的向量数据库召回层，采用本地嵌入式 `Qdrant`

metadata：
- `attack_id`
- `attack_code`
- `attack_family`
- `taxonomy_primary`
- `component_ids`
- `last_seen_at`

### `query_feedback_memory`
用途：
- 记录 query variant 的命中质量与 rewrite 历史
- 支撑 source-aware query reflection

metadata:
- `source_name`
- `query_text`
- `query_intent`
- `rewrite_reason`
- `result_count`
- `novelty_yield`
- `precision_estimate`

## 6. 高质量算法设计建议

## 6.1 去重算法

### 目标
既要强去重，又不能错删“相似描述但不同 AI BOM”的真实情报。

### 方案
- Level 1: `content_hash`
- Level 2: `SimHash / MinHash`
- Level 3: `Qdrant / attack_signature_memory` top-k semantic recall
- Level 4: `embedding cosine similarity`
- Level 5: `cross-encoder rerank`
- Level 6: `DedupAdjudicatorAgent` 二次审查
- Level 7: 结构化约束比对
  - taxonomy overlap
  - CVE / GHSA / paper overlap
  - BOM overlap
  - version overlap

### 合并规则
- narrative 相似 + BOM 相同 -> `merge`
- narrative 相似 + BOM 新增 -> `merge + update attack_component_impact`
- narrative 相似 + BOM 冲突大 -> `review`
- narrative 不相似 -> `new`

说明：
- 向量数据库只负责 semantic recall，不直接替代最终裁决
- `DedupAdjudicatorAgent` 负责复核系统对 `new / merge / review` 的判断是否合理

## 6.2 BOM 实体解析算法

- alias normalization
- exact match
- alias match
- trigram retrieval
- embedding retrieval
- vendor-aware rerank
- version constraint normalization
- confidence thresholding
- unresolved queue fallback

## 6.3 弱信号发现算法

### 输入
- Reddit / HN / GitHub Discussions / Issues

### 方法
- 时间窗口嵌入聚类
- topic signature extraction
- burst detection
- novelty score
- precursor scoring

### 推荐指标
- `burst_score`
- `source_diversity`
- `semantic_cohesion`
- `attackability_score`
- `bom_relevance_score`

## 6.4 覆盖率补采算法

目标：
- 不只追求 attack count 增长，而是优先填补高价值盲区

覆盖建模：
- 从 `mv_owasp_coverage` 读取 taxonomy coverage
- 补充 `taxonomy x source x component_family` 三维视图
- 补充 `vendor_or_model_family x source x taxonomy` 三维视图
- 为每个 gap 计算：
  - attack count gap
  - source diversity gap
  - component coverage gap
  - corroboration gap
  - novelty gap

覆盖主线：
- 攻击类型覆盖率
- 主流厂商 / 主流模型覆盖率

输出：
- `recommended_sources`
- `recommended_queries`
- `expected_evidence_type`
- `estimated_gap_fill_roi`

query expansion 建议包含：
- taxonomy term
- synonym
- framework / model / tool name
- vendor / model family name
- attack family phrase
- exploit symptom phrase
- community phrasing

停止条件：
- ROI 低于阈值
- 连续多轮 rewrite 未带来有效增益
- source budget 已耗尽

## 6.5 搜索反思与 query rewrite

目标：
- 让系统根据实际检索结果自动收窄、放宽或切换 source-specific 语法

一轮检索后记录：
- result count
- parse success rate
- new / merge ratio
- novelty yield
- source-specific noise ratio

反思架构：
- `assess_collection_yield` 先把每个 query run 压缩成结构化 telemetry
- `SearchReflectionAgent` 再用 LLM 对 telemetry、source yield summary、query intent、历史 feedback memory 做综合判断
- LLM 输出结构化 reflection decision，而不是直接依赖阈值规则
- 规则层只负责：budget、轮数、source 语法约束、危险 rewrite 拦截、fallback 审计

LLM 需要回答的核心问题：
- 当前 query 的主要问题是 recall 不足、precision 不足、source mismatch，还是 novelty 已接近饱和
- 是否值得继续追加一轮 rewrite，还是应当停止
- 如果继续，应该采用 broader / narrower / source-specific / corroboration / component-anchored 哪一类 rewrite
- 预期改善的是 recall、precision 还是 novelty

推荐结构化输出：
- `should_retry`
- `stop_reason`
- `diagnosis`
- `recommended_actions`
- `rewritten_queries`
- `expected_gain_dimension`
- `confidence`
- `evidence_summary`
- `fallback_reason`

推荐结构：
- broad recall query
- precision probe query
- evidence corroboration query
- component-anchored query
- taxonomy-anchored query

约束要求：
- 任何 rewrite 都必须保留 parent query / rewrite round / trigger telemetry / expected gain 关系
- `llm_required` 模式下，LLM 反思失败不能静默跳过
- `llm_optional` 模式下允许回退到规则护栏，但必须写入 degraded audit

## 6.6 来源调度算法

Phase 1 推荐：
- priority score = source_trust * freshness_gain * gap_relevance * novelty_potential / expected_cost

Phase 2 可升级：
- contextual bandit
- Thompson sampling
- per-source ROI online learning

## 6.7 置信度校准

建议把最终置信度拆成：
- source trust
- extraction confidence
- dedup certainty
- bom resolution confidence
- evidence density
- source diversity bonus

## 7. Phase 1 MVP 顺序

1. LangGraph state + nodes
2. NVD / GitHub / arXiv / Reddit / HF / HN collectors
3. Ingestion + Standardization
4. Qdrant 语义召回去重
5. BOM resolution
6. Coverage gap fill
7. Alert review

## 8. 与现有 db 层的集成原则

- Agent 不直接写 SQL
- Tool 层调用 `backend/db/services/*`
- 批量处理优先在事务外完成推理，在事务内只做确定写入
- `mv_owasp_coverage` 只在批次结束后刷新
- LangGraph state 优先传 `raw_id` / `attack_id` / `query_run_id` / `artifact_ref`，不长时间传大文本 payload
