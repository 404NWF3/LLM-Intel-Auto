"use client"

import type {
  CollectMode,
  SentinelRunController,
  TriggerMode,
} from "@/lib/hooks/useSentinelRunController"
import styles from "./SentinelControlPanel.module.css"

const MODE_OPTIONS: { value: CollectMode; label: string; desc: string }[] = [
  { value: "full", label: "全量采集", desc: "NVD + GitHub + arXiv + 社区信号" },
  { value: "nvd", label: "NVD", desc: "CVE 与官方漏洞库" },
  { value: "github", label: "GitHub Advisory", desc: "开源生态安全公告" },
  { value: "arxiv", label: "arXiv", desc: "AI 安全文献与研究动态" },
  { value: "community", label: "社区信号", desc: "Hacker News + Reddit" },
]

const TRIGGER_OPTIONS: { value: TriggerMode; label: string; desc: string }[] = [
  {
    value: "openclaw",
    label: "OpenClaw HTTP Responses",
    desc: "通过 Gateway 的 /v1/responses 调起 llm-security-intel agent",
  },
  {
    value: "subprocess",
    label: "本地脚本（备用）",
    desc: "直接运行 workspace 内的 Python 采集脚本",
  },
]

interface SentinelControlPanelProps {
  controller: SentinelRunController
}

export function SentinelControlPanel({ controller }: SentinelControlPanelProps) {
  const {
    collectMode,
    setCollectMode,
    triggerMode,
    setTriggerMode,
    runState,
    connection,
    connectionError,
    loadingConnection,
    refreshConnection,
    start,
    cancel,
    reset,
    isStarting,
    isBusy,
    openClawReady,
  } = controller

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h2 className={styles.title}>Sentinel 采集触发</h2>
        {runState.phase === "running" && <span className={styles.runId}>{runState.runId}</span>}
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <label className={styles.label}>OpenClaw 连接诊断</label>
          <button
            className={styles.inlineBtn}
            onClick={() => void refreshConnection()}
            disabled={loadingConnection}
          >
            {loadingConnection ? "检测中" : "刷新"}
          </button>
        </div>

        {connection && (
          <div className={styles.connectionCard}>
            <div className={styles.connectionTop}>
              <span
                className={[
                  styles.statusPill,
                  connection.status === "ready"
                    ? styles.statusReady
                    : connection.status === "degraded"
                      ? styles.statusDegraded
                      : styles.statusErrorPill,
                ].join(" ")}
              >
                {connection.status === "ready"
                  ? "OpenClaw 已就绪"
                  : connection.status === "degraded"
                    ? "配置未完成"
                    : "连接失败"}
              </span>
              <span className={styles.metaText}>{connection.gateway.responses_url}</span>
            </div>

            <div className={styles.factGrid}>
              <div className={styles.factItem}>
                <span className={styles.factKey}>Workspace</span>
                <span className={styles.factValue}>{connection.workspace_exists ? "存在" : "缺失"}</span>
              </div>
              <div className={styles.factItem}>
                <span className={styles.factKey}>Agent</span>
                <span className={styles.factValue}>
                  {connection.agent.configured ? connection.agent.id : "未配置"}
                </span>
              </div>
              <div className={styles.factItem}>
                <span className={styles.factKey}>HTTP</span>
                <span className={styles.factValue}>{connection.gateway.reachable ? "可访问" : "不可达"}</span>
              </div>
              <div className={styles.factItem}>
                <span className={styles.factKey}>Responses API</span>
                <span className={styles.factValue}>
                  {connection.gateway.models_ready ? "已启用" : "未就绪"}
                </span>
              </div>
            </div>

            <p className={styles.pathText}>{connection.workspace_root}</p>
            <p className={styles.pathText}>HTTP Surface: {connection.gateway.surface}</p>

            {connection.issues.length > 0 && (
              <div className={styles.issueBox}>
                {connection.issues.map((issue) => (
                  <p key={issue} className={styles.issueText}>
                    {issue}
                  </p>
                ))}
              </div>
            )}

            <p className={styles.note}>
              {connection.hooks.enabled
                ? "hooks.enabled=true，但当前面板优先走 HTTP Responses，不再依赖 hooks token 回退。"
                : "当前面板直接走 HTTP Responses；如未启用会自动建议切回本地脚本备用模式。"}
            </p>
          </div>
        )}

        {connectionError && <p className={styles.errorText}>诊断请求失败：{connectionError}</p>}
      </div>

      <div className={styles.section}>
        <label className={styles.label}>采集范围</label>
        <div className={styles.modeGrid}>
          {MODE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={[styles.modeChip, collectMode === opt.value ? styles.modeChipActive : ""].join(" ")}
              onClick={() => setCollectMode(opt.value)}
              disabled={isBusy}
              title={opt.desc}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className={styles.hint}>{MODE_OPTIONS.find((opt) => opt.value === collectMode)?.desc}</p>
      </div>

      <div className={styles.section}>
        <label className={styles.label}>触发方式</label>
        <div className={styles.triggerGroup}>
          {TRIGGER_OPTIONS.map((opt) => {
            const disabled = isBusy || (opt.value === "openclaw" && !openClawReady)
            return (
              <label
                key={opt.value}
                className={[
                  styles.triggerOption,
                  triggerMode === opt.value ? styles.triggerOptionActive : "",
                  disabled ? styles.triggerOptionDisabled : "",
                ].join(" ")}
              >
                <input
                  type="radio"
                  name="triggerMode"
                  value={opt.value}
                  checked={triggerMode === opt.value}
                  onChange={() => setTriggerMode(opt.value)}
                  disabled={disabled}
                  className={styles.radioInput}
                />
                <div>
                  <span className={styles.triggerLabel}>{opt.label}</span>
                  <span className={styles.triggerDesc}>{opt.desc}</span>
                </div>
              </label>
            )
          })}
        </div>
        {triggerMode === "openclaw" && (
          <p className={styles.gatewayNote}>
            优先从 <code>~/.openclaw/openclaw.json</code> 自动发现 gateway、agent 与 workspace。
            若要启用当前链路，请确认 <code>gateway.http.endpoints.responses.enabled=true</code>，
            并配置 <code>OPENCLAW_GATEWAY_TOKEN</code> 或在 OpenClaw 配置中提供
            <code>gateway.auth.token</code>。
          </p>
        )}
      </div>

      <div className={styles.footer}>
        {runState.phase === "idle" && (
          <button
            className={styles.startBtn}
            onClick={() => void start()}
            disabled={triggerMode === "openclaw" && !openClawReady}
          >
            发起采集
          </button>
        )}

        {isStarting && (
          <button className={styles.startBtn} disabled>
            启动中
          </button>
        )}

        {runState.phase === "running" && (
          <>
            <span className={styles.statusRunning}>
              <span className={styles.pulse} />
              采集中 · {MODE_OPTIONS.find((opt) => opt.value === runState.mode)?.label}（
              {runState.transport}）
            </span>
            <button className={styles.cancelBtn} onClick={() => void cancel()}>
              停止等待
            </button>
          </>
        )}

        {runState.phase === "cancelling" && <span className={styles.statusMuted}>停止中</span>}

        {runState.phase === "done" && (
          <>
            <span className={runState.outcome === "succeeded" ? styles.statusDone : styles.statusCancelled}>
              {runState.outcome === "succeeded" ? "采集完成" : "已停止"}
            </span>
            <button className={styles.resetBtn} onClick={reset}>
              重置
            </button>
          </>
        )}

        {runState.phase === "error" && (
          <>
            <span className={styles.statusError} title={runState.message}>
              {runState.message.length > 88 ? `${runState.message.slice(0, 88)}...` : runState.message}
            </span>
            <button className={styles.resetBtn} onClick={reset}>
              重置
            </button>
          </>
        )}
      </div>
    </div>
  )
}
