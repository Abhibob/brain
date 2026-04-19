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
    view.top_struggles.filter((s) => !view.top_mastery.find((m) => m.topic === s.topic))
  );

  return (
    <div className="space-y-6">
      <section className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
        <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
          Learning style
        </div>
        {profile ? (
          <div className="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-6 items-start">
            <StyleRadar vector={profile.style_vector} />
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <span className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-primary-fixed text-on-primary-fixed">
                  {profile.session_count} sessions
                </span>
                <span className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-surface-container-low text-on-surface-variant">
                  {profile.lesson_count} lessons
                </span>
                <span className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-surface-container-low text-on-surface-variant">
                  {profile.quiz_count} quizzes
                </span>
                {profile.last_focus_label && (
                  <span
                    className="font-body text-xs font-semibold px-3 py-1 rounded-full"
                    style={{
                      background: `color-mix(in srgb, ${focusLabelColor(profile.last_focus_label)} 18%, white)`,
                      color: focusLabelColor(profile.last_focus_label),
                    }}
                  >
                    last: {profile.last_focus_label}
                  </span>
                )}
              </div>
              <p className="font-body text-sm text-on-surface-variant">
                Rolling focus{" "}
                <strong className="text-on-surface">{profile.rolling_focus_score.toFixed(2)}</strong>{" "}
                · reading speed{" "}
                <strong className="text-on-surface">
                  {Math.round(profile.rolling_reading_speed_wpm)} wpm
                </strong>{" "}
                · completion{" "}
                <strong className="text-on-surface">
                  {(profile.rolling_completion_rate * 100).toFixed(0)}%
                </strong>
              </p>
              {Object.keys(fingerprint).length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {Object.entries(fingerprint)
                    .filter(([key]) => key !== "session_samples")
                    .filter(([, value]) => typeof value === "number" && value > 0.4)
                    .map(([key, value]) => (
                      <span
                        key={key}
                        className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-surface-container-low text-on-surface-variant"
                      >
                        {key.replace(/_/g, " ")}{" "}
                        {typeof value === "number" ? `· ${value.toFixed(2)}` : ""}
                      </span>
                    ))}
                </div>
              )}
              {hints.length > 0 && (
                <div className="mt-2">
                  <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-2">
                    Recent teaching hints
                  </div>
                  <ul className="pl-4 space-y-1 text-sm text-on-surface-variant">
                    {hints.slice(-3).map((hint, i) => (
                      <li key={i}>{hint}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ) : (
          <p className="font-body text-sm text-on-surface-variant">
            No learning profile yet. This student has not completed any tracked sessions.
          </p>
        )}
      </section>

      <section className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
        <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
          Topic mastery
        </div>
        <TopicGraph
          nodes={mastery}
          edges={view.topic_edges}
          onSelect={onSelectTopic}
          selected={selectedTopic ?? null}
        />
      </section>

      <section className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
        <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
          Recent focus
        </div>
        <FocusTimeline entries={view.recent_focus} />
      </section>

      {narrative.length > 0 && (
        <section className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
          <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
            Narrative notes
          </div>
          <ul className="pl-4 space-y-2 text-sm text-on-surface leading-relaxed">
            {narrative.map((entry, i) => (
              <li key={i}>
                <span className="font-body text-xs text-outline">
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
    <section className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
      <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
        Learning style
      </div>
      {profile ? (
        <>
          <div className="flex justify-center mt-2">
            <StyleRadar vector={profile.style_vector} size={200} />
          </div>
          <div className="flex flex-wrap gap-2 my-3 justify-center">
            {profile.last_focus_label && (
              <span
                className="font-body text-xs font-semibold px-3 py-1 rounded-full"
                style={{
                  background: `color-mix(in srgb, ${focusLabelColor(profile.last_focus_label)} 18%, white)`,
                  color: focusLabelColor(profile.last_focus_label),
                }}
              >
                {profile.last_focus_label}
              </span>
            )}
            <span className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-surface-container-low text-on-surface-variant">
              focus {profile.rolling_focus_score.toFixed(2)}
            </span>
            <span className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-surface-container-low text-on-surface-variant">
              {Math.round(profile.rolling_reading_speed_wpm)} wpm
            </span>
          </div>
          {topMastery.length > 0 && (
            <>
              <div className="h-px bg-surface-dim my-4" />
              <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-3">
                Top topics
              </div>
              <ul className="space-y-2">
                {topMastery.map((node) => (
                  <li key={node.topic} className="flex items-center gap-3 text-sm">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ background: masteryColor(node.mastery_score) }}
                    />
                    <span className="flex-1 truncate text-on-surface">{node.topic}</span>
                    <span className="font-body text-xs text-on-surface-variant">
                      {(node.mastery_score * 10).toFixed(1)}/10
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {hints.length > 0 && (
            <>
              <div className="h-px bg-surface-dim my-4" />
              <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-2">
                Teaching hints
              </div>
              <ul className="pl-4 space-y-1 text-xs text-on-surface-variant">
                {hints.map((hint, i) => (
                  <li key={i}>{hint}</li>
                ))}
              </ul>
            </>
          )}
        </>
      ) : (
        <p className="font-body text-sm text-on-surface-variant">
          Student hasn't completed any tracked sessions yet — scores on the right use defaults.
        </p>
      )}
    </section>
  );
}
