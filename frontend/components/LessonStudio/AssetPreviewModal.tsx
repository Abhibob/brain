"use client";

import { useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LessonAsset } from "@/lib/api";
import { fitRingClass, fitTen } from "@/lib/scores";

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
  const ringClass = fitRingClass(fitScore ?? 0);
  const pct = Math.max(0, Math.min(100, fitScore ?? 0));

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.55)",
        backdropFilter: "blur(6px)",
        display: "grid",
        placeItems: "center",
        padding: 24,
        zIndex: 50
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="card"
        style={{
          width: "min(780px, 100%)",
          maxHeight: "86vh",
          overflow: "auto",
          padding: 0,
          boxShadow: "var(--shadow-card)"
        }}
      >
        <div
          style={{
            padding: "18px 22px",
            borderBottom: "1px solid var(--line)",
            display: "flex",
            alignItems: "center",
            gap: 14,
            position: "sticky",
            top: 0,
            background: "var(--surface)",
            zIndex: 1
          }}
        >
          <div className={`score-ring ${ringClass}`} style={{ ["--pct" as any]: pct, width: 48, height: 48 }}>
            <span className="score-ring__value" style={{ fontSize: 12 }}>
              {ten.toFixed(1)}
              <span>/10</span>
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
              <span className="chip">{asset.kind}</span>
              {asset.generated_by === "source" && <span className="chip chip--accent">in current lesson</span>}
              {asset.generated_by === "youtube" && <span className="chip chip--highlight">YouTube</span>}
            </div>
            <h3 style={{ margin: 0, fontSize: 18, letterSpacing: "-0.02em" }}>{asset.title}</h3>
            {rationale && (
              <div className="muted" style={{ fontSize: 12 }}>
                {rationale}
              </div>
            )}
          </div>
          <button className="button ghost" onClick={onClose} style={{ fontSize: 18, padding: "4px 10px", minHeight: 32 }}>
            ×
          </button>
        </div>
        <div style={{ padding: "18px 22px 24px" }}>
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
      <div style={{ display: "grid", gap: 12 }}>
        {videoId ? (
          <div
            style={{
              position: "relative",
              paddingTop: "56.25%",
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              background: "#000",
              border: "1px solid var(--line)"
            }}
          >
            <iframe
              src={`https://www.youtube.com/embed/${videoId}`}
              title={asset.title}
              loading="lazy"
              referrerPolicy="strict-origin-when-cross-origin"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0 }}
            />
          </div>
        ) : (
          <p className="muted">No embed available. {url && <a href={url} target="_blank" rel="noreferrer">Open on YouTube ↗</a>}</p>
        )}
        {description && <p style={{ margin: 0, fontSize: 14, color: "var(--ink-soft)" }}>{description}</p>}
      </div>
    );
  }

  if (asset.kind === "quiz") {
    const questions: Array<Record<string, any>> = asset.payload?.questions ?? [];
    if (questions.length === 0) return <p className="muted">No questions in this quiz.</p>;
    return (
      <ol style={{ display: "grid", gap: 14, padding: 0, margin: 0, listStyle: "none" }}>
        {questions.map((q, i) => (
          <li key={i} className="card card--flat" style={{ padding: 14 }}>
            <div style={{ fontSize: 13, color: "var(--ink-faint)", marginBottom: 4 }}>Question {i + 1}</div>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>{q.question}</div>
            <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 6 }}>
              {(q.options || []).map((opt: string) => {
                const isCorrect = opt === q.correct_answer;
                return (
                  <li
                    key={opt}
                    style={{
                      padding: "8px 12px",
                      borderRadius: "var(--radius-md)",
                      border: "1px solid var(--line)",
                      background: isCorrect ? "var(--success-soft)" : "var(--surface)",
                      color: isCorrect ? "var(--success)" : "var(--ink)",
                      fontSize: 14,
                      display: "flex",
                      alignItems: "center",
                      gap: 8
                    }}
                  >
                    {isCorrect && <span style={{ fontSize: 13 }}>✓</span>}
                    {opt}
                  </li>
                );
              })}
            </ul>
            {q.hint && (
              <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>
                Hint: {q.hint}
              </div>
            )}
          </li>
        ))}
      </ol>
    );
  }

  if (asset.kind === "practice") {
    const problems: Array<Record<string, any>> = asset.payload?.problems ?? [];
    return (
      <ol style={{ display: "grid", gap: 12, padding: 0, margin: 0, listStyle: "none" }}>
        {problems.map((p, i) => (
          <li key={i} className="card card--flat" style={{ padding: 14 }}>
            <div style={{ fontWeight: 600 }}>{p.prompt}</div>
            {p.hint && (
              <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
                Hint: {p.hint}
              </div>
            )}
          </li>
        ))}
      </ol>
    );
  }

  return <pre style={{ fontSize: 12 }}>{JSON.stringify(asset.payload, null, 2)}</pre>;
}
