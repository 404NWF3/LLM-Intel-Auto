# 沙盒模拟智能体（WP1-3）

本模块将“情报采集 → GraphRAG 构建 → 沙盒审计”接入平台的 GraphRAG 工作台与 WP1-3。SAADS-Red-team 提供仓库对抗审计和离线攻击案例生成，图谱语料来自本项目的真实采集存储。源码版本与本地修订见 [UPSTREAM.md](UPSTREAM.md)。

现有仓库审计、离线案例、检查点和产物已归属 WP1-3。当前提供本地仓库只读审计与面向内置目标的离线案例生成；远程克隆、容器隔离和检测包执行尚未实现。新 WP1-2 的情报驱动检测流程见 [架构与数据契约设计](../../docs/specs/pentest-sandbox-redesign.md)，本轮仅完成设计。

## 目录

```text
backend/sandbox_agent/
  api.py                # /api/sandbox 路由
  service.py            # 任务、进程、预算、历史、产物边界
  worker.py             # 在独立环境中调用上游 CLI
  graph.py              # 从 JSON / Mongo 情报库导出可追溯语料
  graph_builder.py      # 原生 GraphRAG 构建、验证、检索检查
  tests/                # 平台接口与生命周期测试

backend/red_team/        # 旧导入兼容层与固定路径的上游运行时
  runtime/
    saads_grill_agent/  # 代码团队 / 红队 / 裁判的仓库审计
    saads_attack_agent/ # 图谱支持的离线案例生成
    llm_defense_graphrag/
    .claude/skills/     # 上游项目 Skills
    input/ config/ prompts/ scripts/ eval/ tests/
    pyproject.toml uv.lock settings.yaml
```

运行数据统一保存在根目录 `data/red_team/runs/rt_<id>/`：平台 `job.json`、`runtime.log`、审计参数 `request.yaml` 和上游 `results/`。报告、发现、测试草稿可以在页面预览和下载；恢复所需的会话与检查点保留在后端。

## 启动

从仓库根目录执行。红队使用独立的 Python 3.12 环境和上游锁文件，避免 GraphRAG、Claude SDK 与情报采集依赖互相影响。

```bash
uv sync --group dev
uv sync --project backend/red_team/runtime --frozen --group dev
uv run saads-api
```

另一个终端执行 `cd frontend && npm ci && npm run dev -- --hostname 127.0.0.1`，打开 <http://127.0.0.1:3000/dashboard/wp13>。`saads-api` 与 `intel-api` 启动的是同一个服务，默认端口 8001；只启动其中一个，单进程运行。情报采集和红队各自允许一个活动任务。

模型配置沿用根目录 `.env` 的 `DEEPSEEK_API_KEY`。可用 `DEEPSEEK_CHAT_MODEL` 单独指定红队模型；未指定时依次采用 `DEEPSEEK_MODEL`、DeepSeek 采集配置中的 `INTEL_SDK_MODEL`、`deepseek-flash`。上游限定 DeepSeek 官方 Anthropic 兼容端点。环境变量优先于根目录 `.env`，根目录优先于 `runtime/.env`。密钥不发送给浏览器。

## 情报 → GraphRAG → 沙盒审计

1. 在 WP1-1 采集情报。构建器直接读取 `default_store()` 的完整持久化语料，兼容 JSON 与 MongoDB，按情报编号去重。
2. 在独立 GraphRAG 工作台（`/dashboard/graphrag`）选择入图关键词与数量，点击“从情报构建图谱”。关键词匹配标题、摘要与元数据；按相关性和发布时间排序。默认最多 100 条，可选 2–2000 条，每条使用标题、最多 6000 字符摘要及来源信息。
3. 构建器调用 Microsoft GraphRAG 3.1.1 的原生标准工作流，生成文档、文本块、实体、关系、社区和社区报告。复用 DeepSeek，通过社区全局检索取证，无需额外 embedding 密钥；这是 GraphRAG 的 Global Search 模式，尚未启用向量 Local/DRIFT Search。
4. 必需表非空、文档来源对应、关系端点有效、实际检索成功后，才将索引原子切换为活动版本。构建失败或停止会保留旧索引。
5. 后续仓库审计与离线案例自动读取活动图谱。每个任务固定其启动时的图谱路径，恢复任务时沿用该版本，避免混用证据。

图谱与沙盒使用独立页面和历史列表，后端仍共用单任务队列，构建期间可以继续采集。`GET /api/sandbox/runs` 可通过 `workspace=graph` 或 `workspace=sandbox` 先按工作台筛选，再取最近 50 次记录；概览的 `active_run_kind` 用于区分正在构建图谱还是运行红队任务。新采集的情报在下次手动更新图谱时纳入，不会自动产生模型费用。构建调用模型，数量上限控制语料规模，并设置一小时构建超时；GraphRAG 查询费用不包含在 Claude SDK 的红队费用估算中。

索引位于 `data/red_team/runs/<id>/results/graph/`，活动指针为 `data/red_team/active_graph.json`。`source_manifest.json` 保存情报 ID、原文 URL、入图文档 ID 和截断标记；`manifest.json` 保存语料散列、范围、模型和图谱规模；`query_check.json` 保存实际检索验证，`report.md` 可在页面查看。社区报告是模型生成分析，需要结合原始来源核验。

## 仓库对抗审计

填写本机仓库目录、授权记录（例如自有项目说明或工单编号）、审计目标及预算。只接受本地目录；上游通过只读 MCP 工具读取代码，生成的测试草稿写入任务目录，不会自动执行被审计项目。

页面展示真实检查点、威胁面、确认发现、运行事件、历史记录和报告。没有图谱时仍可使用代码证据审计。关闭页面不停止任务；“停止任务”终止该任务的进程组。服务重启后未完成任务显示为中断，不会自动继续。

“从检查点恢复”复用原任务的目标、授权和模型会话，追加原配置的一份调用与费用额度；目标代码内容变化会拒绝恢复，应创建新任务。没有检查点或已完成的任务不能恢复。

调用次数是上游团队轮次，不等于底层模型 HTTP 请求数。费用为 SDK 返回的估算值，可能与 DeepSeek 实际计费不同；调度器在调用结束后检查预算，上游还可能执行裁判收尾和测试草稿生成，因此预算不是严格的支付上限。实际账单以供应商为准。

## 离线攻击案例

支持提示词注入、长对话越界、工具劫持，生成 `attack_case.json` 和面向内置模拟目标的 `attack.py`。

完成上述情报图谱构建后，案例生成入口自动启用。没有活动图谱时，页面提示先构建；不需要人工搬运 `output/`。

如需使用另一个已有的上游向量图谱，可在根目录 `.env` 显式设置 `RED_TEAM_GRAPH_ROOT`（包含 `settings.yaml` 与 `output/` 的目录），并配置该索引所用的 `ZAI_API_KEY`、`ZHIPU_API_KEY` 等变量。显式目录优先于平台活动指针；常规情报图谱流程无需设置这些变量。

## 接口与兼容

`/api/sandbox/*` 为主接口，`/api/redteam/*` 保留为弃用别名，共享同一服务实例与任务锁。`workspace=sandbox` 与旧的 `workspace=redteam` 等价。数据目录、任务 ID、活动图谱指针、`RED_TEAM_GRAPH_ROOT` 以及 `backend/red_team/runtime/` 的独立虚拟环境保留原路径；不会搬动旧任务或改变恢复语义。`red_team.api/service/graph` 仅为兼容导出，平台实现请在 `sandbox_agent` 维护。

后端无活动任务时重启 `saads-api`，前端重新加载后使用新路径。

## 接口与验证

- `GET /api/sandbox/overview`：运行环境、模型、图谱能力和活动任务。
- `POST /api/sandbox/graph/build`：从情报库构建索引，接受 `limit`、`focus`。
- `GET/POST /api/sandbox/runs`：最近 50 次任务 / 创建任务。
- `GET /api/sandbox/runs/{id}`：进度、发现、日志、产物。
- `POST /api/sandbox/runs/{id}/stop`、`.../resume`：停止 / 恢复。
- `GET /api/sandbox/runs/{id}/artifact?path=...`：仅下载任务白名单产物。

```bash
uv run pytest backend/intel_agent/tests backend/console/tests backend/sandbox_agent/tests -q
uv run --project backend/red_team/runtime pytest backend/red_team/runtime/tests/saads_grill_agent backend/red_team/runtime/tests/saads_attack_agent -q
cd frontend
npm test
npm run type-check
npm run build
```

API 沿用平台的本机单用户模式，不含登录鉴权。保持监听 `127.0.0.1`，不要用多 worker 或在有任务时启用自动重载。
