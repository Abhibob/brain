"use client";

import { useMemo, useState } from "react";
import { LearningView, StyleVector } from "@/lib/api";

type Props = {
  view: LearningView;
};

type NodeSpec = {
  id: string;
  label: string;
  value: number; // 0..1
  blurb: string;
};

type Edge = {
  fromIndex: number;
  toIndex: number;
  weight: number; // 0..1
  fromLayer: number;
  toLayer: number;
};

const STYLE_AXES: Array<{ key: keyof StyleVector; label: string; blurb: string }> = [
  { key: "pace", label: "Pace", blurb: "How quickly this student reads through material." },
  { key: "depth", label: "Depth", blurb: "Skim vs. deep-read. Higher means they linger on ideas." },
  { key: "attention_stability", label: "Attention", blurb: "How steadily they hold focus inside a section." },
  { key: "engagement_mode", label: "Engagement", blurb: "Passive reading vs. active highlighting, hovering, re-reading." },
  { key: "revisit_tendency", label: "Revisit", blurb: "How often they go back and re-read earlier parts." },
  { key: "visual_orientation", label: "Visual", blurb: "Preference for diagrams, videos, and hover-driven visuals." },
  { key: "motor_style", label: "Motor", blurb: "Scroll-heavy vs. hover-heavy interaction style." }
];

const INPUT_KEYS = [
  { key: "hover_heavy", label: "Hover-heavy", blurb: "Lingers over terms and concepts with the cursor." },
  { key: "selector", label: "Selector", blurb: "Highlights text while reading." },
  { key: "re_reader", label: "Re-reader", blurb: "Goes back to re-read sections." },
  { key: "back_scroller", label: "Back-scroller", blurb: "Scrolls upward often while reading." },
  { key: "skimmer", label: "Skimmer", blurb: "Moves quickly without finishing sections." }
];

const OUTPUT_AXES = [
  {
    id: "examples-first",
    label: "Examples first",
    blurb: "Prefers concrete worked examples before formal rules.",
    weight: (v: StyleVector) => Math.min(1, 0.5 * (1 - v.depth) + 0.4 * v.engagement_mode + 0.3 * v.visual_orientation)
  },
  {
    id: "short-passages",
    label: "Short passages",
    blurb: "Holds focus better when sections stay brief.",
    weight: (v: StyleVector) => Math.min(1, 0.6 * (1 - v.attention_stability) + 0.2 * (1 - v.depth))
  },
  {
    id: "visual-aids",
    label: "Visual aids",
    blurb: "Benefits from diagrams, videos, and labeled pictures.",
    weight: (v: StyleVector) => Math.min(1, 0.7 * v.visual_orientation + 0.2 * v.engagement_mode)
  },
  {
    id: "review-blocks",
    label: "Review blocks",
    blurb: "Prefers recap boxes and summary callouts inside a lesson.",
    weight: (v: StyleVector) => Math.min(1, 0.6 * v.revisit_tendency + 0.3 * (1 - v.attention_stability))
  },
  {
    id: "deep-dives",
    label: "Deep dives",
    blurb: "Tolerates — and enjoys — longer, more rigorous passages.",
    weight: (v: StyleVector) => Math.min(1, 0.7 * v.depth + 0.2 * v.attention_stability)
  }
];

function clamp01(x: number): number {
  if (!Number.isFinite(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function colorForValue(v: number): string {
  // Blend teal → indigo with value.
  const vv = clamp01(v);
  const r = Math.round(15 + (99 - 15) * vv);
  const g = Math.round(118 + (102 - 118) * vv);
  const b = Math.round(110 + (241 - 110) * vv);
  return `rgb(${r}, ${g}, ${b})`;
}

export function LearningStyleNet({ view }: Props) {
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const profile = view.learning_profile;
  const style = profile?.style_vector;
  const fingerprint = (profile?.engagement_fingerprint || {}) as Record<string, number | string>;

  const layers: NodeSpec[][] = useMemo(() => {
    if (!style) return [[], [], []];
    const input: NodeSpec[] = INPUT_KEYS.map(k => ({
      id: `in:${k.key}`,
      label: k.label,
      value: clamp01(Number(fingerprint[k.key] ?? 0)),
      blurb: k.blurb
    }));
    const hidden: NodeSpec[] = STYLE_AXES.map(axis => ({
      id: `hid:${axis.key}`,
      label: axis.label,
      value: clamp01(Number(style[axis.key] ?? 0.5)),
      blurb: axis.blurb
    }));
    const output: NodeSpec[] = OUTPUT_AXES.map(axis => ({
      id: `out:${axis.id}`,
      label: axis.label,
      value: clamp01(axis.weight(style)),
      blurb: axis.blurb
    }));
    return [input, hidden, output];
  }, [style, fingerprint]);

  // Full-connect edges with weights derived from node values (stronger when both
  // endpoints are "on"). Purely a visual signal — not a real neural net.
  const edges: Edge[] = useMemo(() => {
    const out: Edge[] = [];
    for (let l = 0; l < layers.length - 1; l++) {
      const from = layers[l];
      const to = layers[l + 1];
      for (let i = 0; i < from.length; i++) {
        for (let j = 0; j < to.length; j++) {
          const w = Math.pow(clamp01((from[i].value + to[j].value) / 2), 1.4);
          out.push({ fromIndex: i, toIndex: j, weight: w, fromLayer: l, toLayer: l + 1 });
        }
      }
    }
    return out;
  }, [layers]);

  const width = 760;
  const height = 640;
  const columnX = [130, 380, 630];
  const radius = 18;

  const nodePos = (layerIdx: number, nodeIdx: number, layerLen: number): { x: number; y: number } => {
    const x = columnX[layerIdx];
    if (layerLen <= 1) return { x, y: height / 2 };
    const padding = 60;
    const available = height - padding * 2;
    const step = available / (layerLen - 1);
    return { x, y: padding + nodeIdx * step };
  };

  if (!profile || !style) {
    return (
      <div
        className="card"
        style={{
          minHeight: 320,
          display: "grid",
          placeItems: "center",
          color: "var(--ink-soft)"
        }}
      >
        Learning-style signal appears here after the student completes a few lessons.
      </div>
    );
  }

  const hoverInfo = (() => {
    const active = hovered || selected;
    if (!active) return null;
    for (const layer of layers) {
      const match = layer.find(n => n.id === active);
      if (match) return match;
    }
    return null;
  })();

  const activeIdMatches = (id: string) => {
    if (!hovered && !selected) return false;
    return hovered === id || selected === id;
  };

  const edgeTouchesActive = (fromId: string, toId: string) => {
    if (!hovered && !selected) return false;
    return activeIdMatches(fromId) || activeIdMatches(toId);
  };

  return (
    <div
      className="card"
      style={{
        position: "relative",
        padding: 0,
        overflow: "hidden",
        minHeight: 480,
        background:
          "radial-gradient(560px 360px at 50% 50%, color-mix(in srgb, var(--highlight) 10%, transparent) 0%, transparent 70%), linear-gradient(135deg, #0b1020 0%, #1a1b3a 50%, #0f172a 100%)"
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 14,
          left: 18,
          right: 18,
          display: "flex",
          justifyContent: "space-between",
          zIndex: 2,
          color: "#c7d2fe"
        }}
      >
        <div>
          <div
            style={{
              fontSize: 11,
              letterSpacing: "0.2em",
              textTransform: "uppercase",
              color: "rgba(199, 210, 254, 0.7)"
            }}
          >
            Learning style
          </div>
          <div style={{ fontSize: 14, color: "rgba(255, 255, 255, 0.85)" }}>
            behavior · style · content preferences
          </div>
        </div>
        <div style={{ display: "flex", gap: 20, fontSize: 11, alignItems: "center" }}>
          <LegendLabel color="rgba(165, 243, 252, 0.9)" label="Inputs" />
          <LegendLabel color="rgba(224, 231, 255, 0.9)" label="Style axes" />
          <LegendLabel color="rgba(251, 207, 232, 0.9)" label="Preferences" />
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        style={{ display: "block", maxHeight: "80vh" }}
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <linearGradient id="edge-flow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.15" />
            <stop offset="50%" stopColor="#818cf8" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#f472b6" stopOpacity="0.55" />
          </linearGradient>
          <linearGradient id="edge-active" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#a5f3fc" stopOpacity="0.9" />
            <stop offset="50%" stopColor="#c4b5fd" stopOpacity="1" />
            <stop offset="100%" stopColor="#fbcfe8" stopOpacity="0.9" />
          </linearGradient>
          <radialGradient id="node-halo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#818cf8" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#818cf8" stopOpacity="0" />
          </radialGradient>
        </defs>

        <style>{`
          @keyframes flow { from { stroke-dashoffset: 0 } to { stroke-dashoffset: -60 } }
          @keyframes pulse { 0%,100% { transform: scale(1); opacity: 0.4 } 50% { transform: scale(1.25); opacity: 0.0 } }
          .edge { animation: flow 3.8s linear infinite; }
          .edge-active { animation-duration: 1.6s; }
          .node-halo { animation: pulse 2.4s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
        `}</style>

        {/* Edges */}
        {edges.map((edge, i) => {
          const from = layers[edge.fromLayer][edge.fromIndex];
          const to = layers[edge.toLayer][edge.toIndex];
          if (!from || !to) return null;
          const a = nodePos(edge.fromLayer, edge.fromIndex, layers[edge.fromLayer].length);
          const b = nodePos(edge.toLayer, edge.toIndex, layers[edge.toLayer].length);
          const mx = (a.x + b.x) / 2;
          const active = edgeTouchesActive(from.id, to.id);
          const opacity = active ? 0.95 : 0.15 + edge.weight * 0.55;
          const stroke = active ? "url(#edge-active)" : "url(#edge-flow)";
          const width = (active ? 1.6 : 0.8) + edge.weight * 2.2;
          return (
            <path
              key={i}
              d={`M ${a.x} ${a.y} C ${mx} ${a.y}, ${mx} ${b.y}, ${b.x} ${b.y}`}
              stroke={stroke}
              strokeOpacity={opacity}
              strokeWidth={width}
              fill="none"
              strokeLinecap="round"
              strokeDasharray="4 6"
              className={`edge ${active ? "edge-active" : ""}`}
            />
          );
        })}

        {/* Nodes */}
        {layers.map((layer, layerIdx) =>
          layer.map((node, nodeIdx) => {
            const pos = nodePos(layerIdx, nodeIdx, layer.length);
            const r = radius + 5 * node.value;
            const active = activeIdMatches(node.id);
            const fill = colorForValue(node.value);
            const labelWidth = Math.max(40, node.label.length * 6.2 + 14);
            const labelY = pos.y + r + 18;
            return (
              <g
                key={node.id}
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHovered(node.id)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => setSelected(s => (s === node.id ? null : node.id))}
              >
                {(active || node.value > 0.6) && (
                  <circle cx={pos.x} cy={pos.y} r={r + 12} fill="url(#node-halo)" className="node-halo" />
                )}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={r}
                  fill={fill}
                  fillOpacity={0.88}
                  stroke={active ? "#ffffff" : "rgba(255, 255, 255, 0.25)"}
                  strokeWidth={active ? 3 : 1.5}
                />
                <text
                  x={pos.x}
                  y={pos.y + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fontWeight={700}
                  fill="#fff"
                  style={{ pointerEvents: "none" }}
                >
                  {(node.value * 10).toFixed(1)}
                </text>
                <rect
                  x={pos.x - labelWidth / 2}
                  y={labelY - 10}
                  width={labelWidth}
                  height={16}
                  rx={8}
                  fill="rgba(15, 23, 42, 0.72)"
                  stroke="rgba(148, 163, 184, 0.2)"
                  strokeWidth={0.5}
                  style={{ pointerEvents: "none" }}
                />
                <text
                  x={pos.x}
                  y={labelY + 1}
                  textAnchor="middle"
                  fontSize={11}
                  fill="rgba(241, 245, 249, 0.95)"
                  style={{ pointerEvents: "none", fontWeight: 500 }}
                >
                  {node.label}
                </text>
              </g>
            );
          })
        )}
      </svg>

      {hoverInfo && (
        <div
          style={{
            position: "absolute",
            left: 18,
            bottom: 16,
            maxWidth: 320,
            padding: "12px 14px",
            background: "rgba(15, 23, 42, 0.88)",
            color: "#e2e8f0",
            border: "1px solid rgba(148, 163, 184, 0.3)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-card)",
            fontSize: 13,
            lineHeight: 1.5,
            zIndex: 3
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4, letterSpacing: "-0.01em" }}>
            {hoverInfo.label} · {(hoverInfo.value * 10).toFixed(1)} / 10
          </div>
          <div style={{ color: "rgba(226, 232, 240, 0.78)" }}>{hoverInfo.blurb}</div>
        </div>
      )}
    </div>
  );
}

function LegendLabel({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 10,
          height: 10,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 0 8px ${color}`
        }}
      />
      {label}
    </span>
  );
}
