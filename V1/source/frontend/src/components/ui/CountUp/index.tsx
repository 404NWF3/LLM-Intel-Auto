"use client"

import { useEffect, useRef, useState } from "react"

interface CountUpProps {
  to: number
  /** 动画时长（ms），默认 1600 */
  duration?: number
  /** 自定义格式化函数，如 n => n.toLocaleString() */
  formatter?: (n: number) => string
  className?: string
}

const defaultFormatter = (n: number) =>
  n >= 10000 ? (n / 1000).toFixed(1) + "k" : n.toLocaleString("zh-CN")

export function CountUp({
  to,
  duration = 1600,
  formatter = defaultFormatter,
  className,
}: CountUpProps) {
  const [current, setCurrent] = useState(0)
  const containerRef = useRef<HTMLSpanElement>(null)
  const rafRef = useRef<number | null>(null)
  const hasStarted = useRef(false)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting || hasStarted.current) return
        hasStarted.current = true
        observer.disconnect()

        // 在异步回调内检查 reduced-motion，规避 lint rule react-hooks/set-state-in-effect
        if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
          setCurrent(to)
          return
        }

        const start = performance.now()
        const step = (now: number) => {
          const elapsed = now - start
          const progress = Math.min(elapsed / duration, 1)
          // ease-out cubic
          const eased = 1 - Math.pow(1 - progress, 3)
          setCurrent(Math.round(to * eased))
          if (progress < 1) {
            rafRef.current = requestAnimationFrame(step)
          }
        }
        rafRef.current = requestAnimationFrame(step)
      },
      { threshold: 0.5 }
    )

    observer.observe(el)
    return () => {
      observer.disconnect()
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [to, duration])

  return (
    <span ref={containerRef} className={className} aria-live="polite">
      {formatter(current)}
    </span>
  )
}
