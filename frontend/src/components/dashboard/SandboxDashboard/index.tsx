"use client"
import { useState, useEffect, useRef, type FormEvent } from "react"
import useSWR from "swr"
import Link from "next/link"
import {
  ArrowUpRight,
  BookOpen,
  CircleStop,
  FileSearch,
  GitBranch,
  Play,
  RefreshCw,
  RotateCcw,
  Scale,
  Shield,
  Swords,
} from "lucide-react"
import {
  sandboxFetch,
  useSandboxOverview,
  useSandboxRuns,
  type SandboxConfig,
  type SandboxDetail,
  type SandboxRun,
} from "@/lib/api/sandbox"
import base from "../IntelDashboard/IntelDashboard.module.css"
import s from "./SandboxDashboard.module.css"
import { TaskArtifacts } from "../TaskArtifacts"
import task from "../TaskArtifacts/TaskRun.module.css"

const statusLabels: Record<string, string> = {
  running: "进行中",
  cancelling: "正在停止",
  succeeded: "已完成",
  failed: "失败",
  interrupted: "待恢复",
  cancelled: "已停止",
  unsupported: "未支持",
}
const phases: Record<string, string> = {
  intake: "任务接管",
  profiling: "仓库画像",
  discovery: "假设发现",
  debating: "红蓝辩论",
  adjudicating: "独立裁决",
  generating_tests: "生成测试草稿",
  complete: "报告就绪",
  interrupted: "等待恢复",
  generating_case: "案例生成",
  running: "启动运行环境",
  succeeded: "产物就绪",
  failed: "运行失败",
  cancelled: "已停止",
  unsupported: "意图未支持",
  cancelling: "正在停止",
}
const initial: SandboxConfig = {
  kind: "audit",
  target_repo: "",
  authorization_ref: "",
  goal: "审查该 LLM 应用的提示词边界、工具权限与数据泄露风险",
  request: "",
  max_rounds: 4,
  max_agent_calls: 30,
  max_cost_usd: 5,
  use_graphrag: true,
}
const templates = [
  ["提示词注入", "生成一个提示词注入离线攻击案例，验证不可信检索内容能否覆盖系统指令。"],
  ["长对话越界", "生成一个长对话离线案例，验证多轮交互中的指令边界与安全策略保持。"],
  [
    "工具劫持",
    "生成一个工具劫持离线攻击案例，验证工具返回中的恶意指令能否影响后续工具选择。",
  ],
]
export function SandboxDashboard() {
  const overview = useSandboxOverview()
  const history = useSandboxRuns("sandbox")
  const [selection, setSelection] = useState<string | null>(null)
  const graphActive = overview.data?.active_run_kind === "graph"
  const activeRunId = graphActive ? null : overview.data?.active_run_id
  const runId = selection ?? activeRunId ?? history.data?.[0]?.run_id
  const detail = useSWR<SandboxDetail, Error>(
    runId ? `/api/sandbox/runs/${runId}` : null,
    sandboxFetch,
    { refreshInterval: 2500 }
  )
  const [config, setConfig] = useState(initial)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")
  const [tab, setTab] = useState<"results" | "activity" | "history">("results")
  const logRef = useRef<HTMLPreElement>(null)
  const cap = overview.data?.capabilities
  const current = detail.data
  const busy = pending || Boolean(overview.data?.active_run_id)
  const allowed = config.kind === "audit" ? cap?.audit_ready : cap?.case_ready
  const findings = current?.state.findings || []
  const hypotheses = Object.values(current?.state.hypotheses || {})
  const refresh = () => {
    void overview.mutate()
    void history.mutate()
    void detail.mutate()
  }
  const update = <K extends keyof SandboxConfig>(key: K, value: SandboxConfig[K]) =>
    setConfig((prev) => ({ ...prev, [key]: value }))
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [current?.logs.length, runId])

  async function action(url: string, body?: SandboxConfig) {
    setPending(true)
    setError("")
    try {
      const job = await sandboxFetch<SandboxRun>(url, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      })
      setSelection(job.run_id)
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败，请重试")
    } finally {
      setPending(false)
    }
  }
  function start(e: FormEvent) {
    e.preventDefault()
    void action("/api/sandbox/runs", config)
  }
  function selectRun(id: string) {
    setSelection(id)
    setTab("results")
  }

  return (
    <div className={base.page}>
      <header className={base.header}>
        <div>
          <span className={base.eyebrow}>SANDBOX ASSESSMENT / 03</span>
          <h1>
            沙盒模拟工作台<span className={base.titleDot}>.</span>
          </h1>
          <p>面向具体项目开展仓库审计、离线模拟与证据归档。</p>
        </div>
        <div className={base.headerActions}>
          <span className={`${base.connection} ${overview.error ? base.offline : ""}`}>
            <i />
            {overview.error
              ? "连接异常"
              : !overview.data
                ? "正在连接"
                : activeRunId
                  ? "沙盒任务运行中"
                  : "服务已连接"}
          </span>
          <button className={base.iconButton} aria-label="刷新沙盒数据" onClick={refresh}>
            <RefreshCw size={17} />
          </button>
        </div>
      </header>
      {overview.error && (
        <div className={base.error} role="alert">
          沙盒 API 未连接，请在根目录启动 <code>uv run saads-api</code>。
        </div>
      )}
      {cap && (!cap.runtime_ready || !cap.model_ready) && (
        <div className={base.error} role="alert">
          {!cap.runtime_ready
            ? "沙盒审计运行环境尚未安装。请运行 uv sync --project backend/red_team/runtime --frozen --group dev。"
            : "请在根目录 .env 配置 DeepSeek 模型与密钥。"}
        </div>
      )}
      <section className={s.intro}>
        <div>
          <span className={s.tag}>SAADS SANDBOX</span>
          <h2>先提出假设，再用证据裁决。</h2>
          <p>当前支持本地仓库只读审计与离线案例生成；隔离环境执行尚未接入。</p>
        </div>
        <div className={s.roles}>
          <span>
            <Swords size={21} />
            <b>红队</b>
            <small>提出与追问</small>
          </span>
          <i>→</i>
          <span>
            <Shield size={21} />
            <b>代码团队</b>
            <small>验证与反驳</small>
          </span>
          <i>→</i>
          <span>
            <Scale size={21} />
            <b>独立裁判</b>
            <small>确认与归档</small>
          </span>
        </div>
      </section>
      <section className={base.metrics} aria-label="沙盒概览">
        {[
          {
            label: "最近任务",
            value: history.data?.length,
            note: "最近 50 次审计与案例",
            icon: GitBranch,
          },
          {
            label: "已完成",
            value: history.data?.filter((run) => run.status === "succeeded").length,
            note: "审计与离线案例",
            icon: FileSearch,
          },
          {
            label: "本次确认发现",
            value: current ? findings.length : undefined,
            note:
              current?.kind === "case" ? "离线案例不计入审计发现" : "以裁判确认结果为准",
            icon: Shield,
          },
          {
            label: "知识图谱",
            value: cap ? (cap.graph_index_ready ? "已就绪" : "待配置") : undefined,
            note: "仓库审计支持仅代码证据",
            icon: BookOpen,
          },
        ].map(({ label, value, note, icon: Icon }) => (
          <article className={base.metric} key={label}>
            <div>
              <span>{label}</span>
              <Icon size={17} />
            </div>
            <strong>{value ?? "—"}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>
      <div className={s.graphLink}>
        <span>
          {graphActive
            ? "GraphRAG 正在构建，完成后可启动测试。"
            : "在独立 GraphRAG 工作台构建和更新情报知识图谱。"}
        </span>
        <Link href="/dashboard/graphrag">
          管理情报知识图谱 <ArrowUpRight size={14} />
        </Link>
      </div>
      <div className={s.workspace}>
        <section className={base.control}>
          <div className={base.sectionHeading}>
            <div className={base.iconTile}>
              <Swords size={20} />
            </div>
            <div>
              <h2>定义测试任务</h2>
              <p>从代码审查，或从一个攻击意图开始</p>
            </div>
          </div>
          <form onSubmit={start}>
            <fieldset disabled={busy} className={base.fieldset}>
              <legend className={base.srOnly}>沙盒任务参数</legend>
              <div className={base.modeSwitch} role="group" aria-label="任务类型">
                <button
                  type="button"
                  aria-pressed={config.kind === "audit"}
                  onClick={() => update("kind", "audit")}
                >
                  仓库对抗审计
                </button>
                <button
                  type="button"
                  aria-pressed={config.kind === "case"}
                  onClick={() => update("kind", "case")}
                >
                  离线攻击案例
                </button>
              </div>
              {config.kind === "audit" ? (
                <>
                  <p className={base.modeHint}>
                    指定本地仓库，以只读代码证据推进红蓝辩论。
                  </p>
                  <label className={base.label}>
                    本地仓库目录
                    <input
                      required
                      value={config.target_repo}
                      onChange={(e) => update("target_repo", e.target.value)}
                      placeholder="/path/to/your/llm-app"
                      maxLength={2000}
                    />
                  </label>
                  <label className={base.label}>
                    授权记录
                    <input
                      required
                      value={config.authorization_ref}
                      onChange={(e) => update("authorization_ref", e.target.value)}
                      placeholder="如：自有项目审计 / 工单编号"
                      maxLength={300}
                    />
                  </label>
                  <label className={base.label}>
                    审计目标
                    <textarea
                      className={s.textarea}
                      value={config.goal}
                      onChange={(e) => update("goal", e.target.value)}
                      rows={3}
                      maxLength={3000}
                    />
                  </label>
                  <div className={base.formGrid}>
                    <label className={base.label}>
                      每个假设的辩论上限
                      <input
                        type="number"
                        min={1}
                        max={12}
                        required
                        value={config.max_rounds}
                        onChange={(e) => update("max_rounds", Number(e.target.value))}
                      />
                    </label>
                    <label className={base.label}>
                      智能体调用上限
                      <input
                        type="number"
                        min={5}
                        max={200}
                        required
                        value={config.max_agent_calls}
                        onChange={(e) =>
                          update("max_agent_calls", Number(e.target.value))
                        }
                      />
                    </label>
                  </div>
                  <label className={base.label}>
                    估算费用上限（USD）
                    <input
                      type="number"
                      required
                      min={0.1}
                      max={100}
                      step={0.1}
                      value={config.max_cost_usd}
                      onChange={(e) => update("max_cost_usd", Number(e.target.value))}
                    />
                  </label>
                  <p className={s.budgetNote}>
                    按 SDK 回报估算，调用结束后检查；实际费用以供应商账单为准。
                  </p>
                  <label className={s.check}>
                    <input
                      type="checkbox"
                      checked={config.use_graphrag}
                      onChange={(e) => update("use_graphrag", e.target.checked)}
                    />
                    使用知识图谱辅助取证
                  </label>
                </>
              ) : (
                <>
                  <p className={base.modeHint}>
                    生成结构化案例与内置模拟目标的 Python 脚本。
                  </p>
                  <div className={s.templates}>
                    {templates.map(([label, request]) => (
                      <button
                        type="button"
                        key={label}
                        onClick={() => update("request", request!)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <label className={base.label}>
                    测试意图
                    <textarea
                      required
                      className={s.textarea}
                      rows={7}
                      value={config.request}
                      onChange={(e) => update("request", e.target.value)}
                      maxLength={5000}
                      placeholder="描述你希望验证的攻击场景和安全边界…"
                    />
                  </label>
                  <p className={s.note}>
                    支持提示词注入、长对话越界、工具劫持。生成脚本仅针对内置离线模拟目标。
                  </p>
                </>
              )}
              {cap && (!cap.graph_index_ready || !cap.graph_credentials_ready) && (
                <p className={s.notice}>
                  {config.kind === "audit"
                    ? "知识图谱尚未就绪；本次审计可使用仓库代码证据。"
                    : "案例生成需要 GraphRAG 索引。请先前往 GraphRAG 工作台构建图谱。"}
                </p>
              )}
              <button
                className={base.start}
                type="submit"
                disabled={busy || !allowed || Boolean(overview.error)}
              >
                <Play size={14} fill="currentColor" />
                {busy
                  ? "已有任务运行中…"
                  : config.kind === "audit"
                    ? "开始对抗审计"
                    : "生成离线案例"}
                <ArrowUpRight size={16} />
              </button>
            </fieldset>
          </form>
          <div className={s.boundary}>
            <Shield size={14} />
            <span>目标仓库只读 · 测试草稿写入任务产物目录</span>
          </div>
        </section>
        <div className={s.right}>
          <section className={task.runPanel}>
            <div className={task.runHeading}>
              <div>
                <span className={base.eyebrow}>CURRENT ASSESSMENT</span>
                <h2>{current?.title || "等待新任务"}</h2>
              </div>
              <span className={task.status}>
                {current ? statusLabels[current.status] || current.status : "尚未开始"}
              </span>
            </div>
            <div className={task.runId}>
              {runId || "启动任务后可随时离开页面，进度将保存在后端。"}
            </div>
            <div className={task.steps}>
              {(current?.kind === "case"
                ? ["generating_case"]
                : [
                    "profiling",
                    "discovery",
                    "debating",
                    "adjudicating",
                    "generating_tests",
                  ]
              ).map((phase, index) => (
                <span
                  className={current?.phase === phase ? task.activeStep : ""}
                  key={phase}
                >
                  <i>{String(index + 1).padStart(2, "0")}</i>
                  {phases[phase]}
                </span>
              ))}
            </div>
            <div className={task.runStats}>
              <span>
                当前阶段
                <strong>{current ? phases[current.phase] || current.phase : "—"}</strong>
              </span>
              <span>
                调用次数
                <strong>{current?.state.agent_calls_used ?? "—"}</strong>
              </span>
              <span>
                SDK 费用估算
                <strong>
                  {current?.state.cost_usd_used != null
                    ? `$${current.state.cost_usd_used.toFixed(3)}`
                    : "—"}
                </strong>
              </span>
              <span>
                待检验假设
                <strong>
                  {current
                    ? hypotheses.filter((h) =>
                        ["proposed", "debating"].includes(h.status)
                      ).length
                    : "—"}
                </strong>
              </span>
            </div>
            <div className={task.actions}>
              <button onClick={() => setSelection(null)} type="button">
                跟随最新任务 ↗
              </button>
              {current && overview.data?.active_run_id === runId && (
                <button
                  disabled={pending || current.status === "cancelling"}
                  onClick={() => void action(`/api/sandbox/runs/${runId}/stop`)}
                >
                  <CircleStop size={14} />
                  停止任务
                </button>
              )}
              {current?.can_resume && (
                <button
                  disabled={busy}
                  onClick={() => void action(`/api/sandbox/runs/${runId}/resume`)}
                >
                  <RotateCcw size={14} />
                  从检查点恢复
                </button>
              )}
            </div>
            {current?.can_resume && (
              <p className={s.note}>
                恢复时追加原任务的一份调用与费用预算，并校验目标仓库快照。
              </p>
            )}
            {current?.error && <p className={s.notice}>{current.error}</p>}
            {detail.error && (
              <p className={base.error} role="alert">
                任务读取失败：{detail.error.message}
              </p>
            )}
            {error && (
              <p className={base.error} role="alert">
                {error}
              </p>
            )}
          </section>
          <section className={base.results}>
            <div className={base.resultsHeader}>
              <div className={base.tabs} role="tablist" aria-label="沙盒任务视图">
                {(
                  [
                    ["results", "发现与产物"],
                    ["activity", "运行记录"],
                    ["history", "任务历史"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    role="tab"
                    aria-selected={tab === id}
                    onClick={() => setTab(id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            {tab === "results" && (
              <div role="tabpanel" aria-label="发现与产物">
                {!current ? (
                  <div className={base.empty}>
                    <FileSearch size={30} />
                    <h3>让证据成为结论的起点</h3>
                    <p>启动任务后，在这里查看确认发现、审计报告与测试草稿。</p>
                  </div>
                ) : (
                  <>
                    <div className={s.findingsHeader}>
                      <strong>
                        {current.kind === "case"
                          ? "离线案例产物"
                          : `确认发现 · ${findings.length}`}
                      </strong>
                      <span>
                        {current.state.graph_enabled
                          ? "代码 + 图谱证据"
                          : current.kind === "audit"
                            ? "仓库代码证据"
                            : "GraphRAG 证据"}
                      </span>
                    </div>
                    {findings.map((f) => (
                      <details className={s.finding} key={f.finding_id}>
                        <summary>
                          <span
                            className={`${s.severity} ${["critical", "high"].includes(f.severity) ? s.high : ""}`}
                          >
                            {f.severity}
                          </span>
                          <strong>{f.root_cause}</strong>
                        </summary>
                        <div>
                          <p>
                            <b>影响</b>
                            {f.impact}
                          </p>
                          <p>
                            <b>修复建议</b>
                            {f.remediation}
                          </p>
                          <p>
                            <b>裁判依据</b>
                            {f.judge_rationale.join("\n")}
                          </p>
                          <p className={s.evidence}>
                            {[...f.code_evidence_ids, ...f.graph_evidence_ids].join(
                              " · "
                            )}
                          </p>
                        </div>
                      </details>
                    ))}
                    {!findings.length && current.kind === "audit" && (
                      <p className={s.note}>
                        当前没有已确认的发现。只有完成审计后，才能结合报告判断覆盖范围。
                      </p>
                    )}
                    {current.state.threat_surfaces?.length ? (
                      <details className={s.surfaces}>
                        <summary>
                          已识别 {current.state.threat_surfaces.length} 个威胁面
                        </summary>
                        {current.state.threat_surfaces.map((surface) => (
                          <p key={surface.surface_id}>
                            <span>{surface.kind}</span>
                            {surface.name}
                          </p>
                        ))}
                      </details>
                    ) : null}
                    <TaskArtifacts key={current.run_id} run={current} />
                  </>
                )}
              </div>
            )}
            {tab === "activity" && (
              <div role="tabpanel" aria-label="运行记录">
                <div className={task.logLabel}>进程日志 · 最近 120 行</div>
                <pre ref={logRef} className={task.logs}>
                  {current?.logs.join("\n") || "等待运行事件…"}
                </pre>
                {current?.events.map((event, i) => (
                  <details className={task.event} key={i}>
                    <summary>
                      {event.source === "debate_rounds.jsonl" ? "辩论记录" : "审计事件"} ·{" "}
                      {String(event.data.event || event.data.hypothesis_id || i + 1)}
                    </summary>
                    <pre>{JSON.stringify(event.data, null, 2)}</pre>
                  </details>
                ))}
              </div>
            )}
            {tab === "history" && (
              <div role="tabpanel" aria-label="任务历史">
                {history.error ? (
                  <p className={base.error} role="alert">
                    任务历史读取失败
                  </p>
                ) : !history.data?.length ? (
                  <p className={base.empty}>还没有沙盒任务。</p>
                ) : (
                  history.data.map((run) => (
                    <button
                      className={`${base.historyRow} ${runId === run.run_id ? base.selected : ""}`}
                      key={run.run_id}
                      onClick={() => selectRun(run.run_id)}
                    >
                      <span>
                        <strong>{run.title}</strong>
                        <small>
                          {new Date(run.created_at).toLocaleString("zh-CN")} ·{" "}
                          {run.kind === "audit" ? "仓库审计" : "离线案例"}
                        </small>
                      </span>
                      <span className={base.runBadge}>
                        {statusLabels[run.status] || run.status}
                      </span>
                      <ArrowUpRight size={16} />
                    </button>
                  ))
                )}
              </div>
            )}
          </section>
        </div>
      </div>
      <footer className={base.footer}>
        SAADS SANDBOX<span>假设 · 反驳 · 裁决 · 验证</span>
      </footer>
    </div>
  )
}
