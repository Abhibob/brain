import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, clearAuth, getStoredAuth, storeAuth, wsUrl } from "@/lib/api";

function mockResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

describe("auth storage", () => {
  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("round-trips tokens", () => {
    const state = { access_token: "a", refresh_token: "r", token_type: "bearer", user: { id: 1, email: "e@x.com", role: "student", created_at: "2026-01-01" } } as const;
    storeAuth(state);
    expect(getStoredAuth()).toEqual(state);
  });

  it("clearAuth removes the key", () => {
    storeAuth({ access_token: "a", refresh_token: "r", token_type: "bearer", user: { id: 1, email: "e@x.com", role: "student", created_at: "x" } });
    clearAuth();
    expect(getStoredAuth()).toBeNull();
  });

  it("returns null when empty", () => {
    expect(getStoredAuth()).toBeNull();
  });
});

describe("wsUrl", () => {
  it("converts http to ws and attaches token", () => {
    const url = wsUrl("/track/1", "tok&tok");
    expect(url.startsWith("ws")).toBe(true);
    expect(url).toContain("/track/1");
    expect(url).toContain("token=tok%26tok");
  });
});

describe("api client", () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("attaches Authorization header when auth present", async () => {
    storeAuth({ access_token: "tok", refresh_token: "r", token_type: "bearer", user: { id: 1, email: "e@x.com", role: "student", created_at: "x" } });
    const spy = vi.fn(async (_url: RequestInfo, init?: RequestInit) => {
      expect((init?.headers as Headers).get("Authorization")).toBe("Bearer tok");
      return mockResponse([]);
    });
    globalThis.fetch = spy as unknown as typeof fetch;
    await api.listClasses();
    expect(spy).toHaveBeenCalled();
  });

  it("posts JSON body on register", async () => {
    const spy = vi.fn(async (_url: RequestInfo, init?: RequestInit) => {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(init?.body as string)).toMatchObject({ email: "a@b.com", password: "password-123", role: "student" });
      return mockResponse({ access_token: "x", refresh_token: "y", token_type: "bearer", user: { id: 1, email: "a@b.com", role: "student", created_at: "x" } });
    });
    globalThis.fetch = spy as unknown as typeof fetch;
    const auth = await api.register({ email: "a@b.com", password: "password-123", role: "student" });
    expect(auth.access_token).toBe("x");
  });

  it("throws with server detail on error", async () => {
    globalThis.fetch = (async () => mockResponse({ detail: "Email already registered" }, 409)) as unknown as typeof fetch;
    await expect(api.register({ email: "x@y.com", password: "password-123", role: "student" })).rejects.toThrow(
      "Email already registered"
    );
  });

  it("falls back to status text when body is opaque", async () => {
    globalThis.fetch = (async () =>
      new Response("<html>", { status: 500, statusText: "Internal Server Error" })) as unknown as typeof fetch;
    await expect(api.listClasses()).rejects.toThrow();
  });
});
