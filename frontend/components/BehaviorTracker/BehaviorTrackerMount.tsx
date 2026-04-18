"use client";

import { RefObject, useEffect } from "react";
import { api, getStoredAuth } from "@/lib/api";
import { BehaviorTracker } from "@/lib/tracker";

export function BehaviorTrackerMount({
  materialId,
  rootRef,
  onSession,
  onStatus
}: {
  materialId: number;
  rootRef: RefObject<HTMLElement>;
  onSession: (sessionId: number | null) => void;
  onStatus: (status: string) => void;
}) {
  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth || auth.user.role !== "student" || !rootRef.current) return;
    let tracker: BehaviorTracker | null = null;
    let activeSession: number | null = null;

    api
      .startSession(materialId)
      .then(session => {
        activeSession = session.session_id;
        onSession(session.session_id);
        tracker = new BehaviorTracker(session.session_id, auth.access_token, rootRef.current as HTMLElement);
        tracker.start();
        onStatus("Session tracking is active.");
      })
      .catch((error: Error) => onStatus(error.message));

    const finish = () => {
      tracker?.stop();
      if (activeSession) void api.endSession(activeSession).catch(() => undefined);
    };
    window.addEventListener("beforeunload", finish);
    return () => {
      window.removeEventListener("beforeunload", finish);
      finish();
    };
  }, [materialId, onSession, onStatus, rootRef]);

  return null;
}
