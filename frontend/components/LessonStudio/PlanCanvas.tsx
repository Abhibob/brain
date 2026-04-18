"use client";

import { DragEvent, useState } from "react";
import { LessonPlanCandidate, LessonPlanNode } from "@/lib/api";
import { AssetCard } from "./AssetCard";

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

  const assetLookup = new Map(candidates.map(c => [c.asset.id, c]));

  async function handleDropFromPalette(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    const raw = event.dataTransfer.getData("application/x-lesson-asset");
    if (!raw) return;
    const assetId = Number(raw);
    if (nodes.some(node => node.asset_id === assetId)) return;
    const next: PlanNode[] = [
      ...nodes.map((node, i) => ({
        asset_id: node.asset_id,
        order_index: i,
        teacher_adjusted: true,
        label: node.label,
        notes: node.notes
      })),
      { asset_id: assetId, order_index: nodes.length, teacher_adjusted: true }
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
        notes: node.notes
      }))
    );
  }

  async function handleRemove(assetId: number) {
    const filtered = nodes.filter(node => node.asset_id !== assetId);
    await onChange(
      filtered.map((node, i) => ({
        asset_id: node.asset_id,
        order_index: i,
        teacher_adjusted: true,
        label: node.label,
        notes: node.notes
      }))
    );
  }

  const empty = nodes.length === 0;

  return (
    <div
      className="card"
      style={{ padding: 20, minHeight: 320 }}
      onDragOver={allowDrop}
      onDrop={handleDropFromPalette}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <h3 style={{ margin: 0, fontSize: 18, letterSpacing: "-0.02em" }}>Your lesson</h3>
        <span className="muted" style={{ fontSize: 12 }}>
          {nodes.length} {nodes.length === 1 ? "card" : "cards"}
        </span>
      </div>
      {empty ? (
        <div
          style={{
            border: "1.5px dashed var(--line-strong)",
            borderRadius: "var(--radius-lg)",
            padding: 36,
            textAlign: "center",
            color: "var(--ink-soft)",
            background: "var(--surface-muted)"
          }}
        >
          <strong style={{ color: "var(--ink)", display: "block", marginBottom: 6 }}>Drop cards here</strong>
          Drag a reading, video, or quiz from the suggestions panel to start building this lesson for your student.
        </div>
      ) : (
        <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
          {nodes.map((node, index) => {
            const candidate = assetLookup.get(node.asset_id) || null;
            const asset = node.asset || candidate?.asset;
            if (!asset) return null;
            const isOver = overIndex === index;
            return (
              <li
                key={`${node.asset_id}-${index}`}
                draggable
                onDragStart={e => {
                  setDraggingIndex(index);
                  e.dataTransfer.effectAllowed = "move";
                  e.dataTransfer.setData("application/x-lesson-asset-reorder", String(index));
                }}
                onDragEnd={() => {
                  setDraggingIndex(null);
                  setOverIndex(null);
                }}
                onDragOver={e => {
                  e.preventDefault();
                  if (draggingIndex !== null) setOverIndex(index);
                }}
                onDragLeave={() => setOverIndex(null)}
                onDrop={e => {
                  e.preventDefault();
                  if (draggingIndex !== null) {
                    handleReorder(draggingIndex, index);
                  }
                  setDraggingIndex(null);
                  setOverIndex(null);
                }}
                style={{
                  display: "flex",
                  alignItems: "stretch",
                  gap: 12,
                  borderRadius: "var(--radius-lg)",
                  outline: isOver ? "2px dashed var(--highlight)" : "none",
                  outlineOffset: 2
                }}
              >
                <div
                  style={{
                    width: 40,
                    display: "grid",
                    placeItems: "center",
                    color: "var(--ink-faint)",
                    flexShrink: 0,
                    userSelect: "none"
                  }}
                  aria-hidden
                >
                  <div style={{ fontWeight: 700, fontSize: 18, color: "var(--ink-soft)" }}>{index + 1}</div>
                  <div style={{ fontSize: 12, letterSpacing: 2, marginTop: 4 }}>⋮⋮</div>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
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
  );
}
