"use client";

import { DragEvent, useState } from "react";
import { LessonPlanCandidate } from "@/lib/api";
import { AssetCard } from "./AssetCard";

type Props = {
  candidates: LessonPlanCandidate[];
  usedAssetIds?: Set<number>;
  onRegenerate?: () => void;
  onPreviewAsset?: (candidate: LessonPlanCandidate) => void;
  busy?: boolean;
};

const KIND_ORDER = ["reading", "video", "quiz", "practice"] as const;
type Kind = (typeof KIND_ORDER)[number];
const KIND_LABEL: Record<Kind, string> = {
  reading: "Readings",
  video: "Videos",
  quiz: "Quizzes",
  practice: "Practice"
};

export function AssetPalette({ candidates, usedAssetIds, onRegenerate, onPreviewAsset, busy }: Props) {
  const [filter, setFilter] = useState<Kind | "all">("all");

  const counts: Record<Kind, number> = { reading: 0, video: 0, quiz: 0, practice: 0 };
  for (const c of candidates) {
    counts[c.asset.kind as Kind] = (counts[c.asset.kind as Kind] ?? 0) + 1;
  }

  const sorted = [...candidates].sort((a, b) => b.fit_score - a.fit_score);
  const visible = sorted.filter(c => filter === "all" || c.asset.kind === filter);

  function handleDragStart(event: DragEvent<HTMLDivElement>, candidate: LessonPlanCandidate) {
    event.dataTransfer.setData("application/x-lesson-asset", String(candidate.asset.id));
    event.dataTransfer.effectAllowed = "copy";
  }

  return (
    <section className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        <h3 style={{ margin: 0, fontSize: 16, letterSpacing: "-0.02em" }}>Suggestions</h3>
        {onRegenerate && (
          <button className="button ghost" onClick={onRegenerate} disabled={busy} style={{ fontSize: 13 }}>
            {busy ? "Regenerating…" : "↻ Regenerate"}
          </button>
        )}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={filter === "all" ? "chip chip--active" : "chip"}
          style={{ cursor: "pointer", border: "none" }}
        >
          All · {candidates.length}
        </button>
        {KIND_ORDER.map(kind => (
          <button
            key={kind}
            type="button"
            onClick={() => setFilter(kind)}
            className={filter === kind ? "chip chip--active" : "chip"}
            style={{ cursor: "pointer", border: "none" }}
          >
            {KIND_LABEL[kind]} · {counts[kind] ?? 0}
          </button>
        ))}
      </div>
      <div style={{ display: "grid", gap: 10, maxHeight: 620, overflowY: "auto", paddingRight: 4 }}>
        {visible.length === 0 ? (
          <p className="muted" style={{ fontSize: 13 }}>
            No suggestions in this lane. Try another filter or regenerate.
          </p>
        ) : (
          visible.map(candidate => {
            const isUsed = usedAssetIds?.has(candidate.asset.id);
            return (
              <div
                key={candidate.asset.id}
                style={{ opacity: isUsed ? 0.45 : 1, filter: isUsed ? "grayscale(0.4)" : "none" }}
                title={isUsed ? "Already in your lesson" : undefined}
              >
                <AssetCard
                  asset={candidate.asset}
                  fitScore={candidate.fit_score}
                  rationale={candidate.rationale}
                  components={candidate.components}
                  draggable={!isUsed}
                  onDragStart={e => handleDragStart(e, candidate)}
                  onPreview={onPreviewAsset ? () => onPreviewAsset(candidate) : undefined}
                  compact
                />
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
