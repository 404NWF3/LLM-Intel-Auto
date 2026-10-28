import type { WpStatus } from "@/lib/types/wp"

/* ── WP 元数据定义 ─────────────────────────────────────────── */

export interface WpMetricDef {
  /** API metrics 对象中对应的 key */
  key: string
  /** 展示标签 */
  label: string
  /** 单位（条、%、个…） */
  unit?: string
  /** 格式化方式 */
  format?: "number" | "percent" | "duration"
}

export interface WpMeta {
  /** 唯一 ID，对应路由 /dashboard/[wp] */
  id: string
  /** 中文名称 */
  label: string
  /** 编号（WP1-1 ~ WP1-4） */
  code: string
  /** 层次 */
  layer: "generic" | "user"
  /** 角色定位 */
  role: string
  /** 一句话描述 */
  description: string
  /** 后端 API 基础路径 */
  apiBase: string
  /** Dashboard 卡片展示的核心指标（最多 3 个） */
  metrics: [WpMetricDef, WpMetricDef, WpMetricDef]
  /** SSE 日志流端点路径（相对 apiBase） */
  logStream: string
  /** 卡片排列顺序 */
  order: number
  /** 初始 mock 状态（API 未就绪时使用）*/
  mockStatus: WpStatus
}

/* ── 注册表 ── 新增 WP 只修改此处 ─────────────────────────── */

export const WP_REGISTRY: WpMeta[] = [
  {
    id: "wp11",
    label: "情报采集智能体",
    code: "WP1-1",
    layer: "generic",
    role: "威胁发现者",
    description:
      "从 NVD、arXiv、CISA KEV 与 OSV 采集大模型安全情报，支持增量追踪与自演化检索。",
    apiBase: "/api/wp11",
    metrics: [
      { key: "attack_pool_size", label: "已入库情报", unit: "条", format: "number" },
      { key: "coverage_rate", label: "OWASP 覆盖率", unit: "%", format: "percent" },
      { key: "new_intel_24h", label: "今日新增", unit: "条", format: "number" },
    ],
    logStream: "/api/wp11/logs/stream",
    order: 1,
    mockStatus: "running",
  },
  {
    id: "wp12",
    label: "渗透测试智能体",
    code: "WP1-2",
    layer: "generic",
    role: "漏洞测试脚本生成者",
    description: "根据采集情报分析漏洞条件，生成 HTTP 或聊天接口测试脚本、判定规则和来源说明。",
    apiBase: "/api/pentest",
    metrics: [
      { key: "script_count", label: "测试脚本", unit: "个", format: "number" },
      { key: "owasp_coverage", label: "OWASP 覆盖", unit: "%", format: "percent" },
      { key: "scripts_24h", label: "今日生成", unit: "个", format: "number" },
    ],
    logStream: "/api/pentest/logs/stream",
    order: 2,
    mockStatus: "pending",
  },
  {
    id: "wp13",
    label: "沙盒模拟智能体",
    code: "WP1-3",
    layer: "user",
    role: "项目验证者",
    description: "承接本地仓库对抗审计、离线案例、检查点恢复及报告；隔离执行环境待接入。",
    apiBase: "/api/sandbox",
    metrics: [
      { key: "recent_run_count", label: "审计与案例", unit: "次", format: "number" },
      { key: "recent_completed_count", label: "已完成任务", unit: "次", format: "number" },
      { key: "findings", label: "代码审计发现", unit: "条", format: "number" },
    ],
    logStream: "/api/sandbox/logs/stream",
    order: 3,
    mockStatus: "pending",
  },
  {
    id: "wp14",
    label: "异常检测智能体",
    code: "WP1-4",
    layer: "user",
    role: "防御建设者",
    description: "上传数值 CSV，逐轮比较异常检测模型与参数，评估并导出保留方案。",
    apiBase: "/api/wp14",
    metrics: [
      { key: "models_trained", label: "已训练模型", unit: "个", format: "number" },
      { key: "best_f1", label: "最优 F1", unit: "%", format: "percent" },
      { key: "iterations", label: "迭代轮次", unit: "轮", format: "number" },
    ],
    logStream: "/api/wp14/logs/stream",
    order: 4,
    mockStatus: "pending",
  },
]

/** 按 order 排序后的注册表（使用时请用此导出） */
export const SORTED_WP_REGISTRY = [...WP_REGISTRY].sort((a, b) => a.order - b.order)

/** 通过 id 快速查找 WP，未找到返回 undefined */
export function findWp(id: string): WpMeta | undefined {
  return WP_REGISTRY.find((wp) => wp.id === id)
}
