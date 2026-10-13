# WP1-1 LLM 配置池手册

## 1. 适用范围

本文面向负责模型接入、任务路由、并发预算和故障切换的开发或平台维护者，说明 WP1-1 当前 LLM 配置池的结构、配置方式、路由逻辑和运行时行为。

## 2. 当前实现结论

当前系统已经支持“多 profile 候选池 + 按任务标签路由 + 单 profile 并发上限 + 全满等待 + 失败后切换下一个 profile”。

当前系统不具备“对所有模型做质量评估后自动挑最优”的智能调度能力。它的真实语义是：

1. 每个任务先根据 preset 或 runtime override 得到一个标签路由，例如 `["cheap_fast", "balanced", "fallback"]`
2. 系统再把这个标签路由展开成具体 profile 列表，例如 `["101", "102", "201", "301"]`
3. 调用时按展开后的顺序尝试
4. 若某个 profile 已满、冷却中或失败，则继续尝试下一个
5. 若全部不可用，则等待到阈值后报 `pool_exhausted`

## 3. 配置文件位置

当前推荐配置入口是仓库根目录的两个文件：

- [wp11_llm_profiles.json](/e:/@4C-2026/SUFE-SAADS-Qwen/wp11_llm_profiles.json)
- [wp11_llm_route_presets.json](/e:/@4C-2026/SUFE-SAADS-Qwen/wp11_llm_route_presets.json)

兼容 fallback 仍存在：

- `WP11_LLM_PROFILES_JSON`
- `WP11_LLM_ROUTE_PRESETS_JSON`

但当根目录文件存在时，系统优先读取文件，并把 env JSON 视为过时入口。

## 4. Profile 模型

每个 profile 现在包含两层身份：

- `profile_id`
  具体实例编号，必须是字符串数字，例如 `"101"`
- `profile`
  标签分层，必须属于 `cheap_fast | balanced | fallback`

这意味着：

- `profile_id` 用于并发占用计数、冷却、审计和精确定位
- `profile` 用于路由分层
- 一个标签下可以挂多个具体 profile

### 4.1 当前仓库中的 profile 文件

当前仓库默认带了 4 个 profile：

| profile_id | profile | model 来源 | max_concurrency | cooldown_seconds |
| --- | --- | --- | --- | --- |
| `101` | `cheap_fast` | `OPENAI_FAST_MODEL` | `1` | `20` |
| `102` | `cheap_fast` | `OPENAI_MODEL` | `1` | `20` |
| `201` | `balanced` | `OPENAI_MODEL` | `1` | `30` |
| `301` | `fallback` | `OPENAI_MODEL` | `1` | `45` |

说明：

- 当前你的 `.env` 中 `OPENAI_MODEL` 和 `OPENAI_FAST_MODEL` 一样，所以 4 个 profile 现在会解析到同一模型名。
- 如果你想让 `cheap_fast`、`balanced`、`fallback` 真正映射到不同模型，需要改 `model` 或 `model_env`。

## 5. `wp11_llm_profiles.json` 字段说明

每个 profile 至少包含：

- `profile_id`
- `profile`
- `provider`
- `model` 或 `model_env`
- `base_url` 或 `base_url_env`
- `api_key` 或 `api_key_env`
- `enabled`
- `supports_structured_output`
- `cost_tier`
- `max_concurrency`
- `cooldown_seconds`

示例：

```json
{
  "profiles": [
    {
      "profile_id": "101",
      "profile": "cheap_fast",
      "provider": "openai_compatible",
      "model_env": "OPENAI_FAST_MODEL",
      "base_url_env": "OPENAI_API_BASE",
      "api_key_env": "OPENAI_API_KEY",
      "enabled": true,
      "supports_structured_output": true,
      "cost_tier": "cheap",
      "max_concurrency": 1,
      "cooldown_seconds": 20
    },
    {
      "profile_id": "201",
      "profile": "balanced",
      "provider": "openai_compatible",
      "model": "deepseek/deepseek-chat",
      "base_url_env": "OPENAI_API_BASE",
      "api_key_env": "OPENAI_API_KEY",
      "enabled": true,
      "supports_structured_output": true,
      "cost_tier": "standard",
      "max_concurrency": 2,
      "cooldown_seconds": 30
    }
  ]
}
```

## 6. `wp11_llm_route_presets.json` 写法

route preset 现在按 `profile` 标签写，不按具体 `profile_id` 写。

示例：

```json
{
  "default": {
    "planning": ["balanced", "cheap_fast", "fallback"],
    "reflection": ["balanced", "cheap_fast", "fallback"],
    "standardization": ["balanced", "cheap_fast", "fallback"],
    "bom_resolution": ["cheap_fast", "balanced", "fallback"],
    "dedup_merge": ["balanced", "cheap_fast", "fallback"],
    "dedup_adjudication": ["balanced", "fallback", "cheap_fast"],
    "coverage": ["cheap_fast", "balanced", "fallback"]
  }
}
```

当前固定支持的任务键：

- `planning`
- `reflection`
- `standardization`
- `bom_resolution`
- `dedup_merge`
- `dedup_adjudication`
- `coverage`

## 7. 标签展开逻辑

这是这次重构的核心。

如果某个任务的路由是：

```json
["cheap_fast"]
```

而 profile 文件中存在：

- `101 -> cheap_fast`
- `102 -> cheap_fast`

那么运行时实际候选列表会被展开成：

```json
["101", "102"]
```

展开规则如下：

1. 按 route 中标签出现顺序处理
2. 同一标签下的具体 profile 按数字 `profile_id` 升序展开
3. 同一 profile 只会出现一次
4. 若某个标签在当前 profile 文件中没有任何启用中的配置，直接报配置错误

因此：

- 一个 `cheap_fast` 标签可以对应多个真实配置
- 第一个 `cheap_fast` 满载时，系统会继续尝试第二个 `cheap_fast`
- 多个 `cheap_fast` 的并发预算会被汇总

## 8. 并发占用与等待逻辑

系统现在按具体 `profile_id` 跟踪占用状态，而不是按标签跟踪。

### 8.1 正在工作的标记

内部使用：

- `_PROFILE_ACTIVE_COUNT`
- `_PROFILE_COOLDOWN_UNTIL`

键都是具体的数字 `profile_id`，例如 `"101"`、`"102"`。

### 8.2 单 profile 上限

每个 profile 都有自己的 `max_concurrency`。

含义是：

- 某个 profile 同时工作的请求数不能超过它的 `max_concurrency`
- 到达上限后，该 profile 本轮不会继续接新任务

### 8.3 全满时等待

当某条 route 展开的所有 profile 都满载时：

- 系统会在 `llm_short_wait_threshold_seconds` 窗口内轮询等待
- 如果窗口内仍无可用 slot，就报 `pool_exhausted`

这满足你想要的行为：

- “不能超过一个配置的并发上限”
- “所有配置都被占满时就等待”

## 9. 并发预算如何计算

`recommended_task_concurrency()` 的逻辑现在是：

1. 先解析任务路由
2. 再按标签展开成全部具体 profile
3. 对这些 profile 中“启用、支持结构化输出、且具备连接配置”的条目求和 `max_concurrency`
4. 最后再受 `upper_bound` 限制

这意味着：

- 如果某任务路由为 `["cheap_fast"]`
- 且 `cheap_fast` 下有两个 profile，分别为 `max_concurrency=1` 和 `1`
- 那么该任务的推荐并发预算就是 `2`

## 10. Runtime override 写法

运行时仍可通过 `llm_route_preset` 和 `llm_task_routes` 覆盖默认路由。

注意：`llm_task_routes` 现在也按标签写，不按数字 id 写。

示例：

```json
{
  "llm_route_preset": "cost_saver",
  "llm_task_routes": {
    "standardization": ["balanced", "fallback"],
    "bom_resolution": ["cheap_fast"],
    "coverage": ["cheap_fast", "fallback"]
  }
}
```

## 11. 审计与可观测性

运行时 meta 和审计对象现在同时保留：

- `profile_id`
- `profile`

这解决了“日志里只看到数字，不知道它属于哪一层”的问题。

以 LLM 调用 meta 为例，现在可见：

- `profile_id`
- `profile`
- `selected_route_labels`
- `attempted_profiles`
- `attempted_profile_labels`

## 12. 推荐实践

### 12.1 Profile 设计

- `cheap_fast` 适合高频、预算敏感、可接受轻微质量波动的任务
- `balanced` 适合 planning、reflection、dedup_merge 这类更依赖稳定性的任务
- `fallback` 适合容灾，不建议承担主流量

### 12.2 多个同标签配置

- 若你真想提升同标签吞吐，优先给这个标签挂多个真实独立配置
- 最好是不同 key、不同 provider 或不同限流桶
- 如果只是复制多个使用同一 key 的 profile，代码层面虽然能并发，但 provider 侧不一定真的扩容

### 12.3 路由建议

- `planning`、`reflection`、`dedup_merge` 优先 `balanced`
- `bom_resolution`、`coverage` 优先 `cheap_fast`
- `standardization` 如果质量要求高，可以让 `balanced` 在前，`cheap_fast` 在后

## 13. 常用验证入口

```powershell
python main.py --validate-suite wp11_llm_pool
```

这套验证会检查：

- profile 是否从根目录 JSON 读取
- `profile_id` 是否为数字字符串
- route preset 是否按标签写
- `cheap_fast` 是否能展开成多个具体 profile
- 并发预算是否按展开后的 profile 求和
- 第一个 `cheap_fast` 满载时，是否会切换到同标签下一个 profile
- 所有 `cheap_fast` 满载时，是否会等待后报 `pool_exhausted`
