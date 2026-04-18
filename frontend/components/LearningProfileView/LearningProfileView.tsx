"use client";

import { LearningView } from "@/lib/api";
import { focusLabelColor, masteryColor } from "@/lib/scores";
import { FocusTimeline } from "./FocusTimeline";
import { StyleRadar } from "./StyleRadar";
import { TopicGraph } from "./TopicGraph";

type Props = {
  view: LearningView;
  selectedTopic?: string | null;
  onSelectTopic?: (topic: string) => void;
};

export function LearningProfileView({ view, selectedTopic, onSelectTopic }: Props) {
  const profile = view.learning_profile;
  const fingerprint = profile?.engagement_fingerprint || {};
  const hints = profile?.behavioral_signals?.recent_hints || [];
  const narrative = view.narrative_notes?.slice(-3).reverse() || [];
  const mastery = view.top_mastery.concat(
    view.top_struggles.filter(s => !view.top_mastery.find(m => m.topic === s.topic))
  );

  return (
    <div className="stack" style={{ gap: 18 }}>
      <section className="card">
        <div className="section-heading">Learning style</div>
        {profile ? (
          <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 24, alignItems: "start" }}>
            <StyleRadar vector={profile.style_vector} />
            <div className="stack" style={{ gap: 10 }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                <span className="chip chip--highlight">{profile.session_count} sessions</span>
                <span className="chip">{profile.lesson_count} lessons</span>
                <span className="chip">{profile.quiz_count} quizzes</span>
                {profile.last_focus_label && (
                  <span
                    className="chip"
                    style={{ background: "color-mix(in srgb, " + focusLabelColor(profile.last_focus_label) + " 18%, white)", color: focusLabelColor(profile.last_focus_label) }}
                  >
                    last: {profile.last_focus_label}
                  </span>
                )}
              </div>
              <p style={{ margin: 0, color: "var(--ink-soft)" }}>
                Rolling focus <strong style={{ color: "var(--ink)" }}>{profile.rolling_focus_score.toFixed(2)}</strong> ·
                reading speed <strong style={{ color: "var(--ink)" }}>{Math.round(profile.rolling_reading_speed_wpm)} wpm</strong> ·
                completion <strong style={{ color: "var(--ink)" }}>{(profile.rolling_completion_rate * 100).toFixed(0)}%</strong>
              </p>
              {Object.keys(fingerprint).length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {Object.entries(fingerprint)
                    .filter(([key]) => key !== "session_samples")
                    .filter(([, value]) => typeof value === "number" && value > 0.4)
                    .map(([key, value]) => (
                      <span key={key} className="chip">
                        {key.replace(/_/g, " ")} {typeof value === "number" ? `· ${value.toFixed(2)}` : ""}
                      </span>
                    ))}
                </div>
              )}
              {hints.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  <div className="section-heading" style={{ marginBottom: 4 }}>
                    Recent teaching hints
                  </div>
                  <ul style={{ paddingLeft: 18, margin: 0, color: "var(--ink-soft)", fontSize: 14 }}>
                    {hints.slice(-3).map((hint, i) => (
                      <li key={i}>{hint}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            No learning profile yet. This student has not completed any tracked sessions.
          </p>
        )}
      </section>

      <section className="card">
        <div className="section-heading">Topic mastery</div>
        <TopicGraph nodes={mastery} edges={view.topic_edges} onSelect={onSelectTopic} selected={selectedTopic ?? null} />
      </section>

      <section className="card">
        <div className="section-heading">Recent focus</div>
        <FocusTimeline entries={view.recent_focus} />
      </section>

      {narrative.length > 0 && (
        <section className="card">
          <div className="section-heading">Narrative notes</div>
          <ul style={{ paddingLeft: 18, margin: 0, color: "var(--ink)", fontSize: 14, lineHeight: 1.6 }}>
            {narrative.map((entry, i) => (
              <li key={i} style={{ marginBottom: 6 }}>
                <span className="faint" style={{ fontSize: 12 }}>
                  {new Date(entry.ts).toLocaleString()} ·{" "}
                </span>
                {entry.note}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

type CompactProps = {
  view: LearningView;
};

export function CompactLearningProfileCard({ view }: CompactProps) {
  const profile = view.learning_profile;
  const topMastery = view.top_mastery.slice(0, 3);
  const hints = profile?.behavioral_signals?.recent_hints?.slice(-2) || [];

  return (
    <section className="card" style={{ padding: 18 }}>
      <div className="section-heading">Learning style</div>
      {profile ? (
        <>
          <div style={{ display: "grid", placeItems: "center", marginTop: 6 }}>
            <StyleRadar vector={profile.style_vector} size={200} />
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 6,
              margin: "10px 0",
              justifyContent: "center"
            }}
          >
            {profile.last_focus_label && (
              <span
                className="chip"
                style={{
                  background: `color-mix(in srgb, ${focusLabelColor(profile.last_focus_label)} 18%, white)`,
                  color: focusLabelColor(profile.last_focus_label)
                }}
              >
                {profile.last_focus_label}
              </span>
            )}
            <span className="chip">
              focus {profile.rolling_focus_score.toFixed(2)}
            </span>
            <span className="chip">
              {Math.round(profile.rolling_reading_speed_wpm)} wpm
            </span>
          </div>
          {topMastery.length > 0 && (
            <>
              <div className="divider" />
              <div className="section-heading">Top topics</div>
              <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 8 }}>
                {topMastery.map(node => (
                  <li
                    key={node.topic}
                    style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}
                  >
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        background: masteryColor(node.mastery_score)
                      }}
                    />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {node.topic}
                    </span>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {(node.mastery_score * 10).toFixed(1)}/10
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {hints.length > 0 && (
            <>
              <div className="divider" />
              <div className="section-heading">Teaching hints</div>
              <ul style={{ paddingLeft: 16, margin: 0, fontSize: 12, color: "var(--ink-soft)" }}>
                {hints.map((hint, i) => (
                  <li key={i}>{hint}</li>
                ))}
              </ul>
            </>
          )}
        </>
      ) : (
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>
          Student hasn't completed any tracked sessions yet — scores on the right use defaults.
        </p>
      )}
    </section>
  );
}
