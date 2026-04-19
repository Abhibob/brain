"use client";

import { useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LessonAsset } from "@/lib/api";
import { fitTen } from "@/lib/scores";
import MaterialIcon from "@/components/ui/MaterialIcon";

const KIND_ICON: Record<string, string> = {
  reading: "menu_book",
  quiz: "quiz",
  video: "play_circle",
  practice: "code",
};

type Props = {
  asset: LessonAsset;
  fitScore?: number | null;
  rationale?: string | null;
  onClose: () => void;
};

export function AssetPreviewModal({ asset, fitScore, rationale, onClose }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const ten = fitTen(fitScore ?? 0);
  const pct = Math.max(0, Math.min(100, fitScore ?? 0));
  const fitColor = ten >= 7.5 ? "bg-[#16a34a]" : ten >= 5 ? "bg-[#f59e0b]" : "bg-[#ba1a1a]";

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 bg-on-surface/40 backdrop-blur-md grid place-items-center p-6 z-50"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-surface-container-lowest rounded-[32px] border border-surface-dim/20 shadow-[0px_20px_60px_rgba(27,28,26,0.2)] w-full max-w-[780px] max-h-[86vh] overflow-auto"
      >
        {/* Header */}
        <div className="sticky top-0 z-10 bg-surface-container-lowest rounded-t-[32px] px-8 py-6 border-b border-surface-dim/20 flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-primary-fixed text-on-primary-fixed flex items-center justify-center flex-shrink-0">
            <MaterialIcon name={KIND_ICON[asset.kind] || "description"} className="text-xl" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-body text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
                {asset.kind}
              </span>
              {asset.generated_by === "source" && (
                <span className="font-body text-[10px] font-semibold px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed">
                  in current lesson
                </span>
              )}
              {asset.generated_by === "youtube" && (
                <span className="font-body text-[10px] font-semibold px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container">
                  YouTube
                </span>
              )}
            </div>
            <h3 className="font-headline text-xl text-primary font-medium tracking-[-0.02em]">
              {asset.title}
            </h3>
            {rationale && (
              <p className="font-body text-xs text-on-surface-variant mt-1">{rationale}</p>
            )}
            {fitScore != null && (
              <div className="flex items-center gap-3 mt-3">
                <div className="flex-1 h-1.5 bg-surface-dim rounded-full overflow-hidden max-w-[200px]">
                  <div className={`h-full rounded-full ${fitColor}`} style={{ width: `${pct}%` }} />
                </div>
                <span className="font-body text-xs font-bold text-on-surface tabular-nums">
                  {ten.toFixed(1)}/10
                </span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-full bg-surface-container-high hover:bg-surface-dim flex items-center justify-center transition-colors flex-shrink-0"
          >
            <MaterialIcon name="close" className="text-lg text-on-surface" />
          </button>
        </div>

        {/* Body */}
        <div className="px-8 py-6">
          <PreviewBody asset={asset} />
        </div>
      </div>
    </div>
  );
}

function PreviewBody({ asset }: { asset: LessonAsset }) {
  if (asset.kind === "reading") {
    const content = String(asset.payload?.content ?? "");
    return (
      <div className="markdown">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content || "*(empty reading)*"}</ReactMarkdown>
      </div>
    );
  }

  if (asset.kind === "video") {
    const videoId = String(asset.payload?.video_id ?? "");
    const description = String(asset.payload?.description ?? "");
    const url = asset.external_url || String(asset.payload?.url ?? "");
    return (
      <div className="space-y-4">
        {videoId ? (
          <div className="relative pt-[56.25%] rounded-2xl overflow-hidden bg-black border border-surface-dim">
            <iframe
              src={`https://www.youtube.com/embed/${videoId}`}
              title={asset.title}
              loading="lazy"
              referrerPolicy="strict-origin-when-cross-origin"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              className="absolute inset-0 w-full h-full border-0"
            />
          </div>
        ) : (
          <p className="font-body text-on-surface-variant">
            No embed available.{" "}
            {url && (
              <a href={url} target="_blank" rel="noreferrer" className="text-primary underline">
                Open on YouTube
              </a>
            )}
          </p>
        )}
        {description && (
          <p className="font-body text-sm text-on-surface-variant">{description}</p>
        )}
      </div>
    );
  }

  if (asset.kind === "quiz") {
    const questions: Array<Record<string, any>> = asset.payload?.questions ?? [];
    if (questions.length === 0)
      return <p className="font-body text-on-surface-variant">No questions in this quiz.</p>;
    return (
      <ol className="space-y-4">
        {questions.map((q, i) => (
          <li
            key={i}
            className="bg-surface-container-low rounded-2xl p-5"
          >
            <div className="font-body text-xs text-outline mb-2">Question {i + 1}</div>
            <div className="font-body font-semibold text-on-surface mb-3">{q.question}</div>
            <ul className="space-y-2">
              {(q.options || []).map((opt: string) => {
                const isCorrect = opt === q.correct_answer;
                return (
                  <li
                    key={opt}
                    className={`px-4 py-3 rounded-xl text-sm font-body flex items-center gap-2 ${
                      isCorrect
                        ? "bg-[#dcfce7] text-[#16a34a] border border-[#16a34a]/20"
                        : "bg-surface border border-surface-dim/30 text-on-surface"
                    }`}
                  >
                    {isCorrect && <MaterialIcon name="check_circle" filled className="text-base" />}
                    {opt}
                  </li>
                );
              })}
            </ul>
            {q.hint && (
              <div className="font-body text-xs text-on-surface-variant mt-3">Hint: {q.hint}</div>
            )}
          </li>
        ))}
      </ol>
    );
  }

  if (asset.kind === "practice") {
    const problems: Array<Record<string, any>> = asset.payload?.problems ?? [];
    return (
      <ol className="space-y-3">
        {problems.map((p, i) => (
          <li key={i} className="bg-surface-container-low rounded-2xl p-5">
            <div className="font-body font-semibold text-on-surface">{p.prompt}</div>
            {p.hint && (
              <div className="font-body text-xs text-on-surface-variant mt-2">Hint: {p.hint}</div>
            )}
          </li>
        ))}
      </ol>
    );
  }

  return <pre className="text-xs overflow-auto">{JSON.stringify(asset.payload, null, 2)}</pre>;
}
