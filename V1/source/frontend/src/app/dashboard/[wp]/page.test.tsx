import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import WpDetailPage from "./page"

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

vi.mock("@/components/dashboard/SentinelDashboardContent", () => ({
  SentinelDashboardContent: () => <div data-testid="sentinel-dashboard-content" />,
}))

vi.mock("@/components/dashboard/Wp11MetricsPanel", () => ({
  Wp11MetricsPanel: () => <div data-testid="wp11-metrics-panel" />,
}))

vi.mock("@/components/dashboard/Wp12DashboardContent", () => ({
  Wp12DashboardContent: () => <div data-testid="wp12-dashboard-content" />,
}))

vi.mock("@/components/dashboard/WpDetailHeader", () => ({
  WpDetailHeader: () => <div data-testid="wp-detail-header" />,
}))

vi.mock("@/lib/wp-registry", () => ({
  SORTED_WP_REGISTRY: [],
  findWp: (id: string) =>
    id === "sentinel"
      ? {
          id: "sentinel",
          code: "WP1-5",
          label: "Sentinel 安全情报",
          mockStatus: "pending",
          logStream: "/api/sentinel/logs/stream",
        }
      : id === "wp12"
        ? {
            id: "wp12",
            code: "WP1-2",
            label: "渗透测试智能体",
            mockStatus: "pending",
            logStream: "/api/wp12/logs/stream",
          }
        : undefined,
}))

describe("WpDetailPage", () => {
  it("renders sentinel-specific layout without metrics or log viewer", async () => {
    const page = await WpDetailPage({
      params: Promise.resolve({ wp: "sentinel" }),
    })

    render(page)

    expect(screen.getByTestId("wp-detail-header")).toBeInTheDocument()
    expect(screen.getByTestId("sentinel-dashboard-content")).toBeInTheDocument()
    expect(screen.queryByTestId("metrics-panel")).not.toBeInTheDocument()
    expect(screen.queryByTestId("log-viewer")).not.toBeInTheDocument()
  })

  it("renders wp12-specific layout without generic metrics or alerts", async () => {
    const page = await WpDetailPage({
      params: Promise.resolve({ wp: "wp12" }),
    })

    render(page)

    expect(screen.getByTestId("wp-detail-header")).toBeInTheDocument()
    expect(screen.getByTestId("wp12-dashboard-content")).toBeInTheDocument()
    expect(screen.queryByTestId("metrics-panel")).not.toBeInTheDocument()
    expect(screen.queryByTestId("alert-panel")).not.toBeInTheDocument()
  })
})
