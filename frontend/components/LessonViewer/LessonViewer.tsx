"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BehaviorTrackerMount } from "@/components/BehaviorTracker/BehaviorTrackerMount";
import { api, MaterialOut, SectionOut } from "@/lib/api";
import MaterialIcon from "@/components/ui/MaterialIcon";

const GazeTrackerMount = dynamic(
  () => import("@/components/GazeTracker/GazeTrackerMount").then(m => m.GazeTrackerMount),
  { ssr: false }
);

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

const ENDED_KEY_PREFIX = "edutrack.lesson-ended.";

function readEndedFlag(materialId: number): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(`${ENDED_KEY_PREFIX}${materialId}`) === "1";
  } catch {
    return false;
  }
}

function writeEndedFlag(materialId: number, value: boolean) {
  if (typeof window === "undefined") return;
  try {
    const key = `${ENDED_KEY_PREFIX}${materialId}`;
    if (value) window.sessionStorage.setItem(key, "1");
    else window.sessionStorage.removeItem(key);
  } catch {}
}

export function LessonViewer({ material }: { material: MaterialOut }) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [ended, setEnded] = useState(false);
  const [hydratedEnded, setHydratedEnded] = useState(false);
  const [status, setStatus] = useState("Tracking is ready.");
  const [debugGaze, setDebugGaze] = useState(false);
  const handleSession = useCallback((id: number | null) => setSessionId(id), []);
  const handleStatus = useCallback((nextStatus: string) => setStatus(nextStatus), []);

  // Hydrate "already finished" flag so the camera doesn't auto-restart when
  // the student navigates back here from the quiz page within the same tab.
  useEffect(() => {
    if (typeof window === "undefined") {
      setHydratedEnded(true);
      return;
    }
    const params = new URLSearchParams(window.location.search);
    setDebugGaze(params.get("debug_gaze") === "1");
    if (readEndedFlag(material.id)) {
      setEnded(true);
      setStatus("You already finished this lesson. Tracking is paused.");
    }
    setHydratedEnded(true);
  }, [material.id]);

  async function endSession() {
    if (!sessionId || ended) return;
    await api.endSession(sessionId);
    writeEndedFlag(material.id, true);
    setEnded(true);
    setStatus("Session saved.");
  }

  function reopenSession() {
    writeEndedFlag(material.id, false);
    setEnded(false);
    setSessionId(null);
    setStatus("Starting a fresh reading session…");
  }

  return (
    <div className="space-y-8" ref={rootRef}>
      {hydratedEnded && !ended && (
        <GazeTrackerMount sessionId={sessionId} rootRef={rootRef} debug={debugGaze} />
      )}
      {!ended && (
        <BehaviorTrackerMount
          materialId={material.id}
          rootRef={rootRef}
          onSession={handleSession}
          onStatus={handleStatus}
        />
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 items-center">
        <span className="font-body text-xs font-semibold px-4 py-2 rounded-full bg-surface-container-low text-on-surface-variant">
          Lesson loaded
        </span>
        {!ended && (
          <button
            className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm disabled:opacity-50"
            onClick={endSession}
            disabled={!sessionId}
          >
            Finish reading
          </button>
        )}
        {ended && (
          <button
            className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm"
            onClick={reopenSession}
          >
            Read again
          </button>
        )}
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
