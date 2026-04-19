"use client";

import { DragEvent, useState } from "react";
import { LessonPlanCandidate, LessonPlanNode } from "@/lib/api";
import { AssetCard } from "./AssetCard";
import MaterialIcon from "@/components/ui/MaterialIcon";

type PlanNode = {
  asset_id: number;
  order_index: number;
  teacher_adjusted?: boolean;
  label?: string | null;
  notes?: string | null;
};

type Props = {
  nodes: LessonPlanNode[];
  candidates: LessonPlanCandidate[];
  onChange: (nodes: PlanNode[]) => Promise<void> | void;
  onPreviewAsset?: (asset: LessonPlanNode["asset"], fitScore?: number | null, rationale?: string | null) => void;
};

export function PlanCanvas({ nodes, candidates, onChange, onPreviewAsset }: Props) {
  const [draggingIndex, setDraggingIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const [dropHover, setDropHover] = useState(false);

  const assetLookup = new Map(candidates.map((c) => [c.asset.id, c]));

  async function handleDropFromPalette(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDropHover(false);
    const raw = event.dataTransfer.getData("application/x-lesson-asset");
    if (!raw) return;
    const assetId = Number(raw);
    if (nodes.some((node) => node.asset_id === assetId)) return;
    const next: PlanNode[] = [
      ...nodes.map((node, i) => ({
        asset_id: node.asset_id,
        order_index: i,
        teacher_adjusted: true,
        label: node.label,
        notes: node.notes,
      })),
      { asset_id: assetId, order_index: nodes.length, teacher_adjusted: true },
    ];
    await onChange(next);
  }

  function allowDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  }

  async function handleReorder(sourceIndex: number, targetIndex: number) {
    if (sourceIndex === targetIndex) return;
    const reordered = [...nodes];
    const [moved] = reordered.splice(sourceIndex, 1);
    reordered.splice(targetIndex, 0, moved);
    await onChange(
      reordered.map((node, i) => ({
        asset_id: node.asset_id,
        order_index: i,
        teacher_adjusted: true,
        label: node.label,
        notes: node.notes,
      }))
    );
  }

  async function handleRemove(assetId: number) {
    const filtered = nodes.filter((node) => node.asset_id !== assetId);
    await onChange(
      filtered.map((node, i) => ({
        asset_id: node.asset_id,
        order_index: i,
        teacher_adjusted: true,
        label: node.label,
        notes: node.notes,
      }))
    );
  }

  const empty = nodes.length === 0;

  return (
    <div
      className={`bg-surface-container-lowest rounded-[32px] border-2 transition-all duration-200 ${
        dropHover ? "border-primary/40 bg-primary-fixed/5" : "border-surface-dim/20"
      }`}
      style={{ minHeight: 320 }}
      onDragOver={(e) => { allowDrop(e); setDropHover(true); }}
      onDragLeave={() => setDropHover(false)}
      onDrop={handleDropFromPalette}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-8 pt-8 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary text-on-primary flex items-center justify-center">
            <MaterialIcon name="view_timeline" className="text-lg" />
          </div>
          <div>
            <h3 className="font-headline text-xl text-primary font-medium">Your lesson plan</h3>
            <p className="font-body text-xs text-on-surface-variant">
              {nodes.length} {nodes.length === 1 ? "card" : "cards"} · drag to reorder
            </p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-8 pb-8">
        {empty ? (
          <div className={`border-2 border-dashed rounded-2xl p-12 text-center transition-colors ${
            dropHover ? "border-primary/40 bg-primary-fixed/10" : "border-surface-dim bg-surface-container-low/50"
          }`}>
            <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4">
              <MaterialIcon name="add_circle" className="text-3xl text-on-surface-variant" />
            </div>
            <p className="font-headline text-lg text-on-surface font-medium mb-2">
              Drop cards here
            </p>
            <p className="font-body text-sm text-on-surface-variant max-w-md mx-auto">
              Drag a reading, video, or quiz from the suggestions panel on the right to start building this lesson.
            </p>
          </div>
        ) : (
          <ol className="space-y-3">
            {nodes.map((node, index) => {
              const candidate = assetLookup.get(node.asset_id) || null;
              const asset = node.asset || candidate?.asset;
              if (!asset) return null;
              const isOver = overIndex === index;
              const isDragging = draggingIndex === index;
              return (
                <li
                  key={`${node.asset_id}-${index}`}
                  draggable
                  onDragStart={(e) => {
                    setDraggingIndex(index);
                    e.dataTransfer.effectAllowed = "move";
                    e.dataTransfer.setData("application/x-lesson-asset-reorder", String(index));
                  }}
                  onDragEnd={() => {
                    setDraggingIndex(null);
                    setOverIndex(null);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    if (draggingIndex !== null) setOverIndex(index);
                  }}
                  onDragLeave={() => setOverIndex(null)}
                  onDrop={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (draggingIndex !== null) {
                      handleReorder(draggingIndex, index);
                    }
                    setDraggingIndex(null);
                    setOverIndex(null);
                  }}
                  className={`flex items-stretch gap-3 rounded-2xl transition-all duration-200 ${
                    isOver ? "ring-2 ring-primary/40 ring-offset-2 ring-offset-background" : ""
                  } ${isDragging ? "opacity-50 scale-[0.98]" : ""}`}
                >
                  {/* Drag handle + number */}
                  <div
                    className="w-10 flex flex-col items-center justify-center flex-shrink-0 select-none cursor-grab active:cursor-grabbing"
                    aria-hidden
                  >
                    <div className="w-8 h-8 rounded-lg bg-surface-container-high flex items-center justify-center mb-1">
                      <span className="font-headline text-sm font-bold text-primary">{index + 1}</span>
                    </div>
                    <MaterialIcon name="drag_indicator" className="text-sm text-outline" />
                  </div>

                  {/* Card */}
                  <div className="flex-1 min-w-0">
                    <AssetCard
                      asset={asset}
                      fitScore={node.fit_score ?? candidate?.fit_score ?? 0}
                      rationale={node.rationale ?? candidate?.rationale ?? undefined}
                      components={candidate?.components}
                      onRemove={() => handleRemove(node.asset_id)}
                      onPreview={
                        onPreviewAsset
                          ? () =>
                              onPreviewAsset(
                                asset,
                                node.fit_score ?? candidate?.fit_score ?? null,
                                node.rationale ?? candidate?.rationale ?? null
                              )
                          : undefined
                      }
                    />
                  </div>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
