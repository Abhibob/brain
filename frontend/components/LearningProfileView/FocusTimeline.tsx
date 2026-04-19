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
  { label: "abandoned" },
];

export function FocusTimeline({ entries }: { entries: FocusEntry[] }) {
  if (!entries.length) {
    return <p className="font-body text-sm text-on-surface-variant">No recent sessions yet.</p>;
  }
  const ordered = [...entries].reverse();
  return (
    <div className="space-y-4">
      <div className="flex items-end gap-2 h-24 pb-1 border-b border-surface-dim">
        {ordered.map((entry) => {
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
                transition: "transform 150ms ease",
                cursor: "default",
              }}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-3 text-xs text-on-surface-variant">
        {LEGEND.map((item) => (
          <span key={item.label} className="inline-flex items-center gap-1.5">
            <span
              className="w-2.5 h-2.5 rounded-sm"
              style={{ background: focusLabelColor(item.label) }}
            />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
