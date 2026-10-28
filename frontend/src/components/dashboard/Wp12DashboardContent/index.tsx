"use client"

import Link from "next/link"
import { useEffect, useState, type FormEvent } from "react"
import useSWR from "swr"
import { ArrowUpRight, Download, FileCode2, Play, Search, Square } from "lucide-react"
import { intelFetch, type IntelItem, type IntelItemDetail } from "@/lib/api/intel"
import {
  isPentestActive,
  pentestArtifactUrl,
  PENTEST_STATUS,
  usePentestOverview,
  type PentestDetail,
  type PentestRun,
  type Protocol,
} from "@/lib/api/pentest"
import base from "../IntelDashboard/IntelDashboard.module.css"
import s from "./Wp12DashboardContent.module.css"

function sourceUrl(value?: string | null) {
  try {
    const url = new URL(value || "")
    return ["http:", "https:"].includes(url.protocol) ? url.href : undefined
  } catch {
    return undefined
  }
}

export function Wp12DashboardContent() {
  const overview = usePentestOverview()
  const [query, setQuery] = useState("")
  const [search, setSearch] = useState("")
  const [intelId, setIntelId] = useState("")
  const [runId, setRunId] = useState("")
  const [focus, setFocus] = useState("")
  const [protocol, setProtocol] = useState<Protocol>("auto")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")
  useEffect(() => {
    setIntelId(new URLSearchParams(window.location.search).get("intel_id") || "")
  }, [])
  const items = useSWR<IntelItem[], Error>(
    `/api/intel/items?${new URLSearchParams({ text: search, limit: "50" })}`,
    intelFetch
  )
  const selected = useSWR<IntelItemDetail, Error>(
    intelId ? `/api/intel/items/${encodeURIComponent(intelId)}` : null,
    intelFetch
  )
  const history = useSWR<PentestRun[], Error>("/api/pentest/runs", intelFetch, {
    refreshInterval: 4000,
  })
  const currentId = runId || overview.data?.active?.run_id || history.data?.[0]?.run_id
  const detail = useSWR<PentestDetail, Error>(
    currentId ? `/api/pentest/runs/${encodeURIComponent(currentId)}` : null,
    intelFetch,
    { refreshInterval: (data) => (isPentestActive(data) ? 2000 : 0) }
  )
  const run = detail.data
  const active = overview.data?.active
  const unavailable = !overview.data?.llm_available || Boolean(overview.error)

  async function generate(event: FormEvent) {
    event.preventDefault()
    if (!selected.data || unavailable || active) return
    setError("")
    setSubmitting(true)
    try {
      const job = await intelFetch<PentestRun>("/api/pentest/runs", {
        method: "POST",
        body: JSON.stringify({ intel_id: intelId, focus, protocol }),
      })
      setRunId(job.run_id)
      await Promise.all([overview.mutate(), history.mutate()])
    } catch (e) {
      setError(e instanceof Error ? e.message : "生成请求失败")
    } finally {
      setSubmitting(false)
    }
  }
  async function stop() {
    if (!active) return
    setSubmitting(true)
    setError("")
    try {
      await intelFetch(`/api/pentest/runs/${active.run_id}/stop`, { method: "POST" })
      await Promise.all([overview.mutate(), detail.mutate()])
    } catch (e) {
      setError(e instanceof Error ? e.message : "停止失败")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={base.page}>
      <header className={base.header}>
        <div>
          <span className={base.eyebrow}>INTELLIGENCE TO DETECTION / 02</span>
          <h1>
            渗透测试工作台<span className={base.titleDot}>.</span>
          </h1>
          <p>选择已采集情报，生成对应的漏洞测试脚本、判定规则与来源说明。</p>
        </div>
        <span className={`${s.badge} ${unavailable ? s.warning : ""}`}>
          {overview.error
            ? "后端未连接"
            : !overview.data
              ? "正在连接"
              : unavailable
                ? "模型未配置"
                : `模型 · ${overview.data.model}`}
        </span>
      </header>
      <div className={s.topline}>
        <span>
          初版 · HTTP / 聊天接口 · {overview.data?.script_count ?? "—"} 份脚本（最近 50
          次任务）
        </span>
        <div>
          <Link href="/docs/pentest-sandbox-design">
            架构与契约 <ArrowUpRight size={13} />
          </Link>
          <Link href="/dashboard/wp13">
            沙盒模拟工作台 <ArrowUpRight size={13} />
          </Link>
        </div>
      </div>
      {overview.error && (
        <p role="alert" className={s.error}>
          {overview.error.message}
        </p>
      )}
      {overview.data && !overview.data.llm_available && (
        <p role="alert" className={s.error}>
          配置现有模型凭据并重启后端后，即可生成脚本。
        </p>
      )}
      <div className={s.workspace}>
        <aside className={s.library} aria-label="选择情报">
          <div className={s.sectionTop}>
            <h2>01 / 选择情报</h2>
            <Link href="/dashboard/wp11">情报库 ↗</Link>
          </div>
          <form
            className={s.search}
            onSubmit={(e) => {
              e.preventDefault()
              setSearch(query)
            }}
          >
            <input
              aria-label="搜索情报"
              placeholder="搜索标题、漏洞或机制"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button type="submit" aria-label="搜索">
              <Search size={16} />
            </button>
          </form>
          {items.error ? (
            <p role="alert" className={s.error}>
              情报读取失败：{items.error.message}
            </p>
          ) : items.isLoading ? (
            <p className={s.empty}>正在读取情报库…</p>
          ) : !items.data?.length ? (
            <p className={s.empty}>没有匹配的情报。调整搜索词，或先到情报库采集。</p>
          ) : (
            <div className={s.items}>
              {items.data.map((item) => (
                <button
                  key={item.item_id}
                  type="button"
                  className={`${s.item} ${item.item_id === intelId ? s.selected : ""}`}
                  aria-pressed={item.item_id === intelId}
                  onClick={() => setIntelId(item.item_id)}
                >
                  <span>{item.source_name}</span>
                  <strong>{item.title || item.item_id}</strong>
                  <small>{item.item_id}</small>
                </button>
              ))}
            </div>
          )}
          <p className={s.hint}>最多显示 50 条；用搜索缩小范围。</p>
        </aside>
        <main className={s.main}>
          <section className={s.card} aria-labelledby="generation-title">
            <div className={s.sectionTop}>
              <h2 id="generation-title">02 / 生成检测脚本</h2>
              <FileCode2 size={19} />
            </div>
            {selected.error ? (
              <p role="alert" className={s.error}>
                {selected.error.message}
              </p>
            ) : selected.isLoading ? (
              <p className={s.empty}>正在读取所选情报…</p>
            ) : selected.data ? (
              <div className={s.source}>
                <span className={s.kicker}>
                  {selected.data.source_name} · {selected.data.item_id}
                </span>
                <h3>{selected.data.title}</h3>
                <p>{selected.data.summary || "该情报无摘要，将使用原文分析。"}</p>
                <details>
                  <summary>查看采集原文</summary>
                  <pre className={s.raw}>{selected.data.raw_text || "未采集原文"}</pre>
                </details>
                {sourceUrl(selected.data.source_uri) && (
                  <a
                    href={sourceUrl(selected.data.source_uri)}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    查看来源 ↗
                  </a>
                )}
              </div>
            ) : (
              <p className={s.empty}>
                从左侧选择一条情报。智能体将依据该条目的摘要和原文设计测试。
              </p>
            )}
            <form onSubmit={generate}>
              <div className={s.fields}>
                <label>
                  测试重点（可选）
                  <textarea
                    maxLength={1500}
                    value={focus}
                    onChange={(e) => setFocus(e.target.value)}
                    placeholder="例如：检测不可信文档是否诱导模型泄漏系统提示中的合成秘密"
                    rows={3}
                  />
                </label>
                <label>
                  接口类型
                  <select
                    value={protocol}
                    onChange={(e) => setProtocol(e.target.value as Protocol)}
                  >
                    <option value="auto">根据情报判断</option>
                    <option value="http">HTTP 接口</option>
                    <option value="chat">聊天接口</option>
                  </select>
                </label>
              </div>
              <div className={s.actions}>
                <button
                  className={s.primary}
                  type="submit"
                  disabled={
                    !selected.data ||
                    Boolean(selected.error) ||
                    unavailable ||
                    Boolean(active) ||
                    submitting
                  }
                >
                  <Play size={15} />
                  {submitting ? "正在提交…" : "生成漏洞测试脚本"}
                </button>
                {active && (
                  <button
                    type="button"
                    onClick={stop}
                    disabled={submitting || active.status === "cancelling"}
                    className={s.secondary}
                  >
                    <Square size={13} />
                    停止生成
                  </button>
                )}
                {active && (
                  <button
                    type="button"
                    className={s.textButton}
                    onClick={() => setRunId(active.run_id)}
                  >
                    查看运行任务
                  </button>
                )}
              </div>
              <p className={s.hint}>
                生成约需数分钟。输出 Python
                脚本和说明，默认预览请求；目标地址与凭据在使用脚本时配置。
              </p>
              {error && (
                <p role="alert" className={s.error}>
                  {error}
                </p>
              )}
            </form>
          </section>
          <section
            className={s.card}
            aria-labelledby="result-title"
            aria-busy={isPentestActive(run)}
          >
            <div className={s.sectionTop}>
              <h2 id="result-title">03 / 生成结果</h2>
              {run && <span className={s.badge}>{PENTEST_STATUS[run.status]}</span>}
            </div>
            {detail.error ? (
              <p role="alert" className={s.error}>
                {detail.error.message}
              </p>
            ) : !run ? (
              <p className={s.empty}>
                {detail.isLoading
                  ? "正在读取任务…"
                  : "生成后可查看分析、引用原文、测试请求和完整脚本。"}
              </p>
            ) : (
              <>
                <p className={s.resultTitle}>{run.intel_title}</p>
                <div role="status" className={s.message}>
                  {run.status === "cancelled" ? "任务已停止，可重新生成。" : run.message}
                </div>
                {run.error && (
                  <p role="alert" className={s.error}>
                    {run.error}
                  </p>
                )}
                {run.artifacts_ready && (
                  <>
                    <div className={s.downloads}>
                      <a
                        className={s.primary}
                        href={pentestArtifactUrl(run.run_id, "bundle.zip")}
                      >
                        <Download size={16} />
                        下载完整检测包
                      </a>
                      <a href={pentestArtifactUrl(run.run_id, "detector.py")}>
                        Python 脚本
                      </a>
                      <a href={pentestArtifactUrl(run.run_id, "README.md")}>使用说明</a>
                      <a href={pentestArtifactUrl(run.run_id, "plan.json")}>检测计划</a>
                    </div>
                    <p className={s.validation}>
                      来源引用、契约和语法检查已通过 · 尚未测试真实目标
                    </p>
                    <details>
                      <summary>预览 Python 脚本</summary>
                      <pre className={s.code}>
                        <code>{run.script}</code>
                      </pre>
                    </details>
                  </>
                )}
                {run.events.length > 0 && (
                  <details className={s.events}>
                    <summary>生成过程 · {run.events.length} 步</summary>
                    <ol>
                      {run.events.map((event, i) => (
                        <li key={i}>{event.message}</li>
                      ))}
                    </ol>
                  </details>
                )}
                {run.analysis && (
                  <div className={s.analysis}>
                    <h3>漏洞机制</h3>
                    <p>{run.analysis.mechanism}</p>
                    <details>
                      <summary>分析阶段的初步思路</summary>
                      <p>{run.analysis.strategy}</p>
                      {run.plan && <p>实际请求和判断以最终检测计划为准。</p>}
                    </details>
                    {run.analysis.preconditions.length > 0 && (
                      <>
                        <h3>适用前提</h3>
                        <ul>
                          {run.analysis.preconditions.map((v, i) => (
                            <li key={i}>{v}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {run.analysis.missing_information.length > 0 && (
                      <div className={s.gaps}>
                        <h3>需要补充的证据</h3>
                        <ul>
                          {run.analysis.missing_information.map((v, i) => (
                            <li key={i}>{v}</li>
                          ))}
                        </ul>
                        <p>补齐原情报后重新生成，本次未产出测试脚本。</p>
                      </div>
                    )}
                    <details>
                      <summary>
                        来源原文定位 · {run.analysis.references?.length || 0} 处
                      </summary>
                      {run.analysis.references?.map((ref, i) => (
                        <blockquote key={i}>
                          <p>{ref.quote}</p>
                          <cite>
                            {ref.field} · 字符 {ref.start}–{ref.end}
                          </cite>
                        </blockquote>
                      ))}
                      {run.source.truncated_fields.length > 0 && (
                        <p>分析输入截取了：{run.source.truncated_fields.join("、")}</p>
                      )}
                    </details>
                  </div>
                )}
                {run.plan && (
                  <div className={s.analysis}>
                    <h3>
                      检测范围 ·{" "}
                      {run.plan.test_scope === "behavioral_probe"
                        ? "行为机制测试"
                        : "公告检测"}
                    </h3>
                    <p>{run.plan.applicability}</p>
                    <div className={s.probes}>
                      {[run.plan.baseline, ...run.plan.probes].map((p, i) => (
                        <div key={p.name}>
                          <span>{i === 0 ? "基线" : `探针 ${i}`}</span>
                          <code>
                            {p.method} {p.path}
                          </code>
                          <p>{p.purpose}</p>
                          {p.body_json && (
                            <details>
                              <summary>请求内容</summary>
                              <pre className={s.raw}>{p.body_json}</pre>
                            </details>
                          )}
                        </div>
                      ))}
                    </div>
                    <details>
                      <summary>机器判据：基线有效性与漏洞特征</summary>
                      <pre className={s.raw}>
                        {JSON.stringify(
                          {
                            baseline_checks: run.plan.baseline_checks,
                            predicates: run.plan.predicates,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </details>
                    <p>
                      <strong>阳性：</strong>
                      {run.plan.positive_evidence}
                    </p>
                    <p>
                      <strong>未观察到：</strong>
                      {run.plan.negative_evidence}
                    </p>
                    <details>
                      <summary>无法判断的情形与局限</summary>
                      <ul>
                        {[
                          ...run.plan.inconclusive_when,
                          ...run.plan.limitations,
                          ...(run.analysis?.limitations || []),
                        ].map((v, i) => (
                          <li key={i}>{v}</li>
                        ))}
                      </ul>
                    </details>
                  </div>
                )}
              </>
            )}
          </section>
        </main>
      </div>
      <section className={s.card} aria-labelledby="history-title">
        <div className={s.sectionTop}>
          <h2 id="history-title">生成历史</h2>
          <span className={s.hint}>最近 50 次任务</span>
        </div>
        {history.error ? (
          <p role="alert" className={s.error}>
            {history.error.message}
          </p>
        ) : !history.data?.length ? (
          <p className={s.empty}>
            {history.isLoading ? "读取历史…" : "还没有生成任务。"}
          </p>
        ) : (
          <div className={s.history}>
            {history.data.map((job) => (
              <button
                key={job.run_id}
                aria-pressed={job.run_id === currentId}
                className={job.run_id === currentId ? s.selected : ""}
                onClick={() => setRunId(job.run_id)}
              >
                <strong>{job.intel_title}</strong>
                <span>{PENTEST_STATUS[job.status]}</span>
                <time>
                  {new Date(job.created_at).toLocaleString("zh-CN", { hour12: false })}
                </time>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
