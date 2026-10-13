# WP1-1 运维参数手册

## 1. 适用范围

本文面向 WP1-1 的运维、联调和 live run 使用者，说明当前运行默认参数、每源采集预算、数据库落库相关参数、常用验证入口，以及攻击信息写入最终数据库时的鲁棒性行为。

## 2. 当前 live 实际配置来源

当前 `python main.py --live` 的参数来源分成三层：

1. 根目录 `.env`
2. 根目录 `wp11_llm_profiles.json`
3. 根目录 `wp11_llm_route_presets.json`

其中：

- `.env` 负责基础连接信息，例如 `OPENAI_API_KEY`、`OPENAI_API_BASE`、`OPENAI_MODEL`、数据库连接参数。
- `wp11_llm_profiles.json` 负责定义可用的 LLM profile 实例。
- `wp11_llm_route_presets.json` 负责定义不同任务如何按 profile 标签路由。

`WP11_LLM_PROFILES_JSON` 和 `WP11_LLM_ROUTE_PRESETS_JSON` 仍保留为兼容 fallback，但已经不再是推荐入口。

## 3. 当前 live 关键配置

当前仓库下，live run 的活跃非敏感配置为：

| 类别 | 当前值 |
| --- | --- |
| `OPENAI_API_BASE` | `https://openrouter.ai/api/v1` |
| `OPENAI_MODEL` | `deepseek/deepseek-chat` |
| `OPENAI_FAST_MODEL` | `deepseek/deepseek-chat` |
| LLM profile 文件 | `wp11_llm_profiles.json` |
| LLM route preset 文件 | `wp11_llm_route_presets.json` |
| 默认 preset | `default` |
| DB host | `pgm-uf65m4xfwcgfzc5kwo.pg.rds.aliyuncs.com` |
| DB port | `5432` |
| DB name | `saads` |
| DB schema | `wp11` |
| DB pool | `POSTGRES_MIN_SIZE=1`, `POSTGRES_MAX_SIZE=10` |
| DB connect timeout | `10s` |
| DB statement timeout | `30000ms` |

说明：

- 当前 profile 文件里共有 4 个 profile：`101/102/201/301`。
- 当前 profile 标签分层为 `cheap_fast`、`balanced`、`fallback`。
- 由于你当前 `.env` 中 `OPENAI_MODEL` 和 `OPENAI_FAST_MODEL` 都是 `deepseek/deepseek-chat`，所以这 4 个 profile 目前会解析到同一模型名；如果要让不同标签使用不同模型，需要改 `wp11_llm_profiles.json` 中的 `model` 或 `model_env`。

## 4. `default_live()` 当前默认参数

以下默认值来自 [runtime.py](/e:/@4C-2026/SUFE-SAADS-Qwen/backend/agents/intel_agents/schemas/runtime.py) 的 `RuntimeContextDTO.default_live()`。

### 4.1 运行模式与策略

| 参数 | 当前值 |
| --- | --- |
| `run_mode` | `bootstrap` |
| `source_runtime_mode` | `live` |
| `planning_strategy` | `llm_required` |
| `coverage_strategy` | `llm_required` |
| `reflection_strategy` | `llm_required` |
| `standardization_strategy` | `llm_required` |
| `bom_resolution_strategy` | `llm_required` |
| `dedup_merge_strategy` | `llm_required` |
| `dedup_adjudication_strategy` | `rules_only` |
| `llm_temperature` | `0.0` |
| `validate_llm_online` | `False` |

### 4.2 LLM 弹性与并发

| 参数 | 当前值 |
| --- | --- |
| `llm_route_preset` | `default` |
| `llm_task_routes` | `{}` |
| `llm_retry_attempts` | `3` |
| `llm_backoff_base_seconds` | `2.0` |
| `llm_backoff_max_seconds` | `30.0` |
| `llm_short_wait_threshold_seconds` | `60.0` |
| `llm_resume_on_exhausted_retry` | `True` |
| `standardization_max_concurrency` | 动态计算，当前为 `4` |

当前 `standardization_max_concurrency=4` 的原因：

- `default` preset 下，`standardization` 的标签路由是 `["balanced", "cheap_fast", "fallback"]`
- 这会展开为 profile `201 -> 101 -> 102 -> 301`
- 4 个 profile 的 `max_concurrency` 当前都为 `1`
- `recommended_task_concurrency()` 会把它们的并发预算求和，因此当前结果为 `4`

### 4.3 采集与反思参数

| 参数 | 当前值 |
| --- | --- |
| `planning_max_parallel_sources` | `4` |
| `planning_max_items_per_source` | `10` |
| `planning_max_reflection_rounds` | `1` |
| `planning_reflection_enabled` | `True` |
| `source_retry_attempts` | `2` |
| `source_request_timeout_seconds` | `30.0` |
| `source_health_drift_threshold` | `0.5` |

### 4.4 Coverage、payload 与持久化

| 参数 | 当前值 |
| --- | --- |
| `coverage_min_roi_threshold` | `0.65` |
| `coverage_max_gap_fill_plans` | `3` |
| `coverage_max_gap_fill_rounds` | `1` |
| `artifact_store_dir` | `.runtime/wp11/raw_records` |
| `audit_store_dir` | `.runtime/wp11/audit` |
| `dedup_store_dir` | `.runtime/wp11/dedup` |
| `qdrant_local_path` | `.runtime/wp11/vector_memory` |
| `qdrant_collection_name` | `wp11_attack_signature_memory` |
| `persist_raw_records_to_db` | `True` |
| `payload_retention_days` | `30` |
| `cleanup_expired_payloads` | `False` |

### 4.5 Collection task 元信息

| 参数 | 当前值 |
| --- | --- |
| `collection_task_mode` | `fast` |
| `collection_trigger_type` | `manual` |
| `collection_created_by` | `api_live_run` |
| `resume_policy` | `full_restart` |
| `skip_completed_nodes` | `False` |

## 5. 每源默认预算

以下来自 `default_live().source_registry`，控制 supervisor 生成计划时各 source 的默认 `max_results` 和 `time_window_days`。

| source_name | source_type | enabled | default_max_results | default_time_window_days |
| --- | --- | --- | --- | --- |
| `nvd` | `structured` | `True` | `20` | `30` |
| `github_advisories` | `code` | `True` | `20` | `30` |
| `github_discussions` | `code` | `True` | `20` | `30` |
| `arxiv` | `paper` | `True` | `15` | `30` |
| `reddit` | `community` | `True` | `10` | `7` |
| `hackernews` | `community` | `True` | `10` | `7` |
| `cisa_kev` | `advisory` | `True` | `50` | `90` |
| `mitre_attack` | `structured` | `True` | `30` | `90` |
| `vendor_advisories` | `advisory` | `True` | `15` | `30` |
| `huggingface` | `code` | `True` | `10` | `30` |

补充说明：

- `planning_max_items_per_source=10` 是 supervisor 计划层的全局上限。
- source registry 里的预算是“源默认值”，不一定等于最终下发值；最终结果会受 supervisor plan、reflection 和 runtime override 共同影响。

## 6. 可人为调整的参数入口

### 6.1 `.env` 级

这些参数变更后，会影响所有 live run：

- `OPENAI_API_KEY`
- `OPENAI_API_BASE`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_FAST_MODEL`
- `POSTGRES_DSN`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SCHEMA`
- `POSTGRES_MIN_SIZE`
- `POSTGRES_MAX_SIZE`
- `POSTGRES_CONNECT_TIMEOUT`
- `POSTGRES_STATEMENT_TIMEOUT_MS`
- `POSTGRES_APPLICATION_NAME`

### 6.2 根目录 JSON 级

这些参数定义 LLM 池结构：

- `wp11_llm_profiles.json`
- `wp11_llm_route_presets.json`

其中：

- `wp11_llm_profiles.json` 定义“有哪些具体 profile 实例”
- `wp11_llm_route_presets.json` 定义“不同任务如何按标签挑选 profile”

### 6.3 Runtime context 级

这些参数由 `RuntimeContextDTO` 承载，适合通过 API 或运行时 override 调整：

- `llm_route_preset`
- `llm_task_routes`
- `llm_retry_attempts`
- `llm_backoff_base_seconds`
- `llm_backoff_max_seconds`
- `llm_short_wait_threshold_seconds`
- `llm_resume_on_exhausted_retry`
- `standardization_max_concurrency`
- `planning_max_parallel_sources`
- `planning_max_items_per_source`
- `planning_max_reflection_rounds`
- `planning_reflection_enabled`
- `coverage_max_gap_fill_rounds`
- `source_retry_attempts`
- `source_request_timeout_seconds`
- `persist_raw_records_to_db`

### 6.4 Source override 级

[runtime_tuning_service.py](/e:/@4C-2026/SUFE-SAADS-Qwen/backend/agents/intel_agents/services/runtime_tuning_service.py) 目前支持对单个 source 做细粒度 override：

- `enabled`
- `default_max_results`
- `default_time_window_days`

## 7. 攻击信息落库鲁棒性

当前实现已经具备以下保护：

- `DedupMemoryService.persist_records()` 按记录逐条事务提交
- 单条坏记录不会拖垮整批
- `attack_entry` 主写入与 evidence、taxonomy、component impact、CVSS 子链路隔离
- `score_origin` 会归一化到 `{supplied, calculated, estimated, manual}`
- `source_raw_id` 只有在 UUID 合法且库里存在时才写入
- 非法 `candidate_raw_id` 的 audit 只会被跳过，不会导致整批失败
- 失败记录和部分失败记录会落到 `.runtime/wp11/dedup/dead_letters/*.jsonl`
- graph state 中会回传 `dedup_persist_summary` 和 `dedup_audit_summary`

### 7.1 `dedup_persist_summary`

当前包含：

- `attempted_count`
- `persisted_count`
- `partial_failure_count`
- `failed_count`
- `dead_letter_count`
- `dead_letter_path`
- `failure_reasons`
- `substep_counts`

### 7.2 `dedup_audit_summary`

当前包含：

- `attempted_count`
- `persisted_count`
- `invalid_candidate_count`
- `missing_candidate_count`
- `failed_count`
- `failure_reasons`

### 7.3 写前处理原则

- `severity_level` 这类主字段不会静默纠错；非法时整条记录失败并进入 dead-letter
- `canonical_name`、`attack_family`、`summary`、`description` 等缺省字段允许补齐
- `confidence_score` 会被 clamp 到 `[0, 1]`
- 非法 taxonomy 项会被过滤
- 非法 CVSS 枚举会归一化
- 无效 raw_id 只跳过 evidence，不影响主记录落库

## 8. 常用验证入口

非 pytest 的验证入口如下：

```powershell
python main.py --validate-suite wp11_bugfixes
python main.py --validate-suite wp11_persist_robustness
python main.py --validate-suite wp11_llm_pool
python scripts/validate_wp11_bugfixes.py
```

如果要运行完整 live 流程：

```powershell
python main.py --mode bootstrap --scenario normal --verbose --live
```

在 `semantic_dedup_and_merge` 节点输出中，重点关注：

- `dedup_persist_summary`
- `dedup_audit_summary`
