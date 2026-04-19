"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BehaviorTrackerMount } from "@/components/BehaviorTracker/BehaviorTrackerMount";
import { api, MaterialOut, SectionOut } from "@/lib/api";
import MaterialIcon from "@/components/ui/MaterialIcon";

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
    <div className="space-y-3">
      <div className="relative pt-[56.25%] rounded-2xl overflow-hidden bg-black border border-surface-dim shadow-[0px_10px_30px_rgba(27,28,26,0.1)]">
        <iframe
          src={`https://www.youtube.com/embed/${videoId}`}
          title={caption || "Lesson video"}
          loading="lazy"
          referrerPolicy="strict-origin-when-cross-origin"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
          allowFullScreen
          className="absolute inset-0 w-full h-full border-0"
        />
      </div>
      {caption && <p className="font-body text-sm text-on-surface-variant">{caption}</p>}
    </div>
  );
}

function SectionBlock({ section }: { section: SectionOut }) {
  const video = parseVideo(section.content);
  return (
    <section className="pb-8 border-b border-surface-dim/40" data-section-id={section.id}>
      <h2 className="font-headline text-2xl text-primary font-medium tracking-[-0.02em] mb-4">
        {section.title}
      </h2>
      {video ? (
        <VideoBlock videoId={video.videoId} caption={video.caption} />
      ) : (
        <MarkdownBlock content={section.content} />
      )}
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
    <div className="space-y-8" ref={rootRef}>
      <BehaviorTrackerMount
        materialId={material.id}
        rootRef={rootRef}
        onSession={handleSession}
        onStatus={handleStatus}
      />

      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 items-center">
        <span className="font-body text-xs font-semibold px-4 py-2 rounded-full bg-surface-container-low text-on-surface-variant">
          Lesson loaded
        </span>
        {sessionId && (
          <span className="font-body text-xs font-semibold px-4 py-2 rounded-full bg-primary-fixed text-on-primary-fixed">
            Session #{sessionId}
          </span>
        )}
        <button
          className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm"
          onClick={endSession}
          disabled={!sessionId || ended}
        >
          Finish reading
        </button>
        <Link
          className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm flex items-center gap-2"
          href={`/classes/${material.class_id}/materials/${material.id}/quiz`}
        >
          Take quiz
          <MaterialIcon name="arrow_forward" className="text-[16px]" />
        </Link>
      </div>

      <p className="font-body text-sm text-on-surface-variant">{status}</p>

      {material.generated_content ? (
        <section
          className="pb-8 border-b border-surface-dim/40"
          data-section-id={`personalized-${material.id}`}
        >
          <MarkdownBlock content={material.generated_content} />
        </section>
      ) : (
        material.sections.map((section) => <SectionBlock key={section.id} section={section} />)
      )}
    </div>
  );
}
