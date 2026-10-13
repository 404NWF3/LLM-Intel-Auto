"use client"

import { useEffect, useState } from "react"
import { MOCK_MODE_STORAGE_KEY } from "@/lib/api/client"
import styles from "./DashboardSidebar.module.css"

const ENV_DEFAULT = process.env.NEXT_PUBLIC_USE_MOCK_API === "true"

function readStoredMode(): boolean {
  const stored = localStorage.getItem(MOCK_MODE_STORAGE_KEY)
  return stored !== null ? stored === "true" : ENV_DEFAULT
}

export function MockModeToggle() {
  // 初始值用 ENV_DEFAULT 避免 SSR/hydration 不匹配
  const [isMock, setIsMock] = useState(ENV_DEFAULT)

  // 客户端挂载后同步 localStorage 实际值
  useEffect(() => {
    setIsMock(readStoredMode())
  }, [])

  const handleToggle = () => {
    const next = !isMock
    localStorage.setItem(MOCK_MODE_STORAGE_KEY, String(next))
    window.location.reload()
  }

  return (
    <button
      className={`${styles.apiToggle} ${isMock ? styles.apiToggleMock : styles.apiToggleLive}`}
      onClick={handleToggle}
      title={`数据来源：${isMock ? "Mock 静态数据" : "Live 后端 API"} — 点击切换`}
      aria-label={`切换数据模式，当前为 ${isMock ? "Mock" : "Live"}`}
    >
      <span
        className={`${styles.apiDot} ${isMock ? styles.apiDotMock : styles.apiDotLive}`}
        aria-hidden="true"
      />
      <span className={styles.apiLabel}>
        {isMock ? "MOCK" : "LIVE"}
      </span>
      <span className={styles.apiHint} aria-hidden="true">
        切换
      </span>
    </button>
  )
}
