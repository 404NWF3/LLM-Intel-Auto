import type { ComponentProps } from "react"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { DashboardSidebar } from "./index"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: ComponentProps<"a">) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/wp11",
}))

vi.mock("@/lib/wp-registry", () => ({
  SORTED_WP_REGISTRY: [
    { id: "wp11", code: "WP1-1", label: "情报采集智能体" },
    { id: "sentinel", code: "WP1-5", label: "Sentinel 安全情报" },
  ],
}))

vi.mock("@/lib/hooks/useWpStatus", () => ({
  useWpStatus: () => ({ data: { status: "running" } }),
}))

vi.mock("@/components/ui/StatusDot", () => ({
  StatusDot: () => <span data-testid="status-dot" />,
}))

vi.mock("./MockModeToggle", () => ({
  MockModeToggle: () => <div data-testid="mock-mode-toggle" />,
}))

describe("DashboardSidebar", () => {
  it("does not render the overview link anymore", () => {
    render(<DashboardSidebar />)

    expect(screen.queryByText("总览")).not.toBeInTheDocument()
    expect(screen.getByRole("link", { name: /情报采集智能体/i })).toHaveAttribute(
      "href",
      "/dashboard/wp11"
    )
    expect(screen.getByRole("link", { name: /Sentinel 安全情报/i })).toHaveAttribute(
      "href",
      "/dashboard/sentinel"
    )
  })
})
