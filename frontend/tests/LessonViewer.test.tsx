import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LessonViewer } from "@/components/LessonViewer/LessonViewer";
import type { MaterialOut } from "@/lib/api";

vi.mock("@/components/BehaviorTracker/BehaviorTrackerMount", () => ({
  BehaviorTrackerMount: () => null
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>
}));

const baseMaterial: MaterialOut = {
  id: 1,
  class_id: 7,
  title: "Recursion",
  type: "lesson",
  order_index: 0,
  published_at: "2026-04-18",
  personalized: false,
  generated_content: null,
  sections: [
    { id: 10, title: "Base cases", content: "The base case stops recursion.", order_index: 0, word_count: 5 },
    { id: 11, title: "Recursive steps", content: "Each call reduces the problem.", order_index: 1, word_count: 5 }
  ]
};

describe("LessonViewer", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders each raw section when not personalized", () => {
    render(<LessonViewer material={baseMaterial} />);
    expect(screen.getByText("Base cases")).toBeInTheDocument();
    expect(screen.getByText("Recursive steps")).toBeInTheDocument();
  });

  it("renders generated_content markdown when personalized", () => {
    render(
      <LessonViewer
        material={{ ...baseMaterial, personalized: true, generated_content: "# Custom lesson\nBody." }}
      />
    );
    expect(screen.getByText("Custom lesson")).toBeInTheDocument();
    // raw sections should NOT render when personalized content is present
    expect(screen.queryByText("Base cases")).toBeNull();
  });

  it("renders a link to the quiz", () => {
    render(<LessonViewer material={baseMaterial} />);
    expect(screen.getByRole("link", { name: /take quiz/i })).toHaveAttribute(
      "href",
      "/classes/7/materials/1/quiz"
    );
  });
});
