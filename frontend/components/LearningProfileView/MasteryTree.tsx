"use client";

import { PointerEvent, useMemo, useRef, useState, WheelEvent } from "react";
import { TopicEdge, TopicNode } from "@/lib/api";
import { masteryColor } from "@/lib/scores";

type Props = {
  studentName: string;
  nodes: TopicNode[];
  edges: TopicEdge[];
  onSelectTopic?: (topic: TopicNode) => void;
};

type TreeNode = {
  id: string;
  label: string;
  kind: "root" | "cluster" | "topic";
  children: TreeNode[];
  data?: TopicNode;
  // layout-assigned
  x: number;
  y: number;
  depth: number;
  // tidy-tree bookkeeping
  mod: number;
  prelim: number;
  thread: TreeNode | null;
  parent: TreeNode | null;
};

const H_STEP = 60; // vertical distance per depth level
const SIBLING_GAP = 110; // minimum horizontal gap between siblings

function makeNode(id: string, label: string, kind: TreeNode["kind"], data?: TopicNode): TreeNode {
  return {
    id,
    label,
    kind,
    children: [],
    data,
    x: 0,
    y: 0,
    depth: 0,
    mod: 0,
    prelim: 0,
    thread: null,
    parent: null
  };
}

function buildTree(studentName: string, nodes: TopicNode[]): TreeNode {
  const root = makeNode("root", studentName, "root");
  if (!nodes.length) return root;

  const clusters = new Map<string, TreeNode>();
  for (const node of nodes) {
    const key = (node.topic.split(/\s+/)[0] || node.topic).slice(0, 24).toLowerCase();
    if (!clusters.has(key)) {
      const cluster = makeNode(`cluster:${key}`, key, "cluster");
      clusters.set(key, cluster);
    }
    const cluster = clusters.get(key)!;
    const leaf = makeNode(`topic:${node.topic}`, node.topic, "topic", node);
    leaf.parent = cluster;
    cluster.children.push(leaf);
  }
  // If every cluster has exactly one topic, flatten one level for a tidier look.
  const allSingles = Array.from(clusters.values()).every(c => c.children.length === 1);
  if (allSingles) {
    for (const cluster of clusters.values()) {
      const child = cluster.children[0];
      child.parent = root;
      root.children.push(child);
    }
  } else {
    for (const cluster of clusters.values()) {
      cluster.parent = root;
      root.children.push(cluster);
    }
  }
  return root;
}

/**
 * Reingold–Tilford "tidy tree" layout — compact, symmetric, O(n).
 * Positions are written into node.x / node.y.
 */
function layoutTidy(root: TreeNode): { width: number; height: number; min: number; max: number } {
  const walk = (node: TreeNode, depth: number) => {
    node.depth = depth;
    for (const c of node.children) walk(c, depth + 1);
  };
  walk(root, 0);

  const firstWalk = (node: TreeNode) => {
    if (node.children.length === 0) {
      const prev = leftSibling(node);
      node.prelim = prev ? prev.prelim + SIBLING_GAP : 0;
      return;
    }
    for (const child of node.children) firstWalk(child);
    const first = node.children[0];
    const last = node.children[node.children.length - 1];
    const midpoint = (first.prelim + last.prelim) / 2;
    const prev = leftSibling(node);
    if (prev) {
      node.prelim = prev.prelim + SIBLING_GAP;
      node.mod = node.prelim - midpoint;
    } else {
      node.prelim = midpoint;
    }
    // simple subtree separation — shift the whole subtree right if it collides with a previous sibling
    if (prev) {
      const rightmost = rightContour(prev);
      const leftmost = leftContour(node);
      const push = Math.max(0, rightmost - leftmost + SIBLING_GAP);
      if (push > 0) {
        node.prelim += push;
        node.mod += push;
      }
    }
  };
  const secondWalk = (node: TreeNode, m: number) => {
    node.x = node.prelim + m;
    node.y = node.depth * H_STEP;
    for (const c of node.children) secondWalk(c, m + node.mod);
  };

  firstWalk(root);
  secondWalk(root, 0);

  let min = Infinity;
  let max = -Infinity;
  let maxY = 0;
  const visit = (n: TreeNode) => {
    min = Math.min(min, n.x);
    max = Math.max(max, n.x);
    maxY = Math.max(maxY, n.y);
    n.children.forEach(visit);
  };
  visit(root);
  if (min === Infinity) {
    min = 0;
    max = 0;
  }
  return { width: max - min + 80, height: maxY + 80, min, max };
}

function leftSibling(node: TreeNode): TreeNode | null {
  if (!node.parent) return null;
  const siblings = node.parent.children;
  const idx = siblings.indexOf(node);
  return idx > 0 ? siblings[idx - 1] : null;
}

function leftContour(node: TreeNode, depth = 0, acc: number[] = []): number {
  acc[depth] = acc[depth] === undefined ? node.prelim : Math.min(acc[depth], node.prelim);
  for (const c of node.children) leftContour(c, depth + 1, acc);
  return Math.min(...acc);
}

function rightContour(node: TreeNode, depth = 0, acc: number[] = []): number {
  acc[depth] = acc[depth] === undefined ? node.prelim : Math.max(acc[depth], node.prelim);
  for (const c of node.children) rightContour(c, depth + 1, acc);
  return Math.max(...acc);
}

function flatten(root: TreeNode): TreeNode[] {
  const out: TreeNode[] = [];
  const visit = (n: TreeNode) => {
    out.push(n);
    n.children.forEach(visit);
  };
  visit(root);
  return out;
}

function edgesBetween(root: TreeNode): Array<{ from: TreeNode; to: TreeNode }> {
  const out: Array<{ from: TreeNode; to: TreeNode }> = [];
  const visit = (n: TreeNode) => {
    for (const c of n.children) {
      out.push({ from: n, to: c });
      visit(c);
    }
  };
  visit(root);
  return out;
}

export function MasteryTree({ studentName, nodes, edges, onSelectTopic }: Props) {
  const [hover, setHover] = useState<TreeNode | null>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [panning, setPanning] = useState<{ startX: number; startY: number; origX: number; origY: number } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const { root, layout } = useMemo(() => {
    const root = buildTree(studentName, nodes);
    const layout = layoutTidy(root);
    return { root, layout };
  }, [studentName, nodes]);

  const flat = useMemo(() => flatten(root), [root]);
  const treeEdges = useMemo(() => edgesBetween(root), [root]);
  const masteryEdges = edges.filter(e =>
    flat.some(f => f.kind === "topic" && f.label === e.from_topic) &&
    flat.some(f => f.kind === "topic" && f.label === e.to_topic)
  );

  const vbWidth = Math.max(600, layout.width);
  const vbHeight = Math.max(320, layout.height + 40);
  const offsetX = -layout.min + 40;

  const onPointerDown = (e: PointerEvent<SVGSVGElement>) => {
    setPanning({ startX: e.clientX, startY: e.clientY, origX: pan.x, origY: pan.y });
    (e.target as Element).setPointerCapture?.(e.pointerId);
  };
  const onPointerMove = (e: PointerEvent<SVGSVGElement>) => {
    if (!panning) return;
    setPan({
      x: panning.origX + (e.clientX - panning.startX),
      y: panning.origY + (e.clientY - panning.startY)
    });
  };
  const endPan = () => setPanning(null);
  const onWheel = (e: WheelEvent<SVGSVGElement>) => {
    e.preventDefault();
    const next = Math.max(0.4, Math.min(2.4, zoom * (e.deltaY > 0 ? 0.92 : 1.08)));
    setZoom(next);
  };
  const resetView = () => {
    setPan({ x: 0, y: 0 });
    setZoom(1);
  };

  return (
    <div
      className="card"
      style={{
        position: "relative",
        padding: 0,
        overflow: "hidden",
        minHeight: 420,
        background:
          "radial-gradient(600px 400px at 40% 10%, var(--highlight-soft) 0%, transparent 70%), var(--surface)"
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 12,
          left: 14,
          right: 14,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          zIndex: 2,
          pointerEvents: "none"
        }}
      >
        <div>
          <div className="section-heading" style={{ margin: 0 }}>
            Learning tree
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>
            Drag to pan · scroll to zoom · click a leaf for details
          </div>
        </div>
        <button
          type="button"
          className="button secondary"
          onClick={resetView}
          style={{ pointerEvents: "auto", fontSize: 12, minHeight: 32, padding: "4px 10px" }}
        >
          Reset view
        </button>
      </div>
      <svg
        ref={svgRef}
        width="100%"
        height={Math.min(600, vbHeight + 80)}
        viewBox={`0 0 ${vbWidth + 80} ${vbHeight + 60}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endPan}
        onPointerCancel={endPan}
        onWheel={onWheel}
        style={{ display: "block", cursor: panning ? "grabbing" : "grab", userSelect: "none", touchAction: "none" }}
      >
        <defs>
          <radialGradient id="root-halo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--highlight)" stopOpacity="0.3" />
            <stop offset="100%" stopColor="var(--highlight)" stopOpacity="0" />
          </radialGradient>
        </defs>
        <g transform={`translate(${pan.x + offsetX}, ${pan.y + 50}) scale(${zoom})`}>
          {/* co-occurrence underlay */}
          {masteryEdges.map((edge, i) => {
            const from = flat.find(f => f.label === edge.from_topic);
            const to = flat.find(f => f.label === edge.to_topic);
            if (!from || !to) return null;
            return (
              <path
                key={`coe-${i}`}
                d={`M${from.x},${from.y} Q${(from.x + to.x) / 2},${Math.max(from.y, to.y) + 40} ${to.x},${to.y}`}
                stroke="var(--highlight)"
                strokeOpacity={0.18}
                strokeWidth={Math.min(2 + edge.weight, 6)}
                fill="none"
              />
            );
          })}
          {/* parent-child tree edges */}
          {treeEdges.map(({ from, to }, i) => (
            <path
              key={`te-${i}`}
              d={`M${from.x},${from.y + 16} C${from.x},${from.y + 36} ${to.x},${to.y - 36} ${to.x},${to.y - 16}`}
              fill="none"
              stroke="var(--line-strong)"
              strokeWidth={1.4}
            />
          ))}
          {flat.map(node => {
            if (node.kind === "root") {
              return (
                <g key={node.id}>
                  <circle cx={node.x} cy={node.y} r={48} fill="url(#root-halo)" />
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={28}
                    fill="var(--highlight)"
                    stroke="var(--surface)"
                    strokeWidth={4}
                  />
                  <text
                    x={node.x}
                    y={node.y + 5}
                    textAnchor="middle"
                    fill="white"
                    fontSize={13}
                    fontWeight={700}
                  >
                    {node.label
                      .split(" ")
                      .map(p => p[0])
                      .join("")
                      .slice(0, 2)}
                  </text>
                  <text
                    x={node.x}
                    y={node.y - 48}
                    textAnchor="middle"
                    fill="var(--ink)"
                    fontSize={13}
                    fontWeight={600}
                  >
                    {node.label}
                  </text>
                </g>
              );
            }
            if (node.kind === "cluster") {
              return (
                <g key={node.id}>
                  <rect
                    x={node.x - 60}
                    y={node.y - 14}
                    width={120}
                    height={28}
                    rx={14}
                    fill="var(--surface)"
                    stroke="var(--line-strong)"
                    strokeWidth={1}
                  />
                  <text x={node.x} y={node.y + 4} textAnchor="middle" fill="var(--ink-soft)" fontSize={12}>
                    {node.label}
                  </text>
                </g>
              );
            }
            // leaf topic
            const data = node.data!;
            const size = 10 + Math.min(data.encounter_count, 8) * 2.5;
            const fill = masteryColor(data.mastery_score);
            const struggling = data.struggle_signal > 0.5;
            const isHover = hover?.id === node.id;
            return (
              <g
                key={node.id}
                onMouseEnter={() => setHover(node)}
                onMouseLeave={() => setHover(null)}
                onClick={() => data && onSelectTopic?.(data)}
                style={{ cursor: onSelectTopic ? "pointer" : "default" }}
              >
                {struggling && (
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r={size + 6}
                    fill="none"
                    stroke={fill}
                    strokeDasharray="3 3"
                    strokeOpacity={0.5}
                  />
                )}
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={isHover ? size + 3 : size}
                  fill={fill}
                  stroke="var(--surface)"
                  strokeWidth={3}
                  opacity={0.92}
                />
                <text
                  x={node.x}
                  y={node.y + size + 14}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--ink)"
                  style={{ pointerEvents: "none" }}
                >
                  {data.topic.length > 22 ? data.topic.slice(0, 21) + "…" : data.topic}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
      {hover?.kind === "topic" && hover.data && (
        <div
          style={{
            position: "absolute",
            left: 14,
            bottom: 14,
            maxWidth: 320,
            padding: "12px 14px",
            background: "var(--surface)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-card)",
            zIndex: 3,
            pointerEvents: "none"
          }}
        >
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 6 }}>{hover.data.topic}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
            <span className="chip">mastery {(hover.data.mastery_score * 10).toFixed(1)}/10</span>
            <span className="chip">exposure {(hover.data.exposure_score * 10).toFixed(1)}/10</span>
            <span className="chip">seen {hover.data.encounter_count}×</span>
          </div>
          {hover.data.struggle_signal > 0.5 && (
            <div style={{ fontSize: 12, color: "var(--danger)" }}>
              Struggle signal: {hover.data.struggle_signal.toFixed(2)}
            </div>
          )}
          {hover.data.strength_signal > 0.5 && (
            <div style={{ fontSize: 12, color: "var(--success)" }}>
              Strength signal: {hover.data.strength_signal.toFixed(2)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
