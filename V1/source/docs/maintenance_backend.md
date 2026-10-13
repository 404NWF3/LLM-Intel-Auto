# SUFE-SAADS 后端维护文档

> 面向接手团队的工程维护参考手册
> 最后更新：2026-03-19

---

## 1. 技术栈概览

| 层次 | 技术 | 版本 | 说明 |
|------|------|------|------|
| API 框架 | FastAPI | ≥0.115.0 | 异步 REST + SSE |
| ASGI 服务器 | Uvicorn | ≥0.30.0 | 生产部署 |
| 智能体框架 | LangGraph | ≥0.2.0 | 有状态图结构智能体 |
| LLM 编排 | LangChain | ≥0.1.0 | LLM 调用链 |
| LLM 提供商 | OpenAI / Google Gemini | — | 可在配置中切换 |
| 数据库 | PostgreSQL | — | 主存储（psycopg3 驱动） |
| 向量库 | Qdrant | ≥1.13.0 | 语义去重 / 语义搜索 |
| 数据校验 | Pydantic v2 | ≥2.0.0 | DTO / 配置管理 |
| 语言 | Python | ≥3.10 | |

---

## 2. 项目目录结构

```
backend/
├── agents/
│   └── intel_agents/              ← WP1-1 情报采集智能体（主要业务逻辑）
│       ├── orchestrator/          ← LangGraph 核心
│       │   ├── graph.py           ← 图编译（compile_graph）
│       │   ├── nodes.py           ← 20 个节点函数定义
│       │   ├── router.py          ← 条件路由函数
│       │   ├── runtime.py         ← Phase1GraphRuntime 包装类
│       │   └── state.py           ← WP11GraphState TypedDict + RunMode/RunStatus
│       ├── agents/                ← 子智能体实现
│       ├── runners/               ← 执行器（启动/恢复运行逻辑）
│       ├── schemas/               ← Pydantic DTO schema
│       ├── services/              ← 业务服务层
│       ├── tools/                 ← LLM 工具函数（各节点调用）
│       └── crews/                 ← 智能体团队配置
├── db/                            ← 数据库模块（独立，可复用）
│   ├── models/                    ← SQLAlchemy 模型
│   │   ├── attack.py              ← 攻击情报实体
│   │   ├── component.py           ← AI 组件/BOM 条目
│   │   ├── source.py              ← 数据源注册表
│   │   ├── governance.py          ← 治理/策略模型
│   │   └── views.py               ← 读模型视图
│   ├── repositories/              ← 仓储层（数据访问抽象）
│   │   ├── base.py
│   │   ├── attack_repository.py
│   │   ├── component_repository.py
│   │   ├── source_repository.py
│   │   ├── governance_repository.py
│   │   └── read_model_repository.py
│   ├── services/                  ← 数据库业务逻辑层
│   ├── sql/                       ← 原始 SQL 迁移脚本
│   ├── connection.py              ← 连接池管理
│   ├── session.py                 ← DbSession（带日志和异常映射）
│   ├── dtos.py                    ← 数据传输对象
│   ├── pagination.py              ← 分页工具
│   ├── repository.py              ← 仓储基接口
│   ├── unit_of_work.py            ← 事务协调（UoW 模式）
│   └── exceptions.py              ← 数据库异常映射
├── .runtime/                      ← 运行时状态缓存（不提交 Git）
│   └── wp11/
│       ├── audit/                 ← 采集审计记录
│       ├── dedup/                 ← 去重决策缓存
│       ├── raw_records/           ← 原始采集数据
│       ├── qdrant_attack_signature_memory/  ← 本地 Qdrant 数据
│       └── vector_memory/         ← 向量记忆
└── pyproject.toml                 ← 项目配置 + 依赖声明
```

---

## 3. 环境配置

### 3.1 安装依赖

```bash
# 推荐使用 uv（比 pip 快）
pip install uv
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 3.2 环境变量

在项目根目录创建 `.env` 文件（不提交 Git）：

```env
# LLM 提供商（至少配置一个）
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...

# PostgreSQL 数据库
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/saads

# Qdrant 向量数据库
# 本地模式（默认，使用 .runtime/wp11/qdrant_attack_signature_memory/）
QDRANT_MODE=local
# 远程模式（可选）
# QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=...

# FastAPI
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# 日志级别
LOG_LEVEL=INFO
```

### 3.3 数据库初始化

```bash
# 执行 db/sql/ 目录下的迁移脚本（按文件名顺序）
psql -U user -d saads -f backend/db/sql/001_init.sql
psql -U user -d saads -f backend/db/sql/002_...sql
# 以此类推
```

---

## 4. 启动服务

```bash
# 开发模式（自动重载）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 生产模式
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 若使用 pyproject.toml 定义的入口
python -m saads
```

启动后 API 文档可访问：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 5. WP1-1 智能体架构

WP1-1 是当前唯一全量实现的智能体（WP1-2～WP1-4 为 stub），其核心是一个基于 LangGraph 的有状态图。

### 5.1 状态定义（`orchestrator/state.py`）

`WP11GraphState` 是一个 TypedDict，包含约 70 个字段，分为以下分组：

| 分组 | 关键字段 | 说明 |
|------|---------|------|
| 运行元数据 | `run_id`, `run_mode`, `run_status`, `started_at` | 运行生命周期 |
| 采集 | `source_cursors`, `fetch_audits`, `stored_raw_records` | 数据采集过程 |
| 处理 | `raw_items`, `standardized_items`, `dedup_decisions` | 标准化与去重 |
| 分析 | `coverage_gaps`, `alert_candidates` | 覆盖率与告警 |
| 指标 | `processed_count`, `dedup_merged_count`, `new_attack_count` | 运行统计 |
| 错误 | `node_attempts`, `node_results`, `errors`, `completed_nodes` | 错误追踪 |

**RunMode 枚举：**
- `bootstrap` — 全量采集（首次运行）
- `incremental` — 增量更新（日常）
- `gap_fill` — 补充覆盖缺口
- `mixed` — 组合模式

### 5.2 节点执行顺序（`orchestrator/runtime.py`）

系统共有 **20 个图节点**，按以下顺序执行：

```
1.  load_runtime_context        ← 加载上下文（不可单独触发）
2.  supervisor_plan             ← 主管规划
3.  dispatch_collection         ← 分发采集任务
4.  collect_structured_sources  ← NVD / CWE 结构化源
5.  collect_code_sources        ← GitHub / PoC 代码库
6.  collect_paper_sources       ← arXiv / 学术论文
7.  collect_community_sources   ← 论坛 / 社区
8.  collect_advisory_sources    ← CISA KEV / 厂商公告
9.  store_raw_records           ← 存储原始记录
10. assess_collection_yield     ← 评估采集产出
11. reflect_search_strategy     ← 反思搜索策略
12. parse_and_standardize       ← 解析与标准化
13. semantic_dedup_and_merge    ← 语义去重合并
14. resolve_ai_bom              ← AI BOM 解析
15. review_ai_bom_resolution    ← BOM 解析审核
16. score_confidence_and_novelty ← 置信度与新颖度评分
17. refresh_coverage_view       ← 刷新覆盖率视图
18. coverage_gap_analysis       ← 覆盖缺口分析
19. generate_alerts             ← 生成告警
20. finalize_run                ← 完成运行
```

**注意：** `load_runtime_context`（节点 1）设置为 `is_triggerable: false`，不允许前端单独触发。

### 5.3 运行时包装类（`orchestrator/runtime.py`）

`Phase1GraphRuntime` 提供以下能力：

```python
runtime = Phase1GraphRuntime()

# 启动新运行
run_status = runtime.invoke(run_mode="incremental")

# 从指定节点恢复（断点续跑）
run_status = runtime.resume_from(run_id, node_name)

# 触发单个节点（调试用）
result = runtime.trigger_node(run_id, node_name)

# 取消运行
runtime.cancel(run_id)
```

---

## 6. 数据库模块

### 6.1 DbSession（`db/session.py`）

所有数据库操作必须经过 `DbSession`，它提供：
- SQL 执行日志（记录 elapsed_ms 和上下文字段）
- 自动异常映射（psycopg 异常 → 业务异常）
- 统一接口：`fetch_one()`, `fetch_all()`, `fetch_scalar()`, `execute()`, `execute_many()`

### 6.2 Unit of Work 模式（`db/unit_of_work.py`）

跨仓储的事务协调通过 `UnitOfWork` 管理：

```python
async with UnitOfWork(conn) as uow:
    await uow.attacks.create(attack_dto)
    await uow.sources.update(source_id, updates)
    # commit 在 __aexit__ 自动调用
    # 异常时自动 rollback
```

### 6.3 仓储层（`db/repositories/`）

遵循仓储模式，所有 SQL 封装在仓储类中，不允许在业务逻辑中直接拼接 SQL。

| 仓储 | 操作实体 |
|------|---------|
| `AttackRepository` | 攻击情报记录 |
| `ComponentRepository` | AI 组件 / BOM |
| `SourceRepository` | 数据源注册 |
| `GovernanceRepository` | 治理策略 |
| `ReadModelRepository` | 优化的读模型视图 |

---

## 7. 运行时数据目录（`.runtime/`）

`.runtime/` 目录存储运行时生成的持久化数据，**不提交 Git**，部署时需确保该目录可写。

| 子目录 | 内容 |
|--------|------|
| `wp11/audit/` | 每次运行的采集审计 JSON |
| `wp11/dedup/` | 语义去重决策缓存 |
| `wp11/raw_records/` | 原始采集数据（调试用） |
| `wp11/qdrant_attack_signature_memory/` | 本地 Qdrant 向量数据库文件 |
| `wp11/vector_memory/` | 向量记忆文件 |

**备份建议：** 在重要运行完成后备份 `.runtime/wp11/qdrant_attack_signature_memory/`（包含积累的攻击签名向量，重建成本高）。

---

## 8. 需要前端对接的 API 端点

以下端点在前端联调前必须实现。按优先级排序：

### P0（必须先实现）

| 方法 | 路径 | 返回类型 | 说明 |
|------|------|---------|------|
| GET | `/api/wp11/status` | `WpStatusResponse` | WP1-1 状态 + 关键指标 |
| GET | `/api/wp11/logs/stream` | SSE 流 | 实时日志流 |

### P1

| 方法 | 路径 | 返回类型 | 说明 |
|------|------|---------|------|
| GET | `/api/wp11/alerts` | `WpAlert[]` | WP1-1 告警列表 |
| GET | `/api/wp11/metrics` | `WpMetricSeries[]` | 历史指标时序 |
| POST | `/api/wp11/runs` | `WpRunStatus` | 启动运行 |
| DELETE | `/api/wp11/runs/{run_id}` | — | 取消运行 |
| GET | `/api/wp11/runs/active` | `WpRunStatus?` | 活跃运行状态 |

### P2

| 方法 | 路径 | 返回类型 | 说明 |
|------|------|---------|------|
| GET | `/api/wp11/nodes` | `WpNodeInfo[]` | 20 个图节点信息 |
| POST | `/api/wp11/nodes/{name}/run` | `WpRunStatus` | 触发单节点 |
| GET | `/api/wp11/state/latest` | `WP11StateSnapshot` | GraphState 摘要 |
| GET | `/api/alerts` | `WpAlert[]` | 全局告警 |

### P3（可 stub）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/wp12/status` | WP1-2 状态（pending stub） |
| GET | `/api/wp13/status` | WP1-3 状态（pending stub） |
| GET | `/api/wp14/status` | WP1-4 状态（pending stub） |

完整的请求/响应格式见 `docs/maintenance_integration.md`。

---

## 9. 数据约定

### 9.1 告警严重等级

前端 `WpAlertSchema` 使用大写三值枚举：`"HIGH"` / `"MEDIUM"` / `"LOW"`。

后端 `AlertCandidateDTO` 内部使用四值（含 `"critical"`），序列化时**必须映射为**：

```python
severity_map = {
    "critical": "HIGH",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
}
```

### 9.2 SSE 日志格式

每条消息必须是单行 JSON，字段：

```json
{
  "timestamp": "2026-03-19T12:34:56.789Z",
  "level": "INFO",
  "source": "supervisor_plan",
  "message": "规划完成，分发 5 个采集任务"
}
```

`level` 取值：`"DEBUG"` / `"INFO"` / `"WARN"` / `"ERROR"`

### 9.3 GraphState 精简快照

`GET /api/wp11/state/latest` 不返回完整 70 字段（展开后约 50KB），而是返回精简摘要：

```json
{
  "run_id": "...",
  "run_status": "running",
  "completed_nodes": ["load_runtime_context", "supervisor_plan"],
  "processed_count": 1423,
  "new_attack_count": 87,
  "dedup_merged_count": 156,
  "alert_count": 12,
  "error_count": 0
}
```

前端"展开"时追加 `?include_full=true` 获取完整 JSON。

---

## 10. 常见维护任务

### 10.1 添加新的数据采集源

1. 在 `tools/source_fetch_tools.py` 实现采集函数
2. 在 `orchestrator/nodes.py` 对应的 `collect_*_sources` 节点中注册
3. 在 `db/models/source.py` 添加源类型（如有新类型）

### 10.2 调整 LLM 提供商

在 `.env` 中切换 `OPENAI_API_KEY` 或 `GOOGLE_API_KEY`，并在 `agents/intel_agents/` 的 LLM 初始化代码中修改模型名称。

### 10.3 清理向量数据库

```bash
# 仅在确认需要重建时操作
rm -rf backend/.runtime/wp11/qdrant_attack_signature_memory/
# 下次运行时自动重建（代价：语义去重需重新学习）
```

### 10.4 调试单个节点

通过 `Phase1GraphRuntime.trigger_node()` 或前端调试面板（`/dashboard/wp11` → 调试面板 → 选择节点 → 触发）。

---

## 11. 故障排查

### 11.1 运行卡在某个节点

1. 检查 `WP11GraphState.errors` 字段（通过 `/api/wp11/state/latest?include_full=true`）
2. 检查 `.runtime/wp11/audit/` 中的最新审计文件
3. 使用 `resume_from(run_id, node_name)` 从卡住的节点重启

### 11.2 SSE 流前端收不到数据

1. 确认响应头包含 `Content-Type: text/event-stream` 和 `Cache-Control: no-cache`
2. 确认每次 yield 后调用了 `flush()`（FastAPI StreamingResponse 需要显式 flush）
3. 确认 Nginx 设置了 `proxy_buffering off`

### 11.3 向量搜索结果质量差

检查 Qdrant collection 状态：
```bash
curl http://localhost:6333/collections/attack_signatures
```
若 `vectors_count` 过少，考虑运行一次 `bootstrap` 模式的全量采集。

### 11.4 数据库连接错误

检查 `DATABASE_URL` 格式是否正确（注意 psycopg3 使用 `postgresql+psycopg://`，不是 `postgresql://`）。
