import "@testing-library/jest-dom/vitest"

import { cleanup } from "@testing-library/react"
import { afterEach } from "vitest"

// Testing Library only auto-cleans when test globals are enabled; we import explicitly.
afterEach(cleanup)

// jsdom has no layout engine and no ResizeObserver; the chat's auto-scroll only needs it to exist.
class NoopResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= NoopResizeObserver as unknown as typeof ResizeObserver
