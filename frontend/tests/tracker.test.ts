import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BehaviorTracker } from "@/lib/tracker";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  readyState = 1;
  sent: string[] = [];
  listeners: Record<string, ((event: unknown) => void)[]> = {};
  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }
  addEventListener(type: string, handler: (event: unknown) => void) {
    (this.listeners[type] ||= []).push(handler);
  }
  send(payload: string) {
    this.sent.push(payload);
  }
  close() {
    this.readyState = 3;
  }
  triggerOpen() {
    for (const h of this.listeners.open || []) h({});
  }
}

describe("BehaviorTracker", () => {
  const originalWebSocket = globalThis.WebSocket;
  let originalObserver: typeof IntersectionObserver;

  beforeEach(() => {
    FakeWebSocket.instances = [];
    globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;
    originalObserver = globalThis.IntersectionObserver;
    globalThis.IntersectionObserver = class {
      constructor(public cb: IntersectionObserverCallback) {}
      observe() {}
      disconnect() {}
      unobserve() {}
      takeRecords() {
        return [];
      }
      root = null;
      rootMargin = "";
      thresholds = [];
    } as unknown as typeof IntersectionObserver;
  });
  afterEach(() => {
    globalThis.WebSocket = originalWebSocket;
    globalThis.IntersectionObserver = originalObserver;
    vi.restoreAllMocks();
  });

  it("opens a socket on start() and closes on stop()", () => {
    const root = document.createElement("div");
    const tracker = new BehaviorTracker(7, "tok", root);
    tracker.start();
    expect(FakeWebSocket.instances.length).toBe(1);
    const ws = FakeWebSocket.instances[0];
    expect(ws.url).toContain("/track/7");
    expect(ws.url).toContain("token=tok");
    tracker.stop();
    expect(ws.readyState).toBe(3);
  });

  it("send() serializes event payloads", () => {
    const tracker = new BehaviorTracker(1, "t", document.createElement("div"));
    tracker.start();
    const ws = FakeWebSocket.instances[0];
    ws.triggerOpen();
    tracker.send({ event_type: "section_view", section_id: "1" });
    const last = JSON.parse(ws.sent[ws.sent.length - 1]);
    expect(last.type).toBe("event");
    expect(last.data.event_type).toBe("section_view");
    expect(typeof last.ts).toBe("number");
  });
});
