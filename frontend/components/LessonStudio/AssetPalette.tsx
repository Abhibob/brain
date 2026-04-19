"use client";

import { DragEvent, useState } from "react";
import { LessonPlanCandidate } from "@/lib/api";
import { AssetCard } from "./AssetCard";
import MaterialIcon from "@/components/ui/MaterialIcon";

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
  practice: "Practice",
};
const KIND_ICON: Record<Kind, string> = {
  reading: "menu_book",
  video: "play_circle",
  quiz: "quiz",
  practice: "code",
};

export function AssetPalette({ candidates, usedAssetIds, onRegenerate, onPreviewAsset, busy }: Props) {
  const [filter, setFilter] = useState<Kind | "all">("all");

  const counts: Record<Kind, number> = { reading: 0, video: 0, quiz: 0, practice: 0 };
  for (const c of candidates) {
    counts[c.asset.kind as Kind] = (counts[c.asset.kind as Kind] ?? 0) + 1;
  }

  const sorted = [...candidates].sort((a, b) => b.fit_score - a.fit_score);
  const visible = sorted.filter((c) => filter === "all" || c.asset.kind === filter);

  function handleDragStart(event: DragEvent<HTMLDivElement>, candidate: LessonPlanCandidate) {
    event.dataTransfer.setData("application/x-lesson-asset", String(candidate.asset.id));
    event.dataTransfer.effectAllowed = "copy";
  }

  return (
    <div className="bg-surface-container-lowest rounded-[32px] border border-surface-dim/20 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-6 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-secondary-container text-on-secondary-container flex items-center justify-center">
            <MaterialIcon name="auto_awesome" className="text-lg" />
          </div>
          <div>
            <h3 className="font-headline text-lg text-primary font-medium">Suggestions</h3>
            <p className="font-body text-xs text-on-surface-variant">{candidates.length} available</p>
          </div>
        </div>
        {onRegenerate && (
          <button
            className="w-9 h-9 rounded-full bg-surface-container-high hover:bg-surface-dim flex items-center justify-center transition-colors"
            onClick={onRegenerate}
            disabled={busy}
            title="Regenerate suggestions"
          >
            <MaterialIcon name="refresh" className={`text-lg text-on-surface-variant ${busy ? "animate-spin" : ""}`} />
          </button>
        )}
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1.5 px-6 pb-4 overflow-x-auto">
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={`font-body text-xs font-semibold px-3 py-1.5 rounded-full transition-colors whitespace-nowrap ${
            filter === "all"
              ? "bg-primary text-on-primary"
              : "bg-surface-container-high text-on-surface-variant hover:bg-surface-dim"
          }`}
        >
          All · {candidates.length}
        </button>
        {KIND_ORDER.map((kind) => (
          <button
            key={kind}
            type="button"
            onClick={() => setFilter(kind)}
            className={`font-body text-xs font-semibold px-3 py-1.5 rounded-full transition-colors whitespace-nowrap flex items-center gap-1.5 ${
              filter === kind
                ? "bg-primary text-on-primary"
                : "bg-surface-container-high text-on-surface-variant hover:bg-surface-dim"
            }`}
          >
            <MaterialIcon name={KIND_ICON[kind]} className="text-sm" />
            {KIND_LABEL[kind]} · {counts[kind] ?? 0}
          </button>
        ))}
      </div>

      {/* Card list */}
      <div className="flex-1 overflow-y-auto px-6 pb-6 space-y-3" style={{ maxHeight: 600 }}>
        {visible.length === 0 ? (
          <div className="text-center py-12">
            <MaterialIcon name="search_off" className="text-4xl text-outline mb-3 block mx-auto" />
            <p className="font-body text-sm text-on-surface-variant">
              No suggestions in this category.
            </p>
          </div>
        ) : (
          visible.map((candidate) => {
            const isUsed = usedAssetIds?.has(candidate.asset.id);
            return (
              <div
                key={candidate.asset.id}
                className={`transition-all duration-200 ${isUsed ? "opacity-40 grayscale-[40%]" : ""}`}
                title={isUsed ? "Already in your lesson" : "Drag to add to lesson"}
              >
                <AssetCard
                  asset={candidate.asset}
                  fitScore={candidate.fit_score}
                  rationale={candidate.rationale}
                  components={candidate.components}
                  draggable={!isUsed}
                  onDragStart={(e) => handleDragStart(e, candidate)}
                  onPreview={onPreviewAsset ? () => onPreviewAsset(candidate) : undefined}
                  compact
                />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
