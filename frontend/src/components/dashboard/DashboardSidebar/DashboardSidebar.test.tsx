import type { ComponentProps } from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { DashboardSidebar } from "./index"

const navigation = vi.hoisted(() => ({ pathname: "/dashboard/graphrag" }))

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: ComponentProps<"a">) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
}))

vi.mock("@/lib/api/intel", () => ({
  useIntelOverview: () => ({ data: { active: null } }),
}))

vi.mock("@/lib/api/sandbox", () => ({
  useSandboxOverview: () => ({ data: { active_run_id: null } }),
}))

vi.mock("@/lib/api/researcher", () => ({
  useResearcherOverview: () => ({ data: { active: null } }),
}))

vi.mock("@/lib/api/pentest", () => ({
  usePentestOverview: () => ({ data: { active: null } }),
}))

vi.mock("@/components/ui/StatusDot", () => ({
  StatusDot: () => <span data-testid="status-dot" />,
}))

vi.mock("./MockModeToggle", () => ({
  MockModeToggle: () => <div data-testid="mock-mode-toggle" />,
}))

describe("DashboardSidebar", () => {
  it("shows WP1-3 as a real workspace without the demo switch", () => {
    navigation.pathname = "/dashboard/wp13"
    render(<DashboardSidebar />)
    expect(screen.getByRole("link", { name: /沙盒模拟智能体/ })).toHaveAttribute("href", "/dashboard/wp13")
    expect(screen.queryByTestId("mock-mode-toggle")).not.toBeInTheDocument()
    navigation.pathname = "/dashboard/graphrag"
  })
  it("links the modeling workspace and hides the mock toggle there", () => {
    navigation.pathname = "/dashboard/wp14"
    render(<DashboardSidebar />)
    expect(screen.getByRole("link", { name: /异常检测智能体/ })).toHaveAttribute("href", "/dashboard/wp14")
    expect(screen.queryByTestId("mock-mode-toggle")).not.toBeInTheDocument()
    navigation.pathname = "/dashboard/graphrag"
  })
  it("shows current workspaces without the retired Sentinel entry", () => {
    render(<DashboardSidebar />)

    expect(screen.queryByText("总览")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /GraphRAG 知识图谱/ })).toHaveAttribute(
      "href",
      "/dashboard/graphrag"
    )
    expect(screen.queryByTestId("mock-mode-toggle")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /情报采集智能体/i })).toHaveAttribute(
      "href",
      "/dashboard/wp11"
    )
    expect(screen.queryByRole("link", { name: /Sentinel/i })).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /渗透测试智能体/ })).toHaveAttribute(
      "href",
      "/dashboard/wp12"
    )
  })
})
