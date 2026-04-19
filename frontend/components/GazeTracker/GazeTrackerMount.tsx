"use client";

import { RefObject, useEffect, useRef, useState } from "react";
import { getStoredAuth, wsUrl } from "@/lib/api";
import {
  CalibrationTransform,
  FixationDetector,
  GazeSample,
  GazeStatus,
  GazeTracker,
  attributeSection,
  clearCalibration,
  hasSeenNotice,
  loadCalibration,
  loadEnabled,
  markNoticeSeen,
  saveCalibration,
  saveEnabled,
} from "@/lib/gaze";
import { GazeCalibration } from "./GazeCalibration";

type Mode =
  | "booting"
  | "off"
  | "needs_calibration"
  | "calibrating"
  | "running"
  | "camera_denied";

const LOSS_THRESHOLD_MS = 1500;

export function GazeTrackerMount({
  sessionId,
  rootRef,
  debug = false,
}: {
  sessionId: number | null;
  rootRef: RefObject<HTMLElement>;
  debug?: boolean;
}) {
  const [mode, setMode] = useState<Mode>("booting");
  const [calibration, setCalibrationState] = useState<CalibrationTransform | null>(null);
  const [showNotice, setShowNotice] = useState(false);

  // Boot: read persisted state, auto-start if enabled.
  useEffect(() => {
    const enabled = loadEnabled();
    const cal = loadCalibration();
    setCalibrationState(cal);
    if (!enabled) {
      setMode("off");
      return;
    }
    if (!hasSeenNotice()) {
      setShowNotice(true);
      markNoticeSeen();
      const t = window.setTimeout(() => setShowNotice(false), 6000);
      return () => window.clearTimeout(t);
    }
    if (!cal) {
      setMode("needs_calibration");
    } else {
      setMode("running");
    }
  }, []);

  // Auto-launch calibration when we need it (no opt-in step).
  useEffect(() => {
    if (mode === "needs_calibration") {
      setMode("calibrating");
    }
  }, [mode]);

  function toggleEnabled(next: boolean) {
    saveEnabled(next);
    if (next) {
      const cal = loadCalibration();
      setCalibrationState(cal);
      setMode(cal ? "running" : "needs_calibration");
    } else {
      setMode("off");
    }
  }

  function handleRecalibrate() {
    clearCalibration();
    setCalibrationState(null);
    setMode("needs_calibration");
  }

  const trackerStatusRef = useRef<GazeStatus>("idle");

  return (
    <>
      {mode === "calibrating" && (
        <GazeCalibration
          onComplete={(transform) => {
            saveCalibration(transform);
            setCalibrationState(transform);
            setMode("running");
          }}
          onSkip={(reason) => {
            if (reason === "camera_denied") {
              setMode("camera_denied");
            } else {
              // User bailed out — leave enabled but skip calibration for this session.
              setMode("running");
            }
          }}
        />
      )}
      {mode === "running" && (
        <GazeRuntime
          calibration={calibration}
          sessionId={sessionId}
          rootRef={rootRef}
          debug={debug}
          onStatus={(s) => {
            trackerStatusRef.current = s;
            if (s === "denied") setMode("camera_denied");
          }}
        />
      )}
      <GazeStatusPill
        mode={mode}
        hasCalibration={!!calibration}
        onToggle={toggleEnabled}
        onRecalibrate={handleRecalibrate}
      />
      {showNotice && <NoticeBanner />}
    </>
  );
}

function NoticeBanner() {
  return (
    <div
      style={{
        position: "fixed",
        top: 16,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 10001,
        background: "linear-gradient(135deg, #0f7b66 0%, #095947 100%)",
        color: "#fff",
        padding: "12px 18px",
        borderRadius: 10,
        maxWidth: 460,
        boxShadow: "0 12px 32px rgba(0,0,0,0.3)",
        animation: "gaze-notice-in 260ms ease-out",
      }}
    >
      <style>{`@keyframes gaze-notice-in {
        from { opacity: 0; transform: translate(-50%, -10px); }
        to { opacity: 1; transform: translate(-50%, 0); }
      }`}</style>
      <div style={{ fontSize: 13.5, fontWeight: 600, letterSpacing: -0.2 }}>
        Eye tracking is active during lessons
      </div>
      <div style={{ fontSize: 12, opacity: 0.9, marginTop: 3, lineHeight: 1.5 }}>
        Your webcam is used to measure reading attention. Video stays in your browser. Toggle it off anytime using the chip in the corner.
      </div>
    </div>
  );
}

function GazeStatusPill({
  mode,
  hasCalibration,
  onToggle,
  onRecalibrate,
}: {
  mode: Mode;
  hasCalibration: boolean;
  onToggle: (next: boolean) => void;
  onRecalibrate: () => void;
}) {
  const enabled = mode !== "off" && mode !== "camera_denied";
  const { dotColor, label } = styleForMode(mode);

  return (
    <div
      style={{
        position: "fixed",
        bottom: 16,
        right: 16,
        zIndex: 10000,
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 12px",
        borderRadius: 999,
        background: "rgba(18, 22, 26, 0.92)",
        color: "#fff",
        font: "12px/1.3 ui-sans-serif, system-ui, sans-serif",
        boxShadow: "0 8px 24px rgba(0,0,0,0.28)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: 999,
          background: dotColor,
          boxShadow: `0 0 10px ${dotColor}`,
          flexShrink: 0,
        }}
      />
      <span style={{ fontWeight: 600, letterSpacing: 0.2 }}>Eye tracking</span>
      <span style={{ opacity: 0.65, fontSize: 11 }}>·</span>
      <span style={{ opacity: 0.75, fontSize: 11 }}>{label}</span>
      <button
        role="switch"
        aria-checked={enabled}
        onClick={() => onToggle(!enabled)}
        style={{
          width: 32,
          height: 18,
          borderRadius: 999,
          padding: 0,
          background: enabled ? "#5de08a" : "rgba(255,255,255,0.18)",
          border: 0,
          cursor: "pointer",
          position: "relative",
          transition: "background 160ms ease",
        }}
      >
        <span
          style={{
            position: "absolute",
            top: 2,
            left: enabled ? 16 : 2,
            width: 14,
            height: 14,
            borderRadius: 999,
            background: "#fff",
            transition: "left 160ms ease",
            boxShadow: "0 1px 3px rgba(0,0,0,0.35)",
          }}
        />
      </button>
      {enabled && hasCalibration && (
        <button
          onClick={onRecalibrate}
          style={{
            background: "transparent",
            border: "1px solid rgba(108, 200, 255, 0.4)",
            color: "#6cc8ff",
            fontSize: 11,
            padding: "3px 8px",
            borderRadius: 999,
            cursor: "pointer",
          }}
        >
          recalibrate
        </button>
      )}
    </div>
  );
}

function styleForMode(mode: Mode): { dotColor: string; label: string } {
  switch (mode) {
    case "running":
      return { dotColor: "#5de08a", label: "on" };
    case "calibrating":
    case "needs_calibration":
      return { dotColor: "#6cc8ff", label: "calibrating" };
    case "off":
      return { dotColor: "#8a8f95", label: "off" };
    case "camera_denied":
      return { dotColor: "#ff6b6b", label: "camera denied" };
    case "booting":
    default:
      return { dotColor: "#8a8f95", label: "starting" };
  }
}

function GazeRuntime({
  calibration,
  sessionId,
  rootRef,
  debug,
  onStatus,
}: {
  calibration: CalibrationTransform | null;
  sessionId: number | null;
  rootRef: RefObject<HTMLElement>;
  debug: boolean;
  onStatus: (status: GazeStatus) => void;
}) {
  const dotRef = useRef<HTMLDivElement | null>(null);
  const trailRef = useRef<HTMLCanvasElement | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);
  const sessionIdRef = useRef(sessionId);
  const rootElRef = useRef(rootRef.current);
  const [fps, setFps] = useState(0);
  const [fixationCount, setFixationCount] = useState(0);
  const [emittedCount, setEmittedCount] = useState(0);

  sessionIdRef.current = sessionId;
  rootElRef.current = rootRef.current;

  useEffect(() => {
    if (!sessionId) return;
    const auth = getStoredAuth();
    if (!auth?.access_token) return;

    const socket = new WebSocket(wsUrl(`/track/${sessionId}`, auth.access_token));
    socketRef.current = socket;
    socket.addEventListener("open", () => {
      sendEvent(socket, "gaze_calibrated", {
        points: 9,
        has_calibration: calibration !== null,
      });
    });
    socket.addEventListener("close", () => {
      if (socketRef.current === socket) socketRef.current = null;
    });

    return () => {
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
      if (socketRef.current === socket) socketRef.current = null;
    };
  }, [sessionId, calibration]);

  useEffect(() => {
    mountedRef.current = true;
    const detector = new FixationDetector({
      minDurationMs: 200,
      maxDurationMs: 3000,
      dispersionPx: 80,
    });
    let lossStartTs: number | null = null;
    let localFrameCount = 0;
    let fpsTick = performance.now();

    const tracker = new GazeTracker({
      sampleHz: 15,
      emaAlpha: 0.4,
      calibration,
      onStatus: (next) => {
        if (!mountedRef.current) return;
        onStatus(next);
      },
    });

    const canvas = trailRef.current;
    const ctx = canvas?.getContext("2d") ?? null;
    const resize = () => {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    if (debug) {
      resize();
      window.addEventListener("resize", resize);
    }

    const unsubscribe = tracker.onSample((sample) => {
      if (!mountedRef.current) return;
      localFrameCount++;
      const now = performance.now();
      if (now - fpsTick > 1000) {
        setFps(localFrameCount);
        localFrameCount = 0;
        fpsTick = now;
      }

      handleLoss(sample);
      const fixation = detector.observe(sample.faceDetected ? sample : null);
      if (fixation) {
        setFixationCount((n) => n + 1);
        const rootEl = rootElRef.current;
        const attribution =
          rootEl !== null ? attributeSection(rootEl, fixation.x, fixation.y) : null;
        const socket = socketRef.current;
        if (socket && socket.readyState === WebSocket.OPEN) {
          sendEvent(socket, "gaze_fixation", {
            section_id: attribution?.sectionId ?? null,
            rel_x: attribution ? Number(attribution.relX.toFixed(4)) : null,
            rel_y: attribution ? Number(attribution.relY.toFixed(4)) : null,
            x: Math.round(fixation.x),
            y: Math.round(fixation.y),
            duration_ms: Math.round(fixation.durationMs),
            confidence: Number(fixation.confidence.toFixed(3)),
            sample_count: fixation.sampleCount,
            start_client_ts: fixation.startTs,
            end_client_ts: fixation.endTs,
          });
          setEmittedCount((n) => n + 1);
        }
      }

      if (!debug) return;
      if (!sample.faceDetected) {
        if (dotRef.current) dotRef.current.style.opacity = "0";
        return;
      }
      if (dotRef.current) {
        dotRef.current.style.opacity = "1";
        dotRef.current.style.transform = `translate3d(${sample.x - 14}px, ${sample.y - 14}px, 0)`;
        const hue = 120 * sample.confidence;
        dotRef.current.style.background = `hsla(${hue}, 90%, 55%, 0.85)`;
        dotRef.current.style.boxShadow = `0 0 18px 6px hsla(${hue}, 90%, 55%, 0.4)`;
      }
      if (ctx && canvas) {
        ctx.fillStyle = "rgba(0,0,0,0.035)";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = `hsla(${120 * sample.confidence}, 90%, 55%, 0.22)`;
        ctx.beginPath();
        ctx.arc(sample.x, sample.y, 8, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    function handleLoss(sample: GazeSample) {
      const now = sample.timestamp;
      if (!sample.faceDetected) {
        if (lossStartTs === null) {
          lossStartTs = now;
        } else if (now - lossStartTs >= LOSS_THRESHOLD_MS) {
          const socket = socketRef.current;
          if (socket && socket.readyState === WebSocket.OPEN) {
            sendEvent(socket, "gaze_lost", {
              duration_ms: Math.round(now - lossStartTs),
              reason: "no_face",
              client_ts: now,
            });
          }
          lossStartTs = now;
        }
      } else {
        lossStartTs = null;
      }
    }

    tracker.start().catch(() => undefined);

    return () => {
      mountedRef.current = false;
      if (debug) window.removeEventListener("resize", resize);
      unsubscribe();
      tracker.stop();
    };
  }, [calibration, debug, onStatus]);

  if (!debug) return null;

  return (
    <>
      <canvas
        ref={trailRef}
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          zIndex: 9998,
          opacity: 0.7,
        }}
      />
      <div
        ref={dotRef}
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: 28,
          height: 28,
          borderRadius: "50%",
          pointerEvents: "none",
          zIndex: 9999,
          transition: "transform 60ms linear, background 120ms linear, box-shadow 120ms linear",
          border: "2px solid rgba(255,255,255,0.9)",
          opacity: 0,
        }}
      />
      <div
        style={{
          position: "fixed",
          bottom: 60,
          right: 16,
          zIndex: 10000,
          padding: "8px 12px",
          borderRadius: 10,
          background: "rgba(18, 22, 26, 0.88)",
          color: "#fff",
          font: "11px/1.4 ui-monospace, SFMono-Regular, monospace",
          boxShadow: "0 8px 32px rgba(0,0,0,0.35)",
          minWidth: 180,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 2 }}>DEBUG</div>
        <div>samples: {fps} Hz</div>
        <div>calibrated: {calibration ? "yes" : "no"}</div>
        <div>
          fixations: {fixationCount} {sessionId ? `(${emittedCount} sent)` : "(no session)"}
        </div>
      </div>
    </>
  );
}

function sendEvent(socket: WebSocket, eventType: string, data: Record<string, unknown>) {
  socket.send(
    JSON.stringify({
      type: "event",
      data: { event_type: eventType, ...data },
      ts: Date.now(),
    }),
  );
}
