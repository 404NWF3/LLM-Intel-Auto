"use client"

import { useEffect, useState } from "react"
import type { TocItem } from "@/lib/docs/processor"
import styles from "./DocToc.module.css"

interface DocTocProps {
  items: TocItem[]
}

export function DocToc({ items }: DocTocProps) {
  const [activeId, setActiveId] = useState<string>("")

  useEffect(() => {
    if (items.length === 0) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
          }
        }
      },
      { rootMargin: "0px 0px -65% 0px", threshold: 0 },
    )

    items.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [items])

  if (items.length === 0) return null

  return (
    <nav className={styles.toc} aria-label="文档目录">
      <p className={styles.title}>目录</p>
      <ul className={styles.list}>
        {items.map((item) => (
          <li
            key={item.id}
            className={item.level === 3 ? styles.itemIndent : styles.item}
          >
            <a
              href={`#${item.id}`}
              className={`${styles.link ?? ""} ${activeId === item.id ? (styles.linkActive ?? "") : ""}`}
            >
              {item.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
