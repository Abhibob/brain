"use client";

import { DragEvent, ReactNode, useState } from "react";
import { LessonAsset } from "@/lib/api";
import { fitRingClass, fitTen } from "@/lib/scores";

type Kind = LessonAsset["kind"];

const KIND_LABEL: Record<Kind, string> = {
  reading: "Reading",
  quiz: "Quiz",
  video: "Video",
  practice: "Practice"
};

const KIND_CHIP: Record<Kind, string> = {
  reading: "chip chip--accent",
  quiz: "chip chip--warning",
  video: "chip chip--highlight",
  practice: "chip"
};

type Props = {
  asset: LessonAsset;
  fitScore?: number | null;
  rationale?: string;
  components?: Record<string, number>;
  draggable?: boolean;
  onDragStart?: (event: DragEvent<HTMLDivElement>) => void;
  onRemove?: () => void;
  onPreview?: () => void;
  showWhy?: boolean;
  actions?: ReactNode;
  compact?: boolean;
};

export function AssetCard({
  asset,
  fitScore,
  rationale,
  components,
  draggable,
  onDragStart,
  onRemove,
  onPreview,
  showWhy = true,
  actions,
  compact = false
}: Props) {
  const [open, setOpen] = useState(false);
  const ten = fitTen(fitScore ?? 0);
  const ringClass = fitRingClass(fitScore ?? 0);
  const pct = Math.max(0, Math.min(100, fitScore ?? 0));

  return (
    <div
      className="card card--flat"
      draggable={draggable}
      onDragStart={onDragStart}
      style={{
        padding: compact ? 14 : 18,
        cursor: draggable ? "grab" : onPreview ? "pointer" : "default",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        transition: "transform 150ms var(--ease), box-shadow 150ms var(--ease)"
      }}
      onClick={e => {
        if (!onPreview) return;
        // Don't open the modal when clicking the remove button or any interactive child.
        const target = e.target as HTMLElement;
        if (target.closest("button") || target.closest("a") || target.closest("details")) return;
        onPreview();
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div className={`score-ring ${ringClass}`} style={{ ["--pct" as any]: pct }}>
          <span className="score-ring__value">
            {ten.toFixed(1)}
            <span>/10</span>
          </span>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span className={KIND_CHIP[asset.kind]}>{KIND_LABEL[asset.kind]}</span>
            {asset.generated_by === "youtube" && <span className="chip">YouTube</span>}
          </div>
          <div
            style={{
              fontWeight: 600,
              fontSize: 15,
              color: "var(--ink)",
              lineHeight: 1.3,
              overflow: "hidden",
              textOverflow: "ellipsis",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical"
            }}
          >
            {asset.title}
          </div>
          {rationale && (
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
              {rationale}
            </div>
          )}
        </div>
        {onRemove && (
          <button
            type="button"
            className="button ghost"
            onClick={onRemove}
            aria-label="Remove from lesson"
            style={{ padding: "6px 10px", minHeight: 32, fontSize: 18, lineHeight: 1 }}
          >
            ×
          </button>
        )}
      </div>

      {asset.kind === "video" && asset.external_url && (
        <a
          href={asset.external_url}
          target="_blank"
          rel="noreferrer"
          className="muted"
          style={{ fontSize: 12, textDecoration: "underline" }}
        >
          Open on YouTube ↗
        </a>
      )}

      {showWhy && components && Object.keys(components).length > 0 && (
        <details
          open={open}
          onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}
          style={{ marginTop: 2 }}
        >
          <summary style={{ cursor: "pointer", fontSize: 12, color: "var(--ink-soft)", userSelect: "none" }}>
            Why this fits
          </summary>
          <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
            {Object.entries(components).map(([name, value]) => {
              const v = Math.max(0, Math.min(1, value));
              return (
                <div key={name} style={{ display: "grid", gridTemplateColumns: "100px 1fr 36px", gap: 8, alignItems: "center", fontSize: 12 }}>
                  <span className="muted">{name.replace(/_/g, " ")}</span>
                  <div style={{ height: 6, background: "var(--line)", borderRadius: 999, overflow: "hidden" }}>
                    <div
                      style={{
                        width: `${v * 100}%`,
                        height: "100%",
                        background: "linear-gradient(90deg, var(--accent) 0%, var(--highlight) 100%)"
                      }}
                    />
                  </div>
                  <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums", color: "var(--ink-soft)" }}>
                    {v.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>
        </details>
      )}

      {actions && <div className="toolbar" style={{ marginTop: 4 }}>{actions}</div>}
    </div>
  );
}
