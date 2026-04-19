export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type User = {
  id: number;
  email: string;
  role: "student" | "educator" | "researcher";
  created_at: string;
};

export type AuthState = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
};

export type ClassOut = {
  id: number;
  educator_id: number;
  title: string;
  description: string | null;
  enrollment_code: string;
  created_at: string;
  materials?: MaterialSummary[];
};

export type MaterialSummary = {
  id: number;
  title: string;
  type: string;
  order_index: number;
  published_at: string | null;
};

export type SectionOut = {
  id: number;
  title: string;
  content: string;
  order_index: number;
  word_count: number;
};

export type MaterialOut = MaterialSummary & {
  class_id: number;
  personalized: boolean;
  generated_content: string | null;
  sections: SectionOut[];
};

export type ClassAnalytics = {
  class_id: number;
  model: null | {
    id: number;
    version: string;
    model_type: string;
    rmse: number;
    sample_count: number;
    trained_at: string;
    feature_importances: Record<string, number>;
  };
  drift: {
    checked?: boolean;
    flagged?: boolean;
    reason?: string;
    baseline_rmse?: number;
    recent_rmse?: number;
    threshold?: number;
    sample_count?: number;
  };
  students: Array<{
    id: number;
    email: string;
    session_count: number;
    prediction_count: number;
    average_predicted: number | null;
    average_actual: number | null;
    latest_prediction: Record<string, unknown> | null;
  }>;
  material_engagement: Array<{
    material_id: number;
    title: string;
    session_count: number;
    average_completion_rate: number;
    average_idle_s: number;
    average_total_time_s: number;
  }>;
  section_heatmap: Array<{
    section_id: string;
    title: string;
    session_count: number;
    average_time_s: number;
    average_hovers: number;
  }>;
};

export type QuizQuestion = {
  id: number;
  question: string;
  options: string[];
  points: number;
};

export type ProfileEntry = {
  id: number;
  profile_text: string;
  profile_json: Record<string, unknown>;
  quiz_score: number | null;
  trigger_material_id: number | null;
  created_at: string;
};

export type StyleVector = {
  pace: number;
  depth: number;
  attention_stability: number;
  engagement_mode: number;
  revisit_tendency: number;
  visual_orientation: number;
  motor_style: number;
};

export type UserLearningProfile = {
  user_id: number;
  style_vector: StyleVector;
  rolling_focus_score: number;
  rolling_reading_speed_wpm: number;
  rolling_completion_rate: number;
  preferred_session_length_s: number;
  engagement_fingerprint: Record<string, number | string>;
  behavioral_signals: {
    narrative_notes?: Array<{ note: string; ts: string }>;
    content_preferences?: Record<string, number>;
    recent_hints?: string[];
  };
  peak_focus_time_of_day: { histogram?: Record<string, number>; peak_hour?: string | null };
  session_count: number;
  lesson_count: number;
  quiz_count: number;
  last_focus_label: string | null;
  last_updated_at: string | null;
};

export type TopicNode = {
  topic: string;
  mastery_score: number;
  exposure_score: number;
  encounter_count: number;
  quiz_sample_count: number;
  struggle_signal: number;
  strength_signal: number;
  last_seen_at: string | null;
};

export type TopicEdge = {
  from_topic: string;
  to_topic: string;
  relation: string;
  weight: number;
};

export type LearningView = {
  student_id: number;
  learning_profile: UserLearningProfile | null;
  top_mastery: TopicNode[];
  top_struggles: TopicNode[];
  topic_edges: TopicEdge[];
  recent_focus: Array<{
    session_id: number;
    material_id: number;
    focus_score: number;
    focus_label: string;
    ended_at: string | null;
    gaze_present?: boolean;
    gaze_reading_time_s?: number;
  }>;
  narrative_notes: Array<{ note: string; ts: string }>;
};

// --- Eye tracking types (feature/eye-tracking) ---

export type GazeFixationBin = {
  rel_x: number;
  rel_y: number;
  weight: number;
  confidence: number;
};

export type GazeHeatmapSection = {
  section_id: string;
  title: string;
  order_index: number;
  fixation_count: number;
  time_s: number;
  fixations: GazeFixationBin[];
};

export type GazeHeatmap = {
  session_id: number;
  material_id: number;
  material_title: string;
  started_at: string;
  ended_at: string | null;
  gaze_present: boolean;
  has_calibration: boolean;
  focus_score: number | null;
  focus_label: string | null;
  attention_source: "gaze" | "heuristic";
  total_time_s: number;
  reading_time_s: number;
  off_content_time_s: number;
  lost_pct: number;
  entropy: number;
  fixation_count: number;
  fixation_ms_mean: number;
  sections: GazeHeatmapSection[];
};

// --- Research workbench types (origin/main) ---

export type ResearchWorkbench = {
  class: { id: number; title: string; description: string | null; created_at: string };
  students: Array<{
    id: number;
    email: string;
    profile_entry_count: number;
    neural_model: null | {
      id: number;
      status: string;
      version: string;
      sample_count: number;
      student_sample_count: number;
      confidence?: number;
    };
  }>;
  materials: Array<{
    id: number;
    title: string;
    type: string;
    published_at: string | null;
    section_count: number;
    word_count: number;
  }>;
  tribe_predictions: Array<{
    student_id: number;
    material_id: number;
    status: string;
    model_version: string | null;
    created_at: string;
    completed_at: string | null;
    error: string | null;
  }>;
};

export type MechanisticView = {
  student_id: number;
  class_id: number | null;
  model: {
    id: number;
    version: string;
    status: string;
    personalized: boolean;
    architecture: Record<string, unknown>;
    sample_count: number;
    student_sample_count: number;
    trained_at: string;
    metrics: Record<string, number>;
    loss_history: Array<{ epoch: number; loss: number }>;
  };
  session: {
    id: number | null;
    material_id: number | null;
    started_at: string | null;
    ended_at: string | null;
    target: number | null;
    stored_prediction: Record<string, unknown> | null;
    heuristic_prediction: number | null;
  };
  backprop: {
    prediction: number;
    target: number | null;
    loss: number;
    learning_rate: number;
    input_gradient_norm: number;
  };
  layers: Array<{
    id: string;
    label: string;
    type: string;
    nodes: Array<{ id: string; label: string; activation: number; delta?: number }>;
  }>;
  edges: Array<{ from: string; to: string; weight: number; gradient: number; layer: string }>;
  heatmaps?: Array<{
    id: string;
    label: string;
    rows: string[];
    columns: string[];
    implication?: string;
    weights: number[][];
    gradients: number[][];
    contribution: number[][];
    influence?: number[][];
    stats: {
      weights: { mean_abs: number; max_abs: number; energy: number };
      gradients: { mean_abs: number; max_abs: number; energy: number };
      contribution: { mean_abs: number; max_abs: number; energy: number };
      influence?: { mean_abs: number; max_abs: number; energy: number };
    };
  }>;
  features: Array<{
    name: string;
    value: number;
    normalized_value: number;
    gradient: number;
    saliency: number;
    direction: "raises_score" | "lowers_score";
  }>;
  personalization: Record<string, unknown>;
};

export type PersonalizationAudit = {
  student_id: number;
  material_id: number;
  base_lesson: {
    title: string;
    sections: Array<{ id: number; title: string; content: string; order_index: number; word_count: number }>;
  };
  personalized: boolean;
  personalized_lesson: null | {
    id: number;
    generated_content: string;
    prompt_used: string;
    assigned_at: string;
  };
  retrieved_profile_entries: ProfileEntry[];
};

export type TribePredictionPayload = {
  status: string;
  prediction: null | {
    id: number;
    student_id: number;
    material_id: number;
    personalized_lesson_id: number | null;
    stimulus_hash: string;
    stimulus_title: string;
    stimulus_kind: string;
    model_version: string | null;
    hemodynamic_lag_s: number;
    roi_timeseries: Record<string, number[]>;
    roi_summary: Record<string, any>;
    connectivity: Array<{ source: string; target: string; weight: number }>;
    surface_summary: Record<string, any>;
    error: string | null;
    created_at: string;
    completed_at: string | null;
  };
};

export type LessonAsset = {
  id: number;
  kind: "reading" | "quiz" | "video" | "practice";
  topic: string;
  title: string;
  payload: Record<string, any>;
  external_url: string | null;
  generated_by: string;
};

export type LessonPlanNode = {
  id: number;
  asset_id: number;
  order_index: number;
  label: string | null;
  notes: string | null;
  teacher_adjusted: boolean;
  asset: LessonAsset | null;
  fit_score: number | null;
  rationale: string | null;
};

export type LessonPlanCandidate = {
  asset: LessonAsset;
  fit_score: number;
  rationale: string;
  components: Record<string, number>;
};

export type LessonPlanDraft = {
  id: number;
  educator_id: number;
  student_id: number;
  class_id: number | null;
  topic: string;
  description: string | null;
  status: "draft" | "ready" | "published";
  nodes: LessonPlanNode[];
  edges: Array<{ id: number; from_node_id: number; to_node_id: number; condition: Record<string, unknown> | null }>;
  candidates: LessonPlanCandidate[];
  created_at: string;
  updated_at: string;
};

const AUTH_KEY = "edutrack.auth";

export function getStoredAuth(): AuthState | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(AUTH_KEY);
  return raw ? (JSON.parse(raw) as AuthState) : null;
}

export function storeAuth(auth: AuthState) {
  window.localStorage.setItem(AUTH_KEY, JSON.stringify(auth));
}

export function clearAuth() {
  window.localStorage.removeItem(AUTH_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const auth = getStoredAuth();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (auth?.access_token) headers.set("Authorization", `Bearer ${auth.access_token}`);
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : "Request failed");
  }
  return (await response.json()) as T;
}

export function wsUrl(path: string, token: string) {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}${path}?token=${encodeURIComponent(token)}`;
}

export const api = {
  register: (payload: { email: string; password: string; role: "student" | "educator" | "researcher"; institution?: string }) =>
    request<AuthState>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<AuthState>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  demoLogin: (role: "student" | "educator" | "researcher") =>
    request<AuthState>("/auth/demo", { method: "POST", body: JSON.stringify({ role }) }),
  refresh: (refresh_token: string) =>
    request<AuthState>("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token }) }),
  listClasses: () => request<ClassOut[]>("/classes"),
  getClass: (id: number) => request<ClassOut>(`/classes/${id}`),
  createClass: (payload: { title: string; description?: string }) =>
    request<ClassOut>("/classes", { method: "POST", body: JSON.stringify(payload) }),
  enroll: (classId: number, enrollment_code: string) =>
    request<{ status: string; class_id: number }>(`/classes/${classId}/enroll`, {
      method: "POST",
      body: JSON.stringify({ enrollment_code })
    }),
  roster: (classId: number) => request<Array<{ id: number; email: string; profile_entry_count?: number }>>(`/classes/${classId}/students`),
  getClassAnalytics: (classId: number) => request<ClassAnalytics>(`/classes/${classId}/analytics`),
  createMaterial: (
    classId: number,
    payload: { title: string; type: "lesson" | "quiz"; sections: Array<{ title: string; content: string; order_index: number }> }
  ) => request<MaterialOut>(`/classes/${classId}/materials`, { method: "POST", body: JSON.stringify(payload) }),
  publishMaterial: (materialId: number) =>
    request<{ material_id: number; published_at: string; personalization_tasks: number }>(`/materials/${materialId}/publish`, { method: "PUT" }),
  updateMaterial: (
    materialId: number,
    payload: { title?: string; type?: "lesson" | "quiz"; order_index?: number; sections?: Array<{ title: string; content: string; order_index: number }> }
  ) => request<MaterialOut>(`/materials/${materialId}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteMaterial: (materialId: number) => request<{ status: string; material_id: number }>(`/materials/${materialId}`, { method: "DELETE" }),
  getMaterial: (materialId: number) => request<MaterialOut>(`/materials/${materialId}`),
  createQuiz: (materialId: number, questions: Array<{ question: string; options: string[]; correct_answer: string; points: number }>) =>
    request<QuizQuestion[]>(`/materials/${materialId}/quiz`, { method: "POST", body: JSON.stringify(questions) }),
  getQuiz: (materialId: number) => request<QuizQuestion[]>(`/materials/${materialId}/quiz`),
  submitQuiz: (materialId: number, answers: Record<string, string>, session_id?: number) =>
    request<{ attempt_id: number; score: number; max_score: number; normalized_score: number }>(`/quiz/${materialId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers, session_id })
    }),
  startSession: (material_id: number) =>
    request<{ session_id: number; started_at: string }>("/sessions/start", {
      method: "POST",
      body: JSON.stringify({ material_id })
    }),
  endSession: (sessionId: number) =>
    request<{ session_id: number; features: Record<string, unknown> | null; prediction: Record<string, unknown> | null }>(`/sessions/${sessionId}/end`, {
      method: "POST",
      body: JSON.stringify({})
    }),
  getProfile: (studentId: number) =>
    request<{ student_id: number; entry_count: number; entries: ProfileEntry[] }>(`/students/${studentId}/profile`),
  getLearningProfile: (studentId: number) =>
    request<UserLearningProfile>(`/students/${studentId}/learning-profile`),
  getMastery: (studentId: number, topic?: string) =>
    request<{ seed_topic: string | null; nodes: TopicNode[]; edges: TopicEdge[] }>(
      `/students/${studentId}/mastery${topic ? `?topic=${encodeURIComponent(topic)}` : ""}`
    ),
  getLearningContext: (studentId: number, topic: string) =>
    request<{
      style_summary_lines: string[];
      mastery_lines: string[];
      mastery_nodes: Array<Record<string, unknown>>;
      topic_edges: Array<Record<string, unknown>>;
      profile_entries: Array<Record<string, unknown>>;
      recent_focus: Array<Record<string, unknown>>;
      recent_hints: string[];
      seed_text: string;
    }>(`/students/${studentId}/learning-context?topic=${encodeURIComponent(topic)}`),
  getStudentLessonPlan: (studentId: number, topic: string, material_id?: number) =>
    request<{
      topic: string;
      sections: Array<{ title: string; angle: string; why_this_works_for_them: string; estimated_word_count: number }>;
      prerequisites_to_reinforce: string[];
      cautions: string[];
      style_summary: string[];
    }>(`/students/${studentId}/lesson-plan`, {
      method: "POST",
      body: JSON.stringify({ topic, material_id })
    }),
  getLearningView: (studentId: number) =>
    request<LearningView>(`/teacher/students/${studentId}/learning-view`),
  getResearchWorkbench: (classId: number) =>
    request<ResearchWorkbench>(`/research/classes/${classId}/workbench`),
  trainResearchSurrogate: (studentId: number, classId?: number) =>
    request<{ id: number; version: string; status: string; sample_count: number; student_sample_count: number; metrics: Record<string, number> }>(
      `/research/students/${studentId}/neural-surrogate/train${classId !== undefined ? `?class_id=${classId}` : ""}`,
      { method: "POST" }
    ),
  getMechanisticView: (studentId: number, classId?: number) =>
    request<MechanisticView>(`/research/students/${studentId}/mechanistic${classId !== undefined ? `?class_id=${classId}` : ""}`),
  getPersonalizationAudit: (materialId: number, studentId: number) =>
    request<PersonalizationAudit>(`/research/materials/${materialId}/students/${studentId}/personalization-audit`),
  getTribePrediction: (materialId: number, studentId: number) =>
    request<TribePredictionPayload>(`/research/materials/${materialId}/students/${studentId}/tribe`),
  runTribePrediction: (materialId: number, studentId: number) =>
    request<TribePredictionPayload>(`/research/materials/${materialId}/students/${studentId}/tribe`, { method: "POST" }),
  createLessonPlan: (payload: {
    student_id: number;
    topic: string;
    description?: string;
    class_id?: number;
    material_id?: number;
  }) => request<LessonPlanDraft>("/teacher/lesson-plans", { method: "POST", body: JSON.stringify(payload) }),
  getLessonPlan: (draftId: number) => request<LessonPlanDraft>(`/teacher/lesson-plans/${draftId}`),
  regenerateLessonPlan: (draftId: number) =>
    request<LessonPlanDraft>(`/teacher/lesson-plans/${draftId}/regenerate`, { method: "POST" }),
  patchLessonPlan: (
    draftId: number,
    nodes: Array<{ asset_id: number; order_index: number; label?: string; notes?: string; teacher_adjusted?: boolean }>
  ) =>
    request<LessonPlanDraft>(`/teacher/lesson-plans/${draftId}`, {
      method: "PATCH",
      body: JSON.stringify({ nodes })
    }),
  publishLessonPlan: (draftId: number, targetMaterialId?: number) =>
    request<MaterialOut>(
      `/teacher/lesson-plans/${draftId}/publish${
        targetMaterialId !== undefined ? `?target_material_id=${targetMaterialId}` : ""
      }`,
      { method: "POST" }
    ),
  getSessionGazeHeatmap: (sessionId: number) =>
    request<GazeHeatmap>(`/sessions/${sessionId}/gaze-heatmap`)
};
