# 源码来源与集成修订

- 来源：<https://github.com/404NWF3/SAADS-Red-team>
- 导入提交：`231b4cdc0b54293dff81e5bffbda2dcc713effbf`
- 导入日期：2026-10-14

`../red_team/runtime/` 保存上游运行代码、测试、图谱语料、配置、提示词、脚本、评估资料及项目 Skills，保留原始 `pyproject.toml` 和 `uv.lock`。未导入 Git 历史、大型 Word/PPT 材料、外部 Claude 插件设置、个人密钥或虚拟环境。上游忽略的 `output/` 图谱索引不在此次导入内。

平台接入代码位于 `backend/sandbox_agent/`，由独立子进程调用原始 CLI。根目录 `saads-api` 统一挂载情报采集和沙盒接口；WP1-3 使用 `/api/sandbox`（旧 `/api/redteam` 保留兼容），替换旧演示数据连接。

上游 `saads_grill_agent/repository.py` 的本地修订：

- 修复搜索对索引后被替换为符号链接的文件的读取边界，配合上游已有回归测试。
- 遍历时跳过依赖、构建产物、符号链接、`.env*`、私钥文件；搜索摘要沿用片段读取的敏感值遮罩。
- 仓库快照包含文件内容散列，以便恢复任务时识别同路径文件被修改。
- 新增凭据文件排除、搜索遮罩和文件内容变更快照测试。

审计编排的接入修订：每次团队调用前保存当前阶段，让页面显示真实阶段；恢复时继续未裁决的假设，并允许从裁判和测试生成阶段恢复。SDK 返回轮次上限错误后先完整消费迭代器，再抛出错误，避免异步取消作用域未正确关闭。对应行为有回归测试覆盖。

`saads_attack_agent/security_graph.py` 增加平台图谱的 DeepSeek 注册与原生 Global Search 路径，按索引 manifest 选择检索方式，保留旧上游索引的 Local Search 支持。新建图谱只使用本项目持久化的情报摘要；不会将上游示例语料冒充采集结果。构建器位于平台 `graph.py`、`graph_builder.py`，不覆盖上游原始索引脚本。

升级上游时应保留并复核这些修订，使用上方固定提交比较差异，不要覆盖平台 `api.py`、`service.py`、`worker.py` 和任务数据。

2026-10-26 职责迁移：平台适配层迁至 `sandbox_agent`，上游运行时与已有虚拟环境保留 `backend/red_team/runtime/` 路径；红队/代码团队/裁判等内部角色未改动。新 WP1-2 仅有设计稿，未复用这些审计结果作为动态检测结论。
