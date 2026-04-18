import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudentProfileCard } from "@/components/StudentProfileCard/StudentProfileCard";

describe("StudentProfileCard", () => {
  it("renders the profile text and timestamp", () => {
    render(
      <StudentProfileCard
        entry={{
          id: 1,
          profile_text: "Topic: Recursion. Observed score: 0.8.",
          profile_json: {},
          quiz_score: 0.8,
          trigger_material_id: 5,
          created_at: "2026-04-18T12:00:00Z"
        }}
      />
    );
    expect(screen.getByText(/Observed score/)).toBeInTheDocument();
  });
});
