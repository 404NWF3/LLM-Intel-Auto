export interface DocSourceFile {
  path: string
  label?: string
}

export type DocCategory = "WP1-1 智能体" | "数据库" | "前端设计"

export interface DocMeta {
  slug: string
  title: string
  description: string
  category: DocCategory
  /** Filename under the repo-root `docs/` directory */
  filename: string
  sourceFiles: DocSourceFile[]
  tags: string[]
}

export const DOC_REGISTRY: DocMeta[] = [
  // ── WP1-1 ─────────────────────────────────────────────────────────────────
  {
    slug: "wp11-architecture",
    title: "WP1-1 架构与接口签名",
    description:
      "情报采集智能体的推荐目录结构、模块职责划分、对外接口签名以及各子 Agent 协作关系。",
    category: "WP1-1 智能体",
    filename: "wp11_architecture.md",
    sourceFiles: [
      { path: "backend/agents/intel_agents/orchestrator/runtime.py", label: "运行时" },
      { path: "backend/agents/intel_agents/orchestrator/state.py", label: "状态定义" },
      { path: "backend/agents/intel_agents/", label: "智能体目录" },
    ],
    tags: ["架构", "LangGraph", "接口", "目录结构"],
  },
  {
    slug: "wp11-langgraph-state",
    title: "WP1-1 LangGraph 状态图与 State Schema",
    description:
      "WP1-1 图结构设计、21 个节点的执行顺序、TypedDict State 字段定义与运行模式说明。",
    category: "WP1-1 智能体",
    filename: "wp11_langgraph_state.md",
    sourceFiles: [
      { path: "backend/agents/intel_agents/orchestrator/state.py", label: "State 定义" },
      { path: "backend/agents/intel_agents/orchestrator/runtime.py", label: "图编译" },
    ],
    tags: ["LangGraph", "状态图", "State Schema", "节点顺序"],
  },
  {
    slug: "wp11-agentic-patterns",
    title: "WP1-1 Agentic Design Pattern 总结",
    description:
      "面向展示场景的智能体设计模式分析：工具调用、反思循环、多步规划与弱信号发现的代码落地。",
    category: "WP1-1 智能体",
    filename: "wp11_agentic_design_pattern_summary.md",
    sourceFiles: [
      { path: "backend/agents/intel_agents/", label: "智能体实现" },
      { path: "backend/agents/intel_agents/orchestrator/runtime.py", label: "运行时" },
    ],
    tags: ["Agentic", "设计模式", "反思循环", "弱信号"],
  },
  {
    slug: "wp11-tool-skill-partition",
    title: "WP1-1 子Agent / Tool / Skill 划分",
    description:
      "详细划分哪些功能应作为子 Agent、Tool 还是 Skill，包括划分原则与每个节点的职责边界。",
    category: "WP1-1 智能体",
    filename: "wp11_agent_tool_skill_partition.md",
    sourceFiles: [
      { path: "backend/agents/intel_agents/tools/", label: "工具层" },
      { path: "backend/agents/intel_agents/orchestrator/", label: "编排层" },
    ],
    tags: ["工具", "技能", "职责划分", "子Agent"],
  },
  {
    slug: "wp11-development-plan",
    title: "WP1-1 开发计划",
    description:
      "遵循 Phase 0 原则的完整开发计划：分阶段启用能力、不收窄 schema 与接口契约。",
    category: "WP1-1 智能体",
    filename: "wp11_development_plan.md",
    sourceFiles: [{ path: "backend/agents/intel_agents/", label: "智能体目录" }],
    tags: ["开发计划", "Phase", "路线图"],
  },
  {
    slug: "wp11-phase0-preparation",
    title: "WP1-1 Phase 0 准备工作",
    description:
      "Phase 0 的设计决策记录：不做 MVP 裁剪、保持完整 schema、基础设施搭建策略。",
    category: "WP1-1 智能体",
    filename: "wp11_phase0_preparation.md",
    sourceFiles: [
      { path: "backend/agents/intel_agents/orchestrator/state.py", label: "State" },
      { path: "backend/db/wp11/", label: "数据库层" },
    ],
    tags: ["Phase 0", "设计决策", "基础设施"],
  },
  {
    slug: "wp11-phase-review",
    title: "WP1-1 Phase 1–3 代码审查",
    description:
      "Phase 1 至 Phase 3 的代码质量审查报告，记录关键问题、技术债与改进建议。",
    category: "WP1-1 智能体",
    filename: "wp11_phase1_phase3_code_review.md",
    sourceFiles: [{ path: "backend/agents/intel_agents/", label: "智能体目录" }],
    tags: ["代码审查", "Phase 1", "Phase 3", "技术债"],
  },
  {
    slug: "wp11-phase4-review",
    title: "WP1-1 Phase 4 代码审查",
    description:
      "Phase 4 实现的代码审查记录，覆盖覆盖率补采、弱信号发现与反思循环的实现质量。",
    category: "WP1-1 智能体",
    filename: "wp11_phase4_code_review.md",
    sourceFiles: [{ path: "backend/agents/intel_agents/", label: "智能体目录" }],
    tags: ["代码审查", "Phase 4", "覆盖率补采", "反思循环"],
  },
  // ── 数据库 ─────────────────────────────────────────────────────────────────
  {
    slug: "db-module-design",
    title: "数据库模块详细设计",
    description:
      "SAADS db/ 模块的设计目标、分层结构、Repository 模式实现与跨 Agent 事务管理方案。",
    category: "数据库",
    filename: "db_module_design.md",
    sourceFiles: [
      { path: "backend/db/", label: "数据库层" },
      { path: "backend/db/wp11/", label: "WP1-1 Repository" },
    ],
    tags: ["PostgreSQL", "Repository", "事务", "SQLAlchemy"],
  },
  {
    slug: "db-module-usage",
    title: "数据库模块使用指南",
    description:
      "db/ 模块的使用方法、常见查询模式、异步会话管理与各 Repository 接口调用示例。",
    category: "数据库",
    filename: "db_module_usage.md",
    sourceFiles: [{ path: "backend/db/", label: "数据库层" }],
    tags: ["使用指南", "Repository", "SQLAlchemy", "异步"],
  },
  // ── 前端设计 ───────────────────────────────────────────────────────────────
  {
    slug: "frontend-design",
    title: "前端设计与开发方案",
    description:
      "SUFE-SAADS 前端的完整设计方案：技术选型、部署架构、设计系统、页面规格与组件架构。",
    category: "前端设计",
    filename: "frontend_design.md",
    sourceFiles: [
      { path: "frontend/src/", label: "前端源码" },
      { path: "frontend/src/app/", label: "App Router" },
      { path: "frontend/src/components/", label: "组件" },
    ],
    tags: ["Next.js", "设计系统", "组件架构", "部署"],
  },
]

export const DOC_CATEGORIES: DocCategory[] = ["WP1-1 智能体", "数据库", "前端设计"]

export function findDoc(slug: string): DocMeta | undefined {
  return DOC_REGISTRY.find((d) => d.slug === slug)
}
