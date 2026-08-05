# LLM Security Intel Pipeline

一个面向大语言模型（LLM）与智能体系统安全的**真实情报采集、质量分析和知识图谱构建平台**。

项目从 NVD、CISA KEV、OSV.dev 和 arXiv 持续采集 LLM/AI 安全信息，使用 Claude Agent SDK 驱动多轮检索与反思，并通过确定性规则保证在模型或端点不可用时仍能运行。采集结果可以保存为本地 JSON 或写入 MongoDB；随后可按情报条目生成 CTINexus 小型知识图谱，也可以使用独立的 top-down 流水线从 PDF 语料构建 Neo4j 领域基底图。

> 当前项目名仍保留 `sufe_saads_crewai`，但运行主线已经迁移到 `backend/` 下的 Claude Agent SDK 架构，不再以旧 CrewAI 包作为入口。项目版本见 `pyproject.toml`，当前为 `0.2.0`。

## 项目要解决什么问题

LLM 安全信息分散在漏洞库、已利用漏洞清单、开源软件公告和学术论文中，单纯关键词抓取会遇到噪声高、重复多、来源覆盖不均和检索策略固定等问题。本项目把这项工作拆成四层：

1. **采集**：从真实公共数据源检索漏洞、利用证据与研究论文。
2. **判断**：识别 LLM 安全相关性，按主题、来源、证据通道和时效评估覆盖度。
3. **决策**：根据历史收益、覆盖缺口、重复率和噪声率选择下一轮查询，并在边际收益变低时停止。
4. **构图**：为单条情报生成 item-level KG，或从领域 PDF 语料构建独立的 base KG。

当前正式主题体系包含：

- **18 个 Core 主题**：驱动覆盖配额、缺口分析和停止判断。
- **15 个 Extended 主题**：参与检索、标注和趋势发现，但不进入 Core 覆盖率分母。

<details>
<summary>展开查看完整主题体系</summary>

Core：

- prompt injection
- jailbreak
- agent tool abuse
- data leakage
- model supply chain
- rag poisoning
- insecure output handling
- excessive agency
- model denial of service
- unbounded consumption
- model backdoor
- agent loop and cascading failure
- multi-agent communication attack
- unsafe code generation and execution
- sandbox escape
- plugin and mcp trust attack
- authentication and authorization bypass
- unsafe file handling

Extended：

- training and fine-tuning data poisoning
- adversarial examples
- model extraction
- membership inference
- model inversion
- training data extraction
- system prompt leakage
- context isolation failure
- memory poisoning
- agent impersonation
- server-side request forgery
- internal network reconnaissance
- misinformation and citation fabrication
- insufficient logging and monitoring
- model routing and downgrade attack

</details>

主题关键词和语义锚文本的唯一实现位于 `backend/common/topics.py`。

## 总体架构

```text
NVD / arXiv / CISA KEV / OSV.dev
                 │
                 ▼
       backend/intel_agent
  Agent SDK 工具循环 + rules fallback
  相关性判断 / 覆盖缺口 / UCB / Playbook
                 │
        ┌────────┴────────┐
        ▼                 ▼
本地 JSON              MongoDB
data/intel_runs        runs / items
        └────────┬────────┘
                 ▼
         backend/console
  采集 / 态势 / 轨迹 / KG / 数据 / 记忆
                 │
                 ▼
       backend/ctinexus_kg
          单条情报子图

PDF 语料 ──> base_kg ──> Neo4j 领域基底图
```

关键边界：

- `intel_agent` 只负责采集和持久化，不 import `ctinexus_kg`。
- `ctinexus_kg` 只消费结构兼容的 item DTO，不 import `intel_agent`。
- `console` 是唯一同时依赖采集和 item-KG 两侧的 UI 编排层。
- `base_kg` 是独立实验流水线，目前没有与 CTINexus item-KG 自动融合。

## 已实现功能

### 1. LLM 安全情报采集

| 数据源 | 主要用途 | 支持的高级参数 |
|---|---|---|
| NVD CVE API 2.0 | CVE、CWE、CVSS、产品与漏洞描述 | keyword、精确匹配、CVE ID、CWE、CVSS v3 severity、发布时间窗、KEV、分页 |
| arXiv Atom API | LLM 安全论文与预印本 | 字段/布尔查询、`cs.CR` / `cs.AI` / `cs.CL` 分类、分页 |
| CISA KEV JSON | 已知在野利用证据 | CVE ID 列表、关键词 |
| OSV.dev API | PyPI、npm 等开源生态漏洞 | ecosystem、package、version、purl、vulnerability ID |

采集器提供两种模式：

- `full`：无时间窗的全量采集，以 Core 主题覆盖配额为目标，同时允许命中 Extended 主题。
- `incremental`：按 focus 和时间窗做增量采集；默认 `adaptive` 策略会读取历史去重语料、按 NVD/arXiv 分别维护 checkpoint，并回看 72 小时以容纳延迟入库的数据。

采集过程中已经实现：

- Claude Agent SDK 原生工具循环，自主选择来源、检索词和高级算子。
- SDK 不可用、单轮失败或结构化决策失败时的确定性 fallback。
- 每次 API 调用预算、重复查询拦截、时间窗和候选查询审批。
- 基于历史调用结果的 UCB 查询组合排序。
- 新增量、相关新增、重复率、噪声率、延迟、reward 和覆盖变化归因。
- Core 的 research / vulnerability-advisory 证据通道覆盖与 freshness 衰减。
- Extended 主题近 30 天趋势和正式 taxonomy 之外的候选主题发现。
- 跨运行的自演化 Playbook：沉淀高收益搜索技巧，按语义和历史 reward 召回，持续低收益的技巧自动衰减。

### 2. 相关性与质量控制

源解析阶段始终会给出启发式 `relevance_score`。配置 GLM OpenAI-compatible 接口后，还可以启用三层相关性管线：

1. 规则阈值快速接收或拒绝。
2. title + summary 与主题锚文本做 embedding 相似度判断，并用 content hash 写入缓存。
3. 对中间不确定区间调用 fast LLM 批量裁决。

缓存写入 `data/intel_agent/relevance_cache.jsonl`。如果未设置 `GLM_API_KEY` 或关闭 `INTEL_RELEVANCE_ENABLED`，采集仍可运行，但不会启用这套在线 embedding/LLM 标注管线。

### 3. 持久化、去重与可观测性

系统通过同一套 Store 接口支持两种后端：

| 后端 | 启用方式 | 行为 |
|---|---|---|
| JSON | 未启用 Mongo 时的默认值 | 每个 run 写一个完整 JSON；查询时按 `item_id` 做 best-effort 去重 |
| MongoDB | 设置 `INTEL_MONGO_URI` 或 `INTEL_MONGO_ENABLED=1` | `runs` 保存每次任务，`items` 以 `item_id` 为 `_id` 全局去重，并通过 `run_ids` 保留溯源 |

Mongo 的 `runs.blackboard.raw_items` 会去掉体积较大的 `raw_text`，原文保留在全局 `items` 集合。Mongo 写入失败时，控制器会记录错误并回退到本地 JSON。

使用 `--verbose` 可以把逐轮事件、模型文本、工具调用、工具结果、critic 决策和 fallback 原因同时输出到控制台和 JSONL。Gradio Collect 页也使用同一个 `TraceSink` 实时显示轨迹。

### 4. CTINexus item-level 知识图谱

`backend/ctinexus_kg` 为一条已落库情报生成一张独立子图。默认资格条件为：

- 存在 `raw_text`，或至少存在 `summary`；
- `relevance_score >= 0.5`；
- 能命中一个正式 LLM 安全主题；
- 来源不在排除列表中，默认排除 `arxiv_api`。

构图时只把 `raw_text`（为空则使用 `summary`）传给 CTINexus，`source_uri` 仅用于本项目溯源。默认模型为 `glm-4.7`，embedding 为 `embedding-3`，实体对齐阈值为 `0.6`。

每条成功、失败或跳过的记录都会被保留；单条失败不会回滚已采集情报，也不会中止批处理中其他条目。Gradio 提供单条、小批量和可续跑的大批量生成，并可按以下策略处理已有记录：

- 跳过成功项、重试失败项；
- 仅生成从未处理项；
- 全部重新生成。

底层已经提供 triplet feedback 的 JSONL 读写 API，但当前 UI 尚未提供人工接受、拒绝或修改三元组的闭环页面。

### 5. Gradio 统一控制台

`uv run --env-file .env web` 启动的控制台包含 6 个页面：

| 页面 | 功能 |
|---|---|
| Collect | 运行 full / incremental 采集、设置预算、查看实时轨迹、加载最近一次 run |
| 情报态势 | Core 覆盖矩阵、覆盖 KPI、数据健康、开放缺口、来源质量、12 周趋势、Extended 趋势、候选主题 |
| Trace replay | 按 `run_id` 回放 `data/intel_agent/traces/*.jsonl` |
| Knowledge Graphs | 从已持久化 items 筛选 kg-ready 条目，执行单条、小批量或可续跑大批量构图 |
| Database | 浏览 runs、全局 items 和 knowledge graph records，并导出 UTF-8 BOM CSV |
| Memory | 浏览 Playbook 技巧和 relevance embedding cache，并导出 CSV |

### 6. 独立 base-KG 流水线

`base_kg` 使用 top-down 方法从 PDF 语料构建 LLM 安全领域基底图：

```text
PDF -> 单文档 chunk -> 相关性过滤
    -> NER -> 实体标准化 -> 关系抽取
    -> schema domain/range/自环校验
    -> Neo4j 幂等写入
    -> 结构复杂度 + 语义重构准确性评估
```

当前 schema 为 v0.2.0，包含 27 个实体类型和 30 个关系。节点按“实体类型 + 小写规范名”合并，节点和关系都累积来源文档。评估包含实体冗余、关系冗余、自环、平均度，以及基于子图重构和句级最大余弦相似度的语义保真度。

## 目录结构

```text
backend/
├── common/                 # Core/Extended 主题、关键词与锚文本
├── intel_agent/            # 采集引擎、源客户端、Agent loop、Store、Memory
│   ├── agent/              # 连续 SDK 会话与终止 critic
│   ├── engine/             # full/incremental、gap、UCB、controller、fallback
│   ├── memory/             # Playbook 的召回、更新、衰减与持久化
│   ├── runtime/            # provider 解析与结构化决策
│   ├── tools/              # 进程内 MCP 源工具、记忆工具和控制工具
│   └── tests/
├── ctinexus_kg/            # item-KG 资格判断、适配器、manifest、feedback
└── console/                # Gradio UI、态势、数据库、KG 和记忆面板

base_kg/
├── schema/                 # v0.2 机器可读 LLM 安全 schema
├── prompts/                # 过滤、NER、标准化、关系抽取、文本重构 prompt
└── pipeline/               # corpus / filter / extract / load / evaluate

scripts/
├── smoke_pipeline.py       # 离线集成冒烟
├── bandit_replay.py        # UCB 与轮询策略离线回放
└── query_*/filter_*        # 数据源探索与一次性研究辅助脚本

docs/                       # 路线图、进展和会话纪要；部分章节保留历史架构记录
report/                     # 论文、Beamer 报告和证据矩阵，不参与运行时
data/                       # 本地数据与产物，整目录被 gitignore
ctinexus_output/            # CTINexus 可能生成的原始可视化 HTML
```

## 环境要求

### 必需环境

- Python `>=3.10,<3.14`；当前 Docker 镜像使用 Python 3.12。
- `uv`，用于依赖同步、虚拟环境和命令执行。
- 能访问 NVD、arXiv、CISA 和 OSV.dev 的网络环境。

如果希望启用 Claude Agent SDK 的 agentic loop，本地还应安装 Node.js 和 Claude Code CLI。Dockerfile 已安装 Node.js 20 与 `@anthropic-ai/claude-code`。CLI 或模型端点不可用时会自动降级到规则采集。

可选组件：

- MongoDB 7：历史库和全局去重；不安装时使用 JSON。
- CTINexus 所需的 chat / embedding API：生成 item-KG 时需要。
- Neo4j 5.x：只在运行独立 base-KG 的 `load` / `all` 阶段需要。

主要 Python 依赖由 `pyproject.toml` 锁定：Claude Agent SDK `>=0.2.115,<0.3`、Pydantic `>=2.7`、PyMongo `>=4.6`、CTINexus `0.2.1`、Gradio `>=5,<6` 和 Matplotlib。`basekg` 依赖组额外安装 Neo4j driver、OpenAI-compatible client、pypdf 与 NumPy；`dev` 组安装 pytest 和 mongomock。

### 安装依赖

在仓库根目录执行：

```bash
# 采集 + item-KG + Web + 测试
uv sync --group agentsdk --group intelagent --group ctinexuskg --group web --group dev

# 如果还要运行独立 base-KG
uv sync --all-groups
```

如果本地需要 agentic loop，但系统还没有 `claude` 命令：

```bash
npm install -g @anthropic-ai/claude-code
claude --version
```

复制环境变量模板：

```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

```bash
# Linux / macOS
cp .env.example .env
```

本地运行推荐统一带 `--env-file .env`。采集 SDK、Mongo 和 base-KG 内部会自行读取部分 `.env` 配置，但 relevance、CTINexus 和 Gradio 直接读取进程环境；显式传入可以避免不同模块加载行为不一致。

## 环境变量配置

### 1. 采集 Agent 的模型端点

不配置任何 LLM key 也可以运行：系统会调用真实公共数据源，并使用确定性规则完成检索与停止判断。

DeepSeek Anthropic-compatible 端点：

```dotenv
INTEL_SDK_PROVIDER=deepseek
DEEPSEEK_API_KEY=your_key
# 可选，默认 deepseek-v4-pro / deepseek-v4-flash
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_FAST_MODEL=deepseek-v4-flash
```

GLM Anthropic-compatible 端点：

```dotenv
INTEL_SDK_PROVIDER=glm
GLM_API_KEY=your_key
# SDK 默认使用固定 Anthropic-compatible 地址；以下模型可覆盖默认值
GLM_MODEL=glm-4.7
GLM_FAST_MODEL=glm-4.5-air

# relevance、CTINexus 和 base-KG 使用 OpenAI-compatible 地址
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

自定义 Anthropic-compatible 端点会覆盖 provider 的地址和凭证：

```dotenv
ANTHROPIC_BASE_URL=https://your-endpoint.example/anthropic
ANTHROPIC_AUTH_TOKEN=your_key
INTEL_SDK_MODEL=your_main_model
INTEL_SDK_FAST_MODEL=your_fast_model
```

未显式设置 `INTEL_SDK_PROVIDER` 时，有 `DEEPSEEK_API_KEY` 会优先使用 DeepSeek，其次使用 GLM。

### 2. 采集策略与相关性

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `INTEL_INCREMENTAL_STRATEGY` | `adaptive` | 增量策略；可设为 `legacy` 回滚到简单配额循环 |
| `INTEL_INCREMENTAL_OVERLAP_HOURS` | `72` | NVD/arXiv checkpoint 回看窗口 |
| `INTEL_COVERAGE_QUOTA` | `3` | legacy/full 模式中每个 Core 主题的相关条目配额 |
| `INTEL_STALL_PATIENCE` | `2` | legacy 模式连续低收益轮容忍数 |
| `INTEL_MIN_NEW_RELEVANT_PER_CALL` | `0.5` | legacy 模式低收益判断阈值 |
| `INTEL_AGENT_MAX_TURNS` | `24` | 每轮 SDK 工具 turn 上限 |
| `INTEL_AGENT_HOOKS` | `1` | 开启预算、去重和时间窗审计 hooks |
| `INTEL_PLAYBOOK_ENABLED` | `1` | 开启跨运行检索技巧记忆 |
| `INTEL_PLAYBOOK_EMBED` | `1` | 有 GLM key 时为 Playbook 写语义向量 |
| `INTEL_AGENT_PLAYBOOK_PATH` | `data/intel_agent/playbook.jsonl` | Playbook 文件位置 |
| `INTEL_RELEVANCE_ENABLED` | `1` | 开启在线三层相关性管线 |
| `INTEL_EMBEDDING_MODEL` | `embedding-3` | 相关性 embedding 模型 |
| `INTEL_RELEVANCE_JUDGE_MODEL` | `GLM_FAST_MODEL` / `glm-4.7-flash` | 第三层裁决模型 |
| `NVD_API_KEY` | 空 | 可选；提升 NVD API 配额 |

代码还支持相关性阈值覆盖：`INTEL_RELEVANCE_ACCEPT`、`INTEL_RELEVANCE_REJECT`、`INTEL_RELEVANCE_EMB_ACCEPT`、`INTEL_RELEVANCE_EMB_REJECT`，默认分别为 `0.75`、`0.20`、`0.62`、`0.42`。

> `.env.example` 中的 `INTEL_ENGINE`、`INTEL_MIN_ROUNDS` 和 `INTEL_KG_AUTO_BATCH` 是历史/预留配置，当前 `backend/` 运行主线没有读取它们，请不要依赖这些开关控制行为。

### 3. MongoDB

本地直接运行并连接 Compose Mongo：

```dotenv
INTEL_MONGO_URI=mongodb://localhost:27018
INTEL_MONGO_DB=intel_agent
INTEL_MONGO_HOST_PORT=27018
```

也可以只设置 `INTEL_MONGO_ENABLED=1`，此时默认 URI 就是 `mongodb://localhost:27018`。Compose 内部会覆盖为 `mongodb://mongo:27017`。

### 4. CTINexus item-KG

```dotenv
CTINEXUS_API_KEY=your_key
CTINEXUS_BASE_URL=https://your-openai-compatible-endpoint/v1
CTINEXUS_MODEL=glm-4.7
CTINEXUS_EMBEDDING_MODEL=embedding-3
```

API key 回退顺序是 `CTINEXUS_API_KEY -> OPENAI_API_KEY -> GLM_API_KEY`。控制台解析 base URL 时优先 `CTINEXUS_BASE_URL`，其次 `GLM_BASE_URL`，再其次 `OPENAI_BASE_URL` / `OPENAI_API_BASE`。

### 5. base-KG

```dotenv
BASEKG_LLM_API_KEY=your_key
BASEKG_LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
BASEKG_LLM_MODEL=glm-4.7
BASEKG_EMBEDDING_MODEL=text-embedding-3-large

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

base-KG 的凭证回退顺序为 `BASEKG_* -> OPENAI_* -> GLM_*`。批量抽取还支持：

- `BASEKG_LLM_API_KEYS`：逗号分隔的 key 池；未设置时尝试 `GLM_API_KEY`、`GLM_API_KEY_1..9`。
- `BASEKG_CONCURRENCY`：并发文档数。
- `BASEKG_NER_MODEL` / `BASEKG_STD_MODEL` / `BASEKG_RE_MODEL` / `BASEKG_FILTER_MODEL`：分阶段模型。
- `BASEKG_REQUEST_INTERVAL`：同一 key 上两次请求的最小间隔。
- `BASEKG_DISABLE_THINKING`：为兼容端点关闭 thinking。
- `BASEKG_SOURCE_DIR` / `BASEKG_OUTPUT_DIR`：覆盖语料与输出路径。

### 6. Web 服务

```dotenv
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_SERVER_PORT=8000
```

本地和 Compose 默认都监听 8000 端口。`IS_SANDBOX=1` 主要用于以 root 运行的 Docker 环境，Compose 和两个 Dockerfile 已经设置，普通本地用户不需要手工开启。

## 快速开始

### 方案 A：不使用数据库，直接采集到 JSON

```bash
# 不配置模型 key 时会显示 SDK 不可用警告，然后执行 rules fallback
uv run --env-file .env intel-agent full --verbose

# 查看最近一次结果
uv run --env-file .env intel-agent latest
```

结果位于 `data/intel_runs/`，轨迹位于 `data/intel_agent/traces/`。

### 方案 B：MongoDB + Web 控制台（推荐）

```bash
docker compose up -d mongo
uv run --env-file .env web
```

打开 <http://localhost:8000>。宿主机 Mongo 地址是 `localhost:27018`，数据库名默认是 `intel_agent`，当前 Compose 没有启用鉴权。

也可以把 Web 一并运行在容器中：

```bash
docker compose up -d --build mongo web
docker compose logs -f web
```

### 方案 C：Docker 批处理采集

```bash
docker compose up -d mongo
docker compose run --rm intel-agent full --verbose
docker compose run --rm intel-agent incremental --focus "jailbreak" --window-days 7
```

`intel-agent` 服务属于 `intel` profile，普通 `docker compose up` 不会把它作为常驻服务启动；显式 `run intel-agent` 时作为一次性批任务运行。容器已设置 `IS_SANDBOX=1`，避免 root 用户下 Claude Code 拒绝 `bypassPermissions`。

## 具体模块调用

下面为了可读性使用 bash 的 `\` 拆分长命令；在 PowerShell 中请写成一行，或把续行符替换为反引号 `` ` ``。

### 1. 采集 CLI

全量：

```bash
uv run --env-file .env intel-agent full \
  --max-rounds 6 \
  --max-api-calls 40 \
  --run-id my-bootstrap-run \
  --verbose
```

增量：

```bash
uv run --env-file .env intel-agent incremental \
  --focus "agent tool abuse" \
  --window-days 7 \
  --max-rounds 4 \
  --max-api-calls 20 \
  --verbose
```

使用明确起始时间：

```bash
uv run --env-file .env intel-agent incremental \
  --focus "model extraction" \
  --since 2026-07-01T00:00:00+00:00
```

| 参数 | 适用命令 | 说明 |
|---|---|---|
| `--max-rounds` | full / incremental | 最大轮数安全阀，默认 6 |
| `--max-api-calls` | full / incremental | 整次 run 的源 API 调用预算，默认 40 |
| `--run-id` | full / incremental | 自定义可追踪 run ID |
| `--verbose` / `-v` | full / incremental | 控制台逐轮输出并写 trace JSONL |
| `--focus` | incremental | 任意主题或实体；命中正式 taxonomy 时缩小 target topics |
| `--window-days` | incremental | 回看天数，默认 1 |
| `--since` | incremental | ISO-8601 明确下界，优先于相对时间窗 |
| `--no-watermark` | incremental | 忽略历史 watermark；当前只在 `legacy` 增量路径生效 |

`pyproject.toml` 还提供 `intel_full`、`intel_incremental`、`intel_latest` 三个快捷 script，但推荐使用参数更完整的 `intel-agent` 子命令。

### 2. Python 中调用采集器

```python
from intel_agent.engine.controller import IntelAgentController
from intel_agent.engine.modes import IncrementalCollectionMode
from intel_agent.observability import TraceSink
from intel_agent.schemas import RunBudget

controller = IntelAgentController()
blackboard = controller.run(
    mode=IncrementalCollectionMode(focus="rag poisoning", window_days=7),
    budget=RunBudget(max_rounds=4, max_api_calls=20),
    trace=TraceSink(console=True),
)

print(blackboard.run_id, len(blackboard.raw_items), blackboard.stop_reason)
```

Store 会根据环境变量自动选择 Mongo 或 JSON。

### 3. Python 中调用 item-KG

```python
from ctinexus_kg import KgGenerationConfig, generate_for_run, list_kg_ready
from intel_agent.store import default_store

store = default_store()
run_id = "your-run-id"
items = store.query_items(run_id=run_id, limit=5000)
config = KgGenerationConfig.from_env()

ready = list_kg_ready(items, config=config)
records = generate_for_run(run_id, ready, config=config)

for record in records:
    print(record.item_id, record.status, record.triplet_count)
```

这段 API 会写 item JSON 和 `manifest.json`，但不会自动把记录 upsert 到 Store 的 `knowledge_graphs`；需要数据库记录时优先使用 Gradio Knowledge Graphs 页面，或自行调用 `store.save_knowledge_graph(...)`。

### 4. base-KG 分阶段运行

先准备语料。`data/` 被 gitignore，仓库不会自动分发 PDF；默认目录结构应为：

```text
data/kg-source/
├── OWASP/*.pdf
├── 知网/*.pdf
├── 其他/*.pdf
└── 任意其他分类/*.pdf
```

当前 `docker-compose.yml` **不包含 Neo4j 服务**。请先自行启动可访问的 Neo4j 5.x，并正确设置 `NEO4J_URI`、`NEO4J_USER` 和 `NEO4J_PASSWORD`。

```bash
# 1. PDF -> corpus.jsonl；纯本地，不调用模型
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline corpus --limit 5

# 2. 相关性预过滤；白名单/标题能决定时不调用 LLM
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline filter --limit 5

# 3. NER -> 实体标准化 -> 关系抽取；已有结果默认跳过
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline extract --limit 5

# 需要覆盖已有抽取结果时
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline extract --limit 5 --overwrite

# 4. 幂等写入 Neo4j
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline load --limit 5

# 5. 质量评估；跳过较贵的文本重构准确性，但结构评估仍会使用 embedding
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline evaluate --limit 5 --skip-accuracy

# 一键执行全部阶段
uv run --env-file .env --group basekg python -m base_kg.pipeline.run_pipeline all --limit 5
```

建议第一次始终使用 `--limit 5`。确认模型返回格式、schema 校验、Neo4j 连接和费用都正常后，再去掉限制。

### 5. 离线评估与测试

```bash
# 全部当前后端测试；不需要真实模型 key
uv run pytest \
  backend/common/tests \
  backend/intel_agent/tests \
  backend/ctinexus_kg/tests \
  backend/console/tests -q

# 导入边界 + fake CTINexus + TraceSink 冒烟
uv run python scripts/smoke_pipeline.py

# 从真实历史 outcome 或内置合成数据离线比较 UCB 与轮询
uv run --env-file .env python scripts/bandit_replay.py
```

## 数据产物

| 路径 / 集合 | 内容 |
|---|---|
| `data/intel_runs/<run_id>.json` | JSON Store 的完整 run |
| `data/intel_runs/latest.json` | JSON Store 最近一次 run 的索引 |
| Mongo `intel_agent.runs` | 每次采集任务及 blackboard |
| Mongo `intel_agent.items` | 以 `item_id` 全局去重的原始情报与 run 溯源 |
| `data/intel_agent/traces/<run_id>.jsonl` | 结构化 verbose 轨迹 |
| `data/intel_agent/playbook.jsonl` | 自演化检索技巧 |
| `data/intel_agent/relevance_cache.jsonl` | 相关性 embedding 缓存 |
| `data/intel_runs/<run_id>_kg/<item_id>.json` | CTINexus item-KG 输出 |
| `data/intel_runs/<run_id>_kg/manifest.json` | 一次 item-KG 批次的汇总记录 |
| Mongo `intel_agent.knowledge_graphs` | Mongo 模式下的 KG 元数据和可选完整 graph |
| `data/intel_agent/knowledge_graphs/*.json` | JSON 模式下的 KG Store |
| `ctinexus_output/` | CTINexus 原始 HTML 等输出；成功时适配器会尝试复制到 run KG 目录 |
| `data/exports/*.csv` | Database / Memory 页面生成的 UTF-8 BOM CSV |
| `base_kg/output/corpus.jsonl` | base-KG 单文档语料 |
| `base_kg/output/relevance.jsonl` | base-KG 可恢复相关性判断 |
| `base_kg/output/extractions/*.json` | 实体、三元组和被丢弃三元组 |
| `base_kg/output/evaluation.json` | base-KG 质量评估报告 |

## MongoDB 与 Docker 运维说明

- 宿主机/DBeaver：`localhost:27018`，数据库 `intel_agent`，当前 Compose 无鉴权。
- Compose 网络内部：`mongodb://mongo:27017`。
- 数据保存在 Docker named volume `mongo_data`；`docker compose down` 默认保留它，`docker compose down -v` 会删除它。
- 不要把 Mongo dbpath bind-mount 到 `data/mongo`。同步盘或 sidecar 文件可能破坏 WiredTiger；`data/mongo` 如存在只应视为旧数据遗留。
- 交互查询：`docker compose exec mongo mongosh intel_agent`。
- 全量和筛选 CSV 优先通过 Gradio Database 页面导出，文件会写入 `data/exports/`。

## 当前边界与路线图

以下能力尚未完成，使用时不要把它们当作当前功能：

- CTINexus item-KG 与 5W1H base-KG 之间的 schema 映射、实体对齐和全局融合。
- 从 item-KG 持续生长为一张统一的全局 LLM 安全知识图谱。
- triplet 人工反馈 UI，以及反馈反向注入下一轮 extraction prompt。
- 面向 arXiv 全文的专用 academic KG；当前 item-KG 默认跳过 arXiv 摘要。
- 生产级登录认证、Mongo 鉴权、多租户隔离、后台任务队列和分布式调度。
- base-KG 的内置 Neo4j Compose 服务和随仓库分发的 PDF 语料。

更详细的演进记录见：

- `backend/intel_agent/README.md`
- `backend/ctinexus_kg/README.md`
- `backend/console/README.md`
- `base_kg/README.md`
- `docs/SESSION_2026-07-10_intel_agent_maturity.md`
- `docs/INTEL_AGENT_SDK_ROADMAP.md`

其中部分历史文档仍保留旧 `src/` / CrewAI 架构描述；判断当前行为时以 `backend/`、`base_kg/`、`pyproject.toml` 和本 README 为准。
