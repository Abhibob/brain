"use client";

import { useMemo } from "react";
import { TopicEdge, TopicNode } from "@/lib/api";
import { masteryColor } from "@/lib/scores";

type Props = {
  nodes: TopicNode[];
  edges: TopicEdge[];
  width?: number;
  height?: number;
  onSelect?: (topic: string) => void;
  selected?: string | null;
};

const colorForMastery = masteryColor;

export function TopicGraph({ nodes, edges, width = 520, height = 340, onSelect, selected }: Props) {
  const layout = useMemo(() => {
    if (!nodes.length) return { positions: new Map<string, { x: number; y: number }>() };
    const positions = new Map<string, { x: number; y: number }>();
    const center = { x: width / 2, y: height / 2 };
    const radius = Math.min(width, height) / 2 - 40;
    nodes.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(nodes.length, 3) - Math.PI / 2;
      positions.set(node.topic, {
        x: center.x + Math.cos(angle) * radius,
        y: center.y + Math.sin(angle) * radius
      });
    });
    return { positions };
  }, [nodes, width, height]);

  if (!nodes.length) {
    return (
      <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: 220, color: "var(--ink-soft)" }}>
        No topic signal yet. Finish a few lessons to populate the graph.
      </div>
    );
  }

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ background: "var(--surface-muted)", borderRadius: "var(--radius-lg)" }}>
      {edges.map((edge, i) => {
        const from = layout.positions.get(edge.from_topic);
        const to = layout.positions.get(edge.to_topic);
        if (!from || !to) return null;
        return (
          <line
            key={i}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            stroke="var(--line)"
            strokeWidth={Math.min(edge.weight, 4)}
            opacity={0.6}
          />
        );
      })}
      {nodes.map(node => {
        const pos = layout.positions.get(node.topic);
        if (!pos) return null;
        const size = 16 + Math.min(node.encounter_count, 8) * 3;
        const fill = colorForMastery(node.mastery_score);
        const isSelected = selected === node.topic;
        return (
          <g key={node.topic} style={{ cursor: onSelect ? "pointer" : "default" }} onClick={() => onSelect?.(node.topic)}>
            <circle
              cx={pos.x}
              cy={pos.y}
              r={size}
              fill={fill}
              stroke={isSelected ? "var(--accent-strong)" : "#ffffff"}
              strokeWidth={isSelected ? 4 : 2}
              opacity={0.85}
            />
            <text x={pos.x} y={pos.y + size + 14} textAnchor="middle" fontSize={11} fill="var(--ink)">
              {node.topic}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
