"use client";

import { useMemo, useState } from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MechanisticView } from "@/lib/api";

type Props = {
  view: MechanisticView | null;
  loading?: boolean;
  onRetrain: () => void;
};

type HeatMode = "influence" | "gradients" | "contribution" | "weights";

type SelectedCell = {
  layerId: string;
  layerLabel: string;
  mode: HeatMode;
  row: string;
  column: string;
  value: number;
  implication?: string;
};

function color(value: number) {
  if (value >= 0) return `rgba(37, 99, 235, ${Math.min(0.95, 0.25 + Math.abs(value) * 2)})`;
  return `rgba(225, 29, 72, ${Math.min(0.95, 0.25 + Math.abs(value) * 2)})`;
}

function layerX(index: number, total: number) {
  return 80 + index * (760 / Math.max(total - 1, 1));
}

function heatColor(value: number, maxAbs: number) {
  const intensity = Math.min(1, Math.abs(value) / Math.max(maxAbs, 0.0000001));
  if (value >= 0) return `rgba(37, 99, 235, ${0.1 + intensity * 0.82})`;
  return `rgba(225, 29, 72, ${0.12 + intensity * 0.82})`;
}

function compact(value: number) {
  if (value === 0) return "0.000";
  if (Math.abs(value) >= 0.01) return value.toFixed(3);
  return value.toExponential(1);
}

function LossHeatmap({ history }: { history: Array<{ epoch: number; loss: number }> }) {
  if (!history.length) {
    return <p className="muted">Cold-start mode has no gradient descent history yet.</p>;
  }
  const maxLoss = Math.max(...history.map(item => item.loss), 0.000001);
  const firstLoss = history[0]?.loss || 0;
  const lastLoss = history[history.length - 1]?.loss || 0;
  const reduction = firstLoss > 0 ? ((firstLoss - lastLoss) / firstLoss) * 100 : 0;

  return (
    <div className="loss-heatmap">
      <div className="loss-heatmap__cells" aria-label="Epoch loss heatmap">
        {history.map(item => {
          const ratio = item.loss / maxLoss;
          return (
            <span
              key={item.epoch}
              title={`epoch ${item.epoch}: loss ${item.loss}`}
              style={{
                background: `rgba(37, 99, 235, ${0.1 + ratio * 0.72})`,
                color: ratio > 0.55 ? "#fff" : "#1f2a25",
                fontSize: 9,
                lineHeight: 1,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {compact(item.loss)}
            </span>
          );
        })}
      </div>
      <div className="loss-heatmap__meta">
        <span>epoch {history[0].epoch}</span>
        <strong>{reduction.toFixed(1)}% loss reduction</strong>
        <span>epoch {history[history.length - 1].epoch}</span>
      </div>
    </div>
  );
}

function MatrixHeatmap({
  title,
  rows,
  columns,
  matrix,
  layerId,
  layerLabel,
  mode,
  implication,
  selectedCell,
  focusRow,
  onSelect
}: {
  title: string;
  rows: string[];
  columns: string[];
  matrix: number[][];
  layerId: string;
  layerLabel: string;
  mode: HeatMode;
  implication?: string;
  selectedCell: SelectedCell | null;
  focusRow: string | null;
  onSelect: (cell: SelectedCell) => void;
}) {
  const values = matrix.flat();
  const maxAbs = Math.max(0.0000001, ...values.map(value => Math.abs(value)));

  return (
    <div className="matrix-heatmap">
      <div className="matrix-heatmap__title">{title}</div>
      <div className="matrix-heatmap__columns" style={{ gridTemplateColumns: `120px repeat(${columns.length}, minmax(22px, 1fr))` }}>
        <span />
        {columns.map(column => (
          <b key={column}>{column}</b>
        ))}
      </div>
      <div className="matrix-heatmap__grid" style={{ gridTemplateColumns: `120px repeat(${columns.length}, minmax(22px, 1fr))` }}>
        {rows.map((row, rowIndex) => (
          <div className="matrix-heatmap__row" key={row}>
            <span className={`matrix-heatmap__label ${focusRow === row ? "matrix-heatmap__label--focus" : ""}`}>{row.replace(/_/g, " ")}</span>
            {columns.map((column, columnIndex) => {
              const value = matrix[rowIndex]?.[columnIndex] ?? 0;
              const selected =
                selectedCell?.layerId === layerId &&
                selectedCell.mode === mode &&
                selectedCell.row === row &&
                selectedCell.column === column;
              return (
                <button
                  className={`matrix-heatmap__cell ${selected ? "matrix-heatmap__cell--selected" : ""} ${
                    focusRow === row ? "matrix-heatmap__cell--row-focus" : ""
                  }`}
                  key={`${row}-${column}`}
                  title={`${row} -> ${column}: ${value}`}
                  style={{
                    background: heatColor(value, maxAbs),
                    fontSize: 9,
                    fontWeight: Math.abs(value) === maxAbs ? 700 : 500,
                    lineHeight: 1,
                    padding: "2px 1px",
                    color: Math.abs(value) / Math.max(maxAbs, 1e-7) > 0.55 ? "#fff" : "#1f2a25",
                  }}
                  onClick={() => onSelect({ layerId, layerLabel, mode, row, column, value, implication })}
                >
                  {compact(value)}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function modeTitle(mode: HeatMode) {
  if (mode === "influence") return "Activation-weighted influence";
  if (mode === "gradients") return "Loss gradient";
  if (mode === "contribution") return "Update pressure";
  return "Learned weight";
}

function interpretation(cell: SelectedCell | null) {
  if (!cell) return "Select a heatmap cell to inspect a local mechanism.";
  const sign = cell.value >= 0 ? "positive" : "negative";
  if (cell.mode === "influence") {
    return `${cell.row.replace(/_/g, " ")} has a ${sign} forward route into ${cell.column}. This is a local contribution for this student and session, so inactive ReLU paths collapse toward zero.`;
  }
  if (cell.mode === "gradients") {
    return `${cell.row.replace(/_/g, " ")} -> ${cell.column} has ${sign} loss sensitivity. Larger magnitude means the current error would push this connection harder during backprop.`;
  }
  if (cell.mode === "contribution") {
    return `${cell.row.replace(/_/g, " ")} -> ${cell.column} combines weight and gradient. It estimates where the next update would most change the active circuit.`;
  }
  return `${cell.row.replace(/_/g, " ")} -> ${cell.column} is a learned association. Inspect influence or gradient to see whether it is active and loss-relevant right now.`;
}

export function NeuralMicroscope({ view, loading, onRetrain }: Props) {
  const [openHeatmap, setOpenHeatmap] = useState<string | null>("input-hidden1");
  const [heatMode, setHeatMode] = useState<HeatMode>("influence");
  const [selectedCell, setSelectedCell] = useState<SelectedCell | null>(null);
  const [focusRow, setFocusRow] = useState<string | null>(null);
  const topFeatures = view?.features.slice(0, 10) || [];
  const layers = view?.layers || [];
  const edges = view?.edges.slice(0, 80) || [];
  const heatmaps = view?.heatmaps || [];
  const lossReduction = useMemo(() => {
    const history = view?.model.loss_history || [];
    if (history.length < 2 || !history[0].loss) return null;
    const first = history[0].loss;
    const last = history[history.length - 1].loss;
    return ((first - last) / first) * 100;
  }, [view]);

  const nodePositions = new Map<string, { x: number; y: number }>();
  layers.forEach((layer, layerIdx) => {
    layer.nodes.forEach((node, nodeIdx) => {
      const count = layer.nodes.length;
      const y = count <= 1 ? 180 : 48 + nodeIdx * (270 / Math.max(count - 1, 1));
      nodePositions.set(node.id, { x: layerX(layerIdx, Math.max(layers.length, 1)), y });
    });
  });

  return (
    <section className="research-panel">
      <div className="research-panel__header">
        <div>
          <div className="research-kicker">Neural Microscope</div>
          <h2>Personalized layers, loss, gradients, and backprop</h2>
        </div>
        <button className="button secondary" onClick={onRetrain} disabled={loading}>
          {loading ? "Training..." : "Retrain surrogate"}
        </button>
      </div>

      {!view ? (
        <p className="muted">Choose a student to train and inspect their personalized surrogate.</p>
      ) : (
        <>
          <div className="research-statline research-statline--left">
            <span>Status: {view.model.status}</span>
            <span>Prediction: {(view.backprop.prediction * 100).toFixed(1)}%</span>
            <span>Loss: {view.backprop.loss.toFixed(5)}</span>
            <span>Gradient norm: {view.backprop.input_gradient_norm.toFixed(5)}</span>
            {lossReduction !== null && <span>Training loss: {lossReduction.toFixed(1)}% lower</span>}
          </div>

          <div className="research-network" aria-label="Personalized neural network activation graph">
            <svg viewBox="0 0 920 380" role="img">
              {edges.map((edge, i) => {
                const from = nodePositions.get(edge.from);
                const to = nodePositions.get(edge.to);
                if (!from || !to) return null;
                return (
                  <line
                    key={`${edge.from}-${edge.to}-${i}`}
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke={color(edge.weight)}
                    strokeWidth={Math.max(0.6, Math.min(5, Math.abs(edge.weight) * 5 + Math.abs(edge.gradient) * 40))}
                    opacity={0.58}
                  />
                );
              })}
              {layers.map((layer, layerIdx) => (
                <g key={layer.id}>
                  <text x={layerX(layerIdx, layers.length)} y={24} textAnchor="middle" fill="#3f4f46" fontSize="13">
                    {layer.label}
                  </text>
                  {layer.nodes.map(node => {
                    const pos = nodePositions.get(node.id);
                    if (!pos) return null;
                    const activation = Math.max(0, Math.min(1, Number(node.activation)));
                    const r = layer.type === "input" ? 7 : layer.type === "output" ? 22 : 13 + activation * 8;
                    return (
                      <g key={node.id}>
                        <circle
                          cx={pos.x}
                          cy={pos.y}
                          r={r}
                          fill={layer.type === "output" ? "#1d4ed8" : `rgba(37, 99, 235, ${0.18 + activation * 0.72})`}
                          stroke={node.delta && node.delta < 0 ? "#e11d48" : "#2563eb"}
                          strokeWidth={2}
                        />
                        {layer.type !== "input" && (
                          <text x={pos.x} y={pos.y + 4} textAnchor="middle" fill="#fff" fontSize="11">
                            {node.label}
                          </text>
                        )}
                      </g>
                    );
                  })}
                </g>
              ))}
            </svg>
          </div>

          <div className="research-grid research-grid--three">
            <div className="research-viz">
              <div className="research-viz__title">Loss function</div>
              {view.model.loss_history.length ? (
                <ResponsiveContainer width="100%" height={210}>
                  <LineChart data={view.model.loss_history}>
                    <XAxis dataKey="epoch" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="loss" stroke="#2563eb" strokeWidth={3} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <p className="muted">Cold-start weights are active until labeled samples exist.</p>
              )}
            </div>

            <div className="research-viz research-viz--wide">
              <div className="research-viz__title">Input saliency</div>
              <div className="saliency-list">
                {topFeatures.map(feature => {
                  const width = `${Math.min(100, Math.abs(feature.saliency) * 6000 + 8)}%`;
                  return (
                    <div className="saliency-row" key={feature.name}>
                      <span>{feature.name.replace(/_/g, " ")}</span>
                      <div>
                        <i style={{ width, background: feature.saliency >= 0 ? "#2563eb" : "#e11d48" }} />
                      </div>
                      <strong>{feature.saliency.toFixed(5)}</strong>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="research-viz">
              <div className="research-viz__title">Backprop trace</div>
              <p>
                Target{" "}
                <strong>{view.backprop.target === null ? "unlabeled" : `${(view.backprop.target * 100).toFixed(1)}%`}</strong>
              </p>
              <p>
                Output <strong>{(view.backprop.prediction * 100).toFixed(1)}%</strong>
              </p>
              <p>
                Error signal flows through {view.layers.length} layers with a learning rate of{" "}
                <strong>{view.backprop.learning_rate}</strong>.
              </p>
              <p className="muted">
                Student samples: {view.model.student_sample_count}; cohort samples:{" "}
                {Math.max(view.model.sample_count - view.model.student_sample_count, 0)}.
              </p>
            </div>
          </div>

          <div className="heatmap-lab">
            <div className="heatmap-lab__header">
              <div>
                <div className="research-viz__title">Expandable Backprop Heatmaps</div>
                <p>Open a layer, switch the matrix type, and select cells to inspect local routes through this student-specific surrogate.</p>
              </div>
              <div className="heatmap-legend">
                <span><i className="heatmap-legend__positive" /> positive route</span>
                <span><i className="heatmap-legend__negative" /> negative route</span>
              </div>
            </div>

            <div className="loss-ribbon">
              <div className="research-viz__title">Loss descent by epoch</div>
              <LossHeatmap history={view.model.loss_history} />
            </div>

            <div className="heatmap-controls">
              <div>
                <div className="research-viz__title">Matrix type</div>
                <div className="segmented-control">
                  {(["influence", "gradients", "contribution", "weights"] as HeatMode[]).map(mode => (
                    <button
                      className={heatMode === mode ? "segmented-control__item segmented-control__item--active" : "segmented-control__item"}
                      key={mode}
                      onClick={() => setHeatMode(mode)}
                    >
                      {modeTitle(mode)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <div className="research-viz__title">Focus row</div>
                <div className="focus-chip-row">
                  <button className={!focusRow ? "focus-chip focus-chip--active" : "focus-chip"} onClick={() => setFocusRow(null)}>
                    all rows
                  </button>
                  {topFeatures.slice(0, 5).map(feature => (
                    <button
                      className={focusRow === feature.name ? "focus-chip focus-chip--active" : "focus-chip"}
                      key={feature.name}
                      onClick={() => {
                        setOpenHeatmap("input-hidden1");
                        setFocusRow(feature.name);
                      }}
                    >
                      {feature.name.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="heatmap-stack">
              {heatmaps.length ? (
                heatmaps.map(layer => {
                  const open = openHeatmap === layer.id;
                  const matrix =
                    heatMode === "influence"
                      ? layer.influence || layer.contribution
                      : heatMode === "gradients"
                        ? layer.gradients
                        : heatMode === "contribution"
                          ? layer.contribution
                          : layer.weights;
                  const stat = layer.stats[heatMode] || layer.stats.contribution;
                  return (
                    <article className={`heatmap-card ${open ? "heatmap-card--open" : ""}`} key={layer.id}>
                      <button className="heatmap-card__summary" onClick={() => setOpenHeatmap(open ? null : layer.id)}>
                        <span>{layer.label}</span>
                        <strong>{heatMode} energy {stat.energy.toFixed(5)}</strong>
                        <i>{open ? "collapse" : "expand"}</i>
                      </button>
                      {open && (
                        <div className="heatmap-card__body">
                          {layer.implication && <p className="heatmap-implication">{layer.implication}</p>}
                          <div className="heatmap-stat-grid">
                            <span>weight max {layer.stats.weights.max_abs.toFixed(4)}</span>
                            <span>gradient max {layer.stats.gradients.max_abs.toFixed(6)}</span>
                            <span>influence energy {(layer.stats.influence?.energy || 0).toFixed(6)}</span>
                          </div>
                          <div className="heatmap-inspector-grid">
                            <MatrixHeatmap
                              title={modeTitle(heatMode)}
                              rows={layer.rows}
                              columns={layer.columns}
                              matrix={matrix}
                              layerId={layer.id}
                              layerLabel={layer.label}
                              mode={heatMode}
                              implication={layer.implication}
                              selectedCell={selectedCell}
                              focusRow={layer.id === "input-hidden1" ? focusRow : null}
                              onSelect={setSelectedCell}
                            />
                            <aside className="cell-inspector">
                              <div className="research-viz__title">Selected mechanism</div>
                              {selectedCell ? (
                                <>
                                  <strong>{selectedCell.layerLabel}</strong>
                                  <span>
                                    {selectedCell.row.replace(/_/g, " ")} {"->"} {selectedCell.column}
                                  </span>
                                  <b>{compact(selectedCell.value)}</b>
                                  <p>{interpretation(selectedCell)}</p>
                                </>
                              ) : (
                                <p>{interpretation(null)}</p>
                              )}
                            </aside>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })
              ) : (
                <p className="muted">Heatmap matrices are not available for this surrogate response yet.</p>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
