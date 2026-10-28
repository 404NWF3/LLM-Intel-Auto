"use client"
import { useEffect, useState } from "react"
import useSWR from "swr"
import { artifactUrl } from "@/lib/api/sandbox"
import { processMarkdown } from "@/lib/docs/processor"
import { DocRenderer } from "@/components/docs/DocRenderer"
import base from "../IntelDashboard/IntelDashboard.module.css"
import s from "./TaskArtifacts.module.css"

export function ArtifactPreview({
  runId,
  path,
  active,
}: {
  runId: string
  path: string
  active: boolean
}) {
  const { data, error, isLoading } = useSWR<string, Error>(
    artifactUrl(runId, path),
    async (url) => {
      const response = await fetch(url)
      if (!response.ok) throw new Error("产物加载失败")
      const text = await response.text()
      return text.length > 250000 ? "文件较大，请下载查看完整内容。" : text
    },
    { refreshInterval: active ? 4000 : 0 }
  )
  const [html, setHtml] = useState("")
  useEffect(() => {
    let current = true
    if (data && path.endsWith(".md"))
      void processMarkdown(data)
        .then((value) => {
          if (current) setHtml(value)
        })
        .catch(() => {
          if (current) setHtml("")
        })
    return () => {
      current = false
    }
  }, [data, path])
  if (error) return <p role="alert">{error.message}</p>
  if (isLoading) return <p className={base.empty}>正在加载产物…</p>
  return path.endsWith(".md") && html ? (
    <div className={s.markdown}>
      <DocRenderer html={html} />
    </div>
  ) : (
    <pre className={s.code}>{data}</pre>
  )
}
