"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { TribePredictionPayload } from "@/lib/api";

type Props = {
  tribe: TribePredictionPayload | null;
  loading?: boolean;
  onRun: () => void;
};

// Anatomical positions on a unit sphere — matches the ROI names emitted by the
// backend (services/tribe.py _DEMO_ROIS and the real TRIBE v2 output). Anything
// not listed here falls back to a deterministic hash position so unexpected
// ROI labels still render somewhere.
const ANATOMY: Record<string, { pos: [number, number, number]; label: string; blurb: string }> = {
  IPS_L: {
    pos: [-0.45, 0.82, -0.15],
    label: "Intraparietal sulcus (L)",
    blurb: "Numerical and spatial reasoning — keeping track of quantities and ordering magnitudes."
  },
  IPS_R: {
    pos: [0.45, 0.82, -0.15],
    label: "Intraparietal sulcus (R)",
    blurb: "Right-side numerical/spatial processing, estimating magnitudes and visual layout."
  },
  dlPFC_L: {
    pos: [-0.6, 0.55, 0.7],
    label: "Dorsolateral prefrontal cortex (L)",
    blurb: "Working memory and planning — the mental whiteboard holding multi-step reasoning."
  },
  dlPFC_R: {
    pos: [0.6, 0.55, 0.7],
    label: "Dorsolateral prefrontal cortex (R)",
    blurb: "Right-side working memory and attention control; ramps up during effortful steps."
  },
  ACC: {
    pos: [0.0, 0.35, 0.35],
    label: "Anterior cingulate",
    blurb: "Error monitoring and focus — spikes when the student catches a mistake or resists distraction."
  },
  Angular_L: {
    pos: [-0.85, 0.25, -0.35],
    label: "Angular gyrus (L)",
    blurb: "Binds symbols to meaning — central to reading comprehension and mapping words to math."
  },
  Broca: {
    pos: [-0.78, 0.15, 0.55],
    label: "Broca's area",
    blurb: "Inner-speech and language production; active when a learner silently verbalizes a rule."
  },
  Wernicke: {
    pos: [-0.82, -0.05, -0.35],
    label: "Wernicke's area",
    blurb: "Language comprehension — decoding problem statements into concepts."
  },
  V1: {
    pos: [0.0, 0.0, -0.98],
    label: "Primary visual cortex",
    blurb: "Raw vision — engaged by diagrams, worked-example figures, and video content."
  },
  FG_L: {
    pos: [-0.35, -0.5, -0.55],
    label: "Fusiform gyrus (L)",
    blurb: "Recognizes letters, digits, and symbolic forms — turns squiggles into meaning."
  },
  Hippocampus_L: {
    pos: [-0.28, -0.25, 0.1],
    label: "Hippocampus (L)",
    blurb: "Consolidates new memories — engaged during effortful recall and review blocks."
  }
};

function fallbackPosition(name: string): [number, number, number] {
  // Stable pseudo-random position for ROIs we don't have an anatomy entry for.
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const theta = ((h >>> 0) % 1000) / 1000 * Math.PI;
  const phi = (((h * 17) >>> 0) % 1000) / 1000 * Math.PI * 2;
  return [
    Math.sin(theta) * Math.cos(phi),
    Math.cos(theta),
    Math.sin(theta) * Math.sin(phi)
  ];
}

function roiEntry(name: string) {
  const known = ANATOMY[name];
  if (known) return known;
  return {
    pos: fallbackPosition(name),
    label: name.replace(/_/g, " "),
    blurb: "Additional ROI reported by the prediction."
  };
}

/** Heat color: cool blue → teal → amber → red → pure white-hot, as signed activation -1..+1. */
function heatColor(value: number, target: THREE.Color = new THREE.Color()): THREE.Color {
  const signed = Math.max(-1, Math.min(1, value));
  const a = Math.max(0, signed);
  if (a < 0.3) {
    const t = a / 0.3;
    target.setRGB(0.12 + t * 0.85, 0.45 + t * 0.38, 0.92 - t * 0.65);
  } else if (a < 0.6) {
    const t = (a - 0.3) / 0.3;
    // amber → saturated red
    target.setRGB(0.97 + t * 0.03, 0.83 - t * 0.63, 0.27 - t * 0.22);
  } else if (a < 0.85) {
    const t = (a - 0.6) / 0.25;
    // saturated red → bright yellow
    target.setRGB(1.0, 0.2 + t * 0.78, 0.05 + t * 0.25);
  } else {
    const t = (a - 0.85) / 0.15;
    // bright yellow → pure white-hot
    target.setRGB(1.0, 0.98 + t * 0.02, 0.3 + t * 0.7);
  }
  if (signed < 0) {
    target.lerp(new THREE.Color(0.18, 0.42, 0.85), Math.min(1, -signed));
  }
  return target;
}

function heatCss(value: number): string {
  const c = heatColor(value, new THREE.Color());
  return `#${c.getHexString()}`;
}

// Ellipsoid scale to match the cerebrum mesh proportions.
const BRAIN_SCALE = new THREE.Vector3(1.0, 0.88, 1.18);

export function TribeNeuroView({ tribe, loading, onRun }: Props) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [timeIndex, setTimeIndex] = useState(0);
  const [hoveredRoi, setHoveredRoi] = useState<string | null>(null);
  const [selectedRoi, setSelectedRoi] = useState<string | null>(null);

  const prediction = tribe?.prediction;
  const roiTimeseries = prediction?.roi_timeseries || {};
  const roiNames = useMemo(() => Object.keys(roiTimeseries), [roiTimeseries]);
  const frameCount = Math.max(0, ...roiNames.map((roi) => roiTimeseries[roi]?.length || 0));

  const frameIndex = Math.min(timeIndex, Math.max(frameCount - 1, 0));

  const roiValues = useMemo(() => {
    const out: Record<string, number> = {};
    for (const name of roiNames) {
      const series = roiTimeseries[name] || [];
      out[name] = Number(series[frameIndex] ?? 0);
    }
    return out;
  }, [roiNames, roiTimeseries, frameIndex]);

  const topRois = useMemo(() => {
    return roiNames
      .map((roi) => ({ roi, value: roiValues[roi] ?? 0, meta: roiEntry(roi) }))
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
      .slice(0, 8);
  }, [roiNames, roiValues]);

  const activeRoi = (() => {
    const name = hoveredRoi ?? selectedRoi ?? topRois[0]?.roi ?? null;
    if (!name) return null;
    return { name, value: roiValues[name] ?? 0, meta: roiEntry(name) };
  })();

  useEffect(() => {
    if (!mountRef.current || !prediction || roiNames.length === 0) return;
    const mount = mountRef.current;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      40,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.1,
      100
    );
    camera.position.set(0, 0.25, 4.4);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    // Lighting — bright ambient so vertex-colored heat reads clearly through the translucent surface.
    scene.add(new THREE.AmbientLight(0xffffff, 0.95));
    const key = new THREE.DirectionalLight(0xffffff, 0.75);
    key.position.set(3, 5, 4);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xffd4c8, 0.35);
    rim.position.set(-3, 2, -2);
    scene.add(rim);

    const brain = new THREE.Group();
    scene.add(brain);

    const hemispheres: Array<{
      mesh: THREE.Mesh;
      worldPositions: THREE.Vector3[];
      colors: Float32Array;
    }> = [];

    // --- Realistic(-ish) cerebrum: single mesh with multi-octave ridge noise. ---
    function buildCerebrum(): THREE.Mesh {
      const geom = new THREE.IcosahedronGeometry(1, 6);
      const pos = geom.attributes.position;
      const tmp = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) {
        tmp.fromBufferAttribute(pos, i);
        const dir = tmp.clone().normalize();
        const x = dir.x;
        const y = dir.y;
        const z = dir.z;

        // Multi-octave "ridge noise" using products of trig functions.
        const oct = (fx: number, fy: number, fz: number, phase = 0) =>
          Math.sin(x * fx + phase) *
          Math.cos(y * fy + phase * 0.7) *
          Math.sin(z * fz + phase * 1.3);

        const ridge = (v: number) => 1 - Math.abs(v);

        const big = oct(4.2, 3.1, 4.5, 0.2);
        const mid = oct(9.1, 7.7, 8.8, 1.7);
        const small = oct(17.7, 15.3, 18.4, 3.5);
        const micro = oct(33.1, 30.7, 34.5, 5.1);

        let radius = 1.0;
        radius += 0.03 * big;                 // lobe-scale undulation
        radius -= 0.055 * ridge(mid);         // primary gyri/sulci
        radius -= 0.03 * ridge(small);        // secondary folds
        radius -= 0.014 * ridge(micro);       // surface wrinkles

        // Longitudinal fissure — deep groove along x≈0 on the top surface.
        const fissureDepth = Math.exp(-(x * x) / 0.012) * Math.max(0, y + 0.05) * 0.18;
        radius -= fissureDepth;

        // Central sulcus — horizontal cut roughly at y≈0.25
        const centralSulcus =
          Math.exp(-((y - 0.25) * (y - 0.25)) / 0.012) *
          Math.exp(-(z * z) / 0.45) * 0.045;
        radius -= centralSulcus;

        // Reconstruct and apply anatomical aspect ratio.
        const out = dir.multiplyScalar(radius);
        out.x *= 1.0;   // L-R
        out.y *= 0.88;  // slightly flatter top-to-bottom
        out.z *= 1.18;  // front-to-back longer (frontal/occipital poles)

        pos.setXYZ(i, out.x, out.y, out.z);
      }
      pos.needsUpdate = true;
      geom.computeVertexNormals();

      const colorArr = new Float32Array(pos.count * 3);
      geom.setAttribute("color", new THREE.BufferAttribute(colorArr, 3));

      const mat = new THREE.MeshStandardMaterial({
        color: 0xffffff,
        vertexColors: true,
        roughness: 0.55,
        metalness: 0.04,
        transparent: true,
        opacity: 0.85,
        depthWrite: false,
        flatShading: false
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.renderOrder = 1;
      brain.add(mesh);

      const world: THREE.Vector3[] = [];
      for (let i = 0; i < pos.count; i++) {
        world.push(new THREE.Vector3().fromBufferAttribute(pos, i));
      }
      hemispheres.push({ mesh, worldPositions: world, colors: colorArr });
      return mesh;
    }

    buildCerebrum();

    // Cerebellum — folded sphere protruding behind and below the cortex.
    function buildCerebellum(): void {
      const geom = new THREE.IcosahedronGeometry(0.42, 4);
      const pos = geom.attributes.position;
      const tmp = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) {
        tmp.fromBufferAttribute(pos, i);
        const n = tmp.clone().normalize();
        const folds =
          Math.sin(n.y * 22 + n.x * 7) * 0.02 +
          Math.cos(n.x * 18 + n.z * 10) * 0.015;
        tmp.setLength(0.42 * (1 + folds));
        pos.setXYZ(i, tmp.x, tmp.y, tmp.z);
      }
      pos.needsUpdate = true;
      geom.computeVertexNormals();
      const mat = new THREE.MeshStandardMaterial({
        color: 0xe0a095,
        roughness: 0.62,
        metalness: 0.04,
        transparent: true,
        opacity: 0.92
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.set(0, -0.72, -0.72);
      mesh.scale.set(1.2, 0.75, 0.95);
      mesh.renderOrder = 2;
      brain.add(mesh);
    }
    buildCerebellum();

    // Brainstem — short tapered column below the cerebellum.
    function buildBrainstem(): void {
      const geom = new THREE.CylinderGeometry(0.095, 0.07, 0.4, 20, 1, true);
      const mat = new THREE.MeshStandardMaterial({
        color: 0xc48074,
        roughness: 0.58,
        metalness: 0.05,
        transparent: true,
        opacity: 0.95,
        side: THREE.DoubleSide
      });
      const mesh = new THREE.Mesh(geom, mat);
      mesh.position.set(0, -1.05, -0.4);
      mesh.rotation.x = 0.22;
      mesh.renderOrder = 2;
      brain.add(mesh);
    }
    buildBrainstem();

    // Pre-project ROI anatomical positions onto the same ellipsoid space.
    type MarkerSpec = {
      roi: string;
      labelPos: THREE.Vector3; // near the surface, slightly outside
      surfacePos: THREE.Vector3; // on the ellipsoid (for heat blending)
      markerMesh: THREE.Mesh;
      labelEl: HTMLDivElement;
    };
    const markerGroup = new THREE.Group();
    brain.add(markerGroup);
    const markers: MarkerSpec[] = [];

    // Labels layer — HTML elements projected to 2D.
    const labelLayer = document.createElement("div");
    labelLayer.style.position = "absolute";
    labelLayer.style.inset = "0";
    labelLayer.style.pointerEvents = "none";
    labelLayer.style.overflow = "hidden";
    mount.appendChild(labelLayer);

    for (const roi of roiNames) {
      const meta = roiEntry(roi);
      const pRaw = new THREE.Vector3(...meta.pos).normalize();
      const surfacePos = pRaw.clone().multiply(BRAIN_SCALE);
      // Marker sits right at the heat center (tiny outward nudge to avoid z-fighting).
      const markerPos = surfacePos.clone().multiplyScalar(1.005);
      // Label hovers slightly outside so it doesn't clip into the surface.
      const labelPos = surfacePos.clone().multiplyScalar(1.08);

      const markerMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95 });
      const markerMesh = new THREE.Mesh(new THREE.SphereGeometry(0.04, 16, 16), markerMat);
      markerMesh.position.copy(markerPos);
      markerMesh.userData = { roi };
      markerGroup.add(markerMesh);

      const labelEl = document.createElement("div");
      labelEl.style.position = "absolute";
      labelEl.style.transform = "translate(-50%, -120%)";
      labelEl.style.padding = "3px 8px";
      labelEl.style.borderRadius = "999px";
      labelEl.style.background = "rgba(15, 23, 42, 0.78)";
      labelEl.style.color = "#fff";
      labelEl.style.fontSize = "11px";
      labelEl.style.fontWeight = "600";
      labelEl.style.letterSpacing = "0.01em";
      labelEl.style.whiteSpace = "nowrap";
      labelEl.style.boxShadow = "0 2px 8px rgba(15,23,42,0.18)";
      labelEl.style.pointerEvents = "none";
      labelEl.style.opacity = "0";
      labelEl.style.transition = "opacity 180ms ease";
      labelEl.textContent = meta.label;
      labelLayer.appendChild(labelEl);

      markers.push({ roi, labelPos, surfacePos, markerMesh, labelEl });
    }

    // Raycaster for hover + click on markers.
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let dragging = false;
    let dragX = 0;
    let dragY = 0;
    let downAt = 0;
    let manualYaw = 0;
    let manualPitch = 0;

    const onPointerMove = (e: PointerEvent) => {
      const rect = mount.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      if (dragging) {
        manualYaw += (e.clientX - dragX) * 0.008;
        manualPitch += (e.clientY - dragY) * 0.004;
        manualPitch = Math.max(-0.6, Math.min(0.6, manualPitch));
        dragX = e.clientX;
        dragY = e.clientY;
        return;
      }
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(markers.map((m) => m.markerMesh));
      if (hits.length > 0) {
        const name = (hits[0].object.userData as { roi?: string }).roi ?? null;
        setHoveredRoi(name);
        mount.style.cursor = "pointer";
      } else {
        setHoveredRoi(null);
        mount.style.cursor = dragging ? "grabbing" : "grab";
      }
    };
    const onPointerDown = (e: PointerEvent) => {
      dragging = true;
      dragX = e.clientX;
      dragY = e.clientY;
      downAt = performance.now();
      mount.style.cursor = "grabbing";
    };
    const onPointerUp = () => {
      dragging = false;
      mount.style.cursor = "grab";
      if (performance.now() - downAt < 240) {
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(markers.map((m) => m.markerMesh));
        if (hits.length > 0) {
          const name = (hits[0].object.userData as { roi?: string }).roi ?? null;
          setSelectedRoi(name);
        }
      }
    };
    mount.addEventListener("pointermove", onPointerMove);
    mount.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointerup", onPointerUp);

    // ---- Heat painting: per-vertex color, peaked at each ROI, sharp falloff. ----
    // We paint using the *peak* magnitude per ROI (from roi_summary if provided,
    // else the max-abs over the timeseries) so the heatmap is a stable signature
    // of how this lesson engages the brain, not just frame-0 which is always cold.
    const SIGMA = 0.20;          // tight falloff — hot at the ROI, cool a few cm away
    const SIGMA2 = SIGMA * SIGMA;
    const warmTmp = new THREE.Color();

    const roiPeaks: Record<string, number> = {};
    const summaryRaw = (prediction as any).roi_summary || {};
    for (const roi of roiNames) {
      const s = summaryRaw[roi];
      if (s && typeof s.peak === "number") {
        roiPeaks[roi] = s.peak;
      } else {
        const series = roiTimeseries[roi] || [];
        let peak = 0;
        for (const v of series) {
          if (typeof v === "number" && Math.abs(v) > Math.abs(peak)) peak = v;
        }
        roiPeaks[roi] = peak;
      }
    }
    const roiPositions: Array<{ roi: string; pos: THREE.Vector3; peak: number }> = markers.map((m) => ({
      roi: m.roi,
      pos: m.surfacePos.clone(),
      peak: roiPeaks[m.roi] ?? 0
    }));

    function paintHeat() {
      for (const hemi of hemispheres) {
        const col = hemi.colors;
        for (let i = 0; i < hemi.worldPositions.length; i++) {
          const v = hemi.worldPositions[i];
          // Winner-take-most: strongest local contribution wins the color.
          let bestContribution = 0;
          let bestSigned = 0;
          for (const r of roiPositions) {
            const d2 = v.distanceToSquared(r.pos);
            const w = Math.exp(-d2 / SIGMA2);
            const contribution = w * Math.abs(r.peak);
            if (contribution > bestContribution) {
              bestContribution = contribution;
              bestSigned = w * r.peak;
            }
          }
          // Bias local activation hard so hotspots blaze.
          const intensity = Math.min(1, Math.pow(bestContribution, 0.45) * 2.1);
          heatColor(bestSigned, warmTmp);
          const baseR = 0.97;
          const baseG = 0.84;
          const baseB = 0.8;
          col[i * 3] = baseR * (1 - intensity) + warmTmp.r * intensity;
          col[i * 3 + 1] = baseG * (1 - intensity) + warmTmp.g * intensity;
          col[i * 3 + 2] = baseB * (1 - intensity) + warmTmp.b * intensity;
        }
        (hemi.mesh.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
      }
    }
    paintHeat();

    // Update markers each frame (pulse + color).
    const clock = new THREE.Clock();
    let raf = 0;
    const tmpVec = new THREE.Vector3();
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();
      brain.rotation.y = manualYaw + (dragging ? 0 : t * 0.18);
      brain.rotation.x = manualPitch + Math.sin(t * 0.3) * 0.04;

      // Pulse + recolor each marker based on current value.
      const activeFrame = Math.min(timeIndex, Math.max(frameCount - 1, 0));
      for (const m of markers) {
        const series = roiTimeseries[m.roi] || [];
        const v = Number(series[activeFrame] ?? 0);
        const mag = Math.min(1, Math.abs(v));
        const scale = 0.6 + mag * 1.6 + Math.sin(t * (1.5 + mag * 2)) * 0.1 * mag;
        m.markerMesh.scale.setScalar(scale);
        (m.markerMesh.material as THREE.MeshBasicMaterial).color.copy(heatColor(v));
        // Project label to 2D (only show for active-enough regions).
        tmpVec.copy(m.labelPos).applyMatrix4(brain.matrixWorld).project(camera);
        const inFront = tmpVec.z < 1;
        if (mag < 0.18 || !inFront) {
          m.labelEl.style.opacity = "0";
        } else {
          const rect = mount.getBoundingClientRect();
          const x = (tmpVec.x + 1) * 0.5 * rect.width;
          const y = (-tmpVec.y + 1) * 0.5 * rect.height;
          m.labelEl.style.transform = `translate(${x}px, ${y}px) translate(-50%, -120%)`;
          m.labelEl.style.opacity = (0.45 + mag * 0.55).toFixed(2);
        }
      }

      renderer.render(scene, camera);
    };
    animate();

    const resize = () => {
      camera.aspect = mount.clientWidth / Math.max(mount.clientHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener("resize", resize);
    const ro = new ResizeObserver(resize);
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointerup", onPointerUp);
      mount.removeEventListener("pointermove", onPointerMove);
      mount.removeEventListener("pointerdown", onPointerDown);
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
      if (labelLayer.parentNode === mount) mount.removeChild(labelLayer);
    };
  }, [prediction, roiNames, roiTimeseries, timeIndex, frameCount]);

  return (
    <section className="research-panel">
      <div className="research-panel__header">
        <div>
          <div className="research-kicker">TRIBE Neuroview</div>
          <h2>Predicted fMRI on personalized lesson content</h2>
          <p
            style={{
              marginTop: 8,
              fontSize: 13,
              lineHeight: 1.55,
              color: "#475569",
              maxWidth: 720
            }}
          >
            This map predicts which cortical regions a student's lesson engages. Warm regions are
            the ones the material recruits most: parietal areas (IPS) light up on numerical and
            spatial reasoning, prefrontal areas (dlPFC, ACC) on working memory and focus, the
            angular gyrus on mapping symbols to meaning, Broca/Wernicke on language decoding, and
            the hippocampus on effortful recall. Stronger, broader activation on a lesson suggests
            the student is thinking hard in useful ways; a dim map usually means the content is
            passing through without much engagement.
          </p>
        </div>
        <button className="button secondary" onClick={onRun} disabled={loading}>
          {loading ? "Running…" : "Run TRIBE v2"}
        </button>
      </div>

      {!prediction || !(prediction.roi_timeseries && Object.keys(prediction.roi_timeseries).length > 0) ? (
        <p className="muted">No TRIBE prediction has been generated for this lesson yet.</p>
      ) : (
        <div className="neuro-layout">
          <div className="neuro-scene" ref={mountRef} style={{ position: "relative" }} />
          <aside className="neuro-side">
            <div className="research-viz__title">Timeline</div>
            <input
              className="range"
              type="range"
              min={0}
              max={Math.max(frameCount - 1, 0)}
              value={Math.min(timeIndex, Math.max(frameCount - 1, 0))}
              onChange={(event) => setTimeIndex(Number(event.target.value))}
            />
            <p className="muted">
              Frame {Math.min(timeIndex + 1, Math.max(frameCount, 1))}/{Math.max(frameCount, 1)} · lag{" "}
              {prediction.hemodynamic_lag_s}s · {prediction.surface_summary?.space || "fsaverage5"}
            </p>

            {activeRoi && (
              <div
                style={{
                  marginTop: 12,
                  padding: "12px 14px",
                  borderRadius: 12,
                  background: "rgba(15, 23, 42, 0.04)",
                  border: "1px solid rgba(15, 23, 42, 0.08)"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: heatCss(activeRoi.value),
                      boxShadow: `0 0 10px ${heatCss(activeRoi.value)}`
                    }}
                  />
                  <strong style={{ fontSize: 13 }}>{activeRoi.meta.label}</strong>
                  <span style={{ marginLeft: "auto", fontSize: 12, opacity: 0.7 }}>
                    {activeRoi.value >= 0 ? "+" : ""}
                    {activeRoi.value.toFixed(3)}
                  </span>
                </div>
                <p style={{ fontSize: 12, lineHeight: 1.45, margin: 0, color: "#475569" }}>
                  {activeRoi.meta.blurb}
                </p>
              </div>
            )}

            <div className="research-viz__title" style={{ marginTop: 14 }}>
              Peak regions
            </div>
            <div className="roi-list">
              {topRois.map((item) => (
                <button
                  key={item.roi}
                  onClick={() => setSelectedRoi(item.roi)}
                  className="roi-row"
                  style={{
                    background:
                      selectedRoi === item.roi || hoveredRoi === item.roi
                        ? "rgba(15, 23, 42, 0.06)"
                        : "transparent",
                    border: "none",
                    cursor: "pointer",
                    textAlign: "left",
                    width: "100%"
                  }}
                >
                  <span>{item.meta.label}</span>
                  <strong style={{ color: heatCss(item.value) }}>
                    {item.value >= 0 ? "+" : ""}
                    {item.value.toFixed(3)}
                  </strong>
                </button>
              ))}
            </div>

            <div className="research-viz__title" style={{ marginTop: 14 }}>
              Networks
            </div>
            <div className="roi-list">
              {(prediction.connectivity || []).slice(0, 6).map((edge, index) => (
                <div className="roi-row" key={`${edge.source}-${edge.target}-${index}`}>
                  <span>
                    {roiEntry(edge.source).label} ↔ {roiEntry(edge.target).label}
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
