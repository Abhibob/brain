"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

// ---------------------------------------------------------------------------
// Region presets — not real neuroscience, but plausibly labeled. The positions
// are on the unit hemisphere (x, y, z with |x|≈0.7 for lateral, y up, z front).
// ---------------------------------------------------------------------------

type RegionPreset = {
  id: string;
  label: string;
  position: [number, number, number];
  blurb: string;
};

const REGION_PRESETS: RegionPreset[] = [
  {
    id: "ips",
    label: "Intraparietal sulcus",
    position: [-0.45, 0.82, -0.15],
    blurb:
      "Numerical and spatial reasoning — lights up when manipulating numbers, ordering magnitudes, and stepping through arithmetic."
  },
  {
    id: "dlpfc",
    label: "Dorsolateral prefrontal cortex",
    position: [-0.6, 0.55, 0.7],
    blurb:
      "Working memory and executive control — the mental whiteboard that holds a multi-step plan while you execute it."
  },
  {
    id: "angular",
    label: "Angular gyrus",
    position: [-0.85, 0.25, -0.35],
    blurb:
      "Binds symbols to meanings — central to reading comprehension, arithmetic fact retrieval, and mapping language to math."
  },
  {
    id: "broca",
    label: "Broca's area",
    position: [-0.78, 0.15, 0.55],
    blurb:
      "Language production and mental rehearsal — active when a learner silently verbalizes a rule to themselves."
  },
  {
    id: "wernicke",
    label: "Wernicke's area",
    position: [-0.82, -0.05, -0.35],
    blurb:
      "Language comprehension — decoding the words of a problem into the concepts the problem is really about."
  },
  {
    id: "hippocampus",
    label: "Hippocampus",
    position: [-0.28, -0.25, 0.1],
    blurb:
      "Forms new memories — consolidating today's examples into tomorrow's intuition. Strong engagement during effortful recall."
  },
  {
    id: "visual",
    label: "Primary visual cortex",
    position: [0.0, 0.0, -0.98],
    blurb:
      "Processes raw vision — engaged by diagrams, worked examples on paper, and tracking visual elements in a video."
  },
  {
    id: "fusiform",
    label: "Fusiform gyrus",
    position: [-0.35, -0.5, -0.55],
    blurb:
      "Recognizes letters, digits, and symbolic forms — a specialized reader that turns squiggles on the page into meaning."
  },
  {
    id: "acc",
    label: "Anterior cingulate",
    position: [-0.12, 0.35, 0.25],
    blurb:
      "Error monitoring and focus — ramps up when the student catches a mistake or has to resist a distracting pull."
  }
];

// ---------------------------------------------------------------------------
// Activation model — fakes a topic-driven heat map without any real TRIBE call.
// ---------------------------------------------------------------------------

export type BrainActivation = Record<string, number>; // region id → 0..1

export function activationsForLesson(topic: string | null | undefined, focusScore = 0.6): BrainActivation {
  const t = (topic ?? "").toLowerCase();

  // Start from a floor so every region shows a little signal.
  const base: BrainActivation = Object.fromEntries(
    REGION_PRESETS.map((r) => [r.id, 0.15 + Math.random() * 0.1])
  );

  const bump = (id: string, by: number) => {
    base[id] = Math.min(1, (base[id] ?? 0) + by);
  };

  const has = (...keys: string[]) => keys.some((k) => t.includes(k));

  // Math / arithmetic / algebra
  if (has("algebra", "equation", "linear", "slope", "system", "solve", "variable")) {
    bump("ips", 0.7);
    bump("dlpfc", 0.55);
    bump("angular", 0.55);
    bump("acc", 0.45);
    bump("fusiform", 0.4);
  }
  // Geometry / theorem / proof
  if (has("geometry", "triangle", "pythagorean", "theorem", "proof", "angle", "graph")) {
    bump("ips", 0.7);
    bump("visual", 0.55);
    bump("fusiform", 0.45);
    bump("dlpfc", 0.4);
  }
  // Reading / comprehension
  if (has("reading", "passage", "text", "essay", "literature", "vocabulary", "definition")) {
    bump("broca", 0.6);
    bump("wernicke", 0.6);
    bump("angular", 0.55);
    bump("fusiform", 0.5);
  }
  // Memorization / recall
  if (has("recall", "review", "memorize", "quiz", "checkpoint")) {
    bump("hippocampus", 0.6);
    bump("dlpfc", 0.45);
    bump("acc", 0.35);
  }
  // Visual / video
  if (has("video", "watch", "diagram", "picture", "visual")) {
    bump("visual", 0.65);
    bump("fusiform", 0.4);
  }

  // If nothing matched, treat it as a general algebra-ish lesson.
  const anyActivated = Object.values(base).some((v) => v > 0.5);
  if (!anyActivated) {
    bump("ips", 0.55);
    bump("dlpfc", 0.45);
    bump("angular", 0.4);
  }

  // Focus score modulates overall intensity (distracted sessions → dimmer).
  const gain = 0.5 + focusScore;
  for (const id of Object.keys(base)) {
    base[id] = Math.min(1, base[id] * gain);
  }
  return base;
}

// ---------------------------------------------------------------------------
// 3D component
// ---------------------------------------------------------------------------

type Props = {
  /** Map of region id → 0..1 activation. Keys should match REGION_PRESETS ids. */
  activations: BrainActivation;
  /** Subtitle / overline text above the brain (e.g. the lesson title). */
  contextLabel?: string;
  heading?: string;
};

function heatColorHex(activation: number): number {
  const a = Math.max(0, Math.min(1, activation));
  let r = 0;
  let g = 0;
  let b = 0;
  if (a < 0.3) {
    const t = a / 0.3;
    r = 0.12 + t * 0.85;
    g = 0.45 + t * 0.38;
    b = 0.92 - t * 0.65;
  } else if (a < 0.6) {
    const t = (a - 0.3) / 0.3;
    r = 0.97 + t * 0.03;
    g = 0.83 - t * 0.63;
    b = 0.27 - t * 0.22;
  } else if (a < 0.85) {
    const t = (a - 0.6) / 0.25;
    r = 1.0;
    g = 0.2 + t * 0.78;
    b = 0.05 + t * 0.25;
  } else {
    const t = (a - 0.85) / 0.15;
    r = 1.0;
    g = 0.98 + t * 0.02;
    b = 0.3 + t * 0.7;
  }
  return (Math.round(r * 255) << 16) | (Math.round(g * 255) << 8) | Math.round(b * 255);
}

function heatCss(activation: number): string {
  const hex = heatColorHex(activation).toString(16).padStart(6, "0");
  return `#${hex}`;
}

export function BrainModel({ activations, contextLabel, heading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const regionList = useMemo(
    () =>
      REGION_PRESETS.map((r) => ({
        ...r,
        activation: Math.max(0, Math.min(1, activations[r.id] ?? 0))
      })),
    [activations]
  );

  // Auto-pick the top region if nothing is hovered or selected.
  const topRegionId = useMemo(
    () => [...regionList].sort((a, b) => b.activation - a.activation)[0]?.id ?? null,
    [regionList]
  );
  const activeId = hoveredId ?? selectedId ?? topRegionId;
  const activeRegion = regionList.find((r) => r.id === activeId) ?? regionList[0];

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      40,
      container.clientWidth / Math.max(container.clientHeight, 1),
      0.1,
      100
    );
    camera.position.set(0, 0.25, 4.4);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // Lights — bright ambient so the translucent surface and vertex colors read clearly.
    scene.add(new THREE.AmbientLight(0xffffff, 0.9));
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.75);
    keyLight.position.set(3, 5, 4);
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0xffd4c8, 0.35);
    rimLight.position.set(-3, 2, -2);
    scene.add(rimLight);

    // Brain group
    const brain = new THREE.Group();
    scene.add(brain);

    const brainScale = new THREE.Vector3(1.0, 0.88, 1.18);
    const hemispheres: Array<{ mesh: THREE.Mesh; worldPositions: THREE.Vector3[]; colors: Float32Array }> = [];

    function buildCerebrum(): void {
      const geom = new THREE.IcosahedronGeometry(1, 6);
      const pos = geom.attributes.position;
      const tmp = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) {
        tmp.fromBufferAttribute(pos, i);
        const dir = tmp.clone().normalize();
        const x = dir.x;
        const y = dir.y;
        const z = dir.z;
        const oct = (fx: number, fy: number, fz: number, phase = 0) =>
          Math.sin(x * fx + phase) *
          Math.cos(y * fy + phase * 0.7) *
          Math.sin(z * fz + phase * 1.3);
        const ridge = (v: number) => 1 - Math.abs(v);

        let radius = 1.0;
        radius += 0.03 * oct(4.2, 3.1, 4.5, 0.2);      // lobe-scale undulation
        radius -= 0.055 * ridge(oct(9.1, 7.7, 8.8, 1.7));   // primary gyri
        radius -= 0.03 * ridge(oct(17.7, 15.3, 18.4, 3.5)); // secondary folds
        radius -= 0.014 * ridge(oct(33.1, 30.7, 34.5, 5.1)); // wrinkles

        // Longitudinal fissure
        radius -= Math.exp(-(x * x) / 0.012) * Math.max(0, y + 0.05) * 0.18;
        // Central sulcus
        radius -=
          Math.exp(-((y - 0.25) * (y - 0.25)) / 0.012) *
          Math.exp(-(z * z) / 0.45) *
          0.045;

        const out = dir.multiplyScalar(radius);
        out.x *= brainScale.x;
        out.y *= brainScale.y;
        out.z *= brainScale.z;
        pos.setXYZ(i, out.x, out.y, out.z);
      }
      pos.needsUpdate = true;
      geom.computeVertexNormals();
      const colorArr = new Float32Array(pos.count * 3);
      geom.setAttribute("color", new THREE.BufferAttribute(colorArr, 3));
      const mat = new THREE.MeshStandardMaterial({
        color: 0xffffff, // white albedo so vertex colors pass through unmuted
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
    }
    buildCerebrum();

    // Cerebellum — sits behind and slightly below the cortex, visible at the nape.
    {
      const geom = new THREE.IcosahedronGeometry(0.42, 4);
      const pos = geom.attributes.position;
      const tmp = new THREE.Vector3();
      for (let i = 0; i < pos.count; i++) {
        tmp.fromBufferAttribute(pos, i);
        const n = tmp.clone().normalize();
        const folds = Math.sin(n.y * 22 + n.x * 7) * 0.02 + Math.cos(n.x * 18 + n.z * 10) * 0.015;
        tmp.setLength(0.42 * (1 + folds));
        pos.setXYZ(i, tmp.x, tmp.y, tmp.z);
      }
      pos.needsUpdate = true;
      geom.computeVertexNormals();
      const mesh = new THREE.Mesh(
        geom,
        new THREE.MeshStandardMaterial({
          color: 0xe0a095,
          roughness: 0.62,
          metalness: 0.04,
          transparent: true,
          opacity: 0.92
        })
      );
      mesh.position.set(0, -0.72, -0.72);
      mesh.scale.set(1.2, 0.75, 0.95);
      mesh.renderOrder = 2;
      brain.add(mesh);
    }

    // Brainstem
    {
      const geom = new THREE.CylinderGeometry(0.095, 0.07, 0.4, 20, 1, true);
      const mesh = new THREE.Mesh(
        geom,
        new THREE.MeshStandardMaterial({
          color: 0xc48074,
          roughness: 0.58,
          metalness: 0.05,
          transparent: true,
          opacity: 0.95,
          side: THREE.DoubleSide
        })
      );
      mesh.position.set(0, -1.05, -0.4);
      mesh.rotation.x = 0.22;
      mesh.renderOrder = 2;
      brain.add(mesh);
    }

    // Region markers
    const markerGroup = new THREE.Group();
    brain.add(markerGroup);
    type MarkerRef = {
      core: THREE.Mesh;
      halo: THREE.Mesh;
      region: (typeof regionList)[number];
      surfacePos: THREE.Vector3;
    };
    const markers: MarkerRef[] = [];

    for (const region of regionList) {
      const color = heatColorHex(region.activation);
      const coreGeom = new THREE.SphereGeometry(0.035, 20, 20);
      const coreMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95 });
      const core = new THREE.Mesh(coreGeom, coreMat);
      const haloGeom = new THREE.SphereGeometry(0.055, 20, 20);
      const haloMat = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.15,
        depthWrite: false
      });
      const halo = new THREE.Mesh(haloGeom, haloMat);

      // Project the region onto the ellipsoid surface — marker sits at the heat center.
      const p = new THREE.Vector3(...region.position).normalize();
      const surfacePos = p.clone().multiply(brainScale);
      const markerPos = surfacePos.clone().multiplyScalar(1.005);
      core.position.copy(markerPos);
      halo.position.copy(markerPos);
      core.userData = { regionId: region.id };

      markerGroup.add(halo);
      markerGroup.add(core);
      markers.push({ core, halo, region, surfacePos });
    }

    // Paint surface heat from region activations (tight Gaussian, winner-take-most).
    {
      const SIGMA2 = 0.20 * 0.20;
      const tmpColor = new THREE.Color();
      for (const hemi of hemispheres) {
        const col = hemi.colors;
        for (let i = 0; i < hemi.worldPositions.length; i++) {
          const v = hemi.worldPositions[i];
          let bestContribution = 0;
          let bestSigned = 0;
          for (const m of markers) {
            const d2 = v.distanceToSquared(m.surfacePos);
            const w = Math.exp(-d2 / SIGMA2);
            const contribution = w * Math.abs(m.region.activation);
            if (contribution > bestContribution) {
              bestContribution = contribution;
              bestSigned = w * m.region.activation;
            }
          }
          const intensity = Math.min(1, Math.pow(bestContribution, 0.45) * 2.1);
          tmpColor.setHex(heatColorHex(bestSigned));
          const baseR = 0.97;
          const baseG = 0.84;
          const baseB = 0.8;
          col[i * 3] = baseR * (1 - intensity) + tmpColor.r * intensity;
          col[i * 3 + 1] = baseG * (1 - intensity) + tmpColor.g * intensity;
          col[i * 3 + 2] = baseB * (1 - intensity) + tmpColor.b * intensity;
        }
        (hemi.mesh.geometry.attributes.color as THREE.BufferAttribute).needsUpdate = true;
      }
    }

    // Pointer interaction
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let dragging = false;
    let downAt = 0;
    let dragX = 0;
    let dragY = 0;
    let manualYaw = 0;
    let manualPitch = 0;

    const onPointerMove = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect();
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
      const hits = raycaster.intersectObjects(markers.map((m) => m.core));
      if (hits.length > 0) {
        const id = (hits[0].object.userData as { regionId?: string }).regionId ?? null;
        setHoveredId(id);
        container.style.cursor = "pointer";
      } else {
        setHoveredId(null);
        container.style.cursor = dragging ? "grabbing" : "grab";
      }
    };
    const onPointerDown = (e: PointerEvent) => {
      dragging = true;
      downAt = performance.now();
      dragX = e.clientX;
      dragY = e.clientY;
      container.style.cursor = "grabbing";
    };
    const onPointerUp = (e: PointerEvent) => {
      dragging = false;
      container.style.cursor = "grab";
      // Treat quick releases with no meaningful drag as a click.
      if (performance.now() - downAt < 250) {
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(markers.map((m) => m.core));
        if (hits.length > 0) {
          const id = (hits[0].object.userData as { regionId?: string }).regionId ?? null;
          setSelectedId(id);
        }
      }
    };
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointerup", onPointerUp);

    // Animation
    let raf = 0;
    const clock = new THREE.Clock();
    const animate = () => {
      raf = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // Idle auto-rotation plus manual pan contribution.
      brain.rotation.y = manualYaw + (dragging ? 0 : t * 0.18);
      brain.rotation.x = manualPitch + Math.sin(t * 0.3) * 0.04;

      // Pulse markers by activation.
      for (const m of markers) {
        const a = m.region.activation;
        const pulse = 1 + Math.sin(t * (1.5 + a * 3)) * 0.2 * a;
        const coreScale = 0.4 + a * 1.4;
        m.core.scale.setScalar(coreScale * pulse);
        m.halo.scale.setScalar(coreScale * pulse * 1.8);
        (m.halo.material as THREE.MeshBasicMaterial).opacity = 0.1 + a * 0.35;
      }

      renderer.render(scene, camera);
    };
    animate();

    // Resize
    const onResize = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);
    const ro = new ResizeObserver(onResize);
    ro.observe(container);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointerup", onPointerUp);
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerdown", onPointerDown);
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [regionList]);

  return (
    <section className="bg-surface-container-lowest rounded-[32px] border border-surface-dim/20 overflow-hidden">
      <div className="px-6 md:px-8 pt-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
            {heading ?? "Neural activation"}
          </div>
          {contextLabel && (
            <div className="font-headline text-xl text-primary font-medium tracking-[-0.02em] mt-1">
              {contextLabel}
            </div>
          )}
          <p className="font-body text-xs text-on-surface-variant mt-2 leading-relaxed" style={{ maxWidth: 560 }}>
            Warm regions are the ones this lesson recruits most. Parietal areas drive numerical and
            spatial reasoning; prefrontal areas hold multi-step plans in working memory; the angular
            gyrus ties symbols to meaning; Broca/Wernicke decode language; the hippocampus
            consolidates new facts during effortful recall.
          </p>
          <div className="font-body text-[11px] text-on-surface-variant mt-2 opacity-70">
            Drag to rotate · hover a region for details
          </div>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-body text-on-surface-variant">
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full" style={{ background: heatCss(0.1) }} /> low
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full" style={{ background: heatCss(0.55) }} /> moderate
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full" style={{ background: heatCss(1) }} /> high
          </span>
        </div>
      </div>
      <div
        ref={containerRef}
        className="relative"
        style={{
          width: "100%",
          height: 380,
          background:
            "radial-gradient(600px 380px at 50% 55%, rgba(99, 102, 241, 0.12) 0%, transparent 70%), linear-gradient(180deg, #ffffff 0%, #f7f7f2 100%)"
        }}
      />
      {activeRegion && (
        <div className="px-6 md:px-8 pb-6">
          <div className="flex items-center gap-3 mb-2">
            <span
              className="w-3 h-3 rounded-full"
              style={{ background: heatCss(activeRegion.activation), boxShadow: `0 0 12px ${heatCss(activeRegion.activation)}` }}
            />
            <span className="font-headline text-lg text-primary font-medium">{activeRegion.label}</span>
            <span className="font-body text-xs text-on-surface-variant ml-auto tabular-nums">
              activation {(activeRegion.activation * 10).toFixed(1)} / 10
            </span>
          </div>
          <p className="font-body text-sm text-on-surface-variant leading-relaxed">{activeRegion.blurb}</p>
        </div>
      )}
    </section>
  );
}
