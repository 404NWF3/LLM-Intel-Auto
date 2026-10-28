# 情报采集控制台

执行 `uv run web`，打开 http://127.0.0.1:8000。

- Collect：全量/增量采集与实时追踪。
- 情报态势：话题覆盖、来源健康、候选话题。
- Trace replay：按 run_id 回放日志。
- Database：运行历史、情报查询、CSV 导出。
- Memory：技巧库和相关性缓存。

控制台只依赖采集模块和共享话题定义，不包含知识图谱功能。存储使用 `intel_agent.store.default_store()`，默认 JSON，可选 MongoDB。

测试：`uv run pytest backend/console/tests -q`。部署与配置见根目录 README。
