"use client";

import { useEffect, useRef, useState } from "react";
import {
  CalibrationTransform,
  GazeSample,
  GazeStatus,
  GazeTracker,
  fitCalibration,
} from "@/lib/gaze";

type Point = { x: number; y: number };
type Phase = "initializing" | "prompt" | "show" | "sampling" | "done";

const INSET = 0.1;
const POINT_DURATION_MS = 900;
const GRACE_MS = 400;
const PROMPT_MS = 500;

type Sample = { eyeX: number; eyeY: number; screenX: number; screenY: number };

export function GazeCalibration({
  onComplete,
  onSkip,
}: {
  onComplete: (transform: CalibrationTransform) => void;
  onSkip: (reason: string) => void;
}) {
  const [phase, setPhase] = useState<Phase>("initializing");
  const [statusDetail, setStatusDetail] = useState<string>("");
  const [pointIdx, setPointIdx] = useState(0);
  const [points, setPoints] = useState<Point[]>([]);
  const [liveSampleCount, setLiveSampleCount] = useState(0);
  const collectedRef = useRef<Sample[]>([]);
  const currentSamplesRef = useRef<GazeSample[]>([]);
  const trackerRef = useRef<GazeTracker | null>(null);
  const cancelledRef = useRef(false);
  const onSkipRef = useRef(onSkip);
  const onCompleteRef = useRef(onComplete);
  const phaseRef = useRef(phase);

  onSkipRef.current = onSkip;
  onCompleteRef.current = onComplete;
  phaseRef.current = phase;

  useEffect(() => {
    function computePoints(): Point[] {
      const w = window.innerWidth;
      const h = window.innerHeight;
      const cols = [INSET, 0.5, 1 - INSET];
      const rows = [INSET, 0.5, 1 - INSET];
      // Serpentine path so the eye tracks continuously between adjacent dots.
      const result: Point[] = [];
      rows.forEach((ry, rowIdx) => {
        const order = rowIdx % 2 === 0 ? cols : [...cols].reverse();
        for (const cx of order) result.push({ x: w * cx, y: h * ry });
      });
      return result;
    }
    setPoints(computePoints());
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    const tracker = new GazeTracker({
      sampleHz: 15,
      emaAlpha: 1.0,
      calibration: null,
      onStatus: (status: GazeStatus, detail) => {
        if (detail) setStatusDetail(detail);
        if (status === "denied") {
          onSkipRef.current("camera_denied");
        } else if (status === "error") {
          onSkipRef.current("camera_error");
        } else if (status === "running" && phaseRef.current === "initializing") {
          setPhase("prompt");
        }
      },
    });
    trackerRef.current = tracker;

    const unsub = tracker.onSample((sample) => {
      if (!sample.faceDetected) return;
      if (phaseRef.current === "sampling") {
        currentSamplesRef.current.push(sample);
        setLiveSampleCount(currentSamplesRef.current.length);
      }
    });

    tracker.start().catch(() => undefined);

    return () => {
      cancelledRef.current = true;
      unsub();
      tracker.stop();
      trackerRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (phase !== "prompt" || points.length === 0) return;
    const timeout = window.setTimeout(() => setPhase("show"), PROMPT_MS);
    return () => window.clearTimeout(timeout);
  }, [phase, points.length]);

  useEffect(() => {
    if (phase !== "show") return;
    const timeout = window.setTimeout(() => {
      currentSamplesRef.current = [];
      setPhase("sampling");
    }, GRACE_MS);
    return () => window.clearTimeout(timeout);
  }, [phase]);

  useEffect(() => {
    if (phase !== "sampling") return;
    const timeout = window.setTimeout(() => {
      if (cancelledRef.current) return;
      const samples = currentSamplesRef.current;
      const point = points[pointIdx];
      if (samples.length >= 6 && point) {
        const trimmed = trimOutliers(samples);
        const eyeX = mean(trimmed.map((s) => s.eyeX));
        const eyeY = mean(trimmed.map((s) => s.eyeY));
        collectedRef.current.push({
          eyeX,
          eyeY,
          screenX: point.x,
          screenY: point.y,
        });
      }
      setLiveSampleCount(0);
      if (pointIdx + 1 >= points.length) {
        finalize();
      } else {
        setPointIdx(pointIdx + 1);
        setPhase("show");
      }
    }, POINT_DURATION_MS);
    return () => window.clearTimeout(timeout);
  }, [phase, pointIdx, points]);

  function finalize() {
    const transform = fitCalibration(collectedRef.current);
    if (!transform) {
      onSkipRef.current("fit_failed");
      return;
    }
    setPhase("done");
    onCompleteRef.current(transform);
  }

  if (points.length === 0) return null;
  const active = points[pointIdx];

  return (
    <div
      role="dialog"
      aria-label="Eye tracking calibration"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10000,
        background: "radial-gradient(ellipse at center, #0b1418 0%, #050809 85%)",
      }}
    >
      {points.map((p, i) => (
        <CalibrationDot
          key={i}
          x={p.x}
          y={p.y}
          state={
            i === pointIdx && (phase === "show" || phase === "sampling")
              ? phase === "sampling"
                ? "sampling"
                : "active"
              : i < pointIdx
                ? "done"
                : "pending"
          }
        />
      ))}
      <div
        style={{
          position: "absolute",
          bottom: "50%",
          left: "50%",
          transform: "translate(-50%, 140px)",
          color: "#dce5e8",
          textAlign: "center",
          display: "grid",
          gap: 10,
          maxWidth: 520,
        }}
      >
        {phase === "initializing" && (
          <>
            <div style={{ fontSize: 18, fontWeight: 600 }}>Starting camera…</div>
            <div style={{ fontSize: 13, opacity: 0.65 }}>{statusDetail || "Granting permission and loading the model."}</div>
          </>
        )}
        {phase === "prompt" && (
          <>
            <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.3 }}>Calibrating eye tracking</div>
            <div style={{ fontSize: 14, opacity: 0.75, lineHeight: 1.55 }}>
              Follow the glowing dot with your eyes through all 9 points. Keep your head still. Takes about 12 seconds.
            </div>
          </>
        )}
        {(phase === "show" || phase === "sampling") && active && (
          <div style={{ display: "grid", gap: 6 }}>
            <div style={{ fontSize: 14, opacity: 0.7 }}>
              {phase === "sampling" ? "Capturing…" : "Look at the dot"} · {pointIdx + 1} of {points.length}
            </div>
            {phase === "sampling" && (
              <div style={{ fontSize: 11, opacity: 0.45, fontFamily: "ui-monospace, monospace" }}>
                {liveSampleCount} samples
              </div>
            )}
          </div>
        )}
      </div>
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 3,
          background: "rgba(255,255,255,0.08)",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${(pointIdx / Math.max(points.length, 1)) * 100}%`,
            background: "linear-gradient(90deg, hsla(200, 95%, 62%, 0.9), hsla(145, 85%, 58%, 0.9))",
            transition: "width 400ms ease",
          }}
        />
      </div>
      <button
        onClick={() => {
          cancelledRef.current = true;
          trackerRef.current?.stop();
          onSkipRef.current("user_skipped");
        }}
        style={{
          position: "absolute",
          top: 18,
          right: 18,
          background: "transparent",
          color: "rgba(255,255,255,0.55)",
          border: "1px solid rgba(255,255,255,0.2)",
          borderRadius: 8,
          padding: "6px 12px",
          fontSize: 12,
          cursor: "pointer",
        }}
      >
        Skip
      </button>
    </div>
  );
}

function CalibrationDot({ x, y, state }: { x: number; y: number; state: "pending" | "active" | "sampling" | "done" }) {
  const size = state === "sampling" ? 22 : state === "active" ? 18 : 10;
  const color =
    state === "done"
      ? "rgba(93, 224, 138, 0.85)"
      : state === "sampling"
        ? "hsla(145, 85%, 58%, 1)"
        : state === "active"
          ? "hsla(200, 95%, 62%, 1)"
          : "rgba(255,255,255,0.18)";
  const shadow =
    state === "sampling"
      ? "0 0 32px 12px hsla(145, 85%, 58%, 0.55)"
      : state === "active"
        ? "0 0 26px 8px hsla(200, 95%, 62%, 0.45)"
        : "none";
  return (
    <div
      style={{
        position: "absolute",
        left: x - size / 2,
        top: y - size / 2,
        width: size,
        height: size,
        borderRadius: "50%",
        background: color,
        boxShadow: shadow,
        transition: "left 250ms ease, top 250ms ease, width 250ms ease, height 250ms ease, background 300ms ease, box-shadow 300ms ease",
      }}
    >
      {state === "sampling" && (
        <span
          style={{
            position: "absolute",
            inset: -14,
            borderRadius: "50%",
            border: "2px solid hsla(145, 85%, 58%, 0.35)",
            animation: "gaze-pulse 1.2s ease-in-out infinite",
          }}
        />
      )}
      <style>{`@keyframes gaze-pulse { 0% { transform: scale(0.85); opacity: 0.9; } 100% { transform: scale(1.35); opacity: 0; } }`}</style>
    </div>
  );
}

function mean(xs: number[]): number {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function trimOutliers(samples: GazeSample[]): GazeSample[] {
  if (samples.length < 8) return samples;
  const sortedX = [...samples].sort((a, b) => a.eyeX - b.eyeX);
  const trim = Math.floor(samples.length * 0.15);
  const trimmed = sortedX.slice(trim, samples.length - trim);
  return trimmed;
}
