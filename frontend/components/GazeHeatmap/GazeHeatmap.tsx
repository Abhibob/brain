"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, GazeHeatmap as GazeHeatmapData } from "@/lib/api";

export function GazeHeatmap({
  sessionId,
  data,
  className,
}: {
  sessionId?: number;
  data?: GazeHeatmapData;
  className?: string;
}) {
  const [loaded, setLoaded] = useState<GazeHeatmapData | null>(data ?? null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(
    data ? "ready" : "idle",
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setLoaded(data);
      setStatus("ready");
      return;
    }
    if (!sessionId) return;
    let cancelled = false;
    setStatus("loading");
    api
      .getSessionGazeHeatmap(sessionId)
      .then((result) => {
        if (cancelled) return;
        setLoaded(result);
        setStatus("ready");
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, data]);

  if (status === "loading") {
    return (
      <div className={className} style={{ padding: 18 }}>
        <div className="muted" style={{ fontSize: 13 }}>
          Loading gaze heatmap…
        </div>
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className={className} style={{ padding: 18 }}>
        <div className="error" style={{ fontSize: 13 }}>
          Couldn&apos;t load heatmap: {error}
        </div>
      </div>
    );
  }
  if (!loaded) return null;

  if (!loaded.gaze_present) {
    return (
      <div className={className} style={{ padding: 20, display: "grid", gap: 8 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>No gaze data for this session</div>
        <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.5 }}>
          The student either didn&apos;t enable eye tracking or their session finished before enough fixations were captured. Other focus signals (mouse, scroll, idle) still fed the profile.
        </div>
      </div>
    );
  }

  return <GazeHeatmapContent data={loaded} className={className} />;
}

function GazeHeatmapContent({ data, className }: { data: GazeHeatmapData; className?: string }) {
  const stats = useMemo(
    () => [
      {
        label: "Focus",
        value:
          data.focus_score !== null
            ? `${(data.focus_score * 10).toFixed(1)}/10`
            : "—",
        detail: data.focus_label ?? undefined,
      },
      {
        label: "On-content",
        value: `${formatSeconds(data.reading_time_s)}`,
        detail:
          data.total_time_s > 0
            ? `${Math.round((data.reading_time_s / data.total_time_s) * 100)}% of session`
            : undefined,
      },
      {
        label: "Lost",
        value: `${Math.round(data.lost_pct * 100)}%`,
        detail: "looking away",
      },
      {
        label: "Scatter",
        value: entropyLabel(data.entropy),
        detail: `H=${data.entropy.toFixed(2)}`,
      },
      {
        label: "Fixations",
        value: `${data.fixation_count}`,
        detail:
          data.fixation_ms_mean > 0 ? `${Math.round(data.fixation_ms_mean)}ms avg` : undefined,
      },
    ],
    [data],
  );

  return (
    <div className={className} style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div className="section-heading">Reading heatmap · Session #{data.session_id}</div>
          <div className="muted" style={{ fontSize: 12.5 }}>
            {data.material_title}
            {data.ended_at && ` · ${new Date(data.ended_at).toLocaleString()}`}
          </div>
        </div>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 11,
            color: "var(--ink-soft)",
            padding: "3px 10px",
            borderRadius: 999,
            background: data.has_calibration ? "rgba(93, 224, 138, 0.14)" : "rgba(240, 180, 41, 0.14)",
            border: `1px solid ${data.has_calibration ? "rgba(93, 224, 138, 0.4)" : "rgba(240, 180, 41, 0.4)"}`,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: 999, background: data.has_calibration ? "#2b9d55" : "#a57400" }} />
          {data.has_calibration ? "9-point calibrated" : "uncalibrated"}
        </div>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
          gap: 10,
        }}
      >
        {stats.map((stat) => (
          <div
            key={stat.label}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-md)",
              padding: "10px 12px",
            }}
          >
            <div className="section-heading" style={{ margin: 0, fontSize: 10 }}>
              {stat.label}
            </div>
            <div style={{ fontSize: 19, fontWeight: 700, letterSpacing: "-0.01em", marginTop: 2 }}>
              {stat.value}
            </div>
            {stat.detail && (
              <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                {stat.detail}
              </div>
            )}
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gap: 10 }}>
        {data.sections.map((section) => (
          <SectionHeatmapCard key={section.section_id} section={section} />
        ))}
      </div>
    </div>
  );
}

function SectionHeatmapCard({
  section,
}: {
  section: GazeHeatmapData["sections"][number];
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    renderHeatmapCanvas(canvas, section.fixations);
  }, [section.fixations]);

  const hasData = section.fixations.length > 0;
  const intensity = Math.min(section.time_s / 15, 1);

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(0, 1fr) 180px",
        gap: 12,
        padding: 12,
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-md)",
        background: `linear-gradient(90deg, color-mix(in srgb, var(--accent) ${
          intensity * 6
        }%, var(--surface)) 0%, var(--surface) 100%)`,
      }}
    >
      <div
        style={{
          position: "relative",
          height: 72,
          borderRadius: "var(--radius-sm)",
          overflow: "hidden",
          background: "#0f1418",
        }}
      >
        <canvas
          ref={canvasRef}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        />
        <div
          style={{
            position: "absolute",
            left: 10,
            top: 8,
            color: "rgba(255,255,255,0.88)",
            fontSize: 13,
            fontWeight: 600,
            textShadow: "0 1px 4px rgba(0,0,0,0.6)",
            maxWidth: "90%",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {section.title}
        </div>
        {!hasData && (
          <div
            style={{
              position: "absolute",
              right: 10,
              bottom: 8,
              color: "rgba(255,255,255,0.45)",
              fontSize: 11,
            }}
          >
            no fixations
          </div>
        )}
      </div>
      <div style={{ display: "grid", gap: 4, alignContent: "center", fontSize: 12 }}>
        <div>
          <strong>{section.fixation_count}</strong>{" "}
          <span className="muted">fixations</span>
        </div>
        <div>
          <strong>{formatSeconds(section.time_s)}</strong>{" "}
          <span className="muted">reading</span>
        </div>
        {section.fixation_count > 0 && (
          <div className="muted" style={{ fontSize: 11 }}>
            {Math.round((section.time_s * 1000) / section.fixation_count)}ms avg
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Paints a soft Gaussian-ish density map of fixations on the provided canvas.
 * Each fixation places a radial gradient blob proportional to its weight
 * (duration in seconds). Blobs are additively blended and then remapped to a
 * heat colormap.
 */
function renderHeatmapCanvas(canvas: HTMLCanvasElement, fixations: GazeHeatmapData["sections"][number]["fixations"]) {
  const dpr = window.devicePixelRatio || 1;
  const parent = canvas.parentElement;
  if (!parent) return;
  const w = Math.max(Math.floor(parent.clientWidth), 1);
  const h = Math.max(Math.floor(parent.clientHeight), 1);
  canvas.width = Math.floor(w * dpr);
  canvas.height = Math.floor(h * dpr);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.save();
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);

  if (fixations.length === 0) {
    ctx.restore();
    return;
  }

  // Pass 1: build a grayscale intensity field via additive blending.
  ctx.globalCompositeOperation = "lighter";
  for (const fx of fixations) {
    const cx = fx.rel_x * w;
    const cy = fx.rel_y * h;
    const r = Math.max(18, Math.min(80, 12 + fx.weight * 18));
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    const alpha = Math.min(0.35 + fx.weight * 0.1, 0.9);
    grad.addColorStop(0, `rgba(255, 255, 255, ${alpha})`);
    grad.addColorStop(1, "rgba(255, 255, 255, 0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
  }

  // Pass 2: remap the grayscale intensity to a heat color ramp.
  const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const buf = pixels.data;
  for (let i = 0; i < buf.length; i += 4) {
    const v = buf[i + 3]; // alpha carries the additive intensity
    if (v === 0) continue;
    const t = v / 255;
    const [r, g, b] = heatRamp(t);
    buf[i] = r;
    buf[i + 1] = g;
    buf[i + 2] = b;
    buf[i + 3] = Math.round(Math.min(t * 255 * 1.2, 220));
  }
  ctx.putImageData(pixels, 0, 0);
  ctx.restore();
}

/**
 * Heat colormap: cold blue → cyan → green → yellow → orange → red.
 */
function heatRamp(t: number): [number, number, number] {
  const stops: Array<[number, [number, number, number]]> = [
    [0.0, [26, 35, 126]],
    [0.25, [33, 150, 243]],
    [0.5, [76, 175, 80]],
    [0.7, [255, 193, 7]],
    [0.85, [255, 112, 67]],
    [1.0, [244, 67, 54]],
  ];
  for (let i = 1; i < stops.length; i++) {
    const [stopT, stopColor] = stops[i];
    const [prevT, prevColor] = stops[i - 1];
    if (t <= stopT) {
      const u = (t - prevT) / Math.max(stopT - prevT, 1e-6);
      return [
        Math.round(prevColor[0] + (stopColor[0] - prevColor[0]) * u),
        Math.round(prevColor[1] + (stopColor[1] - prevColor[1]) * u),
        Math.round(prevColor[2] + (stopColor[2] - prevColor[2]) * u),
      ];
    }
  }
  return stops[stops.length - 1][1];
}

function formatSeconds(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

function entropyLabel(entropy: number): string {
  if (entropy < 0.2) return "Tight";
  if (entropy < 0.5) return "Focused";
  if (entropy < 0.75) return "Mixed";
  return "Scattered";
}
