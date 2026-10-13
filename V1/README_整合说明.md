# SAADS Community V1：给情报采集模块的源码交付

交付日期：2026-09-29。

版本：`saads-community-v1.0.0`  
冻结提交：`89edf8f9a8ac1b3711399f8f4272583ad83fb419`。

本包交付的是**加入 PrompTrend 社区发现思路后、通过 Community 专属 release gate 的 V1 源码**，不是 PrompTrend 整仓，也不是后续 V1.1 工作树。所有纳入的原仓库文件均直接读取该提交的 Git blob，内容没有修改；文件清单和 SHA-256 见 `SOURCE_MANIFEST.json`。

## 1. 可以直接发给组长的一段话

> 有，需要整合的是“社区情报采集与结构化输出”这条链路：在原 SAADS 上补充了 GitHub Issues、HN、Hugging Face Forum、Reddit 的真实采集，以及动态关键词、关键词→LLM 两阶段过滤、跨轮增量、checkpoint 恢复和跨平台情报归并。输出保留原始来源、首次观察时间及 STIX 结构化结果。附件是冻结 V1 的完整源码和整合说明，社区限定验收已通过。建议复用已有 adapter、采集 runner 和结构化输出接口；采集结果接入你们现有服务/API/展示层时还需要做一次接线联调。Discord/X 尚缺授权凭据，不计入本次可用来源。

## 2. 包里有什么

- `source/`：冻结提交中的后端、前端、脚本、测试、依赖声明、无密钥配置模板和正式文档，共 399 个文件。
- `source/docs/community_v1_release.md`：最终 release report；以此为 V1 验收范围依据。
- `source/docs/community_v1_remaining_acceptance.md`：Reddit、EchoLeak 跨平台归并、动态关键词的真实验收记录。
- `source/docs/community_discovery_migration.md`：PrompTrend 审查、适配点和迁移过程；前半部分的阶段性阻塞应结合最终 release report 阅读。
- `evidence/`：少量历史验收结果 JSON、历史测试摘要以及本次导出后的回归/安全检查结果。历史数据和本次检查分开标注。
- `SOURCE_MANIFEST.json`：版本身份、每个源码文件的哈希、排除清单。

冻结提交共有 407 个跟踪文件，仅排除 8 个**非代码文件**：3 个旧运行日志、2 个编辑器备份、3 个过程工作便笺。没有删减后端/前端/测试/依赖代码。完整范围保留了原仓库的下游模块和原有 demo/mock 测试设施，**不表示它们属于本次 Community 验收，更不能把它们的输出当作真实采集数据**。

不包含 `.env`、任何本地密钥、`.git` 历史、原始采集数据、私有运行日志、虚拟环境、`node_modules` 或构建缓存。本包是源码交付，不是包含依赖与账号的离线即用镜像。未混入当前未冻结的 V1.1 语义 embedding 改造。

## 3. 哪些代码要整合到“情报采集”

以下路径均相对于 `source/`。

| 能力 | 主要代码入口 | 整合时保留什么 |
|---|---|---|
| 多平台真实采集 | `backend/agents/intel_agents/tools/community_fetch_adapters.py`、`source_fetch_tools.py`；`crews/source_collection_crew.py` | 各平台 adapter、来源标识、原始文本/链接、失败统计 |
| 来源配置与增量 | `backend/agents/intel_agents/services/source_registry.py`；`scripts/run_community_v1_monitor.py` | source/query 各自 cursor、checkpoint、失败不推进游标 |
| 动态发现与两阶段过滤 | `backend/agents/intel_agents/services/community_relevance.py`；`community_discovery.example.json` | 先关键词筛选，再真实 LLM 判断；词表证据与后续查询 |
| 标准化 / STIX | `backend/agents/intel_agents/agents/standardizer_agent.py`、`tools/llm_standardization_tools.py`、`schemas/intel.py` | 标准化 DTO、STIX、原始证据及审计 |
| 去重与跨平台归并 | `backend/agents/intel_agents/agents/dedup_merge_agent.py`、`tools/dedup_tools.py`、`tools/llm_merge_judge_tools.py`、`services/attack_signature_memory.py` | 现有 LLM 裁决、稳定记录、provenance、各来源及时间上下文 |
| 真实 LLM 配置 | `backend/agents/intel_agents/tools/llm_client_factory.py`；`wp11_llm_profiles.json`；`wp11_llm_route_presets.json` | 当前客户端和路由配置，不另建一套 LLM 访问链路 |
| API 与前端接口参考 | `backend/api/routers/wp11.py`、`backend/api/run_store.py`；`frontend/` | 保留既有接口/展示代码；注意下面的接线边界 |

不建议只拷贝一个 adapter 文件：上述代码复用了 SAADS 的 DTO、注册表、LLM 配置、标准化和去重服务。因此提供完整冻结源码，方便按模块整合并检查依赖。

社区范围是“持续获取并结构化 LLM 安全情报”，不包括攻击执行、PrompTrend PVAF、BOM、WP1-2 或数据库迁移。V1 的归并是现有特征/规则候选匹配结合 LLM 裁决；32 维词频哈希不能当作真正语义 embedding 的证据。

## 4. 在接收机器上启动真实社区链路

### 4.1 准备依赖与配置

下面是根据冻结代码整理的操作步骤；**不代表本次打包在新机器上重新安装、部署过**。Python 版本约束以 `pyproject.toml` 为准（`>=3.10`），前端依赖以 `frontend/package-lock.json` 为准。

进入解压后的 `source/`。以下使用 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
```

只在接收机器本地填写 `.env`，不要发在群里或提交 Git。项目实际读取的名称如下，不能改写成自行假设的 `DEEPSEEK_API_KEY`：

```dotenv
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-flash
OPENAI_FAST_MODEL=deepseek-flash
OPENAI_ENABLE_THINKING=false
GITHUB_TOKEN=
```

`OPENAI_API_KEY` 填接收方的 DeepSeek 官方密钥，`GITHUB_TOKEN` 填接收方有权使用的 GitHub 凭据。`OPENAI_` 是此项目沿用的变量名，不表示请求发往 OpenAI。上面的模型名是冻结配置及历史验收使用值，接收方必须再核实自己的账号可用性，不能把历史 HTTP 200 当成当前账号的保证。

profile 301/302/303 已引用这些变量；默认读取根目录 `wp11_llm_profiles.json` 和 `wp11_llm_route_presets.json`，无需重新创造一套 profile。

### 4.2 先跑一次，再持续增量

```powershell
.\.venv\Scripts\python.exe scripts/run_community_v1_monitor.py --config community_discovery.example.json --root .runtime/community-v1/team --once
```

**必须传 `--config community_discovery.example.json`**：该配置开启动态查询、社区过滤、`llm_required` 标准化和去重，默认包含 GitHub Issues、HN、Hugging Face Discourse。不传配置时的默认 HN/rules-only 路径，不等于已经验收的完整社区增强链路。

真实查询是否返回新增数据受时间窗、源站、配额和 checkpoint 影响；某轮新增为零不等于链路失败，也不能用样例数据填充。

持续运行 24 小时：

```powershell
.\.venv\Scripts\python.exe scripts/run_community_v1_monitor.py --config community_discovery.example.json --root .runtime/community-v1/team --interval-seconds 7200 --duration-hours 24
```

这是前台进程，每轮结束后等待 7200 秒，不是整点调度，也不会自动安装为系统服务。接收方需在自己的进程管理环境中运行。重启使用相同 `--root` 读取已有 checkpoint；不要多个进程同时写同一 root。

Reddit 已验收的是公开 RSS，普通 example 配置未启用它。可用冻结的验收入口单独验证：

```powershell
.\.venv\Scripts\python.exe scripts/verify_community_remaining_live.py --phase reddit --root .runtime/community-v1/reddit-check
```

该命令会真实访问源站及 LLM，不是离线单元测试。Discord/X 仍保持外部凭据 BLOCKED，不要开启后把无凭据/零结果误报为成功。

### 4.3 输出交给上游/下游什么

上述 root 目录内：

- `checkpoint.json`：source cursors、稳定情报记录、完成轮次、更新时间。
- `rounds.jsonl`、`24h_report.md`：每轮统计及监控汇总。
- `community-v1-*.json`：`raw_items`、`standardized_items`、`standardization_audits`、`dedup_result`、`llm_dedup_judgments`、`fetch_audits`。
- `raw/<trace>/`：真实源证据。

建议以标准化记录和去重结果为整合输出，同时保留 raw/provenance，避免只剩一条摘要而丢失原文来源。

若需要进程内调用，可查看 runner 的 `run_round(state, root, config)`：输入现有游标/稳定记录和配置，返回单轮统计并更新 state、写出轮次产物。CLI 还承担 env 加载、checkpoint 和周期管理；不能只调用 `run_round` 后就假设这些生命周期工作自动完成。

## 5. API / 前端的实际边界与启动

**“社区链路通过验收”不等于“新机器整套前后端可以零配置上线”。** 最终 release report 已明确以下区别：

1. API 验收使用真实采集结果回放进现有 `RunStore`，并验证鉴权、状态接口和 request ID。它不是一次从浏览器触发的新采集验收。
2. Community runner 将结果/checkpoint 写到文件；API `RunStore` 是内存状态，两者未自动衔接。组内若要在现有情报平台展示，需要完成对应结果接入，不能仅启动两个进程就宣称打通。
3. 设置 `SAADS_API_KEY` 后，API 要求 `X-API-Key`；冻结前端的 fetch/SSE 不自动附带该鉴权。应通过受控服务端代理或现有认证体系接入；不要把后端密钥放进 `NEXT_PUBLIC_*`，也不要为了展示而把未鉴权接口直接暴露公网。
4. 通用 graph 默认可能走 `stub`、关闭 community filter；不能拿 `main.py`/通用 API 的默认调用替代第 4 节的真实 runner。

后端服务启动参考（`source/`）：

```powershell
.\.venv\Scripts\python.exe serve.py --host 127.0.0.1 --port 8000 --no-reload
```

健康检查路径是 `/health`。`.env` 中另行配置 `SAADS_API_KEY` 和所需 `CORS_ORIGINS`；这些不是采集 LLM 密钥。

前端启动参考（`source/frontend/`，先安装匹配锁文件依赖的 Node.js/npm）：

```powershell
$env:NEXT_PUBLIC_USE_MOCK_API='false'
npm ci
npm run build
npm start -- --hostname 127.0.0.1 --port 3000
```

现有 Next 配置将 `/api/*` 代理到 `http://localhost:8000/api/*`。浏览器本地 `localStorage['saads_mock_mode']` 的值优先于构建变量，需关闭 Mock 模式并刷新。旧 `docs/deploy.md`、`docs/frontend_deployment.md` 是更早的全仓部署材料；其中 `/api/health`、Mock 配置及全栈依赖描述不能覆盖这份 Community 交接说明。

## 6. 已有真实证据，以及这次打包查了什么

历史验收日期：2026-09-16；以下来自随包冻结 release report / 验收 JSON，**不是 2026-09-29 新采集的结果**。

| Community 验收项 | 可核验结果 |
|---|---|
| GitHub Issues / HN / HF Forum 跨轮采集 | 分别 10→2、10→10、50→11；各自两轮 external ID 交集为 0 |
| Reddit RSS | 5 条真实采集，4 条 LLM 保留并结构化 |
| 动态关键词及两阶段过滤 | `echoleak`、`365 copilot` 进入后续 GitHub 查询；6 个可追踪匹配；此前一轮 47 条关键词拒绝、11 条 LLM 拒绝 |
| 跨平台归并 | HN `44250774` 与 GitHub `SecOpsNews/news` 的 `49420/49449/49453` 归并为 EchoLeak；保留各来源；负例未合并 |
| checkpoint / 重试 | 真实超时尝试 2 次、失败不推进游标、恢复成功；按 query 独立保存 cursor |
| API | 真实结果回放；401/授权后 200、request ID、缺失 run 404、nodes 接口 |
| 社区回归 | 47 PASS，5 项明确排除 |
| 前端 | 3 个文件 / 4 个测试 PASS；production build 成功；production server 两个 dashboard 路径 HTTP 200 |
| 外部阻塞 | Discord / Twitter(X) 无授权凭据，BLOCKED，非 V1 发布阻塞 |

来源发布时间顺序不等于因果传播证明；Reddit 不代表私域/OAuth 完整历史，HF Forum 不代表整个 Hugging Face 生态。

本次打包额外核对：冻结提交身份、源码逐文件 Git blob/SHA-256、Python 语法、隔离导出的 Community 回归，以及最终 ZIP 的密钥/私有文件扫描和完整性。具体结果见 `evidence/package-verification.json`、`evidence/package-secret-scan.json`。自动 secret scan 不是对所有未知密钥格式的数学保证。

完整原始运行数据没有随包发送。因此 `scripts/community_release_gate.py` 中依赖 `.runtime` 历史采集件的复核，不能在新机器仅靠本 ZIP 直接重跑；需要重新产生真实采集证据或另行安全交接原始材料。不能将缺证据改成跳过并声称 PASS。

## 7. 交付后建议的整合顺序

1. 接收方配置自己的凭据，先按第 4 节用真实 runner 跑一轮。
2. 根据单轮产物确认标准化记录、来源字段及 checkpoint 的保存位置。
3. 将这条链路接到组内既有采集调度/存储接口；若使用本仓 API/前端，补做第 5 节列出的状态和认证接线联调。
4. 用真实连续两轮记录检查新增、重复、失败恢复和页面/API数据一致性，再在目标环境发布。

这些是目标环境交接步骤，不是本包新加的功能，也不是伪称已完成的新一轮 production 验收。
