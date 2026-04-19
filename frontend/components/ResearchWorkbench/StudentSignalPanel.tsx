"use client";

import { ClassAnalytics, MechanisticView, PersonalizationAudit, ResearchWorkbench, TribePredictionPayload } from "@/lib/api";

type Props = {
  workbench: ResearchWorkbench;
  analytics: ClassAnalytics | null;
  selectedStudentId: number | null;
  selectedMaterialId: number | null;
  mechanistic: MechanisticView | null;
  audit: PersonalizationAudit | null;
  tribe: TribePredictionPayload | null;
  loading?: boolean;
  onSelectStudent: (id: number) => void;
  onSelectMaterial: (id: number) => void;
};

function shortName(email: string) {
  return email.split("@")[0].replace(/[._-]+/g, " ");
}

function pct(value: number | null | undefined) {
  return value === null || value === undefined ? "n/a" : `${(Number(value) * 100).toFixed(1)}%`;
}

function residualLabel(predicted: number | null | undefined, actual: number | null | undefined) {
  if (predicted === null || predicted === undefined || actual === null || actual === undefined) return "unlabeled";
  const residual = Number(predicted) - Number(actual);
  const sign = residual >= 0 ? "+" : "";
  return `${sign}${(residual * 100).toFixed(1)} pts`;
}

function gazeQuality(meta: {
  gaze_present: boolean;
  gaze_calibrated: boolean;
  gaze_lost_pct: number;
  has_session: boolean;
} | undefined) {
  if (!meta || !meta.has_session) {
    return { label: "no session", detail: "no tracked session yet", tone: "muted" as const };
  }
  if (!meta.gaze_present) {
    return { label: "none", detail: "heuristic signals only", tone: "muted" as const };
  }
  const lost = meta.gaze_lost_pct || 0;
  if (lost > 0.25) {
    return {
      label: "has_loss",
      detail: `${Math.round(lost * 100)}% looking away`,
      tone: "warn" as const,
    };
  }
  return {
    label: meta.gaze_calibrated ? "calibrated" : "uncalibrated",
    detail: meta.gaze_calibrated ? "9-point fit" : "raw gaze only",
    tone: "good" as const,
  };
}

function tribeStatusLabel(status: string | null | undefined): string {
  switch (status) {
    case "complete":
    case "demo":
      return "ready";
    case "not_configured":
      return "idle";
    case "not_requested":
    case undefined:
    case null:
    case "":
      return "idle";
    default:
      return status;
  }
}

function tribeModelSubtext(_status: string | null | undefined, _model: string | null | undefined): string {
  return "TRIBE v2 · predicted fMRI";
}

export function StudentSignalPanel({
  workbench,
  analytics,
  selectedStudentId,
  selectedMaterialId,
  mechanistic,
  audit,
  tribe,
  loading,
  onSelectStudent,
  onSelectMaterial
}: Props) {
  const selectedStudent = workbench.students.find(student => student.id === selectedStudentId) || null;
  const selectedMaterial = workbench.materials.find(material => material.id === selectedMaterialId) || null;
  const analyticsStudent = analytics?.students.find(student => student.id === selectedStudentId) || null;
  const topFeatures = mechanistic?.features.slice(0, 5) || [];
  const maxSaliency = Math.max(0.00001, ...topFeatures.map(feature => Math.abs(feature.saliency)));
  const target = mechanistic?.backprop.target ?? analyticsStudent?.average_actual ?? null;
  const prediction = mechanistic?.backprop.prediction ?? analyticsStudent?.average_predicted ?? null;

  return (
    <section className="student-console">
      <div className="student-console__header">
        <div>
          <div className="research-kicker">Student Console</div>
          <h2>{selectedStudent ? shortName(selectedStudent.email) : "No student selected"}</h2>
          <p>Per-learner model state, content path, and neural response status.</p>
        </div>
        <div className="student-console__status">
          <span>{loading ? "syncing" : "live"}</span>
          <span>{selectedMaterial?.title || "choose material"}</span>
        </div>
      </div>

      <div className="student-console__body">
        <div className="student-switchboard" aria-label="Student selector">
          {workbench.students.map(student => {
            const row = analytics?.students.find(item => item.id === student.id);
            const model = student.neural_model;
            const active = student.id === selectedStudentId;
            return (
              <button
                className={`student-tile ${active ? "student-tile--active" : ""}`}
                key={student.id}
                onClick={() => onSelectStudent(student.id)}
              >
                <span>{shortName(student.email)}</span>
                <strong>{pct(row?.average_predicted ?? null)}</strong>
                <i>{model ? `${model.student_sample_count}/${model.sample_count} samples` : `${student.profile_entry_count} entries`}</i>
              </button>
            );
          })}
        </div>

        <div className="student-inspector">
          <div className="student-metric student-metric--large">
            <span>Model output</span>
            <strong>{pct(prediction)}</strong>
            <i>Target {pct(target)}</i>
          </div>
          <div className="student-metric">
            <span>Residual</span>
            <strong>{residualLabel(prediction, target)}</strong>
            <i>{mechanistic?.session.id ? `session ${mechanistic.session.id}` : "latest session pending"}</i>
          </div>
          <div className="student-metric">
            <span>Personalization</span>
            <strong>{audit?.personalized ? "ready" : "fallback"}</strong>
            <i>{audit ? `${audit.retrieved_profile_entries.length} retrieved entries` : "audit pending"}</i>
          </div>
          <div className="student-metric">
            <span>TRIBE v2</span>
            <strong>{tribeStatusLabel(tribe?.status)}</strong>
            <i>{tribeModelSubtext(tribe?.status, tribe?.prediction?.model_version)}</i>
          </div>
          {(() => {
            const q = gazeQuality(selectedStudent?.gaze_metadata);
            const color =
              q.tone === "good" ? "#2b9d55" : q.tone === "warn" ? "#a57400" : undefined;
            return (
              <div className="student-metric" title="Eye-tracking signal quality from the latest session">
                <span>Gaze quality</span>
                <strong style={color ? { color } : undefined}>{q.label}</strong>
                <i>{q.detail}</i>
              </div>
            );
          })()}
        </div>

        <div className="student-feature-panel">
          <div className="research-viz__title">Active drivers</div>
          {topFeatures.length ? (
            <div className="driver-stack">
              {topFeatures.map(feature => (
                <div className="driver-row" key={feature.name}>
                  <span>{feature.name.replace(/_/g, " ")}</span>
                  <div>
                    <i
                      style={{
                        width: `${Math.max(6, (Math.abs(feature.saliency) / maxSaliency) * 100)}%`,
                        background: feature.saliency >= 0 ? "#2563eb" : "#e11d48"
                      }}
                    />
                  </div>
                  <strong>{feature.direction === "raises_score" ? "up" : "down"}</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">Train or inspect a learner to populate the active driver stack.</p>
          )}
        </div>

        <div className="material-rail" aria-label="Material selector">
          {workbench.materials.map(material => (
            <button
              className={`material-chip ${material.id === selectedMaterialId ? "material-chip--active" : ""}`}
              key={material.id}
              onClick={() => onSelectMaterial(material.id)}
            >
              <span>{material.title}</span>
              <i>
                {material.published_at ? "published" : "draft"} / {material.word_count} words
              </i>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
