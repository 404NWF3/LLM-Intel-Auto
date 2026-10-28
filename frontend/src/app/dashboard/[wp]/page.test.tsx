import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import WpDetailPage, { generateStaticParams } from "./page"

vi.mock("@/components/dashboard/AlertPanel", () => ({
  AlertPanel: () => <div data-testid="alert-panel" />,
}))

vi.mock("@/components/dashboard/DebugControlPanel", () => ({
  DebugControlPanel: () => <div data-testid="debug-control-panel" />,
}))

vi.mock("@/components/dashboard/LogViewer", () => ({
  LogViewer: () => <div data-testid="log-viewer" />,
}))

vi.mock("@/components/dashboard/MetricsPanel", () => ({
  MetricsPanel: () => <div data-testid="metrics-panel" />,
}))

vi.mock("@/components/dashboard/Wp11MetricsPanel", () => ({
  Wp11MetricsPanel: () => <div data-testid="wp11-metrics-panel" />,
}))

vi.mock("@/components/dashboard/Wp12DashboardContent", () => ({
  Wp12DashboardContent: () => <div data-testid="wp12-dashboard-content" />,
}))

vi.mock("@/components/dashboard/SandboxDashboard", () => ({
  SandboxDashboard: () => <div data-testid="sandbox-dashboard" />,
}))

vi.mock("@/components/dashboard/ResearcherDashboard", () => ({
  ResearcherDashboard: () => <div data-testid="researcher-dashboard" />,
}))

vi.mock("@/components/dashboard/WpDetailHeader", () => ({
  WpDetailHeader: () => <div data-testid="wp-detail-header" />,
}))

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND")
  },
}))

describe("WpDetailPage", () => {
  it("routes migrated repository assessments to wp13", async () => {
    render(await WpDetailPage({ params: Promise.resolve({ wp: "wp13" }) }))
    expect(screen.getByTestId("sandbox-dashboard")).toBeInTheDocument()
    expect(screen.queryByTestId("wp12-dashboard-content")).not.toBeInTheDocument()
    expect(screen.queryByTestId("metrics-panel")).not.toBeInTheDocument()
    expect(screen.queryByTestId("log-viewer")).not.toBeInTheDocument()
  })
  it("renders the real modeling workspace at wp14", async () => {
    render(await WpDetailPage({ params: Promise.resolve({ wp: "wp14" }) }))
    expect(screen.getByTestId("researcher-dashboard")).toBeInTheDocument()
    expect(screen.queryByTestId("metrics-panel")).not.toBeInTheDocument()
    expect(screen.queryByTestId("log-viewer")).not.toBeInTheDocument()
  })
  it("does not generate or render the retired Sentinel workspace", async () => {
    expect(generateStaticParams()).not.toContainEqual({ wp: "sentinel" })
    await expect(
      WpDetailPage({ params: Promise.resolve({ wp: "sentinel" }) })
    ).rejects.toThrow("NEXT_NOT_FOUND")
  })

  it("renders wp12-specific layout without generic metrics or alerts", async () => {
    const page = await WpDetailPage({
      params: Promise.resolve({ wp: "wp12" }),
    })

    render(page)

    expect(screen.queryByTestId("wp-detail-header")).not.toBeInTheDocument()
    expect(screen.getByTestId("wp12-dashboard-content")).toBeInTheDocument()
    expect(screen.queryByTestId("sandbox-dashboard")).not.toBeInTheDocument()
    expect(screen.queryByTestId("metrics-panel")).not.toBeInTheDocument()
    expect(screen.queryByTestId("alert-panel")).not.toBeInTheDocument()
  })
})
