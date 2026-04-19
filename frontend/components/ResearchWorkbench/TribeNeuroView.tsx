"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { TribePredictionPayload } from "@/lib/api";

type Props = {
  tribe: TribePredictionPayload | null;
  loading?: boolean;
  onRun: () => void;
};

function activationColor(value: number) {
  const clamped = Math.max(-1, Math.min(1, value));
  if (clamped >= 0) {
    return new THREE.Color(0.08 + clamped * 0.75, 0.38 + clamped * 0.35, 0.34);
  }
  return new THREE.Color(0.72, 0.28 + Math.abs(clamped) * 0.12, 0.25);
}

function hashAngle(label: string, offset: number) {
  let hash = 0;
  for (let i = 0; i < label.length; i += 1) hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  return ((hash + offset) % 1000) / 1000;
}

function roiPosition(label: string, index: number, total: number) {
  const theta = Math.PI * (0.18 + 0.64 * hashAngle(label, index * 173));
  const phi = Math.PI * 2 * (index / Math.max(total, 1) + hashAngle(label, 91) * 0.18);
  const side = index % 2 === 0 ? -0.44 : 0.44;
  return new THREE.Vector3(
    side + Math.sin(theta) * Math.cos(phi) * 0.64,
    Math.cos(theta) * 0.76,
    Math.sin(theta) * Math.sin(phi) * 0.48
  );
}

export function TribeNeuroView({ tribe, loading, onRun }: Props) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [timeIndex, setTimeIndex] = useState(0);
  const prediction = tribe?.prediction;
  const roiTimeseries = prediction?.roi_timeseries || {};
  const roiNames = useMemo(() => Object.keys(roiTimeseries), [roiTimeseries]);
  const frameCount = Math.max(0, ...roiNames.map(roi => roiTimeseries[roi]?.length || 0));
  const topRois = roiNames
    .map(roi => {
      const series = roiTimeseries[roi] || [];
      const value = Number(series[Math.min(timeIndex, Math.max(series.length - 1, 0))] || 0);
      return { roi, value };
    })
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, 8);

  useEffect(() => {
    if (!mountRef.current || !prediction || roiNames.length === 0) return;
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#eef3ed");
    const camera = new THREE.PerspectiveCamera(42, mount.clientWidth / Math.max(mount.clientHeight, 1), 0.1, 100);
    camera.position.set(0, 0.1, 4.2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight("#ffffff", 1.4));
    const light = new THREE.DirectionalLight("#ffffff", 1.3);
    light.position.set(2, 3, 4);
    scene.add(light);

    const hemisphereGeometry = new THREE.SphereGeometry(0.82, 48, 24);
    const baseMaterial = new THREE.MeshStandardMaterial({
      color: "#f8faf8",
      roughness: 0.58,
      metalness: 0.03,
      transparent: true,
      opacity: 0.72
    });
    const left = new THREE.Mesh(hemisphereGeometry, baseMaterial.clone());
    left.scale.set(0.76, 1.0, 0.62);
    left.position.x = -0.46;
    const right = new THREE.Mesh(hemisphereGeometry, baseMaterial.clone());
    right.scale.set(0.76, 1.0, 0.62);
    right.position.x = 0.46;
    scene.add(left, right);

    const lineMaterial = new THREE.LineBasicMaterial({ color: "#94a3a0", transparent: true, opacity: 0.35 });
    const connectorMaterial = new THREE.LineBasicMaterial({ color: "#0f766e", transparent: true, opacity: 0.5 });
    const positions = new Map<string, THREE.Vector3>();
    roiNames.forEach((roi, index) => {
      const value = Number(roiTimeseries[roi]?.[Math.min(timeIndex, Math.max((roiTimeseries[roi]?.length || 1) - 1, 0))] || 0);
      const pos = roiPosition(roi, index, roiNames.length);
      positions.set(roi, pos);
      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(0.035 + Math.min(Math.abs(value), 1) * 0.07, 24, 16),
        new THREE.MeshStandardMaterial({
          color: activationColor(value),
          emissive: activationColor(value),
          emissiveIntensity: Math.min(0.7, Math.abs(value) * 0.8),
          roughness: 0.38
        })
      );
      sphere.position.copy(pos);
      scene.add(sphere);

      const stem = new THREE.BufferGeometry().setFromPoints([pos.clone().multiplyScalar(0.74), pos]);
      scene.add(new THREE.Line(stem, lineMaterial));
    });

    (prediction.connectivity || []).slice(0, 24).forEach(edge => {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      const material = connectorMaterial.clone();
      material.opacity = Math.max(0.15, Math.min(0.8, Math.abs(edge.weight)));
      material.color = edge.weight >= 0 ? new THREE.Color("#0f766e") : new THREE.Color("#b94a48");
      scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([source, target]), material));
    });

    const grid = new THREE.GridHelper(3.2, 12, "#cbd5cb", "#dde5dc");
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.72;
    scene.add(grid);

    let frame = 0;
    let animation = 0;
    const render = () => {
      frame += 0.006;
      left.rotation.y = frame;
      right.rotation.y = frame;
      scene.rotation.y = Math.sin(frame * 0.7) * 0.14;
      renderer.render(scene, camera);
      animation = requestAnimationFrame(render);
    };
    render();

    const resize = () => {
      if (!mountRef.current) return;
      camera.aspect = mountRef.current.clientWidth / Math.max(mountRef.current.clientHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    };
    window.addEventListener("resize", resize);

    return () => {
      cancelAnimationFrame(animation);
      window.removeEventListener("resize", resize);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [prediction, roiNames, roiTimeseries, timeIndex]);

  return (
    <section className="research-panel">
      <div className="research-panel__header">
        <div>
          <div className="research-kicker">TRIBE Neuroview</div>
          <h2>Predicted fMRI on personalized lesson content</h2>
        </div>
        <button className="button secondary" onClick={onRun} disabled={loading}>
          {loading ? "Requesting..." : "Run TRIBE v2"}
        </button>
      </div>

      {!prediction || tribe?.status === "not_requested" ? (
        <p className="muted">Run TRIBE v2 to request predicted brain responses for the selected personalized lesson.</p>
      ) : tribe?.status !== "complete" ? (
        <div className="research-viz">
          <div className="research-viz__title">Service status</div>
          <p>Status: {tribe?.status}</p>
          {prediction.error && <p className="error">{prediction.error}</p>}
          <p className="muted">
            Configure `EDUTRACK_TRIBE_V2_ENABLED=1` and `EDUTRACK_TRIBE_V2_BASE_URL` to connect the external service.
          </p>
        </div>
      ) : (
        <div className="neuro-layout">
          <div className="neuro-scene" ref={mountRef} />
          <aside className="neuro-side">
            <div className="research-viz__title">Timeline</div>
            <input
              className="range"
              type="range"
              min={0}
              max={Math.max(frameCount - 1, 0)}
              value={Math.min(timeIndex, Math.max(frameCount - 1, 0))}
              onChange={event => setTimeIndex(Number(event.target.value))}
            />
            <p className="muted">
              Frame {Math.min(timeIndex + 1, Math.max(frameCount, 1))}/{Math.max(frameCount, 1)} / lag{" "}
              {prediction.hemodynamic_lag_s}s / {prediction.surface_summary?.space || "fsaverage5"}
            </p>
            <div className="research-viz__title">Peak regions</div>
            <div className="roi-list">
              {topRois.map(item => (
                <div className="roi-row" key={item.roi}>
                  <span>{item.roi}</span>
                  <strong style={{ color: item.value >= 0 ? "#0f766e" : "#b94a48" }}>{item.value.toFixed(3)}</strong>
                </div>
              ))}
            </div>
            <div className="research-viz__title">Networks</div>
            <div className="roi-list">
              {(prediction.connectivity || []).slice(0, 6).map((edge, index) => (
                <div className="roi-row" key={`${edge.source}-${edge.target}-${index}`}>
                  <span>
                    {edge.source} {"->"} {edge.target}
                  </span>
                  <strong>{edge.weight.toFixed(2)}</strong>
                </div>
              ))}
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}
