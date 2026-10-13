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
