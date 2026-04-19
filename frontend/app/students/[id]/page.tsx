"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  clearAuth,
  getStoredAuth,
  LearningView,
  ProfileEntry
} from "@/lib/api";
import { FocusTimeline } from "@/components/LearningProfileView/FocusTimeline";
import { LearningStyleNet } from "@/components/LearningProfileView/LearningStyleNet";
import { StyleRadar } from "@/components/LearningProfileView/StyleRadar";
import { GazeHeatmap } from "@/components/GazeHeatmap/GazeHeatmap";
import { focusLabelColor, masteryColor } from "@/lib/scores";

function emailToName(email: string): string {
  const local = email.split("@")[0] || email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map(p => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

function initials(name: string): string {
  return name
    .split(" ")
    .map(p => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

type Meta = { id: number; email: string; name: string };

export default function StudentPage() {
  const params = useParams<{ id: string }>();
  const studentId = Number(params.id);
  const router = useRouter();

  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [view, setView] = useState<LearningView | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [entries, setEntries] = useState<ProfileEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth) {
      setSignedIn(false);
      router.replace("/login");
      return;
    }
    setSignedIn(true);

    let cancelled = false;
    (async () => {
      try {
        const v = await api.getLearningView(studentId);
        if (!cancelled) setView(v);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Couldn't load learning view");
      }
      try {
        const res = await api.getProfile(studentId);
        if (!cancelled) setEntries(res.entries);
      } catch {
        // 403 is expected for educators — silently ignore.
      }
      if (auth.user.id === studentId) {
        if (!cancelled) {
          setMeta({ id: studentId, email: auth.user.email, name: emailToName(auth.user.email) });
        }
        return;
      }
      try {
        const classes = await api.listClasses();
        for (const cls of classes) {
          try {
            const roster = await api.roster(cls.id);
            const match = roster.find(r => r.id === studentId);
            if (match) {
              if (!cancelled) {
                setMeta({ id: studentId, email: match.email, name: emailToName(match.email) });
              }
              return;
            }
          } catch {
            // ignore classes we can't read
          }
        }
      } catch {
        // swallow
      }
      if (!cancelled) {
        setMeta({ id: studentId, email: `#${studentId}`, name: `Student #${studentId}` });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, studentId]);

  const recentSessions = useMemo(() => {
    const list = view?.recent_focus ?? [];
    return [...list]
      .filter((s) => typeof s.session_id === "number")
      .sort((a, b) => {
        const at = a.ended_at ? new Date(a.ended_at).getTime() : 0;
        const bt = b.ended_at ? new Date(b.ended_at).getTime() : 0;
        return bt - at;
      });
  }, [view]);

  useEffect(() => {
    if (selectedSessionId === null && recentSessions.length > 0) {
      setSelectedSessionId(recentSessions[0].session_id);
    }
  }, [recentSessions, selectedSessionId]);

  const styleStats = useMemo(() => {
    const sv = view?.learning_profile?.style_vector;
    if (!sv) return null;
    return [
      { label: "Pace", value: sv.pace },
      { label: "Depth", value: sv.depth },
      { label: "Attention", value: sv.attention_stability },
      { label: "Engagement", value: sv.engagement_mode }
    ];
  }, [view]);

  if (signedIn === false) return null;

  const name = meta?.name ?? "Student";
  const profile = view?.learning_profile;

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/dashboard">
          EduTrack
        </Link>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          <button
            className="button ghost"
            onClick={() => {
              clearAuth();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </nav>
      </header>
      <main className="main">
        <section
          className="card"
          style={{
            padding: "24px 26px",
            background:
              "linear-gradient(135deg, var(--surface) 0%, var(--highlight-soft) 100%)",
            borderColor: "color-mix(in srgb, var(--highlight) 24%, var(--line))"
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
            <div
              style={{
                width: 60,
                height: 60,
                borderRadius: "50%",
                background: "linear-gradient(135deg, var(--highlight) 0%, var(--accent) 100%)",
                display: "grid",
                placeItems: "center",
                color: "white",
                fontWeight: 700,
                fontSize: 20,
                letterSpacing: 1
              }}
            >
              {initials(name)}
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div className="section-heading" style={{ marginBottom: 4 }}>
                Student
              </div>
              <h1 style={{ margin: 0, fontSize: 26, letterSpacing: "-0.025em" }}>{name}</h1>
              {meta && (
                <div className="muted" style={{ fontSize: 13 }}>
                  {meta.email}
                </div>
              )}
            </div>
            {profile?.last_focus_label && (
              <span
                className="chip"
                style={{
                  background: `color-mix(in srgb, ${focusLabelColor(profile.last_focus_label)} 18%, white)`,
                  color: focusLabelColor(profile.last_focus_label)
                }}
              >
                Last session · {profile.last_focus_label}
              </span>
            )}
          </div>
          {styleStats && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
                gap: 12,
                marginTop: 18
              }}
            >
              {styleStats.map(stat => (
                <div
                  key={stat.label}
                  style={{
                    background: "var(--surface)",
                    borderRadius: "var(--radius-md)",
                    padding: "10px 12px",
                    border: "1px solid var(--line)"
                  }}
                >
                  <div className="section-heading" style={{ margin: 0, fontSize: 11 }}>
                    {stat.label}
                  </div>
                  <div
                    style={{
                      fontSize: 24,
                      fontWeight: 700,
                      letterSpacing: "-0.02em",
                      marginTop: 4,
                      color: masteryColor(stat.value)
                    }}
                  >
                    {(stat.value * 10).toFixed(1)}
                  </div>
                  <div
                    style={{
                      height: 6,
                      background: "var(--line)",
                      borderRadius: 999,
                      overflow: "hidden",
                      marginTop: 8
                    }}
                  >
                    <div
                      style={{
                        width: `${stat.value * 100}%`,
                        height: "100%",
                        background: "linear-gradient(90deg, var(--accent) 0%, var(--highlight) 100%)"
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          {error && <p className="error" style={{ marginTop: 14 }}>{error}</p>}
        </section>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) minmax(260px, 320px)",
            gap: 22,
            marginTop: 22,
            alignItems: "start"
          }}
        >
          <div className="stack">
            {view ? (
              <LearningStyleNet view={view} />
            ) : (
              <div className="card" style={{ minHeight: 320, display: "grid", placeItems: "center" }}>
                <p className="muted">Loading learning style…</p>
              </div>
            )}

            <section className="card">
              <div className="section-heading">Recent focus</div>
              {view ? <FocusTimeline entries={view.recent_focus} /> : <p className="muted">Loading…</p>}
            </section>

            <section className="card" style={{ padding: 18 }}>
              {recentSessions.length === 0 ? (
                <div style={{ display: "grid", gap: 6 }}>
                  <div className="section-heading">Reading heatmap</div>
                  <p className="muted" style={{ margin: 0, fontSize: 13 }}>
                    No tracked sessions yet. The heatmap will appear after a lesson is read with eye tracking enabled.
                  </p>
                </div>
              ) : (
                <div style={{ display: "grid", gap: 14 }}>
                  <div
                    style={{
                      display: "flex",
                      gap: 8,
                      flexWrap: "wrap",
                      alignItems: "center",
                    }}
                  >
                    <div className="section-heading" style={{ marginRight: "auto" }}>
                      Reading heatmap
                    </div>
                    <label style={{ fontSize: 12, color: "var(--ink-soft)" }} htmlFor="gaze-session-picker">
                      Session
                    </label>
                    <select
                      id="gaze-session-picker"
                      className="select"
                      value={selectedSessionId ?? ""}
                      onChange={(e) => setSelectedSessionId(Number(e.target.value))}
                      style={{ padding: "6px 10px", fontSize: 12.5 }}
                    >
                      {recentSessions.map((s) => (
                        <option key={s.session_id} value={s.session_id}>
                          #{s.session_id}
                          {s.ended_at ? ` · ${new Date(s.ended_at).toLocaleString()}` : ""}
                          {s.focus_label ? ` · ${s.focus_label}` : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                  {selectedSessionId !== null && (
                    <GazeHeatmap sessionId={selectedSessionId} />
                  )}
                </div>
              )}
            </section>

            <section className="card">
              <div className="section-heading">Narrative timeline</div>
              {entries.length === 0 && (view?.narrative_notes?.length ?? 0) === 0 ? (
                <p className="muted" style={{ margin: 0 }}>
                  No notes yet. They'll appear here as the student completes lessons and quizzes.
                </p>
              ) : (
                <div className="stack" style={{ gap: 12 }}>
                  {(view?.narrative_notes ?? [])
                    .slice(-3)
                    .reverse()
                    .map((n, i) => (
                      <article
                        key={`n-${i}`}
                        style={{
                          borderLeft: "3px solid var(--highlight)",
                          paddingLeft: 12,
                          fontSize: 14,
                          color: "var(--ink)"
                        }}
                      >
                        <div className="faint" style={{ fontSize: 12, marginBottom: 2 }}>
                          {new Date(n.ts).toLocaleString()} · AI summary
                        </div>
                        {n.note}
                      </article>
                    ))}
                  {entries.slice(0, 4).map(entry => (
                    <article
                      key={entry.id}
                      style={{
                        borderLeft: "3px solid var(--accent)",
                        paddingLeft: 12,
                        fontSize: 14,
                        color: "var(--ink)"
                      }}
                    >
                      <div className="faint" style={{ fontSize: 12, marginBottom: 2 }}>
                        {new Date(entry.created_at).toLocaleString()} · profile entry{" "}
                        {entry.quiz_score !== null && entry.quiz_score !== undefined && (
                          <span> · quiz {(entry.quiz_score * 10).toFixed(1)}/10</span>
                        )}
                      </div>
                      {entry.profile_text}
                    </article>
                  ))}
                </div>
              )}
            </section>
          </div>

          <aside className="stack" style={{ position: "sticky", top: 96 }}>
            <section className="card" style={{ display: "grid", gap: 12 }}>
              <div className="section-heading">Style radar</div>
              {profile ? (
                <div style={{ display: "grid", placeItems: "center" }}>
                  <StyleRadar vector={profile.style_vector} size={240} />
                </div>
              ) : (
                <p className="muted">Loading…</p>
              )}
              {profile && (
                <div style={{ fontSize: 13, color: "var(--ink-soft)", display: "grid", gap: 4 }}>
                  <div>
                    Rolling focus{" "}
                    <strong style={{ color: "var(--ink)" }}>{profile.rolling_focus_score.toFixed(2)}</strong>
                  </div>
                  <div>
                    Reading speed{" "}
                    <strong style={{ color: "var(--ink)" }}>
                      {Math.round(profile.rolling_reading_speed_wpm)} wpm
                    </strong>
                  </div>
                  <div>
                    Completion{" "}
                    <strong style={{ color: "var(--ink)" }}>
                      {(profile.rolling_completion_rate * 100).toFixed(0)}%
                    </strong>
                  </div>
                  <div>
                    {profile.session_count} sessions · {profile.lesson_count} lessons · {profile.quiz_count} quizzes
                  </div>
                </div>
              )}
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}
