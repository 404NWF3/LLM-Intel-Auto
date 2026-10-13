# WP1-1 子Agent / Tool / Skill 划分方案

## 1. 划分原则

### 什么适合做子Agent
满足任一条件就优先做 Agent：
- 需要多步推理
- 需要在多个来源、策略、候选之间做选择
- 需要调用多个 tools
- 需要输出“任务结果”，而不是一步 I/O

### 什么适合做 Tool
满足以下特征优先做 Tool：
- 单一职责
- 输入输出稳定
- 可单元测试
- 对外部系统做明确调用
- 不应自行规划下一步

### 什么适合做 Skill
适合封装“最佳实践流程”：
- 高价值分析 SOP
- 多 Agent 都会复用
- 主要是流程、检查清单、判定规范
- 不直接承载底层数据库 / HTTP 细节

## 2. 子Agent 列表

### 2.1 IntelSupervisorAgent
职责：
- 读取 runtime context
- 决定 run mode
- 生成 collection plan
- 设定 source priority / target taxonomy / query strategy
- 为不同 source 指定 broad recall / precision probe 检索意图
- 约束 query reflection 的轮数、预算与停止条件

输入：
- coverage snapshot
- source quality dashboard
- recent alerts
- cursor state

输出：
- `CollectionPlan`

### 2.2 SearchReflectionAgent
职责：
- 读取 query telemetry 与 source yield summary
- 由大模型判断“recall 不足 / precision 不足 / 噪声过大 / source 语法不匹配 / novelty 饱和”
- 生成 narrower / broader / source-specific rewrite
- 生成 corroboration / component-anchored / taxonomy-anchored rewrite
- 决定是否继续补采、切换 source 或终止本轮检索
- 输出结构化 reflection 审计与 expected gain 方向

### 2.3 CveIntelCollectorAgent
职责：
- 面向 NVD / CISA KEV / MITRE ATT&CK 抓结构化漏洞与战术信息

### 2.4 CodeSecurityCollectorAgent
职责：
- 面向 GitHub Security Advisories / Issues / Discussions / repos 抓 PoC 与公告

### 2.5 PaperIntelCollectorAgent
职责：
- 面向 arXiv / HuggingFace papers / vendor reports 抓论文与技术报告

### 2.6 CommunitySignalCollectorAgent
职责：
- 面向 Reddit / Hacker News / GitHub Discussions 采集讨论与求助帖

### 2.7 StandardizerAgent
职责：
- 把异构源转换为统一情报对象
- 生成 STIX payload
- 提取 taxonomy / CVSS hints / BOM mentions

### 2.8 DedupMergeAgent
职责：
- 执行多级去重与归并
- 处理“叙事相似但 BOM 不同”的合并策略

### 2.9 DedupAdjudicatorAgent
职责：
- 对 `semantic_dedup_and_merge` 的初始判断做二次审查
- 复核 `new / merge / review` 是否正确
- 在“叙事相似但 BOM 不同”时优先保护组件差异，不做冒进合并

### 2.10 BomMapperAgent
职责：
- 抽取 AI BOM mentions
- 组件实体解析
- unresolved 入 queue

### 2.11 BomResolutionReviewerAgent
职责：
- 对 AI BOM 解析结果执行二次审查
- 判断 accept / revise / review_queue
- 审查 vendor、version、component mapping 是否合理

### 2.12 CoverageAnalystAgent
职责：
- 读取覆盖率
- 计算 multi-dimensional gap score
- 分析 `taxonomy x source x component_family` 覆盖盲区
- 分析 `vendor_or_model_family x source x taxonomy` 覆盖盲区
- 生成 targeted sources / targeted query sets / expected evidence type
- 判断 gap_fill 是否值得回流到采集环

### 2.13 AlertReviewerAgent
职责：
- 判断是否需要发出高危告警
- 过滤低质量弱信号

## 3. Tool 列表

## 3.1 Source Fetch Tools

### `fetch_nvd_records`
```python
def fetch_nvd_records(keyword: str, max_results: int = 20) -> list[dict]: ...
```

### `fetch_github_advisories`
```python
def fetch_github_advisories(keyword: str, max_results: int = 20) -> list[dict]: ...
```

### `fetch_github_discussions`
```python
def fetch_github_discussions(repo_or_org: str, query: str, max_results: int = 20) -> list[dict]: ...
```

### `fetch_arxiv_papers`
```python
def fetch_arxiv_papers(query: str, max_results: int = 20) -> list[dict]: ...
```

### `fetch_huggingface_items`
```python
def fetch_huggingface_items(query: str, max_results: int = 20) -> list[dict]: ...
```

### `fetch_reddit_posts`
```python
def fetch_reddit_posts(subreddit: str, query: str, limit: int = 20) -> list[dict]: ...
```

### `fetch_hackernews_posts`
```python
def fetch_hackernews_posts(query: str, max_results: int = 20) -> list[dict]: ...
```

### `fetch_cisa_kev`
```python
def fetch_cisa_kev(max_results: int = 100) -> list[dict]: ...
```

### `fetch_mitre_attack_updates`
```python
def fetch_mitre_attack_updates(keyword: str | None = None, max_results: int = 100) -> list[dict]: ...
```

### `fetch_vendor_advisories`
```python
def fetch_vendor_advisories(vendor: str, query: str | None = None, max_results: int = 50) -> list[dict]: ...
```

## 3.2 Parsing / Normalization Tools

### `clean_raw_content`
```python
def clean_raw_content(raw_text: str, source_name: str) -> str: ...
```

### `extract_structured_intel`
```python
def extract_structured_intel(raw_item: dict) -> dict: ...
```

### `build_stix_attack_object`
```python
def build_stix_attack_object(standardized: dict) -> dict: ...
```

### `infer_taxonomy_labels`
```python
def infer_taxonomy_labels(text: str) -> list[dict]: ...
```

### `infer_cvss_hint`
```python
def infer_cvss_hint(text: str) -> dict | None: ...
```

### `extract_bom_mentions`
```python
def extract_bom_mentions(text: str) -> list[dict]: ...
```

## 3.3 Dedup / Memory Tools

### `compute_content_hash`
```python
def compute_content_hash(content: str) -> str: ...
```

### `generate_embedding`
```python
def generate_embedding(text: str) -> list[float]: ...
```

### `query_qdrant_similar_raw`
```python
def query_qdrant_similar_raw(text: str, top_k: int = 5) -> list[dict]: ...
```

### `query_qdrant_similar_attack`
```python
def query_qdrant_similar_attack(text: str, top_k: int = 5) -> list[dict]: ...
```

### `upsert_qdrant_attack_signature`
```python
def upsert_qdrant_attack_signature(attack_id: str, text: str, metadata: dict) -> None: ...
```

### `query_qdrant_semantic_candidates`
```python
def query_qdrant_semantic_candidates(text: str, top_k: int = 10) -> list[dict]: ...
```

### `decide_dedup_merge`
```python
def decide_dedup_merge(candidate: dict, retrieved: list[dict]) -> dict: ...
```

## 3.4 BOM / Entity Resolution Tools

### `normalize_component_alias`
```python
def normalize_component_alias(name: str, vendor: str | None = None) -> str: ...
```

### `match_ai_component`
```python
def match_ai_component(mentioned_name: str, vendor: str | None = None) -> dict: ...
```

### `normalize_version_constraint`
```python
def normalize_version_constraint(raw_version: str | None) -> str | None: ...
```

### `resolve_bom_mentions_batch`
```python
def resolve_bom_mentions_batch(attack_id: str, mentions: list[dict], raw_id: str | None = None) -> list[dict]: ...
```

## 3.5 Coverage Tools

### `load_owasp_coverage_snapshot`
```python
def load_owasp_coverage_snapshot() -> list[dict]: ...
```

### `compute_gap_scores`
```python
def compute_gap_scores(coverage_rows: list[dict], target_baseline: dict[str, int]) -> list[dict]: ...
```

### `expand_gap_fill_queries`
```python
def expand_gap_fill_queries(taxonomy_code: str, attack_family: str | None = None) -> list[str]: ...
```

### `build_source_specific_queries`
```python
def build_source_specific_queries(
    source_name: str,
    intent: str,
    seed_terms: list[str],
    component_terms: list[str] | None = None,
) -> list[str]: ...
```

### `analyze_query_outcomes`
```python
def analyze_query_outcomes(query_runs: list[dict]) -> dict: ...
```

### `rewrite_queries_with_feedback`
```python
def rewrite_queries_with_feedback(
    source_name: str,
    query_runs: list[dict],
    target_taxonomy: str | None = None,
) -> list[dict]: ...
```

### `compute_multi_dimensional_gap_scores`
```python
def compute_multi_dimensional_gap_scores(
    coverage_rows: list[dict],
    source_rows: list[dict],
    component_rows: list[dict],
) -> list[dict]: ...
```

### `compute_vendor_model_gap_scores`
```python
def compute_vendor_model_gap_scores(
    vendor_rows: list[dict],
    source_rows: list[dict],
    taxonomy_rows: list[dict],
) -> list[dict]: ...
```

### `estimate_gap_fill_roi`
```python
def estimate_gap_fill_roi(gap: dict, candidate_sources: list[dict]) -> dict: ...
```

### `detect_burst_events`
```python
def detect_burst_events(clusters: list[dict], window_hours: int = 72) -> list[dict]: ...
```

### `score_threat_precursor`
```python
def score_threat_precursor(cluster: dict) -> float: ...
```

## 3.6 DB Bridge Tools

### `store_raw_records_via_db`
```python
def store_raw_records_via_db(task_id: str, items: list[dict]) -> list[str]: ...
```

### `merge_attack_via_db`
```python
def merge_attack_via_db(raw_id: str, standardized: dict, dedup: dict) -> dict: ...
```

### `resolve_bom_via_db`
```python
def resolve_bom_via_db(attack_id: str, mentions: list[dict], raw_id: str | None = None) -> list[dict]: ...
```

### `refresh_coverage_materialized_view`
```python
def refresh_coverage_materialized_view() -> None: ...
```

### `store_query_telemetry_via_db`
```python
def store_query_telemetry_via_db(run_id: str, query_runs: list[dict]) -> list[str]: ...
```

## 4. Skill 列表

Skill 不是底层函数。Skill 是“流程经验包”。

### 4.1 `source-query-expansion`
用途：
- 根据 taxonomy 缺口扩展搜索词
- 输出 source-specific query set

适合调用者：
- `IntelSupervisorAgent`
- `CoverageAnalystAgent`

### 4.2 `search-reflection-loop`
用途：
- 为 LLM reflection 提供 telemetry、source summary、query feedback memory、source templates
- 由 LLM 主导判断 recall 不足、precision 不足、source mismatch、novelty 饱和
- 生成 broader / narrower / source-specific / corroboration rewrite
- 规定最大反思轮数、停止条件、预算约束和降级护栏

适合调用者：
- `IntelSupervisorAgent`
- `SearchReflectionAgent`
- `CoverageAnalystAgent`

### 4.3 `attack-standardization-playbook`
用途：
- 指导如何把原始文本整理成标准攻击对象
- 包含字段抽取顺序、缺失字段补全策略、证据规范

适合调用者：
- `StandardizerAgent`

### 4.4 `dedup-adjudication-playbook`
用途：
- 指导“new / merge / review”的判定
- 明确 BOM 差异场景如何处理

适合调用者：
- `DedupMergeAgent`
- `DedupAdjudicatorAgent`

### 4.5 `ai-bom-resolution-playbook`
用途：
- 指导 BOM mention 抽取、vendor 推断、版本规范化、冲突判定

适合调用者：
- `BomMapperAgent`
- `BomResolutionReviewerAgent`

### 4.6 `coverage-gap-fill-playbook`
用途：
- 定义 `taxonomy x source x component_family` 三维缺口分析方法
- 定义 `vendor_or_model_family x source x taxonomy` 缺口分析方法
- 规定何时执行 targeted gap fill、何时停止追采
- 给出 expected evidence type 与优先 source 模板

适合调用者：
- `IntelSupervisorAgent`
- `CoverageAnalystAgent`

### 4.7 `high-risk-alert-review`
用途：
- 审查是否触发高危告警
- 要求 evidence density、source diversity、BOM relevance 达阈值

适合调用者：
- `AlertReviewerAgent`

## 5. 最终建议的划分表

- `子Agent`
  - 计划、检索反思、归并、二次审查、覆盖率分析、审查
- `Tool`
  - HTTP 抓取、embedding、向量检索、query telemetry、gap 计算、DB 调用、视图读取
- `Skill`
  - query expansion、search reflection、coverage gap fill、标准化、去重裁决、BOM 解析、告警审查

## 6. 一个简单判断口诀

- “需要思考” -> Agent
- “需要执行” -> Tool
- “需要方法论” -> Skill
