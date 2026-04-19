import type { FaceLandmarker as FaceLandmarkerType, NormalizedLandmark } from "@mediapipe/tasks-vision";

export type GazeSample = {
  x: number;
  y: number;
  eyeX: number;
  eyeY: number;
  confidence: number;
  timestamp: number;
  faceDetected: boolean;
};

export type GazeStatus =
  | "idle"
  | "requesting_camera"
  | "loading_model"
  | "running"
  | "face_lost"
  | "error"
  | "denied";

export type GazeTrackerOptions = {
  sampleHz?: number;
  emaAlpha?: number;
  calibration?: CalibrationTransform | null;
  onStatus?: (status: GazeStatus, detail?: string) => void;
};

export type CalibrationTransform = {
  version: 2;
  // screen_x = xCoef[0] + xCoef[1]*eyeX + xCoef[2]*eyeY + xCoef[3]*eyeX*eyeY
  xCoef: [number, number, number, number];
  yCoef: [number, number, number, number];
};

export type Fixation = {
  x: number;
  y: number;
  startTs: number;
  endTs: number;
  durationMs: number;
  confidence: number;
  sampleCount: number;
};

export type FixationDetectorOptions = {
  minDurationMs?: number;
  maxDurationMs?: number;
  dispersionPx?: number;
};

/**
 * I-DT (dispersion threshold) fixation detector.
 * Call `observe(sample)` for each gaze sample (or null when the face is lost).
 * Returns a completed fixation when one finishes, otherwise null.
 */
export class FixationDetector {
  private buffer: GazeSample[] = [];
  private readonly minDurationMs: number;
  private readonly maxDurationMs: number;
  private readonly dispersionPx: number;

  constructor(opts: FixationDetectorOptions = {}) {
    this.minDurationMs = opts.minDurationMs ?? 200;
    this.maxDurationMs = opts.maxDurationMs ?? 3000;
    this.dispersionPx = opts.dispersionPx ?? 60;
  }

  observe(sample: GazeSample | null): Fixation | null {
    if (sample === null || !sample.faceDetected) {
      return this.flush();
    }
    if (this.buffer.length === 0) {
      this.buffer.push(sample);
      return null;
    }
    const candidate = [...this.buffer, sample];
    if (this.dispersion(candidate) <= this.dispersionPx) {
      this.buffer = candidate;
      const span = this.buffer[this.buffer.length - 1].timestamp - this.buffer[0].timestamp;
      if (span >= this.maxDurationMs) {
        const fixation = this.buildFixation();
        this.buffer = [sample];
        return fixation;
      }
      return null;
    }
    const fixation = this.flush();
    this.buffer = [sample];
    return fixation;
  }

  private dispersion(samples: GazeSample[]): number {
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const s of samples) {
      if (s.x < minX) minX = s.x;
      if (s.x > maxX) maxX = s.x;
      if (s.y < minY) minY = s.y;
      if (s.y > maxY) maxY = s.y;
    }
    return maxX - minX + maxY - minY;
  }

  private flush(): Fixation | null {
    if (this.buffer.length === 0) return null;
    const span = this.buffer[this.buffer.length - 1].timestamp - this.buffer[0].timestamp;
    if (span < this.minDurationMs) {
      this.buffer = [];
      return null;
    }
    const fixation = this.buildFixation();
    this.buffer = [];
    return fixation;
  }

  private buildFixation(): Fixation {
    const n = this.buffer.length;
    let sx = 0;
    let sy = 0;
    let sc = 0;
    for (const s of this.buffer) {
      sx += s.x;
      sy += s.y;
      sc += s.confidence;
    }
    return {
      x: sx / n,
      y: sy / n,
      startTs: this.buffer[0].timestamp,
      endTs: this.buffer[n - 1].timestamp,
      durationMs: this.buffer[n - 1].timestamp - this.buffer[0].timestamp,
      confidence: sc / n,
      sampleCount: n,
    };
  }
}

export type SectionAttribution = {
  sectionId: string;
  relX: number;
  relY: number;
};

export function attributeSection(root: HTMLElement, x: number, y: number): SectionAttribution | null {
  const sections = root.querySelectorAll<HTMLElement>("[data-section-id]");
  for (const el of Array.from(sections)) {
    const r = el.getBoundingClientRect();
    if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
      const sid = el.dataset.sectionId;
      if (!sid) return null;
      const width = Math.max(r.width, 1);
      const height = Math.max(r.height, 1);
      return {
        sectionId: sid,
        relX: clamp((x - r.left) / width, 0, 1),
        relY: clamp((y - r.top) / height, 0, 1),
      };
    }
  }
  return null;
}

export function applyCalibration(t: CalibrationTransform, eyeX: number, eyeY: number): { x: number; y: number } {
  const basis = [1, eyeX, eyeY, eyeX * eyeY];
  let x = 0;
  let y = 0;
  for (let i = 0; i < 4; i++) {
    x += t.xCoef[i] * basis[i];
    y += t.yCoef[i] * basis[i];
  }
  return { x, y };
}

const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";
const WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.34/wasm";

const LM_LEFT_IRIS = 468;
const LM_RIGHT_IRIS = 473;
const LM_LEFT_OUTER = 33;
const LM_LEFT_INNER = 133;
const LM_LEFT_TOP = 159;
const LM_LEFT_BOTTOM = 145;
const LM_RIGHT_INNER = 362;
const LM_RIGHT_OUTER = 263;
const LM_RIGHT_TOP = 386;
const LM_RIGHT_BOTTOM = 374;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function normInEye(iris: NormalizedLandmark, outer: NormalizedLandmark, inner: NormalizedLandmark, top: NormalizedLandmark, bottom: NormalizedLandmark) {
  const rangeX = inner.x - outer.x;
  const rangeY = bottom.y - top.y;
  if (Math.abs(rangeX) < 1e-6 || Math.abs(rangeY) < 1e-6) return null;
  return {
    nx: (iris.x - outer.x) / rangeX,
    ny: (iris.y - top.y) / rangeY,
  };
}

export class GazeTracker {
  private landmarker: FaceLandmarkerType | null = null;
  private video: HTMLVideoElement | null = null;
  private stream: MediaStream | null = null;
  private rafId: number | null = null;
  private lastSampleMs = 0;
  private ema: { x: number; y: number } | null = null;
  private listeners = new Set<(sample: GazeSample) => void>();
  private statusListeners = new Set<(status: GazeStatus, detail?: string) => void>();
  private _status: GazeStatus = "idle";
  private running = false;

  constructor(private options: GazeTrackerOptions = {}) {
    if (options.onStatus) this.statusListeners.add(options.onStatus);
  }

  get status(): GazeStatus {
    return this._status;
  }

  onSample(cb: (sample: GazeSample) => void): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  onStatus(cb: (status: GazeStatus, detail?: string) => void): () => void {
    this.statusListeners.add(cb);
    return () => this.statusListeners.delete(cb);
  }

  setCalibration(calibration: CalibrationTransform | null) {
    this.options.calibration = calibration;
  }

  async start() {
    if (this.running) return;
    this.running = true;
    try {
      this.setStatus("requesting_camera");
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } },
        audio: false,
      });
      if (!this.running) {
        // stop() was called while we were waiting for the camera.
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      this.stream = stream;

      const video = document.createElement("video");
      video.autoplay = true;
      video.playsInline = true;
      video.muted = true;
      video.srcObject = stream;
      video.style.position = "fixed";
      video.style.left = "-9999px";
      video.style.width = "1px";
      video.style.height = "1px";
      document.body.appendChild(video);
      this.video = video;
      try {
        await video.play();
      } catch {
        // Autoplay policy quirks — we'll still get frames via the landmarker loop.
      }
      if (!this.running) {
        this.cleanup();
        return;
      }

      this.setStatus("loading_model");
      const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
      if (!this.running) {
        this.cleanup();
        return;
      }
      const vision = await FilesetResolver.forVisionTasks(WASM_URL);
      if (!this.running) {
        this.cleanup();
        return;
      }
      const landmarker = await FaceLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
        runningMode: "VIDEO",
        numFaces: 1,
        outputFaceBlendshapes: false,
        outputFacialTransformationMatrixes: false,
      });
      if (!this.running) {
        try {
          landmarker.close();
        } catch {}
        this.cleanup();
        return;
      }
      this.landmarker = landmarker;

      this.setStatus("running");
      this.loop();
    } catch (err) {
      this.running = false;
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("Permission") || msg.includes("denied") || msg.includes("NotAllowed")) {
        this.setStatus("denied", msg);
      } else {
        this.setStatus("error", msg);
      }
      this.cleanup();
      throw err;
    }
  }

  stop() {
    this.running = false;
    if (this.rafId !== null) cancelAnimationFrame(this.rafId);
    this.rafId = null;
    this.cleanup();
    this.setStatus("idle");
  }

  /**
   * Release all webcam resources. Order matters: close the landmarker first
   * (it may hold an internal reference to the video element), then tear down
   * the video element (pause + null srcObject + remove), then stop the
   * MediaStream tracks. That sequence is what makes the OS camera indicator
   * go dark immediately.
   */
  private cleanup() {
    if (this.landmarker) {
      try {
        this.landmarker.close();
      } catch {}
      this.landmarker = null;
    }
    if (this.video) {
      try {
        this.video.pause();
      } catch {}
      try {
        this.video.srcObject = null;
        this.video.removeAttribute("src");
        this.video.load();
      } catch {}
      try {
        this.video.remove();
      } catch {}
      this.video = null;
    }
    if (this.stream) {
      for (const track of this.stream.getTracks()) {
        try {
          track.stop();
        } catch {}
      }
      this.stream = null;
    }
  }

  private setStatus(next: GazeStatus, detail?: string) {
    this._status = next;
    for (const cb of this.statusListeners) cb(next, detail);
  }

  private emit(sample: GazeSample) {
    for (const cb of this.listeners) cb(sample);
  }

  private loop = () => {
    if (!this.running || !this.video || !this.landmarker) return;
    const targetMs = 1000 / (this.options.sampleHz ?? 10);
    const now = performance.now();
    if (now - this.lastSampleMs >= targetMs && this.video.readyState >= 2) {
      this.lastSampleMs = now;
      this.processFrame(now);
    }
    this.rafId = requestAnimationFrame(this.loop);
  };

  private processFrame(timestamp: number) {
    if (!this.video || !this.landmarker) return;
    let result;
    try {
      result = this.landmarker.detectForVideo(this.video, timestamp);
    } catch {
      return;
    }
    const landmarks = result.faceLandmarks?.[0];
    if (!landmarks || landmarks.length < 478) {
      if (this._status === "running") this.setStatus("face_lost");
      this.emit({
        x: NaN,
        y: NaN,
        eyeX: NaN,
        eyeY: NaN,
        confidence: 0,
        timestamp: Date.now(),
        faceDetected: false,
      });
      return;
    }
    if (this._status === "face_lost") this.setStatus("running");

    const leftIris = landmarks[LM_LEFT_IRIS];
    const rightIris = landmarks[LM_RIGHT_IRIS];
    const leftNorm = normInEye(
      leftIris,
      landmarks[LM_LEFT_OUTER],
      landmarks[LM_LEFT_INNER],
      landmarks[LM_LEFT_TOP],
      landmarks[LM_LEFT_BOTTOM],
    );
    const rightNorm = normInEye(
      rightIris,
      landmarks[LM_RIGHT_INNER],
      landmarks[LM_RIGHT_OUTER],
      landmarks[LM_RIGHT_TOP],
      landmarks[LM_RIGHT_BOTTOM],
    );
    if (!leftNorm || !rightNorm) return;

    const eyeX = (leftNorm.nx + rightNorm.nx) / 2;
    const eyeY = (leftNorm.ny + rightNorm.ny) / 2;

    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;

    let screenX: number;
    let screenY: number;
    const cal = this.options.calibration;
    if (cal) {
      const projected = applyCalibration(cal, eyeX, eyeY);
      screenX = projected.x;
      screenY = projected.y;
    } else {
      const gain = 3.0;
      screenX = viewportW / 2 + (eyeX - 0.5) * viewportW * gain;
      screenY = viewportH / 2 + (eyeY - 0.5) * viewportH * gain;
    }

    const alpha = this.options.emaAlpha ?? 0.35;
    if (this.ema) {
      screenX = lerp(this.ema.x, screenX, alpha);
      screenY = lerp(this.ema.y, screenY, alpha);
    }
    this.ema = { x: screenX, y: screenY };

    const confidence = clamp(
      1 - (Math.abs(eyeX - 0.5) + Math.abs(eyeY - 0.5)) * 0.8,
      0.1,
      1.0,
    );

    const margin = 40;
    this.emit({
      x: clamp(screenX, -margin, viewportW + margin),
      y: clamp(screenY, -margin, viewportH + margin),
      eyeX,
      eyeY,
      confidence,
      timestamp: Date.now(),
      faceDetected: true,
    });
  }
}

export function fitCalibration(
  samples: Array<{ eyeX: number; eyeY: number; screenX: number; screenY: number }>,
): CalibrationTransform | null {
  if (samples.length < 4) return null;

  // Design matrix: each row is [1, eyeX, eyeY, eyeX*eyeY]
  const A: number[][] = samples.map((s) => [1, s.eyeX, s.eyeY, s.eyeX * s.eyeY]);
  const bX = samples.map((s) => s.screenX);
  const bY = samples.map((s) => s.screenY);

  // Normal equations: (A^T A) c = A^T b — solve 4x4 system
  const AtA: number[][] = Array.from({ length: 4 }, () => Array(4).fill(0));
  const AtbX: number[] = Array(4).fill(0);
  const AtbY: number[] = Array(4).fill(0);
  for (let r = 0; r < A.length; r++) {
    for (let i = 0; i < 4; i++) {
      AtbX[i] += A[r][i] * bX[r];
      AtbY[i] += A[r][i] * bY[r];
      for (let j = 0; j < 4; j++) {
        AtA[i][j] += A[r][i] * A[r][j];
      }
    }
  }

  const xCoef = solveLinear(AtA, AtbX);
  const yCoef = solveLinear(AtA, AtbY);
  if (!xCoef || !yCoef) return null;
  return {
    version: 2,
    xCoef: xCoef as [number, number, number, number],
    yCoef: yCoef as [number, number, number, number],
  };
}

function solveLinear(A: number[][], b: number[]): number[] | null {
  // Gauss-Jordan elimination with partial pivoting.
  const n = A.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let row = col + 1; row < n; row++) {
      if (Math.abs(M[row][col]) > Math.abs(M[pivot][col])) pivot = row;
    }
    if (Math.abs(M[pivot][col]) < 1e-12) return null;
    if (pivot !== col) [M[col], M[pivot]] = [M[pivot], M[col]];
    const pval = M[col][col];
    for (let k = col; k <= n; k++) M[col][k] /= pval;
    for (let row = 0; row < n; row++) {
      if (row === col) continue;
      const factor = M[row][col];
      if (Math.abs(factor) < 1e-14) continue;
      for (let k = col; k <= n; k++) M[row][k] -= factor * M[col][k];
    }
  }
  return M.map((row) => row[n]);
}

const CAL_KEY = "edutrack.gaze.calibration.v2";
const CONSENT_KEY = "edutrack.gaze.consent.v1";

function isFiniteQuad(arr: unknown): arr is [number, number, number, number] {
  return (
    Array.isArray(arr) &&
    arr.length === 4 &&
    arr.every((v) => typeof v === "number" && Number.isFinite(v))
  );
}

export function loadCalibration(): CalibrationTransform | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(CAL_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed?.version !== 2) return null;
    if (!isFiniteQuad(parsed.xCoef) || !isFiniteQuad(parsed.yCoef)) return null;
    return { version: 2, xCoef: parsed.xCoef, yCoef: parsed.yCoef };
  } catch {
    return null;
  }
}

export function saveCalibration(transform: CalibrationTransform) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CAL_KEY, JSON.stringify(transform));
}

export function clearCalibration() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(CAL_KEY);
}

export function loadConsent(): "granted" | "denied" | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(CONSENT_KEY);
  if (raw === "granted" || raw === "denied") return raw;
  return null;
}

export function saveConsent(value: "granted" | "denied") {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(CONSENT_KEY, value);
}

const ENABLED_KEY = "edutrack.gaze.enabled.v1";
const NOTICE_KEY = "edutrack.gaze.notice_seen.v1";

export function loadEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const raw = window.localStorage.getItem(ENABLED_KEY);
  // Default: ON. Only turn off when user explicitly toggles.
  if (raw === "false") return false;
  return true;
}

export function saveEnabled(value: boolean) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ENABLED_KEY, value ? "true" : "false");
}

export function hasSeenNotice(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(NOTICE_KEY) === "1";
}

export function markNoticeSeen() {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(NOTICE_KEY, "1");
}
