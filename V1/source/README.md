# 基于多智能体的 AI 系统态势感知与自动化防御系统

## 系统定位

通过构建一套**自我感知、学习、规划、执行**的智能体群，解决各类 AI 系统（包括大模型、小模型、AI OS、AI 应用等）所面临的各类安全挑战，涵盖**网络安全**与**功能安全**。

**第一阶段**主攻大模型的安全问题（提示词注入、模型越狱等网络安全相关问题）；未来将逐步开发各类子系统与智能体，解决更广泛的安全问题。

四个智能体模块 (WP1-1 ~ WP1-4) 协同工作，形成完整的 **攻防一体化安全闭环** — 不仅自动发现和验证漏洞，还能自动生成防御能力（检测模型），持续进化。

## 核心架构

| 智能体 | 编号 | 角色定位 | 所属层次 |
|--------|------|----------|----------|
| **情报采集智能体** | WP1-1 | 威胁发现者 | 通用层 |
| **渗透测试智能体** | WP1-2 | 测试方案生成者 | 通用层 |
| **沙盒模拟智能体** | WP1-3 | 测试执行与数据采集者 | 用户层 |
| **异常检测智能体** | WP1-4 | 防御建设者 | 用户层 |

### 通用层与用户层

系统明确划分为两个层次：

**通用层（与用户应用无关，持续运行）**

WP1-1 和 WP1-2 独立运行，不依赖任何用户的具体应用。它们持续积累威胁情报、测试方案和脚本，类似于"弹药工厂"。

**用户层（与用户应用绑定）**

WP1-3 和 WP1-4 在用户接入系统后才开始工作。WP1-3 接入用户应用、解析其 AI BOM、与通用层的情报库匹配后筛选出相关威胁，然后执行测试并采集数据；WP1-4 基于采集的数据为用户训练定制化检测模型。

![系统架构图](./assets/ai_security_testing.svg)

### 核心设计原则

1. **通用层与用户层分离** — WP1-1/WP1-2 持续积累通用安全知识，不依赖用户；WP1-3/WP1-4 在用户接入后匹配并执行
2. **系统层用 Pipeline + Event-Driven, 子系统内部各自选择最合适的 Agent 架构**
3. **智能体之间通过中央知识库解耦, 而非直接 Handoff** — 各子系统运行时间跨度差异巨大, 且需要独立运行/调试
4. **渐进式复杂度** — 先用文件系统 + JSON 跑通, 再演进为数据库 + 向量存储
5. **攻防一体闭环** — 蓝队防御结果反馈回红队, 驱动下一轮攻击进化


## 技术架构分层

| 层级 | 组成 |
|------|------|
| **应用层** | 四个智能体 (WP1-1 ~ WP1-4) + 安全运营智能助手 |
| **模型层** | 大语言模型 (攻击生成/评估)、多模态模型、向量模型、搜索引擎 |
| **数据层** | 数据采集、预处理、向量化、知识库 (知识问答、报警根因分析) |
| **中间层** | 资源管理 (Docker 容器/虚拟化)、AI 工具 (Dify)、安全模块 |
| **基础设施** | 计算 (CPU/GPU)、存储 (HBM/NVMe)、网络 (IB/RoCE) |


## 4 个子系统的详细设计

### 子系统 1: 情报采集智能体 (WP1-1)

**所属层次**: 通用层

**核心任务**: 监控各类主流 AI 系统，自动化采集、分析各类安全威胁情报，标注受影响的 AI BOM 组件

**内部架构**: Supervisor

选择 Supervisor 是因为爬取目标是动态的, 需要 Supervisor 根据当前攻击池的覆盖情况决定"接下来去哪里找什么类型的攻击"。

![情报采集智能体架构图](./assets/02_Intelligence-Collection-Module.svg)

**数据来源**:

| 来源 | 采集内容 |
|------|---------|
| **公开漏洞库** (CVE、NVD、MITRE ATT&CK) | 已知 AI 系统相关 CVE、ATT&CK 战术映射 |
| **技术社区** (GitHub Security、HuggingFace、arXiv) | PoC 代码、安全论文、模型卡中的安全声明 |
| **暗网数据** (论坛、Telegram 群组) | 地下攻击工具、泄露的攻击手法 |
| **第三方情报 API** (VirusTotal、AlienVault 等) | 结构化威胁指标 (IoC)、关联分析 |

**内部 Agent 说明**:

| Agent | 职责 | 工具 |
|-------|------|------|
| **Intel Supervisor** | 分析攻击池覆盖率 (按 OWASP LLM Top 10 分类), 决定优先采集方向 | 知识库查询, 覆盖率统计 |
| **Web Crawler Agent** | 爬取公开漏洞库、技术社区、安全博客 | httpx, BeautifulSoup, GitHub API, HuggingFace API |
| **Paper Analyzer Agent** | 解析学术论文和安全报告, 提取攻击方法与 PoC | PDF 解析, LLM 摘要提取 |
| **Dark Web Agent** | 采集暗网论坛和 Telegram 群组中的攻击情报 | Tor 代理, Telegram Bot API |
| **Standardizer Agent** | 将原始情报标准化为 **STIX 2.1 兼容** 的 attack_pool schema, 去重, 标注受影响的 AI BOM 组件 | JSON Schema 验证, 相似度检测, STIX 序列化 |

**产出**:
- **安全威胁情报库**：`attack_pool/` 目录下的标准化攻击条目 (STIX 2.1 兼容 JSON)，每条标注受影响的 AI BOM 组件类型与版本
- **AI BOM 通用组件知识库**：主流 AI 模型、框架、工具的组件信息与已知风险（类似 SBOM，用于后续与用户系统匹配）
- **推荐处置方案**：基于公开安全建议和最佳实践的防御性建议（告诉你怎么修）
- 实时告警 (高危新攻击技术发现时)
- 可操作的测试用例 (直接可被 WP1-2 消费)

---

### 子系统 2: 渗透测试智能体 (WP1-2)

**所属层次**: 通用层

**核心任务**: 针对 WP1-1 输出的安全威胁情报，借助大模型及"本体+知识图谱"技术，自动生成通用测试方案和测试脚本（代码、语料库等）

**注意**: WP1-2 **仅负责生成**测试方案与脚本，不负责执行测试。实际测试执行在 WP1-3 沙盒中进行。

**内部架构**: Supervisor

- Orchestrator 需要从 attack_pool **按策略选择** 攻击任务, 而非让 Agent 自行决定
- 攻击覆盖率 (OWASP LLM Top 10) 需要 Orchestrator 统一追踪

<!-- ![渗透测试智能体架构图](./assets/03_Red-team-Orchestrator.svg) -->

**关键能力**:

| 能力 | 说明 |
|------|------|
| **基于本体+知识图谱生成测试方案** | 利用 AI 安全知识图谱理解攻击模式间的关联，生成系统化的测试方案 |
| **基于模板生成测试脚本** | 参照 OWASP LLM Top 10 分类, 从 attack_pool 读取模板并实例化为可执行脚本 |
| **攻击向量库管理** | 提示注入、数据泄露、拒绝服务、越狱、Agent 劫持等 |
| **多模态测试支持** | 文本、图像、音频三种模态的攻击脚本生成 |
| **预估 CVSS 评分** | 基于情报信息对威胁进行理论评分（最终验证在 WP1-3 执行后确定） |

**内部 Agent 说明**:

| Agent | 职责 | 工具 |
|-------|------|------|
| **Red Team Orchestrator** | 从 attack_pool 选择攻击、分派生成任务、追踪 OWASP Top 10 覆盖率 | 知识库读取, 知识图谱查询, 任务调度 |
| **Prompt Injection Agent** | 生成直接/间接提示词注入攻击脚本 | Payload 模板库, 变异引擎 |
| **Jailbreak Agent** | 生成越狱攻击脚本 (DAN、角色扮演、编码绕过、token 走私) | 越狱模板库, 变异引擎 |
| **Info Leakage Agent** | 生成系统提示词泄露、训练数据泄露、RAG 数据源泄露的探测脚本 | 探测 Prompt 库 |
| **Multimodal Attack Agent** | 生成图像对抗样本、音频攻击、跨模态注入脚本 | 图像处理库, 音频处理库 |

**产出**:
- **测试方案库**：针对各类威胁的系统化测试方案
- **测试脚本库**：可执行的攻击脚本包（代码、语料库等），存入 `test_scripts/` 目录
- 预估 CVSS 评分（理论评分，供 WP1-3 参考）

---

## 项目代码结构说明

### 根目录配置文件

| 文件                        | 说明                                      |
| --------------------------- | ----------------------------------------- |
| README.md                   | 项目说明文档                              |
| .env                        | 运行时环境变量（API Key、数据库连接串等） |
| requirements.txt            | Python 依赖清单                           |
| main.py                     | 后端主入口（启动 FastAPI 应用）           |
| serve.py                    | uvicorn 服务启动封装                      |
| wp11_llm_profiles.jsonn)    | WP1.1 LLM 模型实例池配置                  |
| wp11_llm_route_presets.json | WP1.1 各节点 LLM 路由预设规则             /


### 后端

```
backend/
├── __init__.py
│
├── api/                              # FastAPI 层
│   ├── server.py                     # 应用工厂，注册路由、中间件
│   ├── run_store.py                  # WP1.1 运行状态内存存储
│   ├── wp12_run_store.py             # WP1.2 运行状态内存存储
│   └── routers/
│       ├── sentinel.py               # /sentinel/* 路由（状态查询、健康检查）
│       ├── wp11.py                   # /wp11/* 路由（触发运行、SSE 日志流）
│       └── wp12.py                   # /wp12/* 路由
│
├── agents/
│   │
│   ├── intel_agents/                 # WP1.1 情报采集子系统
│   │   ├── agents/                   # Agent 角色定义
│   │   │   ├── supervisor_agent.py       # 规划 Supervisor
│   │   │   ├── standardizer_agent.py     # 情报标准化 Agent
│   │   │   ├── bom_mapper_agent.py       # AI BOM 映射 Agent
│   │   │   ├── bom_resolution_reviewer_agent.py  # BOM 决议审核 Agent
│   │   │   ├── coverage_analyst_agent.py # 覆盖度分析 Agent
│   │   │   ├── dedup_adjudicator_agent.py # 去重裁决 Agent
│   │   │   ├── dedup_merge_agent.py      # 去重合并 Agent
│   │   │   └── search_reflection_agent.py # 搜索反思 Agent
│   │   │
│   │   ├── crews/                    # 多 Agent 协作编排
│   │   │   ├── crew_collaboration.py
│   │   │   └── source_collection_crew.py
│   │   │
│   │   ├── orchestrator/             # LangGraph 图编排层
│   │   │   ├── graph.py              # 主图定义（节点 + 边）
│   │   │   ├── nodes.py              # 节点函数实现
│   │   │   ├── router.py             # 条件路由逻辑
│   │   │   ├── runtime.py            # 图运行时（执行、流式输出）
│   │   │   ├── state.py              # LangGraph 全局状态 TypedDict
│   │   │   └── subgraphs/
│   │   │       ├── ai_bom_graph.py   # AI BOM 解析子图
│   │   │       └── stix_graph.py     # STIX 图谱构建子图
│   │   │
│   │   ├── runners/
│   │   │   └── bootstrap_runner.py   # 初始化 + 单次运行入口
│   │   │
│   │   ├── schemas/                  # Pydantic 数据模型
│   │   │   ├── alert.py
│   │   │   ├── coverage.py
│   │   │   ├── intel.py
│   │   │   ├── patch.py
│   │   │   ├── plan.py
│   │   │   ├── query.py
│   │   │   ├── runtime.py
│   │   │   └── source.py
│   │   │
│   │   ├── services/                 # 领域服务（无副作用的业务逻辑）
│   │   │   ├── attack_signature_memory.py
│   │   │   ├── component_resolution_service.py
│   │   │   ├── confidence_scoring_service.py
│   │   │   ├── coverage_read_model_service.py
│   │   │   ├── dedup_memory_service.py
│   │   │   ├── gap_scoring_service.py
│   │   │   ├── query_feedback_memory.py
│   │   │   ├── raw_ingest_flow.py
│   │   │   ├── runtime_tuning_service.py    # 运行时动态调参
│   │   │   ├── source_health_service.py
│   │   │   ├── source_query_template_service.py
│   │   │   ├── source_registry.py
│   │   │   ├── source_scheduler.py
│   │   │   └── stix_graph_service.py
│   │   │
│   │   └── tools/                    # LangGraph Tool 函数（LLM 调用封装）
│   │       ├── llm_client_factory.py      # LLM 客户端工厂（对接 LLM 池）
│   │       ├── llm_supervisor_planning_tools.py
│   │       ├── llm_standardization_tools.py
│   │       ├── llm_bom_resolver_tools.py
│   │       ├── llm_bom_review_tools.py
│   │       ├── llm_coverage_analyst_tools.py
│   │       ├── llm_dedup_adjudication_tools.py
│   │       ├── llm_merge_judge_tools.py
│   │       ├── llm_search_reflection_tools.py
│   │       ├── llm_stix_graph_tools.py
│   │       ├── bom_tools.py
│   │       ├── dedup_tools.py
│   │       ├── parsing_tools.py
│   │       ├── rule_validator_fuser.py
│   │       └── source_fetch_tools.py
│   │
│   └── saads_wp12/                   # WP1.2 漏洞测试包生成子系统
│       ├── agent.py                  # WP1.2 Agent 入口
│       ├── config.py
│       ├── state.py                  # WP1.2 LangGraph 状态
│       ├── data/                     # 数据馈入层
│       │   ├── feed_provider.py          # 抽象基类
│       │   ├── db_feed_provider.py       # 数据库馈入
│       │   ├── local_feed_provider.py    # 本地文件馈入
│       │   ├── mock_feed_provider.py     # Mock 数据馈入
│       │   └── models.py
│       ├── engines/                  # 核心处理引擎
│       │   ├── threat_understanding.py
│       │   └── test_package_generation.py
│       ├── graphs/                   # LangGraph 图
│       │   ├── main_graph.py
│       │   └── subgraphs/
│       │       ├── threat_understanding.py
│       │       └── test_package_generation.py
│       ├── llm/                      # LLM 调用层
│       │   ├── client.py
│       │   ├── test_package_generation_prompts.py
│       │   └── test_package_prompt_router.py
│       ├── nodes/                    # 图节点
│       │   ├── intel.py
│       │   ├── persistence.py
│       │   ├── routing.py
│       │   └── validation.py
│       └── reporting/                # 结果输出
│           ├── llm_plan_writer.py
│           ├── state_export.py
│           └── test_plan_renderer.py
│
└── db/                               # 数据持久化层
    ├── connection.py                 # 数据库连接配置
    ├── session.py                    # SQLAlchemy AsyncSession 工厂
    ├── unit_of_work.py               # 工作单元模式
    ├── repository.py                 # 泛型 Repository 基类
    ├── dtos.py                       # 跨层数据传输对象
    ├── exceptions.py
    ├── pagination.py
    ├── typing.py
    ├── models/                       # ORM 模型（SQLAlchemy）
    │   ├── attack.py
    │   ├── component.py
    │   ├── governance.py
    │   ├── source.py
    │   ├── stix.py
    │   └── views.py
    ├── repositories/                 # 数据访问对象
    │   ├── base.py
    │   ├── attack_repository.py
    │   ├── component_repository.py
    │   ├── governance_repository.py
    │   ├── read_model_repository.py
    │   ├── source_repository.py
    │   └── stix_repository.py
    ├── services/                     # 数据库业务服务
    │   ├── attack_merge_service.py
    │   ├── bom_resolution_service.py
    │   ├── component_seed_service.py
    │   ├── cvss_service.py
    │   ├── ingestion_service.py
    │   ├── taxonomy_service.py
    │   └── wp12_feed_service.py
    └── sql/                          # 原生 SQL 查询模块
        ├── attack_queries.py
        ├── bom_queries.py
        ├── governance_queries.py
        ├── read_model_queries.py
        ├── source_queries.py
        └── stix_queries.py
```

### 前端

```
frontend/
├── package.json                      # npm 依赖与脚本
├── next.config.ts                    # Next.js 配置
├── tsconfig.json                     # TypeScript 配置
├── .env.local                        # 前端环境变量（NEXT_PUBLIC_* 等）
│
└── src/
    ├── app/                          # Next.js App Router
    │   ├── layout.tsx                # 根布局
    │   ├── globals.css
    │   ├── (marketing)/              # 落地页路由组
    │   │   ├── layout.tsx
    │   │   ├── page.tsx              # 首页 /
    │   │   ├── docs/
    │   │   │   ├── page.tsx          # 文档列表 /docs
    │   │   │   └── [slug]/page.tsx   # 文档详情 /docs/:slug
    │   │   └── story/
    │   │       ├── page.tsx          # 项目介绍 /story
    │   │       └── StoryShell.tsx
    │   ├── api/
    │   │   └── stats/route.ts        # Next.js API 路由（聚合后端统计）
    │   └── dashboard/                # Dashboard 路由
    │       ├── layout.tsx            # Dashboard 布局（含侧边栏）
    │       ├── page.tsx              # /dashboard（概览）
    │       └── [wp]/page.tsx         # /dashboard/wp11 | /dashboard/wp12
    │
    ├── components/
    │   ├── dashboard/                # Dashboard 业务组件
    │   │   ├── AlertPanel/           # 告警面板
    │   │   ├── DashboardSidebar/     # 侧边导航（含 MockMode 开关）
    │   │   ├── DebugControlPanel/    # Agent 节点调试面板
    │   │   │   ├── AgentNodeCard.tsx
    │   │   │   ├── RunControl.tsx
    │   │   │   ├── RunProgressTracker.tsx
    │   │   │   └── StateInspector.tsx
    │   │   ├── LogViewer/            # SSE 实时日志流查看器
    │   │   ├── MetricsPanel/         # 指标面板（含 SparkLine）
    │   │   ├── SentinelAssistantPanel/  # Sentinel 对话助手面板
    │   │   ├── SentinelControlPanel/    # Sentinel 运行控制面板
    │   │   ├── SentinelDashboardContent/ # WP1.1 Dashboard 整体布局
    │   │   ├── SystemHealthBar/         # 系统健康状态栏
    │   │   ├── Wp11MetricsPanel/        # WP1.1 专用指标面板
    │   │   ├── Wp12ControlPanel/        # WP1.2 运行控制面板
    │   │   ├── Wp12DashboardContent/    # WP1.2 Dashboard 整体布局
    │   │   ├── Wp12PlanPanel/           # WP1.2 测试计划展示
    │   │   ├── Wp12ResultPanel/         # WP1.2 结果展示
    │   │   ├── WpDetailHeader/          # 子系统详情页头部
    │   │   └── WpStatusCard/            # WP 状态卡片
    │   ├── docs/                     # 文档渲染组件
    │   │   ├── DocCard/
    │   │   ├── DocRenderer/          # Markdown 渲染器
    │   │   └── DocToc/              # 目录导航
    │   ├── layout/                   # 全局布局组件
    │   │   ├── SiteHeader/
    │   │   └── SiteFooter/
    │   ├── sections/                 # 落地页各区块
    │   │   ├── ArchitectureFlow/     # 架构流程图区块
    │   │   ├── CtaBand/             # CTA 号召区块
    │   │   ├── HeroSection/         # Hero 区块（含系统状态浮层）
    │   │   └── KpiStrip/            # KPI 数字区块
    │   └── ui/                       # 通用原子 UI 组件
    │       ├── Badge/
    │       ├── CodeWindow/
    │       ├── CountUp/              # 数字滚动动画
    │       ├── ScrollReveal/         # 滚动入场动画
    │       ├── SkeletonLine/         # 骨架屏
    │       └── StatusDot/            # 状态指示点
    │
    ├── lib/
    │   ├── api/
    │   │   ├── client.ts             # 后端 HTTP/SSE 客户端封装
    │   │   └── mock.ts               # Mock 数据层（离线开发用）
    │   ├── docs/
    │   │   ├── processor.ts          # Markdown 处理管线
    │   │   └── registry.ts           # 文档注册表
    │   ├── hooks/                    # React 自定义 Hooks
    │   │   ├── useSSELog.ts              # SSE 日志流订阅
    │   │   ├── useSentinelRunController.ts # WP1.1 运行控制逻辑
    │   │   ├── useStats.ts               # 系统统计数据拉取
    │   │   ├── useWp11Nodes.ts           # WP1.1 Agent 节点状态
    │   │   ├── useWp11State.ts           # WP1.1 全局状态订阅
    │   │   ├── useWp12RunController.ts   # WP1.2 运行控制逻辑
    │   │   ├── useWpAlerts.ts
    │   │   ├── useWpMetrics.ts
    │   │   ├── useWpRun.ts
    │   │   └── useWpStatus.ts
    │   ├── types/                    # TypeScript 类型定义
    │   │   ├── dashboard.ts
    │   │   ├── stats.ts
    │   │   ├── wp.ts
    │   │   └── wp12.ts
    │   └── wp-registry.ts            # WP 子系统注册表（路由 + 元数据）
    │
    └── styles/                       # 全局样式
        ├── tokens.css                # CSS 设计令牌（颜色、间距、字体）
        ├── base.css                  # 全局基础样式重置
        └── animations.css            # 动画关键帧定义
```