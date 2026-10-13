/**
 * mock.ts — Phase 0-3 阶段的 mock 数据
 * 通过 NEXT_PUBLIC_USE_MOCK_API=true 启用，Phase 3 联调后弃用。
 */
import type {
  WpStatusResponse,
  WpAlert,
  WpLogEntry,
  WpMetricSeries,
} from "@/lib/types/wp"
import type {
  WpRunStatus,
  WpNodeInfo,
  WP11StateSnapshot,
} from "@/lib/types/dashboard"
import type { StatsResponse } from "@/lib/types/stats"

/* ── Phase 0-2 mock 数据 ─────────────────────────────────────── */

export const MOCK_WP11_STATUS: WpStatusResponse = {
  wp_id: "wp11",
  status: "running",
  uptime_seconds: 306420, // ~3.5 天
  version: "v0.9.3",
  metrics: {
    attack_pool_size: 2412,
    coverage_rate: 91.3,
    new_intel_24h: 47,
  },
  current_tasks: [
    "Intel Supervisor: analyzing coverage gaps",
    "Web Crawler: fetching NVD CVE entries",
    "Standardizer: normalizing 12 raw records",
  ],
  last_updated: new Date().toISOString(),
}

export const MOCK_STATS: StatsResponse = {
  attack_entry_count: Number(MOCK_WP11_STATUS.metrics.attack_pool_size ?? 0),
  eval_job_count: 0,
  owasp_covered: 9,
  owasp_coverage_pct: Number(MOCK_WP11_STATUS.metrics.coverage_rate ?? 0),
}

export const MOCK_WP_STATUS_STUBS: Record<string, WpStatusResponse> = {
  wp12: {
    wp_id: "wp12",
    status: "pending",
    uptime_seconds: 0,
    version: "v0.0.0",
    metrics: { script_count: 0, owasp_coverage: 0, scripts_24h: 0 },
    current_tasks: [],
    last_updated: new Date().toISOString(),
  },
  wp13: {
    wp_id: "wp13",
    status: "pending",
    uptime_seconds: 0,
    version: "v0.0.0",
    metrics: { sessions: 0, datasets: 0, vuln_confirmed: 0 },
    current_tasks: [],
    last_updated: new Date().toISOString(),
  },
  wp14: {
    wp_id: "wp14",
    status: "pending",
    uptime_seconds: 0,
    version: "v0.0.0",
    metrics: { models_trained: 0, best_f1: 0, iterations: 0 },
    current_tasks: [],
    last_updated: new Date().toISOString(),
  },
}

export const MOCK_ALERTS: WpAlert[] = [
  {
    id: "alert-001",
    severity: "HIGH",
    title: "新发现 Prompt Injection 变体（多步骤间接注入）",
    cvss: 8.1,
    created_at: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
  },
  {
    id: "alert-002",
    severity: "MEDIUM",
    title: "检测到 Jailbreak 绕过技术更新（DAN v15）",
    cvss: 5.3,
    created_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
  },
  {
    id: "alert-003",
    severity: "LOW",
    title: "arXiv 新论文涉及 RAG 数据源泄露攻击",
    cvss: 3.7,
    created_at: new Date(Date.now() - 6 * 3600 * 1000).toISOString(),
  },
]

export const MOCK_LOGS: WpLogEntry[] = [
  {
    timestamp: new Date(Date.now() - 5000).toISOString(),
    level: "INFO",
    source: "supervisor_plan",
    message: "Coverage gap analysis complete: 3 new priority areas identified",
  },
  {
    timestamp: new Date(Date.now() - 14000).toISOString(),
    level: "INFO",
    source: "collect_structured_sources",
    message: "Fetched 12 CVE entries from NVD (last 24h)",
  },
  {
    timestamp: new Date(Date.now() - 29000).toISOString(),
    level: "WARN",
    source: "collect_community_sources",
    message: "Tor circuit timeout, retrying with new identity (attempt 2/3)",
  },
  {
    timestamp: new Date(Date.now() - 45000).toISOString(),
    level: "INFO",
    source: "parse_and_standardize",
    message: "Normalized 8 records, 2 flagged for LLM enhancement",
  },
  {
    timestamp: new Date(Date.now() - 62000).toISOString(),
    level: "ERROR",
    source: "collect_paper_sources",
    message: "PDF parse failed for arxiv:2501.12345 — skipping",
  },
  {
    timestamp: new Date(Date.now() - 90000).toISOString(),
    level: "ERROR",
    source: "resolve_ai_bom",
    message: "BOM resolution failed for CVE-2025-1234: LLM timeout after 30s",
  },
  {
    timestamp: new Date(Date.now() - 120000).toISOString(),
    level: "WARN",
    source: "semantic_dedup_and_merge",
    message:
      "Duplicate cluster size 3 exceeds threshold — dispatching adjudicator",
  },
  {
    timestamp: new Date(Date.now() - 150000).toISOString(),
    level: "INFO",
    source: "coverage_gap_analysis",
    message: "OWASP LLM Top 10 coverage: 9/10 categories covered",
  },
  {
    timestamp: new Date(Date.now() - 180000).toISOString(),
    level: "DEBUG",
    source: "assess_collection_yield",
    message:
      "Yield assessment: 47 raw records, 12 new attacks, yield_score=0.83",
  },
]

/** 生成 48h 的 mock 指标时序数据 */
export function generateMockMetricSeries(
  key: string,
  baseValue: number,
  growth: number
): WpMetricSeries {
  const now = Date.now()
  const points = Array.from({ length: 48 }, (_, i) => ({
    timestamp: new Date(now - (47 - i) * 3600 * 1000).toISOString(),
    value: Math.round(
      baseValue + growth * i + (Math.random() - 0.5) * growth * 2
    ),
  }))
  return { key, points }
}

/* ── Phase 3 mock 数据 ───────────────────────────────────────── */

export const MOCK_RUN_STATUS: WpRunStatus = {
  run_id: "run_mock_abc123",
  status: "running",
  run_mode: "bootstrap",
  progress: {
    current_node: "parse_and_standardize",
    completed_nodes: [
      "load_runtime_context",
      "supervisor_plan",
      "dispatch_collection",
      "collect_structured_sources",
      "collect_code_sources",
      "collect_paper_sources",
    ],
    total_nodes: 21,
    percent: 29,
  },
  started_at: new Date(Date.now() - 90000).toISOString(),
  completed_at: null,
  errors: [],
}

export const MOCK_WP11_NODES: WpNodeInfo[] = [
  {
    node_name: "load_runtime_context",
    display_name: "加载运行时配置",
    description: "初始化运行时上下文，加载数据源配置和过滤规则",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: false,
  },
  {
    node_name: "supervisor_plan",
    display_name: "规划主管",
    description: "supervisor_agent：分析 OWASP 覆盖缺口，制定采集优先级",
    last_run_at: new Date(Date.now() - 3600000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "dispatch_collection",
    display_name: "分发采集任务",
    description: "根据采集计划分发各数据源的采集任务",
    last_run_at: new Date(Date.now() - 3500000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "collect_structured_sources",
    display_name: "采集结构化数据源",
    description: "NVD CVE、CWE 等结构化漏洞数据库",
    last_run_at: new Date(Date.now() - 3400000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "collect_code_sources",
    display_name: "采集代码数据源",
    description: "GitHub Security Advisories、PoC 代码仓库",
    last_run_at: new Date(Date.now() - 3400000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "collect_paper_sources",
    display_name: "采集论文数据源",
    description: "arXiv 安全方向论文、HuggingFace 安全报告",
    last_run_at: new Date(Date.now() - 3400000).toISOString(),
    last_status: "failed",
    is_triggerable: true,
  },
  {
    node_name: "collect_community_sources",
    display_name: "采集社区数据源",
    description: "安全论坛、Tor 网络情报",
    last_run_at: new Date(Date.now() - 3400000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "collect_advisory_sources",
    display_name: "采集安全公告",
    description: "CISA KEV、厂商安全公告",
    last_run_at: new Date(Date.now() - 3400000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "store_raw_records",
    display_name: "存储原始记录",
    description: "将采集结果写入 raw_intel_records 表",
    last_run_at: new Date(Date.now() - 3300000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "assess_collection_yield",
    display_name: "评估采集产出",
    description: "计算产出率，决定是否需要反思或继续",
    last_run_at: new Date(Date.now() - 3200000).toISOString(),
    last_status: "succeeded",
    is_triggerable: true,
  },
  {
    node_name: "reflect_search_strategy",
    display_name: "反思搜索策略",
    description: "search_reflection_agent：分析缺口，调整搜索方向",
    last_run_at: null,
    last_status: "skipped",
    is_triggerable: true,
  },
  {
    node_name: "parse_and_standardize",
    display_name: "解析与标准化",
    description: "standardizer_agent：将原始记录规范化为 STIX 2.1 格式",
    last_run_at: new Date(Date.now() - 3000000).toISOString(),
    last_status: "failed",
    is_triggerable: true,
  },
  {
    node_name: "semantic_dedup_and_merge",
    display_name: "语义去重与合并",
    description: "dedup_merge_agent：向量相似度去重，LLM 裁决冲突",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "resolve_ai_bom",
    display_name: "解析 AI BOM",
    description: "bom_mapper_agent：将攻击条目映射到受影响的 AI 组件",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "review_ai_bom_resolution",
    display_name: "审核 BOM 解析结果",
    description: "bom_resolution_reviewer_agent：审核组件匹配决策",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "score_confidence_and_novelty",
    display_name: "评分置信度与新颖性",
    description: "计算每条攻击情报的置信度和新颖性分数",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "refresh_coverage_view",
    display_name: "刷新覆盖视图",
    description: "更新 OWASP LLM Top 10 覆盖率统计",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "coverage_gap_analysis",
    display_name: "覆盖缺口分析",
    description: "coverage_analyst_agent：识别尚未覆盖的威胁类别",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "weak_signal_mining",
    display_name: "弱信号挖掘",
    description: "从低置信度记录中识别新兴威胁模式",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "generate_alerts",
    display_name: "生成告警",
    description: "将高优先级新情报生成安全告警",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
  {
    node_name: "finalize_run",
    display_name: "完成运行",
    description: "记录运行统计，更新运行状态为 succeeded/partial_success",
    last_run_at: null,
    last_status: "never_run",
    is_triggerable: true,
  },
]

export const MOCK_WP11_STATE: WP11StateSnapshot = {
  run_id: "run_mock_abc123",
  run_mode: "bootstrap",
  run_status: "running",
  current_node: "parse_and_standardize",
  processed_count: 47,
  dedup_merged_count: 3,
  new_attack_count: 12,
  bom_queue_count: 5,
  reflection_round: 0,
  gap_fill_round: 0,
  errors_count: 2,
  completed_nodes: [
    "load_runtime_context",
    "supervisor_plan",
    "dispatch_collection",
    "collect_structured_sources",
    "collect_code_sources",
    "collect_paper_sources",
  ],
  raw_items_count: 52,
  standardized_items_count: 47,
  reflection_needed: false,
  gap_fill_needed: false,
  started_at: new Date(Date.now() - 90000).toISOString(),
  finished_at: null,
}
