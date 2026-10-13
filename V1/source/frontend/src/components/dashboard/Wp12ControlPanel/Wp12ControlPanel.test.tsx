import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { Wp12RunController } from "@/lib/hooks/useWp12RunController"
import type { Wp12FeedItemSummary } from "@/lib/types/wp12"
import { Wp12ControlPanel } from "./index"

const FEED_ITEM: Wp12FeedItemSummary = {
  attack_id: "atk-001",
  attack_code: "WP12-PI-001",
  canonical_name: "Prompt Injection",
  attack_family: "prompt_injection",
  summary: "Prompt injection summary",
  severity_level: "high",
  last_seen_at: "2026-04-11T00:00:00+00:00",
  primary_cvss_base_score: 8.1,
  primary_cvss_severity_label: "high",
  taxonomy_code: "LLM01",
  taxonomy_name: "Prompt Injection",
  component_name: "langchain",
  asset_name: "seed-asset",
  active: true,
}

function buildController(overrides: Partial<Wp12RunController> = {}): Wp12RunController {
  return {
    feedQuery: "",
    setFeedQuery: vi.fn(),
    feedItems: [FEED_ITEM],
    isLoadingFeed: false,
    feedError: null,
    selectedAttackId: null,
    setSelectedAttackId: vi.fn(),
    selectedFeedDetail: null,
    isLoadingFeedDetail: false,
    feedDetailError: null,
    runStatus: null,
    runError: null,
    result: null,
    planHtml: "",
    planRenderError: null,
    start: vi.fn(async () => {}),
    cancel: vi.fn(async () => {}),
    clearResult: vi.fn(),
    isStarting: false,
    isBusy: false,
    ...overrides,
  }
}

describe("Wp12ControlPanel", () => {
  it("keeps the start button disabled before a sample is selected", () => {
    render(<Wp12ControlPanel controller={buildController()} />)

    expect(
      screen.getByRole("button", { name: "生成测试方案" })
    ).toBeDisabled()
  })

  it("shows cancel action while a run is active", () => {
    const cancel = vi.fn(async () => {})
    render(
      <Wp12ControlPanel
        controller={buildController({
          isBusy: true,
          cancel,
          runStatus: {
            run_id: "run-123",
            attack_id: "atk-001",
            status: "running",
            current_stage: "normalize_intel",
            current_task: "Normalize Intel",
            completed_stages: ["ingest_intel"],
            total_stages: 7,
            percent: 14,
            started_at: "2026-04-11T00:00:00+00:00",
            completed_at: null,
            error: null,
          },
        })}
      />
    )

    fireEvent.click(screen.getByRole("button", { name: "取消运行" }))
    expect(cancel).toHaveBeenCalledTimes(1)
  })
})
