"use client"
import { useState } from "react"
import { Braces, Download, FileCode2 } from "lucide-react"
import { artifactUrl, type SandboxDetail } from "@/lib/api/sandbox"
import { ArtifactPreview } from "./ArtifactPreview"
import base from "../IntelDashboard/IntelDashboard.module.css"
import s from "./TaskArtifacts.module.css"

export function TaskArtifacts({ run }: { run: SandboxDetail }) {
  const [path, setPath] = useState("")
  const selected =
    run.artifacts.find((a) => a.path === path) ??
    run.artifacts.find((a) => a.name === "report.md") ??
    run.artifacts[0]
  if (!selected)
    return (
      <div className={base.empty}>
        <Braces size={25} />
        <p>产物会在任务推进后出现；中断时保留已生成的内容。</p>
      </div>
    )
  return (
    <>
      <div className={s.artifactBar}>
        <label>
          <FileCode2 size={15} />
          <select
            aria-label="选择产物"
            value={selected.path}
            onChange={(e) => setPath(e.target.value)}
          >
            {run.artifacts.map((a) => (
              <option value={a.path} key={a.path}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <a href={artifactUrl(run.run_id, selected.path)} download>
          <Download size={14} />
          下载
        </a>
      </div>
      <ArtifactPreview
        key={`${run.run_id}-${selected.path}`}
        runId={run.run_id}
        path={selected.path}
        active={run.status === "running" || run.status === "cancelling"}
      />
    </>
  )
}
