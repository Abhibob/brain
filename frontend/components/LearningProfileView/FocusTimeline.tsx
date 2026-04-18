"use client";

import { focusLabelColor } from "@/lib/scores";

type FocusEntry = {
  session_id: number;
  material_id: number;
  focus_score: number;
  focus_label: string;
  ended_at: string | null;
};

const LEGEND = [
  { label: "focused" },
  { label: "engaged" },
  { label: "distracted" },
  { label: "skimming" },
  { label: "abandoned" }
];

export function FocusTimeline({ entries }: { entries: FocusEntry[] }) {
  if (!entries.length) {
    return <p className="muted" style={{ margin: 0 }}>No recent sessions yet.</p>;
  }
  const ordered = [...entries].reverse();
  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div
        style={{
          display: "flex",
          alignItems: "end",
          gap: 8,
          height: 96,
          padding: "4px 0",
          borderBottom: "1px solid var(--line)"
        }}
      >
        {ordered.map(entry => {
          const height = Math.max(14, Math.round(entry.focus_score * 86));
          return (
            <div
              key={entry.session_id}
              title={`${entry.focus_label} · ${entry.focus_score.toFixed(2)}${
                entry.ended_at ? ` (${new Date(entry.ended_at).toLocaleString()})` : ""
              }`}
              style={{
                height,
                width: 24,
                background: `linear-gradient(180deg, ${focusLabelColor(entry.focus_label)} 0%, color-mix(in srgb, ${focusLabelColor(entry.focus_label)} 65%, transparent) 100%)`,
                borderRadius: 6,
                transition: "transform 150ms var(--ease)",
                cursor: "default"
              }}
            />
          );
        })}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, fontSize: 12, color: "var(--ink-soft)" }}>
        {LEGEND.map(item => (
          <span key={item.label} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 3,
                background: focusLabelColor(item.label)
              }}
            />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
