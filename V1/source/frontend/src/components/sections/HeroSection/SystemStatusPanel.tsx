"use client"

import { findWp } from "@/lib/wp-registry"
import styles from "./HeroSection.module.css"

const RECENT_INTEL = [
  { id: "CVE-2024-41091", desc: "LLM 提示词注入变种", time: "2h 前" },
  { id: "OWASP-LLM01", desc: "向量存储越权访问", time: "4h 前" },
  { id: "CISA-AA24-291", desc: "多智能体协调劫持", time: "6h 前" },
] as const

// 2×2 grid layout — SVG viewport: 0 0 288 208
// top-left=WP1-1, top-right=WP1-2, bottom-right=WP1-3, bottom-left=WP1-4
const NODE_LAYOUT = [
  { id: "wp11", cx: 72, cy: 60 },
  { id: "wp12", cx: 216, cy: 60 },
  { id: "wp13", cx: 216, cy: 152 },
  { id: "wp14", cx: 72, cy: 152 },
] as const

// Each entry: line coords + inline arrowhead polygon points (pre-computed)
const FLOW_LINES = [
  {
    key: "top",
    x1: 96, y1: 60, x2: 188, y2: 60,
    arrow: "188,55 196,60 188,65",
  },
  {
    key: "right",
    x1: 216, y1: 82, x2: 216, y2: 130,
    arrow: "211,130 216,138 221,130",
  },
  {
    key: "bottom",
    x1: 192, y1: 152, x2: 100, y2: 152,
    arrow: "100,147 92,152 100,157",
  },
  {
    key: "left",
    x1: 72, y1: 130, x2: 72, y2: 82,
    arrow: "67,82 72,74 77,82",
  },
] as const

export function SystemStatusPanel() {
  return (
    <div className="hero__panel">
      <div className={styles.panelHeader}>
        <span className={styles.panelTitle}>系统态势</span>
        <span className={styles.panelLive}>
          <span className={styles.liveDot} aria-hidden="true" />
          LIVE
        </span>
      </div>

      <svg
        viewBox="0 0 288 212"
        className={styles.networkSvg}
        aria-label="四智能体网络拓扑图"
        role="img"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Layer divider */}
        <line
          x1="24"
          y1="106"
          x2="264"
          y2="106"
          stroke="rgba(23,21,18,0.1)"
          strokeWidth="1"
          strokeDasharray="3 5"
        />
        <text
          x="12"
          y="100"
          fontSize="7.5"
          fill="rgba(23,21,18,0.28)"
          fontWeight="700"
          letterSpacing="0.04em"
        >
          通
        </text>
        <text
          x="12"
          y="112"
          fontSize="7.5"
          fill="rgba(23,21,18,0.28)"
          fontWeight="700"
          letterSpacing="0.04em"
        >
          用
        </text>
        <text
          x="270"
          y="100"
          fontSize="7.5"
          fill="rgba(23,21,18,0.28)"
          fontWeight="700"
          letterSpacing="0.04em"
        >
          用
        </text>
        <text
          x="270"
          y="112"
          fontSize="7.5"
          fill="rgba(23,21,18,0.28)"
          fontWeight="700"
          letterSpacing="0.04em"
        >
          户
        </text>

        {/* Flow lines with inline arrowheads */}
        {FLOW_LINES.map((fl) => (
          <g key={fl.key}>
            <line
              x1={fl.x1}
              y1={fl.y1}
              x2={fl.x2}
              y2={fl.y2}
              stroke="rgba(160,106,67,0.4)"
              strokeWidth="1.5"
              strokeDasharray="6 4"
              className={styles.flowLine}
            />
            <polygon points={fl.arrow} fill="rgba(160,106,67,0.5)" />
          </g>
        ))}

        {/* WP Nodes */}
        {NODE_LAYOUT.map(({ id, cx, cy }) => {
          const wp = findWp(id)
          if (!wp) return null
          const isRunning = wp.mockStatus === "running"
          return (
            <g key={id}>
              <circle
                cx={cx}
                cy={cy}
                r={22}
                fill={
                  isRunning ? "rgba(45,110,78,0.1)" : "rgba(255,253,249,0.82)"
                }
                stroke={
                  isRunning
                    ? "rgba(45,110,78,0.3)"
                    : "rgba(23,21,18,0.12)"
                }
                strokeWidth="1.5"
              />
              {/* Status dot */}
              <circle
                cx={cx + 15}
                cy={cy - 15}
                r={4.5}
                fill={isRunning ? "var(--status-running)" : "var(--status-idle)"}
                className={isRunning ? styles.pulseDot : undefined}
              />
              {/* WP code */}
              <text
                x={cx}
                y={cy - 4}
                textAnchor="middle"
                fontSize="8.5"
                fontWeight="700"
                letterSpacing="0.05em"
                fill="rgba(23,21,18,0.45)"
              >
                {wp.code}
              </text>
              {/* Role short label */}
              <text
                x={cx}
                y={cy + 9}
                textAnchor="middle"
                fontSize="7.5"
                fill="rgba(23,21,18,0.55)"
              >
                {wp.role.slice(0, 4)}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Recent Intel */}
      <div className={styles.recentIntel}>
        <div className={styles.intelHeader}>最近情报</div>
        {RECENT_INTEL.map((item) => (
          <div key={item.id} className={styles.intelItem}>
            <span className={styles.intelId}>{item.id}</span>
            <span className={styles.intelDesc}>{item.desc}</span>
            <span className={styles.intelTime}>{item.time}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
