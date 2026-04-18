import { APIRequestContext, expect, request } from "@playwright/test";

const BACKEND_URL = process.env.E2E_BACKEND_URL ?? "http://127.0.0.1:8000";

export async function backend(): Promise<APIRequestContext> {
  return request.newContext({ baseURL: BACKEND_URL });
}

export async function registerUser(api: APIRequestContext, email: string, role: "student" | "educator" | "researcher") {
  const response = await api.post("/auth/register", {
    data: { email, password: "password-123", role, institution: "E2E" }
  });
  if (response.status() === 409) {
    // already exists from an earlier run — log in instead
    const login = await api.post("/auth/login", { data: { email, password: "password-123" } });
    expect(login.ok()).toBeTruthy();
    return login.json();
  }
  expect(response.ok()).toBeTruthy();
  return response.json();
}

export async function authHeaders(token: string) {
  return { Authorization: `Bearer ${token}` };
}

export function uniqueEmail(prefix: string): string {
  return `${prefix}+${Date.now()}@example.com`;
}
