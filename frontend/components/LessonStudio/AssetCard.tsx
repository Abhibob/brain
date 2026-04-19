"use client";

import { DragEvent, ReactNode, useState } from "react";
import { LessonAsset } from "@/lib/api";
import { fitTen } from "@/lib/scores";
import MaterialIcon from "@/components/ui/MaterialIcon";

type Kind = LessonAsset["kind"];

const KIND_LABEL: Record<Kind, string> = {
  reading: "Reading",
  quiz: "Quiz",
  video: "Video",
  practice: "Practice",
};

const KIND_ICON: Record<Kind, string> = {
  reading: "menu_book",
  quiz: "quiz",
  video: "play_circle",
  practice: "code",
};

const KIND_COLOR: Record<Kind, string> = {
  reading: "bg-primary-fixed text-on-primary-fixed",
  quiz: "bg-tertiary-fixed text-on-tertiary-fixed",
  video: "bg-secondary-container text-on-secondary-container",
  practice: "bg-surface-container-high text-on-surface-variant",
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
  compact = false,
}: Props) {
  const [open, setOpen] = useState(false);
  const ten = fitTen(fitScore ?? 0);
  const pct = Math.max(0, Math.min(100, fitScore ?? 0));
  const fitColor = ten >= 7.5 ? "bg-[#16a34a]" : ten >= 5 ? "bg-[#f59e0b]" : "bg-[#ba1a1a]";

  return (
    <div
      className={`bg-surface-container-lowest rounded-2xl border border-surface-dim/20 transition-all duration-200 ${
        draggable ? "cursor-grab active:cursor-grabbing hover:shadow-[0px_10px_30px_rgba(27,28,26,0.08)] hover:scale-[1.01]" : onPreview ? "cursor-pointer hover:bg-surface-container-low" : ""
      }`}
      draggable={draggable}
      onDragStart={onDragStart}
      style={{ padding: compact ? 14 : 18 }}
      onClick={(e) => {
        if (!onPreview) return;
        const target = e.target as HTMLElement;
        if (target.closest("button") || target.closest("a") || target.closest("details")) return;
        onPreview();
      }}
    >
      <div className="flex items-start gap-4">
        {/* Kind icon */}
        <div className={`w-10 h-10 rounded-xl ${KIND_COLOR[asset.kind]} flex items-center justify-center flex-shrink-0`}>
          <MaterialIcon name={KIND_ICON[asset.kind]} className="text-lg" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-body text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
              {KIND_LABEL[asset.kind]}
            </span>
            {asset.generated_by === "youtube" && (
              <span className="font-body text-[10px] font-semibold px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant">
                YouTube
              </span>
            )}
          </div>
          <div className="font-body font-semibold text-on-surface leading-snug line-clamp-2">
            {asset.title}
          </div>
          {rationale && (
            <div className="font-body text-xs text-on-surface-variant mt-1 line-clamp-1">
              {rationale}
            </div>
          )}

          {/* Fit score bar */}
          {fitScore != null && (
            <div className="flex items-center gap-3 mt-3">
              <div className="flex-1 h-1.5 bg-surface-dim rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${fitColor}`} style={{ width: `${pct}%` }} />
              </div>
              <span className="font-body text-xs font-bold text-on-surface tabular-nums w-12 text-right">
                {ten.toFixed(1)}/10
              </span>
            </div>
          )}
        </div>

        {/* Remove button */}
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Remove from lesson"
            className="w-8 h-8 rounded-full bg-surface-container-high hover:bg-error-container hover:text-error flex items-center justify-center transition-colors flex-shrink-0"
          >
            <MaterialIcon name="close" className="text-base" />
          </button>
        )}
      </div>

      {asset.kind === "video" && asset.external_url && (
        <a
          href={asset.external_url}
          target="_blank"
          rel="noreferrer"
          className="font-body text-xs text-primary hover:text-primary-container underline mt-2 inline-block"
        >
          Open on YouTube
        </a>
      )}

      {showWhy && components && Object.keys(components).length > 0 && (
        <details
          open={open}
          onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
          className="mt-3"
        >
          <summary className="cursor-pointer font-body text-xs text-on-surface-variant select-none flex items-center gap-1">
            <MaterialIcon name={open ? "expand_less" : "expand_more"} className="text-sm" />
            Why this fits
          </summary>
          <div className="mt-2 space-y-2 pl-5">
            {Object.entries(components).map(([name, value]) => {
              const v = Math.max(0, Math.min(1, value));
              return (
                <div key={name} className="grid grid-cols-[100px_1fr_36px] gap-2 items-center text-xs">
                  <span className="font-body text-on-surface-variant truncate">{name.replace(/_/g, " ")}</span>
                  <div className="h-1.5 bg-surface-dim rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-primary to-primary-container"
                      style={{ width: `${v * 100}%` }}
                    />
                  </div>
                  <span className="text-right tabular-nums text-on-surface-variant">{v.toFixed(2)}</span>
                </div>
              );
            })}
          </div>
        </details>
      )}

      {actions && <div className="flex flex-wrap gap-2 mt-3">{actions}</div>}
    </div>
  );
}
