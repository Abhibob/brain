"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BehaviorTrackerMount } from "@/components/BehaviorTracker/BehaviorTrackerMount";
import { api, MaterialOut } from "@/lib/api";

function MarkdownBlock({ content }: { content: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
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
        <span className="muted">Lesson loaded.</span>
        {sessionId ? <span className="muted">Session #{sessionId}</span> : null}
        <button className="button secondary" onClick={endSession} disabled={!sessionId || ended}>
          Finish reading
        </button>
        <Link className="button" href={`/classes/${material.class_id}/materials/${material.id}/quiz`}>
          Take quiz
        </Link>
      </div>
      <p className="muted">{status}</p>
      {material.generated_content ? (
        <section className="lesson-section" data-section-id={`personalized-${material.id}`}>
          <MarkdownBlock content={material.generated_content} />
        </section>
      ) : (
        material.sections.map(section => (
          <section className="lesson-section" data-section-id={section.id} key={section.id}>
            <h2>{section.title}</h2>
            <p>{section.content}</p>
          </section>
        ))
      )}
    </div>
  );
}
