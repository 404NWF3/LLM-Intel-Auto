import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { SentinelAssistantPanel } from "./index"

vi.mock("@/components/docs/DocRenderer", () => ({
  DocRenderer: ({ html }: { html: string }) => <div data-testid="doc-renderer">{html}</div>,
}))

describe("SentinelAssistantPanel", () => {
  const baseProps = {
    title: "OpenClaw 智能体回复",
    assistantHtml: "",
    assistantMarkdown: "",
    renderError: null,
    isBusy: false,
    emptyState: "暂无消息",
  }

  it("renders html content when available", () => {
    render(<SentinelAssistantPanel {...baseProps} assistantHtml="<p>reply</p>" />)
    expect(screen.getByTestId("doc-renderer")).toHaveTextContent("<p>reply</p>")
  })

  it("falls back to markdown text", () => {
    render(<SentinelAssistantPanel {...baseProps} assistantMarkdown="plain reply" />)
    expect(screen.getByText("plain reply")).toBeInTheDocument()
  })

  it("renders render error and fallback markdown", () => {
    render(
      <SentinelAssistantPanel
        {...baseProps}
        assistantMarkdown="fallback reply"
        renderError="boom"
      />
    )

    expect(screen.getByText(/Markdown 渲染失败：boom/)).toBeInTheDocument()
    expect(screen.getByText("fallback reply")).toBeInTheDocument()
  })

  it("renders empty state when there is no message", () => {
    render(<SentinelAssistantPanel {...baseProps} />)
    expect(screen.getByText("暂无消息")).toBeInTheDocument()
  })
})
