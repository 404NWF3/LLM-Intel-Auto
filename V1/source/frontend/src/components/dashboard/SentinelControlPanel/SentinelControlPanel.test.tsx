import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { SentinelRunController } from "@/lib/hooks/useSentinelRunController"
import { SentinelControlPanel } from "./index"

function makeController(overrides: Partial<SentinelRunController> = {}): SentinelRunController {
  return {
    collectMode: "full",
    setCollectMode: vi.fn(),
    triggerMode: "openclaw",
    setTriggerMode: vi.fn(),
    runState: { phase: "idle" },
    connection: {
      status: "degraded",
      checked_at: "2026-04-09T00:00:00Z",
      workspace_root: "C:\\Users\\sven3\\.openclaw\\workspace-llm-security-intel",
      workspace_exists: true,
      workspace_source: "openclaw-config",
      preferred_transport: "subprocess",
      issues: ["OpenClaw HTTP Responses API 未就绪"],
      agent: {
        id: "llm-security-intel",
        configured: true,
        workspace: "C:\\Users\\sven3\\.openclaw\\workspace-llm-security-intel",
        workspace_matches: true,
      },
      gateway: {
        http_url: "http://127.0.0.1:18789",
        responses_url: "http://127.0.0.1:18789/v1/responses",
        ws_url: "ws://127.0.0.1:18789",
        surface: "subprocess-fallback",
        auth_configured: true,
        reachable: true,
        models_ready: false,
        protocol: null,
        server_version: "2026.4.8",
        default_agent_id: null,
      },
      hooks: {
        enabled: false,
        mapping_present: false,
      },
    },
    connectionError: null,
    loadingConnection: false,
    assistantMarkdown: "",
    assistantHtml: "",
    assistantRenderError: null,
    refreshConnection: vi.fn().mockResolvedValue(undefined),
    start: vi.fn().mockResolvedValue(undefined),
    cancel: vi.fn().mockResolvedValue(undefined),
    reset: vi.fn(),
    isStarting: false,
    isBusy: false,
    openClawReady: false,
    ...overrides,
  }
}

describe("SentinelControlPanel", () => {
  it("shows HTTP Responses diagnostics and disables the OpenClaw trigger when models are not ready", () => {
    render(<SentinelControlPanel controller={makeController()} />)

    expect(screen.getByText("http://127.0.0.1:18789/v1/responses")).toBeInTheDocument()
    expect(screen.getByText("未就绪")).toBeInTheDocument()
    expect(screen.getByRole("radio", { name: /OpenClaw HTTP Responses/i })).toBeDisabled()
    expect(screen.getByRole("button", { name: "发起采集" })).toBeDisabled()
  })

  it("keeps subprocess available as a fallback trigger", () => {
    const controller = makeController()
    render(<SentinelControlPanel controller={controller} />)

    fireEvent.click(screen.getByRole("radio", { name: /本地脚本（备用）/i }))
    expect(controller.setTriggerMode).toHaveBeenCalledWith("subprocess")
  })
})
