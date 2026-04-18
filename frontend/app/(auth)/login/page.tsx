"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, storeAuth } from "@/lib/api";

type Role = "student" | "educator" | "researcher";

const ROLES: Array<{
  role: Role;
  name: string;
  title: string;
  summary: string;
  accent: string;
}> = [
  {
    role: "student",
    name: "Jordan Lee",
    title: "Student",
    summary: "Open your lessons, read with focus tracking on, take the quizzes, watch your learning style take shape.",
    accent: "var(--accent)"
  },
  {
    role: "educator",
    name: "Taylor Chen",
    title: "Teacher",
    summary: "Build personalized lessons for each student with readings, videos, and quizzes scored for how well they fit.",
    accent: "var(--highlight)"
  },
  {
    role: "researcher",
    name: "Morgan Patel",
    title: "Researcher",
    summary: "Inspect learning-style graphs, class analytics, focus timelines, and the predictive model's performance.",
    accent: "#8b5cf6"
  }
];

export default function LoginPage() {
  const router = useRouter();
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pick(role: Role) {
    setBusy(role);
    setError(null);
    try {
      const auth = await api.demoLogin(role);
      storeAuth(auth);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(null);
    }
  }

  return (
    <div className="auth-page">
      <main className="auth-shell">
        <header className="auth-hero">
          <span className="auth-eyebrow">EduTrack</span>
          <h1 className="auth-title">Sign in as</h1>
          <p className="auth-subtitle">
            Pick who you are. Every card signs you into a real-looking class where the teacher, student, and researcher
            share the same world.
          </p>
          {error ? <p className="error">{error}</p> : null}
        </header>

        <div className="auth-role-grid">
          {ROLES.map(option => (
            <button
              key={option.role}
              className="role-card"
              onClick={() => pick(option.role)}
              disabled={busy !== null}
              style={{
                borderTopColor: option.accent,
                opacity: busy && busy !== option.role ? 0.4 : 1
              }}
            >
              <div className="role-card__row">
                <div
                  className="role-card__avatar"
                  style={{ background: `color-mix(in srgb, ${option.accent} 18%, white)` }}
                >
                  {option.name
                    .split(" ")
                    .map(part => part[0])
                    .join("")}
                </div>
                <div className="role-card__who">
                  <span className="role-card__title">{option.title}</span>
                  <span className="role-card__name">{option.name}</span>
                </div>
              </div>
              <p className="role-card__summary">{option.summary}</p>
              <span className="role-card__cta">{busy === option.role ? "Signing in…" : "Continue →"}</span>
            </button>
          ))}
        </div>
      </main>
    </div>
  );
}
