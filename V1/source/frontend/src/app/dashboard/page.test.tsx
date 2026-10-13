import { describe, expect, it, vi } from "vitest"
import { redirect } from "next/navigation"
import DashboardPage from "./page"

vi.mock("next/navigation", () => ({
  redirect: vi.fn(),
}))

describe("DashboardPage", () => {
  it("redirects /dashboard to /dashboard/wp11", () => {
    DashboardPage()
    expect(redirect).toHaveBeenCalledWith("/dashboard/wp11")
  })
})
