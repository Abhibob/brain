# Eye Tracking Pipeline

Webcam-based gaze tracking that produces high-confidence attention signals and feeds them into the rest of EduTrack — focus scoring, the learning profile, researcher analytics, and any new feature that wants truth-grade "what did this student actually read" data.

**It's a producer, not a product.** The pipeline captures gaze, derives features, and stores them where every other service already looks. You almost never have to know this file exists unless you're building on top of gaze signals.

## TL;DR integration recipes

| You're building… | What you need |
|---|---|
| Any lesson-style page that should feed gaze into the session pipeline | Drop `<GazeTrackerMount sessionId rootRef />` next to `<BehaviorTrackerMount>` on the page. |
| A researcher / student view that should show how someone read | Drop `<GazeHeatmap sessionId={n} />` — it loads itself. |
| A backend service that needs attention truth | Read `session.features["gaze_*"]` — it's there whenever the student had gaze on. |
| A backend service that needs a single "was this real attention" score | Read `session.focus_score` and `session.focus_breakdown.attention_source`. Gaze is already wired in. |
| Something brand new that needs raw fixations | `GET /sessions/{id}/gaze-heatmap` returns everything. |

## Architecture

```
[browser]
  MediaPipe FaceLandmarker (478 landmarks, iris included)
    → iris-in-eye normalization (per-eye, mirror-safe)
    → bilinear calibration transform (9-point, 8 coeffs)
    → screen (x, y) at ~15 Hz
    → I-DT fixation detector (dispersion threshold, 200 ms min)
    → section attribution via data-section-id bounding boxes
    → WebSocket /track/{session_id}
       events: gaze_fixation | gaze_lost | gaze_calibrated

[backend]
  /track/{session_id} WebSocket
    → Redis list tracking:{session_id}       (existing path, no changes)
    → on session end, Celery drains and persists
    → services/tracking.py compute_features()
       → services/gaze.py extract_gaze_features(events, duration_s)
       → 12 gaze_* feature keys merged into tracking_sessions.features
       → time_per_section[k] is replaced with gaze time when available
    → services/focus.py compute_focus_score(features)
       → _gaze_attention_component wins over heuristic when gaze_present
       → focus label sharpened when gaze_lost_pct is high
    → downstream pipelines (profile reasoning, ml training, RAG) read
      these features without any gaze-specific code
```

## Event contract

All three types flow through the existing `/track/{session_id}` WebSocket alongside mouse/scroll/section events. Redis persistence, draining, and event persistence are all unchanged.

### `gaze_fixation`
Emitted when gaze dwells within ~80 px for ≥200 ms (I-DT detector in `frontend/lib/gaze.ts`).

| field | type | meaning |
|---|---|---|
| `section_id` | `string \| null` | `data-section-id` the fixation landed in; `null` if off-content |
| `rel_x`, `rel_y` | `number \| null` | fixation center in section-relative `[0, 1]` coords (null if off-content) |
| `x`, `y` | `int` | fixation center in viewport pixels |
| `duration_ms` | `int` | how long the fixation lasted |
| `confidence` | `float` | `[0, 1]` — degrades near iris extremes |
| `sample_count` | `int` | number of raw samples in this fixation |
| `start_client_ts`, `end_client_ts` | `int` | browser `Date.now()` timestamps |

### `gaze_lost`
Emitted at 1.5 s intervals while the face is undetected.

| field | type | meaning |
|---|---|---|
| `duration_ms` | `int` | elapsed since loss started (or since last emit) |
| `reason` | `string` | currently always `"no_face"` |
| `client_ts` | `int` | browser `Date.now()` |

### `gaze_calibrated`
Emitted once per session when the gaze WebSocket opens.

| field | type | meaning |
|---|---|---|
| `points` | `int` | `9` (calibration grid size) |
| `has_calibration` | `bool` | `true` if student completed calibration; `false` if they skipped |

## Feature contract

After session end, `tracking_sessions.features` gets these keys merged in (when the student had any gaze data). Everything downstream that reads `features` gets them for free.

| key | type | meaning |
|---|---|---|
| `gaze_present` | `bool` | truthy marker that gaze was captured this session |
| `gaze_has_calibration` | `bool` | whether calibration was completed |
| `gaze_reading_time_s` | `float` | total time eyes were on a section (truth attention) |
| `gaze_off_content_time_s` | `float` | total time eyes were on-screen but not on content |
| `gaze_lost_s` | `float` | total time face was not detected |
| `gaze_lost_pct` | `float` | `gaze_lost_s / total_time_s`, clamped to `[0, 1]` |
| `gaze_fixation_count` | `int` | number of fixations recorded |
| `gaze_fixation_ms_mean` | `float` | average fixation duration |
| `gaze_fixation_ms_median` | `float` | median fixation duration |
| `gaze_entropy` | `float` | normalized Shannon entropy of per-section time distribution — `0` = focused on one section, `1` = evenly scattered |
| `gaze_time_per_section` | `{section_id: seconds}` | per-section reading time |
| `gaze_fixations_per_section` | `{section_id: count}` | per-section fixation count |
| `gaze_heatmap` | `{section_id: [{rel_x, rel_y, weight, confidence}]}` | raw bins for heatmap rendering |

`time_per_section` (the pre-existing key) is also **overwritten with gaze time** when available — it's a better signal than IntersectionObserver and every downstream consumer benefits automatically.

## Focus score behavior

`services/focus.py :: compute_focus_score(features)` returns:

```python
{
  "focus_score": float,           # [0, 1]
  "confidence": float,            # higher with gaze data
  "breakdown": {pace, completion, attention, engagement},
  "attention_source": "gaze" | "heuristic",
  "label": "focused" | "engaged" | "distracted" | "skimming" | "abandoned"
}
```

With gaze present:
- `attention` component is `gaze_reading_time / total_time`, penalized by `gaze_lost_pct` and high entropy.
- `label` flips to `"abandoned"` or `"distracted"` early when `gaze_lost_pct` crosses 0.3 / 0.5.
- `confidence` gets a bump proportional to fixation count.

Without gaze, falls back to the existing idle/mouse/back-scroll heuristic. No caller has to branch.

## REST API

### `GET /sessions/{session_id}/gaze-heatmap`

Auth: owning student, owning educator, or any researcher. Returns `GazeHeatmapOut`:

```ts
{
  session_id: number,
  material_id: number,
  material_title: string,
  started_at: string,
  ended_at: string | null,
  gaze_present: boolean,
  has_calibration: boolean,
  focus_score: number | null,
  focus_label: string | null,
  attention_source: "gaze" | "heuristic",
  total_time_s: number,
  reading_time_s: number,
  off_content_time_s: number,
  lost_pct: number,
  entropy: number,
  fixation_count: number,
  fixation_ms_mean: number,
  sections: Array<{
    section_id: string,
    title: string,
    order_index: number,
    fixation_count: number,
    time_s: number,
    fixations: Array<{ rel_x, rel_y, weight, confidence }>
  }>
}
```

Backend file: `backend/app/api/tracking.py :: get_gaze_heatmap`.

## Frontend components

All in `frontend/components/GazeTracker/` and `frontend/components/GazeHeatmap/`.

### `<GazeTrackerMount>`
Producer. Put this on any page that should emit gaze into the student's active tracking session.

```tsx
import { GazeTrackerMount } from "@/components/GazeTracker/GazeTrackerMount";

<GazeTrackerMount
  sessionId={sessionId}      // number | null — waits for session before emitting
  rootRef={rootRef}          // RefObject<HTMLElement> — sections with data-section-id live inside
  debug={false}              // optional, shows live dot + trail when true
/>
```

Requirements:
- The content container you point `rootRef` at must contain `[data-section-id]` elements — that's the same attribute the behavior tracker already uses. No extra markup.
- It manages consent + calibration + camera lifecycle itself; you don't have to handle permissions.
- Deny state is recoverable (pill bottom-right).

The component lazy-loads MediaPipe from CDN — first use pulls ~10 MB of model assets, then caches.

### `<GazeHeatmap>`
Consumer. Visualizes any session's gaze data as canvas density + per-section stats.

```tsx
import { GazeHeatmap } from "@/components/GazeHeatmap/GazeHeatmap";

// Loads itself by session id:
<GazeHeatmap sessionId={42} />

// Or pass pre-fetched data (handy if you already called the endpoint):
<GazeHeatmap data={gazeData} />
```

Handles loading, error, and "no gaze data" states internally. Uses `api.getSessionGazeHeatmap(id)` under the hood — if you want the raw data without UI, use that method directly.

## Common integration recipes

### 1. "My teacher page should show if each student had eye tracking on"
Read `recent_focus` from `LearningView`. Entries with `gaze_present`-flagged sessions come from the feature dict downstream. Alternatively call `getSessionGazeHeatmap` and check `gaze_present`.

### 2. "I'm building analytics and want class-wide gaze stats"
Aggregate `features["gaze_reading_time_s"]`, `gaze_lost_pct`, `gaze_entropy` across each class's sessions. No new endpoint needed — the features are on `tracking_sessions.features`.

### 3. "My profile reasoning wants to factor in gaze"
In `services/profile_reasoning.py` or your equivalent, `features.get("gaze_entropy")` and `features.get("gaze_lost_pct")` are the two most predictive single signals. High entropy + low loss = confused. High loss = disengaged. High reading_time / total = truly focused.

### 4. "I want a live classroom dashboard showing who's focused right now"
Subscribe to the Redis list `tracking:{session_id}` (same source the drainer uses). Filter `event_type == "gaze_fixation"` and compute a rolling focus proxy from last-30-seconds fixation count / elapsed time. New endpoint scope is yours — the raw signal is already flowing.

### 5. "I need the student's learning profile to reflect their attention truthfulness"
`features["gaze_lost_pct"]` is the cleanest signal to feed into an "attention_stability" style vector axis. The session-end hook at `workers/tasks.py :: _run_session_end_pipeline` already fires profile updates; add your gaze reads there.

## Configuration

### Frontend
- `NEXT_PUBLIC_API_URL` — unchanged; gaze uses the same WebSocket base as the rest of the app.
- URL flag: `?debug_gaze=1` — show live gaze dot + trail + debug pill. Safe to leave off in production.
- LocalStorage keys (per device):
  - `edutrack.gaze.consent.v1` — `"granted" | "denied"`
  - `edutrack.gaze.calibration.v2` — bilinear transform `{version: 2, xCoef, yCoef}`

Clearing both → consent banner + calibration reappear next visit.

### Backend
No new env vars. Gaze is infrastructure-free — it reuses the existing WebSocket, Redis, and Celery pipeline. Feature extraction runs inside the existing `extract_features_and_predict` task.

## Gotchas

- **Calibration is per-device, per-browser.** Students who switch devices re-calibrate. By design — head geometry varies.
- **Head movement during reading drifts gaze.** Bilinear calibration is static. For demo shots, tell users to keep head still. For production this would want a head-pose offset.
- **Glasses, low light, low-res webcams all degrade accuracy** roughly 20–40%. The `confidence` field is your hint — drop fixations below 0.5 if you care about quality.
- **The browser hides the camera permission prompt behind a user gesture.** The consent banner is that gesture. Don't try to pre-prompt from a `useEffect`.
- **First gaze session loads ~10 MB of MediaPipe assets from CDN.** Subsequent sessions cache. If you need offline/air-gapped demo, bundle the `.task` file — see `MODEL_URL` constant in `frontend/lib/gaze.ts`.
- **Second WebSocket per session.** `<GazeTrackerMount>` opens its own `/track/{session_id}` connection in parallel to the behavior tracker's. The backend is fine with this (both write to the same Redis list), but it means one session can have two concurrent WS connections.

## Files

Backend:
- `backend/app/services/gaze.py` — feature extraction
- `backend/app/services/tracking.py` — integration point (`compute_features` → merges gaze features)
- `backend/app/services/focus.py` — `_gaze_attention_component` + label sharpening
- `backend/app/api/tracking.py` — `GET /sessions/{id}/gaze-heatmap`
- `backend/app/schemas/__init__.py` — `GazeHeatmapOut`, `GazeHeatmapSectionOut`
- `backend/tests/unit/test_gaze.py`, `backend/tests/api/test_tracking.py::TestGazeHeatmap`

Frontend:
- `frontend/lib/gaze.ts` — `GazeTracker`, `FixationDetector`, `attributeSection`, calibration math
- `frontend/components/GazeTracker/GazeTrackerMount.tsx` — top-level orchestrator
- `frontend/components/GazeTracker/GazeConsentBanner.tsx` — consent UI
- `frontend/components/GazeTracker/GazeCalibration.tsx` — 9-point calibration overlay
- `frontend/components/GazeHeatmap/GazeHeatmap.tsx` — drop-in visualization

## Research workbench integration (already wired)

Gaze signals are pre-integrated into the research workbench so researchers
see them without lifting a finger.

**Neural surrogate input layer** (`services/research_nn.py`):
- `RESEARCH_FEATURE_KEYS` now includes 4 normalized gaze inputs:
  `gaze_reading_time_ratio`, `gaze_lost_pct`, `gaze_entropy`,
  `gaze_fixation_count_norm`.
- `feature_vector_for_session` appends `_gaze_feature_values(session.features)`
  to every training row.
- Sessions without gaze contribute zeros on those inputs — safe for mixed
  cohorts. The surrogate learns to downweight them when information is
  sparse.
- **Consequence:** the NeuralMicroscope ranks gaze saliency alongside
  mouse/scroll features automatically. When gaze matters for a student,
  its node lights up in the input layer viz.

**Workbench API** (`api/research.py::get_research_workbench`):
- Each student entry now includes `gaze_metadata: {gaze_present,
  gaze_calibrated, gaze_lost_pct, has_session}` from their latest session.
- Each material entry now includes `gaze_stats: {total_sessions,
  gaze_present_count, gaze_present_pct, avg_reading_time_s}` aggregated
  across all sessions for that material.
- Researchers can spot "this material's cohort has 20% gaze coverage" and
  adjust interpretation.

**StudentSignalPanel UI**:
- New **Gaze quality** metric card: `calibrated` (green), `has_loss` (amber
  if >25% face-lost), `none`, or `no session`. One glance tells the
  researcher whether to trust gaze-derived saliency for the student.

**CohortOverview material engagement chart**:
- Dual-bar: completion % alongside gaze present %. Shows data-quality
  distribution across the cohort.

**What teammates can layer on top** (not built — signals exposed):
- New endpoint joining `/sessions/{id}/gaze-heatmap` with the neural
  microscope's saliency map for side-by-side "what the eyes saw vs what
  the model thought mattered" validation.
- Filter training rows by minimum gaze quality in a separate call path
  (would need a new `research_nn` entry point).
- Attention-aware TRIBE visualization: weight ROI time-series by
  `gaze_reading_time_ratio` to separate "engaged looking" from "dwelling
  but checked out".

## What this feature explicitly does NOT do

(Flagging these so teammates know the scope boundary.)

- Does not build a live "who's focused right now" teacher dashboard — the raw signal is available, UI is yours.
- Does not modify `UserLearningProfile` style vectors with gaze signals — surfaces exposed, profile teammate wires them in.
- Does not do real-time confusion intervention or adaptive content — raw entropy/loss signal exposed, product layer is yours.
- Does not compensate for head movement — static calibration only.
- Does not work on mobile. Desktop demo only.
