"use client"

import { useEffect, useRef } from "react"

interface ScrollRevealProps {
  children: React.ReactNode
  /** 0–4，映射到 data-reveal-delay（80ms 步进） */
  delay?: 0 | 1 | 2 | 3 | 4
  className?: string
}

export function ScrollReveal({ children, delay = 0, className }: ScrollRevealProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    // 尊重用户减弱动态效果偏好，直接显示内容
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      el.style.opacity = "1"
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible")
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.15 }
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      data-reveal=""
      data-reveal-delay={delay > 0 ? delay : undefined}
      className={className}
    >
      {children}
    </div>
  )
}
