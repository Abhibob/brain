import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuizEngine } from "@/components/QuizEngine/QuizEngine";

const questions = [
  { id: 1, question: "What stops recursion?", options: ["Base case", "Timer"], points: 1 },
  { id: 2, question: "What reduces the problem?", options: ["Grow", "Recursive step"], points: 1 }
];

function mockJson(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("QuizEngine", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("renders fetched questions", async () => {
    globalThis.fetch = (async (url: RequestInfo) => {
      if (String(url).endsWith("/quiz")) return mockJson(questions);
      throw new Error("unexpected url " + url);
    }) as unknown as typeof fetch;

    render(<QuizEngine materialId={1} />);
    expect(await screen.findByText("What stops recursion?")).toBeInTheDocument();
    expect(screen.getByText("What reduces the problem?")).toBeInTheDocument();
  });

  it("submits selected answers and displays score", async () => {
    const submitSpy = vi.fn();
    globalThis.fetch = (async (url: RequestInfo, init?: RequestInit) => {
      if (init?.method === "POST" && String(url).includes("/submit")) {
        submitSpy(JSON.parse(init.body as string));
        return mockJson({ attempt_id: 1, score: 2, max_score: 2, normalized_score: 1 });
      }
      return mockJson(questions);
    }) as unknown as typeof fetch;

    const user = userEvent.setup();
    render(<QuizEngine materialId={1} />);
    await screen.findByText("What stops recursion?");
    await user.click(screen.getByLabelText(/Base case/));
    await user.click(screen.getByLabelText(/Recursive step/));
    await user.click(screen.getByRole("button", { name: /submit quiz/i }));

    await waitFor(() => {
      expect(submitSpy).toHaveBeenCalledWith({ answers: { "1": "Base case", "2": "Recursive step" }, session_id: undefined });
      expect(screen.getByText(/Score: 2\/2/)).toBeInTheDocument();
    });
  });

  it("shows error message on fetch failure", async () => {
    globalThis.fetch = (async () => mockJson({ detail: "Boom" }, 500)) as unknown as typeof fetch;
    render(<QuizEngine materialId={1} />);
    expect(await screen.findByText(/Boom/)).toBeInTheDocument();
  });

  it("submit button disabled when no questions", async () => {
    globalThis.fetch = (async () => mockJson([])) as unknown as typeof fetch;
    render(<QuizEngine materialId={1} />);
    const button = await screen.findByRole("button", { name: /submit quiz/i });
    expect(button).toBeDisabled();
  });
});
