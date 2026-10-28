# 大模型安全情报采集智能体

主系统位于 `backend/intel_agent/`，使用 Claude Agent SDK 编排 NVD、arXiv、CISA KEV、OSV 情报采集，支持全量/增量采集、相关性过滤、去重、覆盖缺口分析、技巧库和运行追踪。未配置模型密钥时自动使用确定性规则采集，仍会请求真实公开数据源。

## 本地运行

需要 Python 3.10–3.13 和 uv。从仓库根目录执行：

```bash
uv sync --group dev
cp .env.example .env
uv run intel-agent full --max-rounds 1 --max-api-calls 4 --verbose
uv run intel-agent latest
uv run web
```

控制台地址：<http://127.0.0.1:8000>。包括采集、情报态势、追踪回放、历史查询/CSV 导出、技巧库。启动服务后终端需保持运行，Ctrl+C 停止。

首次运行可以不创建 `.env`，不需要模型密钥或数据库。要启用大模型自主调用工具，在 `.env` 中选择 `INTEL_SDK_PROVIDER=deepseek` 或 `glm`，填写对应的一个 API 密钥。也支持 `ANTHROPIC_BASE_URL` 与 `ANTHROPIC_AUTH_TOKEN` 自定义兼容端点。DeepSeek 主模型和快速模型均默认使用 `deepseek-flash`（V4.1 Flash）。模型默认值来自 `runtime/client.py`；供应商不支持时用 `INTEL_SDK_MODEL` 和 `INTEL_SDK_FAST_MODEL` 覆盖。配置修改后重启进程。

GLM embedding/LLM 相关性过滤是可选增强，单独使用 `GLM_API_KEY`；仅配置 DeepSeek 时仍有规则过滤。NVD 密钥可选。配置统一按系统环境变量、根目录 `.env`、代码默认值的顺序读取。

```bash
# 全量采集
uv run intel-agent full --max-rounds 6 --max-api-calls 40 --verbose
# 增量采集；读取历史 checkpoint，默认重叠回看 72 小时
uv run intel-agent incremental --focus "prompt injection" --window-days 7 --max-rounds 2 --max-api-calls 8 --verbose
# 指定起始时间，或用 --no-watermark 忽略历史水位
uv run intel-agent incremental --focus jailbreak --since 2026-09-01
```

预算耗尽时可能仍有覆盖缺口，这是正常的部分采集结果。网络失败和 SDK 降级可在 verbose 日志中查看，命令退出成功不代表所有来源都成功。

## 保留目录

- `backend/intel_agent/`：采集核心及离线测试。
- `backend/common/`：核心共享的话题定义，不可删除。
- `backend/console/`：仅与采集相关的可视化控制台。
- `scripts/bandit_replay.py`：离线策略回放；`scripts/_check_mongo.py`：可选数据库连通性检查。
- `模版/`：软件著作权材料模版。
- `data/`：运行数据，未纳入 Git；保留原有数据。

已移除知识图谱控制台及存储接口、CTINexus/BaseKG 依赖和配置、旧的一次性 OSV/CISA 采集脚本。同时删除上述实验脚本的静态输出、旧 README 截图与遗留运行日志。

## 输出与测试

默认输出 `data/intel_runs/<run_id>.json`，`latest.json` 为最近运行索引；技巧库与缓存位于 `data/intel_agent/`，追踪位于 `data/intel_agent/traces/`。

```bash
uv run pytest backend -q
uv run python scripts/bandit_replay.py
```

测试使用模拟源、模型和数据库；实际网络及模型端点需单独验证。

## MongoDB 与 Docker（可选）

```bash
cp .env.example .env  # 仅首次执行，不要覆盖已有配置
# 只启动数据库；本地 .env 再设置 INTEL_MONGO_URI=mongodb://localhost:27018
docker compose up -d mongo
# 容器运行控制台及数据库
docker compose up -d --build web
# 容器批量采集
docker compose run --rm intel-agent full --max-rounds 1 --max-api-calls 4 --verbose
```

容器内部连接 `mongo:27017`，宿主机连接 `localhost:27018`。已有 MongoDB 数据卷不受代码清理影响。

## Next.js 智能体工作台

前端已接入情报采集 `backend/intel_agent`（WP1-1）和沙盒模拟 `backend/sandbox_agent`（WP1-3）。首次安装红队环境：`uv sync --project backend/red_team/runtime --frozen --group dev`；然后在根目录运行 `uv run saads-api`，另一个终端进入 `frontend` 运行 `npm ci && npm run dev`。

- 情报采集：http://127.0.0.1:3000/dashboard/wp11
- GraphRAG：http://127.0.0.1:3000/dashboard/graphrag
- 渗透测试脚本生成：http://127.0.0.1:3000/dashboard/wp12
- 沙盒模拟：http://127.0.0.1:3000/dashboard/wp13
- 异常检测 Researcher：http://127.0.0.1:3000/dashboard/wp14

红队支持本地仓库对抗审计、检查点恢复、发现与报告预览、产物下载。已接通“情报采集 → GraphRAG 构建 → 沙盒审计”：在独立 GraphRAG 工作台从持久化情报构建实体关系与社区报告，验证成功后自动供审计和离线案例取证，复用现有 DeepSeek 配置。详见 [沙盒接入说明](backend/sandbox_agent/README.md) 与 [前端说明](frontend/README.md)。

### 异常检测 Researcher

运行 `uv sync --group dev` 安装建模依赖，启动同一后端和前端后进入 WP1-4。上传 CSV 或载入合成示例，选择标签列和轮数即可开始。单个循环在 Isolation Forest、LOF 和 PCA 重构模型之间尝试参数，每轮记录理由、得分和保留/丢弃结果；可随时停止，任务历史在刷新后保留。

- CSV 需 UTF-8 编码、有唯一表头，30–10,000 行、1–100 个数值特征，不超过 8 MiB。非数值及全空列忽略；缺失值在训练分区内填充。标签须为 0（正常）/1（异常），每类至少 5 行。常见标签列名 `label/target/y/anomaly/is_anomaly/class` 始终不作为特征。
- 有标签时固定 60/20/20 训练、验证、测试划分，按验证集 AP 选优，仅最佳模型接受最终测试；无标签时按固定参考集上的 bootstrap 排名稳定性选优，该分数不代表检测准确率。
- 规划复用现有模型配置。关闭模型规划、未配置密钥、调用失败或建议重复时，使用内置候选继续循环，并标记为内置方案。首轮为固定基线，最多 20 轮，单任务最多 15 分钟。
- 成功后可下载模型包和带 `train/validation/test` 或 `train/reference` 标记的异常分数 CSV。模型包包含拟合管线、特征顺序及分数定义；它产生排序分数，不自动承诺告警阈值或校准概率。仅加载自己生成的 joblib 文件。

实现位于 `backend/intel_agent/researcher/`，数据与任务保存在 `data/researcher/`，通过现有 API 的 `/api/researcher/*` 提供服务。首版使用单工作进程；停止或服务关闭会终止本次实验，不支持断点续跑。

WP1-2 已接通初版脚本生成：选择情报库条目，分析漏洞条件和原文依据，生成 HTTP / chat-completions 接口检测计划及独立 Python 脚本，支持历史、停止、预览与完整包下载。模型配置沿用采集系统；生成阶段不访问检测目标。脚本默认 dry-run，使用时显式指定目标与 `--execute`。详见[初版使用与 API](backend/pentest_agent/README.md)和[职责重构设计](docs/specs/pentest-sandbox-redesign.md)。旧仓库审计、离线案例与历史任务位于 WP1-3；新检测包自动交付与隔离执行仍待实现。
