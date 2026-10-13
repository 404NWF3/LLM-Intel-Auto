# SAADS `db/` 模块调用说明

本文档说明 `agents/intel_agents/` 中的各类智能体，如何调用 `db/` 模块完成 PostgreSQL 读写。重点不是解释 psycopg 的基础语法，而是说明 **Agent 与数据库模块的协作方式**。

---

## 1. 调用总原则

### 1.1 Agent 不直接写 SQL

`agents/intel_agents/` 中的业务代码不应直接出现：

- 表名拼接
- `SELECT * FROM wp11.xxx`
- 事务显式提交/回滚
- psycopg 原始异常处理

这些全部应下沉到 `db/`。

### 1.2 读简单、写集中

- 简单读取：可直接调用 read repository
- 所有跨表写入：必须走 service 或 unit of work

### 1.3 WP1-2 默认读视图，不直接拼多表 join

WP1-2 要生成测试脚本时，默认入口应是：

- `wp11.v_wp12_attack_feed`

而不是让 WP1-2 自己去 join：

- `attack_entry`
- `attack_cvss_assessment`
- `attack_taxonomy_map`
- `attack_component_impact`
- `attack_seed_asset`

---

## 2. 初始化方式

项目启动时，建议在应用入口初始化连接池。

### 典型流程

1. 读取 `config.py`
2. 调用 `db.connection.init_pool()`
3. 启动各智能体
4. 进程退出时调用 `close_pool()`

### 启动示意

```python
from db.connection import init_pool, close_pool


def main():
    init_pool()
    try:
        # 启动各 Agent
        ...
    finally:
        close_pool()
```

---

## 3. 推荐的 Agent 与数据库交互层级

### 3.1 采集 Agent

优先调用：

- `source_repository`
- `ingestion_service`

### 3.2 解析 Agent

优先调用：

- `attack_merge_service`
- `cvss_service`
- `taxonomy_service`

### 3.3 BOM 解析 Agent

优先调用：

- `component_repository`
- `bom_resolution_service`

### 3.4 WP1-2 消费侧

优先调用：

- `read_model_repository`
- `wp12_feed_service`

---

## 4. 采集 Agent：如何写入来源和任务

### 目标

当 `collector_agent.py` 启动一次采集时，需要：

1. 查找启用的情报源
2. 为某个源创建采集任务
3. 下载内容并计算 hash
4. 写入 `raw_intel_record`
5. 更新任务状态

### 推荐调用方式

```python
from db.unit_of_work import UnitOfWork
from db.services.ingestion_service import IngestionService


def run_collect(source_name: str, fetched_items: list[dict]):
    with UnitOfWork() as uow:
        service = IngestionService(uow)
        task = service.create_collection_task(
            source_name=source_name,
            task_mode="fast",
            trigger_type="manual",
            created_by="collector_agent"
        )

        for item in fetched_items:
            service.store_raw_intel_record(
                task_id=task.task_id,
                source_uri=item["source_uri"],
                title=item.get("title"),
                content_hash=item["content_hash"],
                raw_format=item["raw_format"],
                payload_uri=item["payload_uri"],
                language_code=item.get("language_code"),
                relevance_score=item.get("relevance_score"),
                fetched_at=item["fetched_at"]
            )

        service.finish_task(task.task_id, success=True)
```

### 说明

这里不要让 Agent 自己处理：

- 重复 hash 冲突
- task 状态切换
- 入库失败回滚

这些都应在 service / uow 中统一处理。

---

## 5. Parser Agent：如何从原始记录生成攻击条目

### 目标

解析 Agent 读取待解析 `raw_intel_record`，抽取标准化攻击对象，并与已有攻击条目做合并。

### 推荐调用方式

```python
from db.unit_of_work import UnitOfWork
from db.services.attack_merge_service import AttackMergeService


def process_one_raw_record(raw_id: str, parsed_attack: dict):
    with UnitOfWork() as uow:
        service = AttackMergeService(uow)
        result = service.merge_parsed_attack(
            raw_id=raw_id,
            attack_code=parsed_attack["attack_code"],
            canonical_name=parsed_attack["canonical_name"],
            attack_family=parsed_attack["attack_family"],
            severity_level=parsed_attack["severity_level"],
            summary=parsed_attack["summary"],
            description=parsed_attack["description"],
            exploit_preconditions=parsed_attack.get("exploit_preconditions"),
            impact_scope=parsed_attack.get("impact_scope"),
            confidence_score=parsed_attack["confidence_score"],
            first_seen_at=parsed_attack.get("first_seen_at"),
            last_seen_at=parsed_attack.get("last_seen_at"),
            evidence_role="primary",
            extractor_name="parser_agent"
        )
        return result.attack_id
```

### Service 内部应完成

- 根据 `attack_code` 查找是否已存在条目
- 新建或更新 `attack_entry`
- 插入 `attack_evidence`
- 必要时写 `dedup_audit`
- 更新 `raw_intel_record.parser_status`

---

## 6. CVSS Agent：如何补全或写入 CVSS

### 场景

你的系统中 CVSS 可能来自：

- 情报源直接提供
- 规则/程序计算
- LLM 估计
- 人工录入

这些都写入 `attack_cvss_assessment`，只是 `score_origin` 不同。

### 推荐调用方式

```python
from db.unit_of_work import UnitOfWork
from db.services.cvss_service import CvssService


def attach_cvss(raw_id: str, attack_id: str, cvss: dict):
    with UnitOfWork() as uow:
        service = CvssService(uow)
        service.add_cvss_assessment(
            attack_id=attack_id,
            source_raw_id=raw_id,
            cvss_version=cvss["cvss_version"],
            vector_string=cvss.get("vector_string"),
            base_score=cvss.get("base_score"),
            temporal_score=cvss.get("temporal_score"),
            environmental_score=cvss.get("environmental_score"),
            severity_label=cvss["severity_label"],
            exploitability_subscore=cvss.get("exploitability_subscore"),
            impact_subscore=cvss.get("impact_subscore"),
            score_origin=cvss["score_origin"],
            score_provider=cvss.get("score_provider"),
            confidence_score=cvss["confidence_score"],
            is_primary=cvss.get("is_primary", False),
            published_at=cvss.get("published_at"),
            calculated_at=cvss.get("calculated_at")
        )
```

### 注意

当 `is_primary=True` 时，service 内部必须处理：

- 同攻击、同版本其他评分全部取消主标记
- 再写当前评分为主

这一点不能由 Agent 手工操作。

---

## 7. Taxonomy Agent：如何写 OWASP/CWE/CAPEC/ATT&CK 映射

### 场景

从原始情报或解析结构中提取 taxonomy 标签。

### 推荐调用方式

```python
from db.unit_of_work import UnitOfWork
from db.services.taxonomy_service import TaxonomyService


def save_taxonomy(attack_id: str, taxonomy_items: list[dict]):
    with UnitOfWork() as uow:
        service = TaxonomyService(uow)
        service.replace_taxonomy_set(
            attack_id=attack_id,
            taxonomy_items=taxonomy_items
        )
```

### `taxonomy_items` 示例

```python
[
    {
        "taxonomy_type": "OWASP_LLM",
        "taxonomy_code": "LLM01",
        "taxonomy_name": "Prompt Injection",
        "is_primary": True,
        "confidence_score": 0.95,
    },
    {
        "taxonomy_type": "CWE",
        "taxonomy_code": "CWE-74",
        "taxonomy_name": "Injection",
        "is_primary": True,
        "confidence_score": 0.88,
    }
]
```

### Service 内部应保证

- 同一 `(attack_id, taxonomy_type, taxonomy_code)` 幂等
- 每个 taxonomy_type 最多一个主项

---

## 8. BOM Mapper Agent：如何完成组件匹配与队列入库

### 场景

从攻击描述中抽取：

- 组件名
- vendor
- 版本约束

然后映射到 `ai_component` / `ai_component_alias`。

### 推荐调用方式

```python
from db.unit_of_work import UnitOfWork
from db.services.bom_resolution_service import BomResolutionService


def resolve_component_mentions(attack_id: str, mentions: list[dict], raw_id: str | None = None):
    with UnitOfWork() as uow:
        service = BomResolutionService(uow)
        for m in mentions:
            service.resolve_or_enqueue(
                attack_id=attack_id,
                raw_id=raw_id,
                mentioned_name=m["mentioned_name"],
                mentioned_vendor=m.get("mentioned_vendor"),
                mentioned_version=m.get("mentioned_version"),
                reason_code="alias_not_found"
            )
```

### 该服务的内部逻辑应为

1. 先用严格匹配查 `ai_component.component_name`
2. 再查 `ai_component_alias.normalized_alias`
3. 必要时执行 trigram 模糊匹配
4. 若唯一且置信足够，写 `attack_component_impact`
5. 若无法确定，写 `bom_resolution_queue`

### 一个重要原则

BOM 解析失败时，绝不能静默吞掉。必须进入 `bom_resolution_queue`。

---

## 9. Seed Builder Agent：如何写攻击测试种子

### 场景

WP1-1 需要从攻击知识中沉淀可供 WP1-2 使用的测试资产，例如：

- `poc`
- `payload_template`
- `prompt_corpus`
- `rule`

### 推荐调用方式

```python
from db.unit_of_work import UnitOfWork
from db.repositories.attack_repository import AttackRepository


def save_seed_asset(attack_id: str, asset: dict):
    with UnitOfWork() as uow:
        repo = uow.attacks
        repo.insert_seed_asset(
            attack_id=attack_id,
            asset_type=asset["asset_type"],
            asset_name=asset["asset_name"],
            artifact_uri=asset["artifact_uri"],
            checksum=asset["checksum"],
            language=asset.get("language"),
            modality=asset.get("modality"),
            qa_status=asset.get("qa_status", "draft"),
            is_template=asset.get("is_template", True),
            metadata_json=asset.get("metadata_json")
        )
```

### 什么时候可以不经过 service

如果只是对单表做一次简单插入，可以直接调 repository。

但如果你要同时：

- 插入 seed asset
- 追加 remediation advice
- 更新 attack 状态

就应回到 service 层。

---

## 10. WP1-2：如何从数据库读取测试脚本生成输入

这是最关键的消费场景。

### 原则

WP1-2 **不要直接 join 基础表**。优先读：

- `v_wp12_attack_feed`

因为这个视图已经聚合了：

- 攻击主信息
- 主 CVSS
- 主 taxonomy
- 组件影响
- 可发布 seed asset

### 推荐调用方式

```python
from db.repositories.read_model_repository import ReadModelRepository
from db.unit_of_work import UnitOfWork


def get_wp12_feed(min_cvss: float = 7.0):
    with UnitOfWork() as uow:
        rows = uow.read_models.list_wp12_attack_feed(
            min_cvss=min_cvss,
            active_only=True,
            qa_statuses=["reviewed", "published"]
        )
        return rows
```

### 返回对象中至少应包含

- `attack_id`
- `attack_code`
- `canonical_name`
- `summary`
- `primary_cvss_base_score`
- `primary_cvss_vector`
- `taxonomy_type`
- `taxonomy_code`
- `component_name`
- `version_constraint_raw`
- `asset_type`
- `artifact_uri`

WP1-2 只关心“能不能生成测试脚本”，不关心底层表结构。

---

## 11. WP1-2 读取后的下一步处理

拿到 `v_wp12_attack_feed` 的结果后，WP1-2 通常会做三件事：

### 11.1 过滤

例如：

- 只要 `primary_cvss_base_score >= 7.0`
- 只要 `asset_type in ('poc', 'payload_template')`
- 只要 `qa_status in ('reviewed', 'published')`

### 11.2 分组

可按以下键分组：

- `attack_id`
- `component_id`
- `asset_type`

### 11.3 生成脚本

- 从 `artifact_uri` 取模板
- 从 `component_name + version_constraint_raw` 构造目标匹配条件
- 从 `taxonomy_code` 决定脚本类别

这三步都应在 WP1-2 内完成，而不是数据库模块完成。

---

## 12. 风险概览与看板读取

### 场景 1：按组件看风险

调用：

```python
with UnitOfWork() as uow:
    rows = uow.read_models.list_component_risk_overview(
        component_type="framework"
    )
```

读取对象来源：

- `v_component_risk_overview`

### 场景 2：看采集源质量

调用：

```python
with UnitOfWork() as uow:
    rows = uow.read_models.get_source_quality_dashboard()
```

读取对象来源：

- `v_source_quality_dashboard`

### 场景 3：看未解析 BOM 队列

调用：

```python
with UnitOfWork() as uow:
    rows = uow.read_models.list_unresolved_bom_queue(limit=100)
```

读取对象来源：

- `v_unresolved_bom_queue`

---

## 13. 物化视图的刷新

### 场景

`mv_owasp_coverage` 是物化视图，不会自动实时刷新。

### 推荐调用方式

```python
with UnitOfWork() as uow:
    uow.read_models.refresh_mv_owasp_coverage()
```

### 建议

- 不要在每次写入后立刻刷新
- 可在批处理结束后刷新
- 或在独立调度任务中刷新

---

## 14. 常见调用模式

### 模式 A：纯查询

适用：

- WP1-2 读取 feed
- dashboard 读取
- queue 查看

做法：

- `with UnitOfWork() as uow:`
- 调 `uow.read_models.xxx()`
- 不写数据

### 模式 B：单表简单写入

适用：

- 插入一条 `attack_seed_asset`
- 插入一条 `remediation_advice`

做法：

- 可直接调某个 repository

### 模式 C：跨表写入事务

适用：

- 原始记录解析成攻击条目
- 写入 CVSS 与 taxonomy
- BOM 自动解析 + queue

做法：

- 必须调 service
- 不要把多个 repository 调用散落在 Agent 里

---

## 15. Agent 内建议的依赖注入方式

不要在每个函数内部现建 service 和连接池。建议：

### 方案 A：构造器注入

```python
class ParserAgent:
    def __init__(self, attack_merge_service_factory):
        self.attack_merge_service_factory = attack_merge_service_factory
```

### 方案 B：运行时按任务创建 UoW

```python
class ParserAgent:
    def run_one(self, raw_id, parsed_attack):
        with UnitOfWork() as uow:
            service = AttackMergeService(uow)
            ...
```

对当前项目而言，方案 B 更直接。

---

## 16. 错误处理建议

### Agent 层应处理的错误

- `NotFoundError`
- `ValidationError`
- `DuplicateEntityError`
- `ConcurrencyConflictError`
- `TransactionError`

### Agent 层不应直接处理的错误

- psycopg 原始异常
- cursor 级别异常
- SQL 语法异常

这些应由 `db/` 统一转换。

### 示例

```python
try:
    with UnitOfWork() as uow:
        service = CvssService(uow)
        service.add_cvss_assessment(...)
except DuplicateEntityError:
    # 记录重复写入，转为幂等成功或告警
    ...
except ValidationError as exc:
    # 记录输入不合法
    ...
```

---

## 17. 日志字段建议

Agent 调用数据库模块时，建议日志里始终带上：

- `trace_id`
- `task_id`
- `raw_id`
- `attack_id`
- `component_id`
- `agent_name`

### 说明

数据库模块本身不应强依赖这些字段都存在，但 service 的方法签名可支持透传上下文信息。

---

## 18. 调用示例总览

### 18.1 采集源列表

```python
with UnitOfWork() as uow:
    sources = uow.sources.list_enabled_sources(source_type="api")
```

### 18.2 新建采集任务

```python
with UnitOfWork() as uow:
    task = uow.sources.create_collection_task(...)
```

### 18.3 插入原始记录

```python
with UnitOfWork() as uow:
    raw = uow.sources.insert_raw_intel_record(...)
```

### 18.4 建立攻击条目

```python
with UnitOfWork() as uow:
    attack = uow.attacks.upsert_attack_entry_by_code(...)
```

### 18.5 写入 CVSS

```python
with UnitOfWork() as uow:
    uow.attacks.insert_cvss_assessment(...)
```

### 18.6 写入 taxonomy

```python
with UnitOfWork() as uow:
    uow.attacks.replace_primary_taxonomy(...)
```

### 18.7 组件别名搜索

```python
with UnitOfWork() as uow:
    matches = uow.components.search_component_alias("langchain", limit=5)
```

### 18.8 BOM 失败入队

```python
with UnitOfWork() as uow:
    uow.governance.enqueue_bom_resolution(...)
```

### 18.9 WP1-2 读取 feed

```python
with UnitOfWork() as uow:
    feed_rows = uow.read_models.list_wp12_attack_feed(min_cvss=8.0)
```

---

## 19. 一个完整的端到端示例

下面给出一个典型链路：

### Step 1：采集 Agent 抓到一条原始情报

- 创建 `collection_task`
- 写 `raw_intel_record`

### Step 2：Parser Agent 解析并标准化

- 新建/更新 `attack_entry`
- 建立 `attack_evidence`

### Step 3：CVSS Agent 补充分数

- 写 `attack_cvss_assessment`
- 必要时切主分数

### Step 4：Taxonomy Agent 写分类

- 写 `attack_taxonomy_map`

### Step 5：BOM Mapper Agent 关联组件

- 写 `attack_component_impact`
- 失败则写 `bom_resolution_queue`

### Step 6：Seed Builder Agent 写测试资产

- 写 `attack_seed_asset`

### Step 7：WP1-2 消费

- 从 `v_wp12_attack_feed` 读取
- 生成测试脚本

这个流程中，WP1-2 完全不需要知道前面 6 步涉及哪些基础表；它只需要消费 read model。

---

## 20. 最后建议

对当前 SAADS 项目，调用数据库模块时最重要的四条规则是：

1. **Agent 不直接写 SQL**；
2. **跨表写入必须经过 service + unit of work**；
3. **WP1-2 默认只读 `v_wp12_attack_feed`**；
4. **BOM 解析失败必须显式进入 queue**。

只要严格遵守这四条，后续即使你继续扩展：

- 更多采集源
- 更多 taxonomy 体系
- 更复杂的 WP1-2 脚本生成
- 风险总览看板

数据库模块也不会失控。

---

## 21. 本地初始化与测试（当前实现）

### 21.1 环境变量

`db` 模块现已统一读取以下 PostgreSQL 配置（优先级从高到低）：

1. `POSTGRES_DSN`
2. `POSTGRES_HOST` + `POSTGRES_PORT` + `POSTGRES_DB` + `POSTGRES_USER` + `POSTGRES_PASSWORD`

并支持：

- `POSTGRES_SCHEMA`（默认 `wp11`）
- `POSTGRES_MIN_SIZE` / `POSTGRES_MAX_SIZE`
- `POSTGRES_CONNECT_TIMEOUT`
- `POSTGRES_STATEMENT_TIMEOUT_MS`
- `POSTGRES_APPLICATION_NAME`

### 21.2 Schema 初始化

在 PostgreSQL 目标库执行：

```sql
\i backend/db/wp11_postgresql_schema.sql
```

### 21.3 测试执行

- 单元测试：`python -m pytest tests/db -q`
- 集成测试：先设置 `SAADS_TEST_DSN`，再执行 `python -m pytest tests/db/integration -q`

集成测试会覆盖：

- `raw_intel_record` 幂等写入
- 主 CVSS 切换
- 主 taxonomy 替换
- BOM 队列 resolved 一致性
- `v_wp12_attack_feed` 读取与 `mv_owasp_coverage` 刷新

### 21.4 兼容接口说明

`db.repository.insert_attack_entry(...)` 仍保留作为过渡包装，但已标记为 deprecated。新代码应改用：

- `UnitOfWork().attacks`（简单仓储调用）
- `db.services.*`（跨表事务调用）
