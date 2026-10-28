"use client"

import { useState, useEffect, useRef, type FormEvent } from "react"
import useSWR from "swr"
import Link from "next/link"
import {
  Activity,
  ArrowUpRight,
  Database,
  Download,
  Globe2,
  Play,
  Radar,
  RefreshCw,
  Search,
  ShieldCheck,
  Terminal,
  Layers3,
} from "lucide-react"
import {
  intelFetch,
  exportIntelItems,
  useIntelOverview,
  type IntelRun,
  type IntelItem,
  type IntelDetail,
  type IntelItemDetail,
} from "@/lib/api/intel"
import styles from "./IntelDashboard.module.css"

const labels: Record<string, string> = {
  running: "采集中",
  succeeded: "已完成",
  partial_success: "部分完成",
  failed: "失败",
  interrupted: "已中断",
}
const contentScopeLabels: Record<string, string> = {
  issue_body: "GitHub Issue 正文（不含评论）",
  post_text: "HN 帖子或评论文本",
  title_only: "仅标题（未抓取外链正文）",
  search_excerpt: "论坛搜索摘录（非帖子全文）",
  rss_entry: "RSS 条目文本（非完整讨论串）",
}
const date = (value?: string | null) =>
  value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—"
export function safeSourceUrl(value?: string | null) {
  try {
    const url = new URL(value || "")
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}

function RawTextDetails({ itemId }: { itemId: string }) {
  const [open, setOpen] = useState(false)
  const content = useSWR<IntelItemDetail, Error>(
    open ? `/api/intel/items/${encodeURIComponent(itemId)}` : null,
    intelFetch
  )
  return (
    <details onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary>查看已采集原文（raw text）</summary>
      {content.error ? (
        <p role="alert">原文加载失败：{content.error.message}</p>
      ) : !content.data ? (
        <p>正在读取原文…</p>
      ) : content.data.raw_text ? (
        <>
          <small>
            {contentScopeLabels[content.data.metadata?.content_scope || ""] ||
              (content.data.source_name === "arxiv_api"
                ? "论文完整摘要"
                : "来源原始文本")}
            {" · "}
            {content.data.raw_text.length.toLocaleString()} 字符
          </small>
          {content.data.metadata?.raw_text_check?.status ===
            "source_ends_with_ellipsis" && <p>已核对来源：来源文本本身以省略号结尾。</p>}
          <pre className={styles.rawText}>{content.data.raw_text}</pre>
        </>
      ) : (
        <p>这条情报尚未保存原文。</p>
      )}
    </details>
  )
}

export function IntelDashboard() {
  const overview = useIntelOverview()
  const history = useSWR<IntelRun[], Error>("/api/intel/runs", intelFetch, {
    refreshInterval: 4000,
  })
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const runId =
    selectedRun ??
    overview.data?.active?.run_id ??
    history.data?.[0]?.run_id ??
    overview.data?.latest?.run_id
  const detail = useSWR<IntelDetail, Error>(
    runId ? `/api/intel/runs/${encodeURIComponent(runId)}` : null,
    intelFetch,
    { refreshInterval: 2500 }
  )
  const logRef = useRef<HTMLDivElement>(null)
  const [followLogs, setFollowLogs] = useState(true)
  const lastEvent = detail.data?.events.at(-1)
  useEffect(() => {
    if (followLogs && logRef.current)
      logRef.current.scrollTop = logRef.current.scrollHeight
  }, [lastEvent?.ts, lastEvent?.message, runId, followLogs])
  const [mode, setMode] = useState<"full" | "incremental">("incremental")
  const [focus, setFocus] = useState("")
  const [windowDays, setWindowDays] = useState(1)
  const [rounds, setRounds] = useState(6)
  const [calls, setCalls] = useState(40)
  const [submitting, setSubmitting] = useState(false)
  const [actionError, setActionError] = useState("")
  const [search, setSearch] = useState("")
  const [query, setQuery] = useState("")
  const [source, setSource] = useState("")
  const [topic, setTopic] = useState("")
  const [onlyRun, setOnlyRun] = useState(false)
  const [tab, setTab] = useState<"items" | "history">("items")
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState("")
  const params = new URLSearchParams({
    text: query,
    source,
    topic,
    limit: "100",
    run_id: onlyRun ? runId || "" : "",
  })
  const items = useSWR<IntelItem[], Error>(`/api/intel/items?${params}`, intelFetch, {
    refreshInterval: 6000,
  })
  const data = overview.data
  const busy = submitting || Boolean(data?.active)
  const covered = Object.values(data?.coverage || {}).filter((n) => n > 0).length
  const refresh = () => {
    void overview.mutate()
    void history.mutate()
    void items.mutate()
    void detail.mutate()
  }

  async function downloadAll() {
    setExporting(true)
    setExportError("")
    try {
      const { blob, filename } = await exportIntelItems()
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      link.remove()
      // Keep the blob alive until the browser has started reading the download.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "导出失败，请稍后重试。")
    } finally {
      setExporting(false)
    }
  }

  async function start(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setActionError("")
    try {
      const run = await intelFetch<IntelRun>("/api/intel/runs", {
        method: "POST",
        body: JSON.stringify({
          mode,
          focus,
          window_days: windowDays,
          max_rounds: rounds,
          max_api_calls: calls,
        }),
      })
      setSelectedRun(run.run_id)
      refresh()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "采集启动失败")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>SECURITY INTELLIGENCE / 01</span>
          <h1>
            情报采集工作台<span className={styles.titleDot}>.</span>
          </h1>
          <p>从分散的安全信号，到可追溯的大模型威胁情报。</p>
        </div>
        <div className={styles.headerActions}>
          <span
            className={`${styles.connection} ${overview.error ? styles.offline : ""}`}
          >
            <i />
            {overview.error
              ? "连接异常"
              : !data
                ? "正在连接"
                : data.active
                  ? "智能体采集中"
                  : "服务已连接"}
          </span>
          <button
            type="button"
            className={styles.iconButton}
            aria-label="刷新数据"
            onClick={refresh}
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </header>
      {overview.error && (
        <div className={styles.error} role="alert">
          无法连接情报服务。请在项目根目录运行 <code>uv run intel-api</code>，然后刷新。
          {data ? " 当前保留上次加载的数据。" : ""}
        </div>
      )}
      <section className={styles.metrics} aria-label="情报概览">
        {[
          {
            label: "累计入库情报",
            value: data?.item_count,
            icon: Database,
            note: "历史情报去重统计",
          },
          {
            label: "已持久化任务",
            value: data?.run_count,
            icon: Layers3,
            note: "全量与增量采集",
          },
          {
            label: "本次核心话题",
            value: data ? `${covered} / ${Object.keys(data.coverage).length}` : undefined,
            icon: ShieldCheck,
            note: "最近一次任务 · 按标注统计",
          },
          {
            label: "已产出来源",
            value: data?.sources.length,
            icon: Globe2,
            note: "历史库中实际出现的来源",
          },
        ].map(({ label, value, icon: Icon, note }) => (
          <article key={label} className={styles.metric}>
            <div>
              <span>{label}</span>
              <Icon size={17} />
            </div>
            <strong>{value ?? "—"}</strong>
            <small>{note}</small>
          </article>
        ))}
      </section>
      <div className={styles.workspace}>
        <section className={styles.control}>
          <div className={styles.sectionHeading}>
            <div className={styles.iconTile}>
              <Radar size={20} />
            </div>
            <div>
              <h2>发起一次探索</h2>
              <p>设定目标，让智能体寻找线索</p>
            </div>
          </div>
          <form onSubmit={start}>
            <fieldset disabled={busy} className={styles.fieldset}>
              <legend className={styles.srOnly}>采集参数</legend>
              <div className={styles.modeSwitch} role="group" aria-label="采集模式">
                <button
                  type="button"
                  aria-pressed={mode === "incremental"}
                  onClick={() => setMode("incremental")}
                >
                  增量追踪
                </button>
                <button
                  type="button"
                  aria-pressed={mode === "full"}
                  onClick={() => setMode("full")}
                >
                  全量探索
                </button>
              </div>
              <p className={styles.modeHint}>
                {mode === "incremental"
                  ? "沿历史检查点回看，发现新的漏洞与研究。"
                  : "围绕 18 个核心安全话题，补齐覆盖缺口。"}
              </p>
              {mode === "incremental" && (
                <>
                  <label className={styles.label}>
                    关注方向 <span>可选</span>
                    <input
                      value={focus}
                      maxLength={300}
                      onChange={(e) => setFocus(e.target.value)}
                      placeholder="例如 prompt injection、MCP 安全"
                    />
                  </label>
                  <label className={styles.label}>
                    回看天数
                    <input
                      type="number"
                      required
                      min={1}
                      max={365}
                      value={windowDays}
                      onChange={(e) => setWindowDays(Number(e.target.value))}
                    />
                  </label>
                </>
              )}
              <div className={styles.formGrid}>
                <label className={styles.label}>
                  最大轮次
                  <input
                    type="number"
                    required
                    min={1}
                    value={rounds}
                    onChange={(e) => setRounds(Number(e.target.value))}
                  />
                </label>
                <label className={styles.label}>
                  API 调用预算
                  <input
                    type="number"
                    required
                    min={1}
                    value={calls}
                    onChange={(e) => setCalls(Number(e.target.value))}
                  />
                </label>
              </div>
              <button
                className={styles.start}
                disabled={busy || !data || Boolean(overview.error)}
                type="submit"
              >
                <Play size={15} fill="currentColor" />
                {busy ? "采集任务运行中…" : "开始采集"}
                <ArrowUpRight size={17} />
              </button>
            </fieldset>
            {actionError && (
              <p className={styles.error} role="alert">
                {actionError}
              </p>
            )}
          </form>
          <div className={styles.sources}>
            <span>检索来源</span>
            <div>
              {[
                "NVD",
                "arXiv",
                "CISA KEV",
                "OSV",
                "Hacker News",
                "HF Forum",
                "GitHub Issues",
                "Reddit RSS",
              ].map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            <small>GitHub Issues、Reddit RSS 按配置启用；OSV 用于包与实体定向确认</small>
          </div>
        </section>
        <section className={styles.tracePanel}>
          <div className={styles.traceHeader}>
            <div>
              <Terminal size={17} />
              <h2>运行观察</h2>
              <span className={styles.traceStatus}>
                {detail.data
                  ? labels[detail.data.status] || detail.data.status
                  : "等待任务"}
              </span>
            </div>
            <button type="button" onClick={() => setSelectedRun(null)}>
              跟随最新任务 ↗
            </button>
          </div>
          <div className={styles.runMeta}>
            <span title={runId}>{runId || "尚未选择任务"}</span>
            <span>
              {detail.data?.summary.rounds ?? "—"} 轮 ·{" "}
              {detail.data?.metrics.api_calls_used ?? "—"} 次调用
            </span>
          </div>
          <div ref={logRef} className={styles.log} tabIndex={0} aria-label="运行日志">
            {detail.error ? (
              <p role="alert">日志加载失败：{detail.error.message}</p>
            ) : detail.isLoading ? (
              <p>正在加载任务记录…</p>
            ) : detail.data?.events.length ? (
              detail.data.events.map((event, i) => (
                <div className={styles.logLine} key={`${i}-${event.ts}`}>
                  <time>{event.ts?.slice(11, 19)}</time>
                  <span>
                    <b>{event.event}</b>
                    {event.message}
                  </span>
                </div>
              ))
            ) : (
              <div className={styles.logEmpty}>
                <Activity size={30} />
                <strong>{runId ? "等待新的运行事件" : "每一条情报，都有迹可循"}</strong>
                <p>
                  {runId
                    ? "该任务尚无可回放日志，采集时会自动更新。"
                    : "发起采集后，在这里查看检索、分析与决策过程。"}
                </p>
              </div>
            )}
          </div>
          <div className={styles.traceFooter}>
            <span>
              {detail.data?.error ||
                (detail.data?.summary.stop_reason
                  ? `结束原因：${detail.data.summary.stop_reason}`
                  : "自动刷新 · 显示最近 300 条事件")}
            </span>
            <label className={styles.liveIndicator}>
              <input
                type="checkbox"
                checked={followLogs}
                onChange={(e) => setFollowLogs(e.target.checked)}
              />
              跟随日志
            </label>
          </div>
          {!!detail.data?.errors.length && (
            <details className={styles.runErrors}>
              <summary>本次任务有 {detail.data.errors.length} 条运行告警</summary>
              {detail.data.errors.map((error, i) => (
                <p key={i}>
                  {error.error_type} · {error.message}
                </p>
              ))}
            </details>
          )}
        </section>
      </div>
      <section className={styles.results}>
        <div className={styles.resultsHeader}>
          <div className={styles.tabs} role="tablist" aria-label="情报与历史">
            <button
              role="tab"
              aria-selected={tab === "items"}
              onClick={() => setTab("items")}
            >
              情报库 <span>{data?.item_count ?? "—"}</span>
            </button>
            <button
              role="tab"
              aria-selected={tab === "history"}
              onClick={() => setTab("history")}
            >
              运行历史
            </button>
          </div>
          <div className={styles.resultActions}>
            <span className={styles.resultNote}>
              {tab === "items"
                ? "全库 JSON · 含完整原文 · 不受筛选影响"
                : "最近 50 次任务 · 点击回放日志"}
            </span>
            {tab === "items" && (
              <button
                type="button"
                className={styles.downloadButton}
                onClick={downloadAll}
                disabled={exporting}
                aria-busy={exporting}
                title="下载全库 JSON，包含完整摘要、raw_text、元数据与运行来源，不受筛选条件影响"
              >
                <Download size={15} aria-hidden="true" />
                {exporting ? "正在准备下载…" : "下载全部完整情报"}
              </button>
            )}
          </div>
        </div>
        {tab === "items" ? (
          <div role="tabpanel" aria-label="情报库">
            {exportError && (
              <p role="alert" className={styles.exportError}>
                下载失败：{exportError}
              </p>
            )}
            <div className={styles.filters}>
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  setQuery(search)
                }}
                className={styles.search}
              >
                <Search size={17} />
                <input
                  aria-label="搜索情报"
                  placeholder="搜索标题、摘要或编号…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  maxLength={200}
                />
                <button type="submit">搜索</button>
              </form>
              <select
                aria-label="筛选来源"
                value={source}
                onChange={(e) => setSource(e.target.value)}
              >
                <option value="">全部来源</option>
                {data?.sources.map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
              <select
                aria-label="筛选话题"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
              >
                <option value="">全部安全话题</option>
                {data?.topics.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={onlyRun}
                  disabled={!runId}
                  onChange={(e) => setOnlyRun(e.target.checked)}
                />
                所选任务
              </label>
            </div>
            {items.error ? (
              <div role="alert" className={styles.empty}>
                情报加载失败：{items.error.message}
              </div>
            ) : items.isLoading ? (
              <div className={styles.empty}>正在读取情报库…</div>
            ) : !items.data?.length ? (
              <div className={styles.empty}>
                <Database size={27} />
                <h3>
                  {query || source || topic || onlyRun
                    ? "没有匹配的情报"
                    : "等待第一批安全情报"}
                </h3>
                <p>
                  {query || source || topic || onlyRun
                    ? "调整搜索词或筛选条件后重试。"
                    : "发起采集后，结果将在这里自动汇集。"}
                </p>
              </div>
            ) : (
              <div className={styles.itemList}>
                {items.data.map((item) => (
                  <article className={styles.intelItem} key={item.item_id}>
                    <div className={styles.itemSource}>
                      <span>{item.source_name}</span>
                      <small>{item.item_id}</small>
                    </div>
                    <div className={styles.itemBody}>
                      <h3>
                        {safeSourceUrl(item.source_uri) ? (
                          <a
                            href={safeSourceUrl(item.source_uri)}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {item.title || item.item_id}
                            <ArrowUpRight size={15} />
                          </a>
                        ) : (
                          item.title || item.item_id
                        )}
                      </h3>
                      {item.summary && (
                        <details>
                          <summary>
                            {item.summary.slice(0, 150)}
                            {item.summary.length > 150 ? "…" : ""}
                          </summary>
                          <p>{item.summary}</p>
                        </details>
                      )}
                      <RawTextDetails itemId={item.item_id} />
                      <Link
                        className={styles.pentestLink}
                        href={`/dashboard/wp12?${new URLSearchParams({ intel_id: item.item_id })}`}
                      >
                        生成漏洞测试脚本 <ArrowUpRight size={12} />
                      </Link>
                      <div className={styles.tags}>
                        {item.topics?.map((t) => (
                          <button key={t} onClick={() => setTopic(t)}>
                            {t}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className={styles.itemScore}>
                      <strong>{(item.relevance_score ?? 0).toFixed(2)}</strong>
                      <span>相关性</span>
                      <time>
                        {item.published_at
                          ? date(item.published_at).split(" ")[0]
                          : "日期未知"}
                      </time>
                    </div>
                  </article>
                ))}
                <p className={styles.listFooter}>
                  当前显示 {items.data.length} 条
                  {items.data.length === 100 ? "（最多 100 条，请通过筛选缩小范围）" : ""}
                </p>
              </div>
            )}
          </div>
        ) : (
          <div role="tabpanel" aria-label="运行历史" className={styles.history}>
            {history.error ? (
              <p role="alert">运行历史加载失败：{history.error.message}</p>
            ) : history.isLoading ? (
              <p className={styles.empty}>正在读取运行历史…</p>
            ) : !history.data?.length ? (
              <p className={styles.empty}>还没有采集任务。</p>
            ) : (
              history.data.map((run) => (
                <button
                  key={run.run_id}
                  className={`${styles.historyRow} ${runId === run.run_id ? styles.selected : ""}`}
                  onClick={() => setSelectedRun(run.run_id)}
                >
                  <span>
                    <strong>
                      {run.stop_reason === "csv_import"
                        ? "历史情报导入"
                        : ["full", "bootstrap"].includes(run.run_mode)
                          ? "全量探索"
                          : "增量追踪"}
                    </strong>
                    <small>{run.run_id}</small>
                  </span>
                  <span>{date(run.saved_at)}</span>
                  <span>{run.item_count} 条情报</span>
                  <span className={styles.runBadge}>
                    {labels[run.status] || run.status}
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              ))
            )}
          </div>
        )}
      </section>
      <section className={styles.coverage}>
        <div>
          <span className={styles.eyebrow}>TOPIC COVERAGE</span>
          <h2>核心话题分布</h2>
          <p>最近一次任务的情报标注，不代表配额达标率。</p>
        </div>
        <div className={styles.coverageGrid}>
          {Object.entries(data?.coverage || {}).map(([name, count]) => (
            <button
              key={name}
              className={count ? styles.covered : ""}
              onClick={() => {
                setTopic(name)
                setTab("items")
                setOnlyRun(false)
              }}
            >
              <span>{name}</span>
              <b>{count}</b>
            </button>
          ))}
          {!data && <p>连接服务后展示话题覆盖。</p>}
        </div>
      </section>
      <footer className={styles.footer}>
        LLM SECURITY INTELLIGENCE<span>检索 · 过滤 · 分析 · 沉淀</span>
      </footer>
    </div>
  )
}
