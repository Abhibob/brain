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
    request<{ student_id: number; entry_count: number; entries: ProfileEntry[] }>(`/students/${studentId}/profile`)
};
