"use client"

import { useEffect, useRef, useState } from "react"

interface CountUpProps {
  to: number
  /** 动画时长（ms），默认 1600 */
  duration?: number
  formatter?: (n: number) => string
  className?: string
}

const defaultFormatter = (n: number) =>
  n >= 10000 ? (n / 1000).toFixed(1) + "k" : Math.round(n).toLocaleString("zh-CN")

export function CountUp({
  to,
  duration = 1600,
  formatter = defaultFormatter,
  className,
}: CountUpProps) {
  const [current, setCurrent] = useState(0)
  const currentRef = useRef(0)
  const containerRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    let frame: number | undefined
    let started = false
    const update = (value: number) => {
      currentRef.current = value
      setCurrent(value)
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting || started) return
        started = true
        observer.disconnect()

        if (
          duration <= 0 ||
          window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ) {
          update(to)
          return
        }

        const from = currentRef.current
        const start = performance.now()
        const step = (now: number) => {
          const progress = Math.min((now - start) / duration, 1)
          const eased = 1 - Math.pow(1 - progress, 3)
          // Preserve fractional percentages and animate subsequent API updates too.
          update(progress === 1 ? to : from + (to - from) * eased)
          if (progress < 1) frame = requestAnimationFrame(step)
        }
        frame = requestAnimationFrame(step)
      },
      { threshold: 0.5 }
    )

    observer.observe(el)
    return () => {
      observer.disconnect()
      if (frame !== undefined) cancelAnimationFrame(frame)
    }
  }, [to, duration])

  return (
    <span ref={containerRef} className={className} aria-live="polite">
      {formatter(current)}
    </span>
  )
}
