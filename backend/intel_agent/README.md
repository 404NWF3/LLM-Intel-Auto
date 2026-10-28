# backend/intel_agent

以 **Claude Agent SDK** 为核心、loop-engineering + self-evolving 的 LLM 安全情报采集智能体。

本模块是**完全自包含**的：不 import 任何 `src/sufe_saads_crewai` 代码，自带 schema、源客户端、三层相关性过滤、持久化与自演化技巧库。老 `src/` 后端可随时删除而不影响本模块运行。

## 设计总览

```
backend/intel_agent/
├── schemas.py          # 自包含 Pydantic 模型（RawIntelItem / Blackboard / 决策输出…）
├── topics.py           # re-export common.topics（Core / Extended）
├── sources.py          # NVD / arXiv / CISA KEV / OSV 源客户端（含重试）
├── community_sources.py # V1 的 GitHub Issues / HN / HF Forum / Reddit RSS 来源适配
├── relevance.py        # 三层相关性过滤：rule → embedding → flash LLM
├── analysis.py         # 确定性分析层：合并/覆盖配额/停滞检测/fallback 组词
├── persistence.py      # JSON 存储：data/intel_runs/<run_id>.json + latest.json
├── mongo_store.py      # MongoDB 历史库：runs 集合 + 全局去重 items 集合（_id=item_id）
├── store.py            # 存储工厂：配置了 Mongo 走 Mongo，否则回退 JSON
├── observability.py    # --verbose 追踪：控制台 + data/intel_agent/traces/<run_id>.jsonl
├── runtime/            # SDK provider 解析、options 构建、tool-forcing 结构化决策
├── memory/             # 自演化技巧库 Playbook（upsert/衰减/召回/harvest）
├── tools/              # 轮内 @tool：源搜索 + recall/record + submit_round_summary
├── hooks.py            # 审批/预算/去重/时间窗的审计层（handler 同步复验）
├── agent/              # adaptive incremental 单 run 连续会话 + 隔离终止 critic
├── engine/             # 采集模式、轮次编排 controller、上下文 digest、rules fallback
├── cli.py              # intel-agent full / incremental / latest
└── tests/              # 离线单测（注入 fake runner/embedder，无需联网）
```

### 核心思路

- **agentic loop**：每轮由智能体在 SDK 原生 tool loop 里**自己调用**源工具（组合 NVD 的
  CWE/CVSS/时间窗、arXiv 字段与布尔、OSV 生态/包等高级算子），观察产出再决定下一步。
- **self-evolving**：高产出的算子组合被 harvest 成**自然语言技巧**写入 Playbook，下次运行前
  按语义相似度 + 历史收益召回注入上下文；持续不产出的技巧会衰减、废弃。
- **loop-engineering**：full 保留 quota；incremental v2 从历史库计算 Core CorpusGap，
  用 RunGap、单调用真实收益和 UCB 审批查询。critic 提供解释，预算、checkpoint、饱和条件
  与 rules fallback 由确定性控制面执行。
- **三层 fallback**：SDK 不可用 → 确定性 rules 轮次；结构化决策失败 → 规则兜底；相关性
  在线过滤失败 → 退回规则分。

## 两种采集模式

- **full（全量）**：覆盖 **Core** 话题配额（18 项，驱动 `open_gaps` / critic）；检索与标注同时覆盖
  **Extended**（另 15 项）。话题定义见 `backend/common/topics.py`。
  ```bash
  uv run intel-agent full --max-rounds 6 --max-api-calls 40
  ```
- **incremental（增量）**：默认启用 adaptive v2。18 个 Core 按 research / vulnerability
  证据渠道计算软覆盖缺口；15 个 Extended 可搜索和标注，但不设 coverage quota。
  NVD/arXiv 使用独立 checkpoint，并默认重叠回看 72 小时；OSV 只做实体/包定向确认。
  ```bash
  uv run intel-agent incremental --focus "agent tool abuse" --window-days 1
  uv run intel-agent incremental --focus "model extraction" --since 2026-07-01
  ```
- 查看最近一次结果：`uv run intel-agent latest`

回滚到原增量策略：`INTEL_INCREMENTAL_STRATEGY=legacy`。离线比较 UCB 与轮询基线：

```bash
uv run python scripts/bandit_replay.py
```

## 运行前提

```bash
uv sync --group dev
```
在 `.env` 配置 Anthropic 兼容端点（DeepSeek 或 GLM Coding Plan），见根目录 `.env.example`
中 `INTEL_SDK_PROVIDER` / `DEEPSEEK_*` / `GLM_*` 与 `backend/intel_agent` 段的调参项。
未配置密钥时会自动降级为**确定性 rules 采集**，仍可产出结果。

adaptive incremental 在一个 run 内复用同一个 `ClaudeSDKClient`，捕获 session ID，并按
resume → 携带当前 round 状态的新会话 → legacy rules 的顺序恢复。SDK options 显式禁用
内建工具和文件系统 settings，仅允许进程内 MCP 白名单；因此 `bypassPermissions` 不会暴露
Bash、Read、Write 或 Edit。`full` 和 `INTEL_INCREMENTAL_STRATEGY=legacy` 保持原有隔离会话/配额路径。

## V1 情报来源

四个社区来源复用现有 SDK 工具、rules fallback、相关性过滤、`RawIntelItem`、JSON/Mongo 存储和
`/api/intel/*` 接口。这里只迁移来源，不引入 V1 的标准化、归并、动态关键词、独立数据库或运行器；
不需要额外 OpenAI-compatible 模型配置，智能采集继续使用已有 `.env` 配置。

| 来源 | source_name / SDK 工具 | 默认状态 | 保存内容 |
|---|---|---|---|
| Hacker News | `hackernews` / `search_hackernews` | 启用 | 帖子/评论文本；链接帖可能只有标题，不抓取外链正文 |
| Hugging Face Forum | `discourse` / `search_hf_forum` | 启用 | 搜索摘录，标注 `search_excerpt` |
| GitHub Issues | `github_issues` / `search_github_issues` | 配置仓库/组织后启用 | Issue 正文及元数据，不含评论与 PR |
| Reddit RSS | `reddit` / `search_reddit` | 配置版块后启用 | 有界公开 RSS 条目，不保证历史完整性 |

在 `.env` 中按需配置（示例范围不作为代码默认值）：

```dotenv
INTEL_COMMUNITY_SOURCES=hackernews,discourse,github_issues,reddit
INTEL_GITHUB_REPOSITORIES=langchain-ai/langchain
# INTEL_GITHUB_ORGANIZATIONS=your-org
# GITHUB_TOKEN=  # 可选，提高 GitHub 限流额度
INTEL_REDDIT_SUBREDDITS=netsec
```

仓库、组织、版块可用逗号分隔。`INTEL_COMMUNITY_SOURCES=` 关闭全部社区来源；只保留部分名称可限制来源。
修改 `.env` 后重启 API/CLI 进程。GitHub token 仅用于该 API 的请求头，不保存到条目或日志。

每次来源工具调用获取一页，纳入现有 API 调用预算。HN、GitHub、HF 返回下一页参数；HF 保存整页，
避免本地截断后跳页。GitHub 搜索最多开放前 1000 条，达到上限需缩小查询/时间范围；RSS 没有续页。
增量采集按所选时间窗口筛选，GitHub 使用更新时间并保留首次发布时间。社区来源不推进全来源 checkpoint，
也不替代 adaptive 模式的 research / vulnerability_advisory 证据配额。
稳定 ID 沿用现有去重行为：同一条目的后续编辑不形成新条目。HTTP 403/429 等错误记录为来源失败，
不伪装为空结果成功，也不阻止其他来源采集。

`raw_text` 保存已取得的完整文本，原始 JSON/XML 条目保存在 `metadata.source_payload`。
工作台按 `content_scope` 显示内容范围，原有筛选、详情和完整导出直接支持新增来源。

## 测试

```bash
uv run pytest backend/intel_agent/tests -q
```
全部离线（注入 fake SDK runner / embedder），不联网、不需要密钥。

## 数据产物

- 运行结果：`data/intel_runs/<run_id>.json` + `latest.json`（未开 Mongo 时）。
- 技巧库：`data/intel_agent/playbook.jsonl`
- 相关性缓存：`data/intel_agent/relevance_cache.jsonl`
- verbose 追踪（`--verbose`）：`data/intel_agent/traces/<run_id>.jsonl`
- CSV 导出（Gradio Database / `mongoexport`）：`data/exports/`

### 完整原文、历史导入与修复

`raw_text` 不设置字符截断：arXiv 保存完整摘要（summary，保留段落换行），
NVD 保存完整漏洞描述，OSV 保存完整 details，CISA 保存来源描述与处置要求。
来源本身带省略号时保留原样，不生成缺失的内容。重复采集不会用空值或截短的前缀
覆盖已经保存的完整文本。列表摘要可作预览，工作台的“查看已采集原文（raw text）”
通过 `GET /api/intel/items/{item_id}` 按需读取全部文本；CSV 导出也保留完整字段。

工作台情报库右上角的“下载全部完整情报”通过 `GET /api/intel/export` 下载 JSON。
导出全库按 item_id 去重后的完整条目，不受当前搜索、来源、话题、任务筛选或列表条数限制。
文件包含 `format`、`exported_at`、`item_count` 和 `items`；每条情报保留完整 summary、
raw_text、metadata、来源链接、时间、主题及运行归属等详情字段（不含 Mongo 内部 `_id`）。
JSON 支持换行、引号和嵌套元数据，不再对原文做截断。

从仓库根目录执行：

```bash
uv run intel-agent import-csv intel_agent.items.csv --dry-run
uv run intel-agent import-csv intel_agent.items.csv
uv run intel-agent backfill-raw-text --dry-run
uv run intel-agent backfill-raw-text
```

导入支持 Mongo Compass 的点号／数组下标列与控制台导出，恢复 metadata、作者、主题及
run_ids。按 item_id 去重，同一文件使用固定导入任务 ID，重跑不产生重复任务。
历史 CSV 仅包含情报条目，导入任务不会虚构原来任务的轮次或日志；原 run_ids 仍可查询。
修复先用已保存的完整摘要补齐缺失或短前缀，再针对缺失／末尾省略号条目按来源 ID 回查。
Mongo Compass CSV 的字面量 `\n` 只在已有历史原文或来源回查能够确认时还原，保留代码中的合法转义。
同一情报在较早运行和批次中的缺失／短文本也会同步修复。
不会重新采集整个库，也不会改写已完成任务的状态或保存时间。
写入前备份与操作报告位于 `data/intel_agent/maintenance/<时间_标识>/`。
请在采集任务空闲时执行维护命令；源请求失败会记录在报告中并返回非零退出码，可重试。

## 历史库（MongoDB，可选）

把每次采集任务沉淀进数据库，并保证情报不重复：

```bash
docker compose up -d mongo                     # 起 Docker Mongo（宿主机端口 27018）
# .env 里设置（见 .env.example）：
#   INTEL_MONGO_URI=mongodb://localhost:27018
#   INTEL_MONGO_DB=intel_agent
uv run intel-agent full --verbose              # 自动落库 MongoDB
uv run intel-agent latest                      # 从当前存储读取最近一次
```

- `runs` 集合：每次采集任务一份文档（完整 blackboard，item 的 `raw_text` 移到 items 里以控体积）。
- `items` 集合：**以 `item_id` 作 `_id` 的全局去重库**。同一情报无论被多少轮采到，都只存一份；重复出现 upsert 并把 run 追加进 `run_ids`，刷新 `last_seen_at`。
- 大型运行／导入任务的 `runs` 文档仅存条目引用，读取时从 `items` 还原完整内容，避免 MongoDB 单文档大小限制。
- 查询 API（供 Gradio Database）：`list_run_summaries` / `query_items` / `distinct_sources` / `run_count`（JSON store 有对等实现）。
- 未配置 `INTEL_MONGO_*` 时回退 JSON，离线/测试零依赖。


## 控制台与部署

运行 `uv run web` 查看采集、情报态势、追踪、历史库与技巧库。完整启动与 Docker 操作见根目录 [README](../../README.md)。
