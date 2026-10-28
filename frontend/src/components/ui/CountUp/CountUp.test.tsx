import { StrictMode } from "react"
import { act, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { CountUp } from "./index"

let observers: IntersectionObserverCallback[]
let frames: Map<number, FrameRequestCallback>
let nextFrame: number

beforeEach(() => {
  observers = []
  frames = new Map()
  nextFrame = 0
  vi.stubGlobal("matchMedia", () => ({ matches: false }))
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: IntersectionObserverCallback) {
        observers.push(callback)
      }
      observe() {}
      disconnect() {}
    }
  )
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.set(++nextFrame, callback)
    return nextFrame
  })
  vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id))
})
afterEach(() => vi.unstubAllGlobals())

function enterAndFinish() {
  act(() =>
    observers.at(-1)!(
      [{ isIntersecting: true } as IntersectionObserverEntry],
      {} as IntersectionObserver
    )
  )
  act(() => {
    const callbacks = [...frames.values()]
    frames.clear()
    callbacks.forEach((callback) => callback(performance.now() + 2000))
  })
}

describe("CountUp", () => {
  it("animates async updates after an initial zero, including decimals and decreases", () => {
    const view = (to: number) => (
      <StrictMode>
        <CountUp to={to} formatter={(n) => n.toFixed(1)} />
      </StrictMode>
    )
    const { rerender } = render(view(0))
    enterAndFinish()
    expect(screen.getByText("0.0")).toBeInTheDocument()
    rerender(view(11.1))
    enterAndFinish()
    expect(screen.getByText("11.1")).toBeInTheDocument()
    rerender(view(5.6))
    enterAndFinish()
    expect(screen.getByText("5.6")).toBeInTheDocument()
  })

  it("updates reduced-motion users without scheduling an animation", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }))
    const { rerender } = render(<CountUp to={1} />)
    enterAndFinish()
    expect(screen.getByText("1")).toBeInTheDocument()
    rerender(<CountUp to={9} />)
    enterAndFinish()
    expect(screen.getByText("9")).toBeInTheDocument()
    expect(frames.size).toBe(0)
  })
})
