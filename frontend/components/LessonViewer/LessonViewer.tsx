"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BehaviorTrackerMount } from "@/components/BehaviorTracker/BehaviorTrackerMount";
import { api, MaterialOut, SectionOut } from "@/lib/api";

function MarkdownBlock({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

function parseVideo(content: string): { videoId: string; caption: string } | null {
  const match = content.match(/^YT::([A-Za-z0-9_-]+)(?:::([\s\S]*))?$/);
  if (!match) return null;
  return { videoId: match[1], caption: (match[2] ?? "").trim() };
}

function VideoBlock({ videoId, caption }: { videoId: string; caption: string }) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div
        style={{
          position: "relative",
          paddingTop: "56.25%",
          borderRadius: "var(--radius-lg)",
          overflow: "hidden",
          background: "#000",
          border: "1px solid var(--line)",
          boxShadow: "var(--shadow-md)"
        }}
      >
        <iframe
          src={`https://www.youtube.com/embed/${videoId}`}
          title={caption || "Lesson video"}
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0 }}
        />
      </div>
      {caption && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          {caption}
        </p>
      )}
    </div>
  );
}

function SectionBlock({ section }: { section: SectionOut }) {
  const video = parseVideo(section.content);
  return (
    <section className="lesson-section" data-section-id={section.id}>
      <h2 style={{ fontSize: 22, letterSpacing: "-0.02em", marginTop: 0 }}>{section.title}</h2>
      {video ? <VideoBlock videoId={video.videoId} caption={video.caption} /> : <MarkdownBlock content={section.content} />}
    </section>
  );
}

export function LessonViewer({ material }: { material: MaterialOut }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [ended, setEnded] = useState(false);
  const [status, setStatus] = useState("Tracking is ready.");
  const handleSession = useCallback((id: number | null) => setSessionId(id), []);
  const handleStatus = useCallback((nextStatus: string) => setStatus(nextStatus), []);

  async function endSession() {
    if (!sessionId || ended) return;
    await api.endSession(sessionId);
    setEnded(true);
    setStatus("Session saved.");
  }

  return (
    <div className="lesson" ref={rootRef}>
      <BehaviorTrackerMount materialId={material.id} rootRef={rootRef} onSession={handleSession} onStatus={handleStatus} />
      <div className="toolbar">
        <span className="chip">Lesson loaded</span>
        {sessionId ? <span className="chip chip--accent">Session #{sessionId}</span> : null}
        <button className="button secondary" onClick={endSession} disabled={!sessionId || ended}>
          Finish reading
        </button>
        <Link className="button" href={`/classes/${material.class_id}/materials/${material.id}/quiz`}>
          Take quiz
        </Link>
      </div>
      <p className="muted" style={{ fontSize: 13 }}>{status}</p>
      {material.generated_content ? (
        <section className="lesson-section" data-section-id={`personalized-${material.id}`}>
          <MarkdownBlock content={material.generated_content} />
        </section>
      ) : (
        material.sections.map(section => <SectionBlock key={section.id} section={section} />)
      )}
    </div>
  );
}
