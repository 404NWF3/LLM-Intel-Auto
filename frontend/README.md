# 前端与智能体后端

Next.js 的 `/dashboard/wp11` 接入 `backend/intel_agent`，`/dashboard/wp12` 接入 `backend/pentest_agent`，`/dashboard/wp13` 接入 `backend/sandbox_agent`，`/dashboard/wp14` 接入 `backend/intel_agent/researcher`。这些工作台使用真实后端数据，不受原有 mock 开关影响。

## 启动

在项目根目录：

```bash
uv sync --group dev
uv sync --project backend/red_team/runtime --frozen --group dev
uv run saads-api
```

在另一个终端：

```bash
cd frontend
npm ci
npm run dev -- --hostname 127.0.0.1
```

打开 http://127.0.0.1:3000/dashboard/wp11 或 http://127.0.0.1:3000/dashboard/wp13 。API 默认监听 `127.0.0.1:8001`，不占用旧 Gradio 的 8000 端口。`intel-api` 是同一服务的兼容命令，勿重复启动。部署前构建：`npm run build`，然后 `npm start -- --hostname 127.0.0.1`。

需要自定义后端地址时，在 `frontend/.env.local` 设置：

```dotenv
INTEL_API_URL=http://127.0.0.1:8001
```

修改后重启 Next.js；生产环境需要重新构建。该变量仅用于服务端代理，模型密钥继续放在项目根目录 `.env`，不要放到 `NEXT_PUBLIC_*`。

## 首页统计

首页 `/` 的三个指标通过 `/api/stats` 读取同一后端，每 30 秒及窗口重新聚焦时同步，也可手动刷新：

- 已入库安全情报：当前存储中按 `item_id` 去重的全部情报数，并显示实际来源数。
- 核心安全话题覆盖率：全部入库情报中已有标注的核心话题数 / `CORE_SECURITY_TOPICS` 总数；这不是 OWASP 覆盖率，也不表示安全验证完成或采集配额达标。
- 已生成测试脚本：WP1-2 全部历史中成功完成、检测包与 `detector.py` 均存在且脚本可下载的数量；不受最近 50 条历史列表限制。

首页不再依赖旧 PostgreSQL 表或 mock 开关；加载和首次请求失败显示占位符，后续刷新失败保留上次成功数据并提示同步失败。

## 情报采集功能

- 全量探索：对应引擎的 `bootstrap` 模式，按核心话题采集。
- 增量追踪：关注方向、回看天数、历史检查点与自适应检索。
- 最大轮次、API 调用预算、重复启动拦截。
- 运行日志自动刷新及跟随开关，历史任务日志回放（最近 300 条）。
- 情报标题／摘要／编号搜索、来源／话题／所选任务筛选、原文跳转。
- 最近 50 次任务记录，失败、部分完成、重启中断等状态。
- 真实历史库指标，以及最近一次已保存任务的核心话题标注数量。

搜索结果最多显示 100 条，请通过筛选缩小范围；JSON 存储沿用引擎现有最多 500 份运行记录的查询范围。话题覆盖表示存在标注情报，不是 OWASP 覆盖率，也不表示达到采集配额。轮次数沿用引擎 `query_history` 的统计口径。采集的最大轮次和 API 调用预算可填写任意正整数，前端与接口不设置数值上限；引擎按填写的预算执行。

## 存储和运行限制

API 复用 `default_store()`：按根目录配置使用 MongoDB 或 JSON；不使用旧前端的 PostgreSQL WP1-1 数据库。原始任务结果继续写入 `data/intel_runs` 或 MongoDB；Web 任务状态记录在 `data/intel_agent/web_jobs`，日志在 `data/intel_agent/traces`。

这是本机单用户接口，不包含登录鉴权；保持本机监听。**只启动一个 API 进程、一个 worker**，采集任务在线程中执行；运行时不要使用 `--reload` 或重启服务。服务重启后，未完成的 Web 任务显示为“已中断”，不会自动续跑。关闭浏览器不会停止采集；采集页当前不提供中止按钮。

后端未启动、存储不可用、日志缺失或无匹配情报时，页面显示对应提示，不回填演示数据。

## 沙盒模拟功能（WP1-3）

WP1-3 提供仓库对抗审计和离线攻击案例两个入口。支持目标与授权记录、审计目标、轮次与调用/费用预算、任务停止、检查点恢复、威胁面和确认发现、运行记录、最近 50 次任务、报告预览及下载。费用显示为 SDK 估算，预算在调用完成后检查，收尾可能继续消耗调用。GraphRAG 的构建、进度、日志、报告和来源位于独立工作台 `/dashboard/graphrag`，验证成功后自动接入红队。模型配置和 GraphRAG 工作流见 [backend/sandbox_agent/README.md](../backend/sandbox_agent/README.md)。

红队 UI 位于 `src/components/dashboard/SandboxDashboard`，图谱 UI 位于 `src/components/dashboard/GraphDashboard`，通用报告预览位于 `src/components/dashboard/TaskArtifacts`；接口类型在 `src/lib/api/sandbox.ts`；`/api/sandbox/*` 与情报接口共用 `INTEL_API_URL` 代理。红队依赖运行于独立 Python 环境，任务写入 `data/red_team/runs`。图谱构建与红队共享单任务队列，使用 `/api/sandbox/graph/build`。两个工作台通过 `GET /api/sandbox/runs?workspace=graph|sandbox` 分别显示各自最近 50 次任务；图谱不计入红队任务统计。尚未构建图谱时，可通过沙盒模拟页的“管理情报知识图谱”进入独立工作台。

## 渗透测试脚本生成（WP1-2）

`/dashboard/wp12` 从真实情报库搜索并选择条目，支持填写测试重点、选择自动/HTTP/聊天接口、发起或停止生成。采集页的“生成漏洞测试脚本”可通过 `intel_id` 深链接带入条目。结果展示分析、来源定位、基线、探针、机器判据和局限；成功后可预览 Python 脚本、下载脚本/说明/计划或完整 ZIP。证据不足和协议不支持有独立状态，不伪造脚本。

接口类型在 `src/lib/api/pentest.ts`，UI 位于 `Wp12DashboardContent`，`/api/pentest/*` 使用同一 `INTEL_API_URL` 代理。独立生成服务最多同时运行一个任务，进度轮询每 2 秒，历史保留并展示最近 50 次。模型配置、API 和运行说明见 [backend/pentest_agent/README.md](../backend/pentest_agent/README.md)。页面不会收集目标凭据或直接执行测试；脚本默认 dry-run。

旧仓库审计、离线案例、历史与产物入口为 `/dashboard/wp13`。沙盒主接口 `/api/sandbox/*` 与旧 `/api/redteam/*` 共用任务服务；旧数据与上游运行环境路径保持兼容。新检测包自动交付和隔离执行待实现。

## 异常检测自动建模

打开 `/dashboard/wp14`，上传 CSV 或载入合成演示数据，选择异常标签列、轮数和是否使用大模型后开始。CSV 上限为 8 MiB、30–10,000 行和 1–100 个数值特征；标签须为 0（正常）和 1（异常），每类至少 5 行。最大轮次为 1–20，默认 6。

- loop 比较 Isolation Forest、Local Outlier Factor 与 PCA 重构方案，页面显示每轮参数、候选来源、评估分数和保留结果。
- 有标签时区分验证 AP 与最终测试 AP / AUROC；无标签时显示排序稳定性参考，不将其表述为检测准确率。无标签模式也会排除常见标签列，避免将其作为特征。
- 可以关闭大模型直接运行；大模型不可用或候选生成失败时显示规则回退。模型配置沿用后端现有配置。
- 支持停止任务、历史任务回看，以及成功完成后下载模型和带数据划分标记的异常分数。

UI 位于 `src/components/dashboard/ResearcherDashboard`，接口类型与上传函数在 `src/lib/api/researcher.ts`。`/api/researcher/*` 通过 `INTEL_API_URL` 代理到同一后端；上传使用原始 CSV 请求体，不使用 multipart。任务详情在运行中每 2.5 秒刷新。

## 验证

```bash
# 根目录
uv run pytest backend/intel_agent/tests backend/console/tests backend/sandbox_agent/tests -q
# frontend 目录
npm run type-check
npm test
npm run build
```

接口路径：`GET /api/intel/overview`、`GET/POST /api/intel/runs`、`GET /api/intel/runs/{run_id}`、`GET /api/intel/items`。浏览器统一通过 Next.js 同源代理访问。
