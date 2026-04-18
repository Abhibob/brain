"use client";

import { StyleVector } from "@/lib/api";

const AXES: Array<{ key: keyof StyleVector; label: string }> = [
  { key: "pace", label: "Pace" },
  { key: "depth", label: "Depth" },
  { key: "attention_stability", label: "Attention" },
  { key: "engagement_mode", label: "Engagement" },
  { key: "revisit_tendency", label: "Revisit" },
  { key: "visual_orientation", label: "Visual" },
  { key: "motor_style", label: "Motor" }
];

type Props = {
  vector: StyleVector;
  size?: number;
};

export function StyleRadar({ vector, size = 260 }: Props) {
  const radius = size / 2 - 28;
  const center = size / 2;
  const n = AXES.length;
  const gridLevels = [0.25, 0.5, 0.75, 1.0];

  const point = (axisIndex: number, value: number) => {
    const angle = (Math.PI * 2 * axisIndex) / n - Math.PI / 2;
    return {
      x: center + Math.cos(angle) * radius * value,
      y: center + Math.sin(angle) * radius * value
    };
  };

  const polygon = AXES.map((axis, index) => {
    const v = Math.max(0, Math.min(1, Number(vector[axis.key] ?? 0.5)));
    const p = point(index, v);
    return `${p.x},${p.y}`;
  }).join(" ");

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: "block" }}>
      {gridLevels.map(level => (
        <polygon
          key={level}
          points={AXES.map((_, index) => {
            const p = point(index, level);
            return `${p.x},${p.y}`;
          }).join(" ")}
          fill="none"
          stroke="var(--line)"
          strokeWidth={1}
        />
      ))}
      {AXES.map((axis, index) => {
        const outer = point(index, 1);
        return (
          <line
            key={axis.key}
            x1={center}
            y1={center}
            x2={outer.x}
            y2={outer.y}
            stroke="var(--line)"
            strokeWidth={0.5}
          />
        );
      })}
      <defs>
        <linearGradient id="radar-fill" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.45" />
          <stop offset="100%" stopColor="var(--highlight)" stopOpacity="0.35" />
        </linearGradient>
      </defs>
      <polygon points={polygon} fill="url(#radar-fill)" stroke="var(--highlight-strong)" strokeWidth={2} />
      {AXES.map((axis, index) => {
        const p = point(index, 1.12);
        return (
          <text
            key={axis.label}
            x={p.x}
            y={p.y}
            textAnchor="middle"
            dominantBaseline="middle"
            fontSize={11}
            fill="var(--ink-soft)"
          >
            {axis.label}
          </text>
        );
      })}
    </svg>
  );
}
