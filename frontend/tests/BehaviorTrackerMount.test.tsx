import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { createRef, RefObject } from "react";
import { BehaviorTrackerMount } from "@/components/BehaviorTracker/BehaviorTrackerMount";
import { storeAuth } from "@/lib/api";

class FakeTracker {
  static instances: FakeTracker[] = [];
  started = false;
  stopped = false;
  constructor(public sessionId: number, public token: string, public root: HTMLElement) {
    FakeTracker.instances.push(this);
  }
  start() {
    this.started = true;
  }
  stop() {
    this.stopped = true;
  }
}

vi.mock("@/lib/tracker", () => ({
  BehaviorTracker: class {
    constructor(sessionId: number, token: string, root: HTMLElement) {
      return new FakeTracker(sessionId, token, root) as unknown as FakeTracker;
    }
  }
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("BehaviorTrackerMount", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => {
    FakeTracker.instances = [];
    window.localStorage.clear();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("does nothing when no auth present", async () => {
    const ref: RefObject<HTMLDivElement> = { current: document.createElement("div") };
    const onSession = vi.fn();
    const onStatus = vi.fn();
    globalThis.fetch = vi.fn() as unknown as typeof fetch;
    render(<BehaviorTrackerMount materialId={1} rootRef={ref} onSession={onSession} onStatus={onStatus} />);
    expect(globalThis.fetch).not.toHaveBeenCalled();
    expect(onSession).not.toHaveBeenCalled();
  });

  it("does nothing when user is not a student", async () => {
    storeAuth({ access_token: "t", refresh_token: "r", token_type: "bearer", user: { id: 1, email: "e@x.com", role: "educator", created_at: "x" } });
    const ref: RefObject<HTMLDivElement> = { current: document.createElement("div") };
    globalThis.fetch = vi.fn() as unknown as typeof fetch;
    render(<BehaviorTrackerMount materialId={1} rootRef={ref} onSession={vi.fn()} onStatus={vi.fn()} />);
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("starts a session and a tracker for a student", async () => {
    storeAuth({ access_token: "t", refresh_token: "r", token_type: "bearer", user: { id: 1, email: "s@x.com", role: "student", created_at: "x" } });
    const ref: RefObject<HTMLDivElement> = { current: document.createElement("div") };
    globalThis.fetch = vi.fn(async (url: RequestInfo) => {
      if (String(url).endsWith("/sessions/start")) {
        return jsonResponse({ session_id: 42, started_at: "2026-04-18" });
      }
      return jsonResponse({ session_id: 42 });
    }) as unknown as typeof fetch;

    const onSession = vi.fn();
    const onStatus = vi.fn();
    render(<BehaviorTrackerMount materialId={7} rootRef={ref} onSession={onSession} onStatus={onStatus} />);

    await waitFor(() => {
      expect(onSession).toHaveBeenCalledWith(42);
      expect(FakeTracker.instances.length).toBe(1);
      expect(FakeTracker.instances[0].started).toBe(true);
    });
  });

  it("reports startSession errors via onStatus", async () => {
    storeAuth({ access_token: "t", refresh_token: "r", token_type: "bearer", user: { id: 1, email: "s@x.com", role: "student", created_at: "x" } });
    const ref: RefObject<HTMLDivElement> = { current: document.createElement("div") };
    globalThis.fetch = (async () => jsonResponse({ detail: "Student is not enrolled" }, 403)) as unknown as typeof fetch;
    const onStatus = vi.fn();
    render(<BehaviorTrackerMount materialId={7} rootRef={ref} onSession={vi.fn()} onStatus={onStatus} />);
    await waitFor(() => {
      expect(onStatus).toHaveBeenCalledWith("Student is not enrolled");
    });
  });
});
