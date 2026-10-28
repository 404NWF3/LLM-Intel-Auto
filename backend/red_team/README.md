# 兼容目录与上游运行时

现有仓库审计与离线案例能力已迁入 WP1-3 沙盒模拟智能体。平台实现位于 [sandbox_agent](../sandbox_agent/README.md)，主接口为 `/api/sandbox/*`，工作台为 `/dashboard/wp13`。

此目录仅保留 `api.py`、`service.py`、`graph.py` 的旧导入兼容层，以及固定路径的上游 `runtime/`。旧 `/api/redteam/*`、`data/red_team/`、`RED_TEAM_GRAPH_ROOT` 和独立虚拟环境继续有效，新旧 API 共用同一个任务服务。

安装上游依赖仍使用 `uv sync --project backend/red_team/runtime --frozen --group dev`。源码来源与集成修订见 [UPSTREAM](../sandbox_agent/UPSTREAM.md)。

新 WP1-2 的职责是根据情报设计漏洞检测代码包，当前仅完成[架构、数据契约与交互设计](../../docs/specs/pentest-sandbox-redesign.md)，尚未实现新的生成服务。
