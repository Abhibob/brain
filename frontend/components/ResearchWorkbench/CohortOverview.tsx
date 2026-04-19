"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { ClassAnalytics, ResearchWorkbench } from "@/lib/api";

type Props = {
  workbench: ResearchWorkbench;
  analytics: ClassAnalytics | null;
  selectedStudentId: number | null;
  selectedMaterialId: number | null;
  onSelectStudent: (id: number) => void;
  onSelectMaterial: (id: number) => void;
};

function name(email: string) {
  return email.split("@")[0].replace(/[._-]+/g, " ");
}

export function CohortOverview({
  workbench,
  analytics,
  selectedStudentId,
  selectedMaterialId,
  onSelectStudent,
  onSelectMaterial
}: Props) {
  const residuals =
    analytics?.students
      .filter(student => student.average_predicted !== null && student.average_actual !== null)
      .map(student => ({
        student: name(student.email),
        predicted: Number(student.average_predicted),
        actual: Number(student.average_actual),
        residual: Number(student.average_predicted) - Number(student.average_actual)
      })) || [];
  const gazeByTitle = new Map(
    workbench.materials
      .filter(m => m.gaze_stats)
      .map(m => [m.title, m.gaze_stats!] as const)
  );
  const engagement =
    analytics?.material_engagement.map(item => {
      const stats = gazeByTitle.get(item.title);
      return {
        title: item.title,
        completion: Number((item.average_completion_rate * 100).toFixed(1)),
        idle: Number(item.average_idle_s.toFixed(1)),
        time: Number(item.average_total_time_s.toFixed(1)),
        gazePresent: stats ? Number((stats.gaze_present_pct * 100).toFixed(1)) : 0
      };
    }) || [];

  return (
    <section className="research-panel">
      <div className="research-panel__header">
        <div>
          <div className="research-kicker">Cohort Overview</div>
          <h2>Signals, residuals, and model readiness</h2>
        </div>
        <div className="research-statline">
          <span>{workbench.students.length} students</span>
          <span>{workbench.materials.length} materials</span>
          <span>{analytics?.model ? `${analytics.model.model_type} active` : "heuristic active"}</span>
        </div>
      </div>

      <div className="research-grid research-grid--three">
        <div className="research-viz">
          <div className="research-viz__title">Predicted vs actual</div>
          {residuals.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={residuals}>
                <CartesianGrid stroke="#d8ded8" strokeDasharray="3 3" />
                <XAxis dataKey="student" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 1]} />
                <Tooltip />
                <Bar dataKey="predicted" name="Predicted" fill="#0f766e" radius={[4, 4, 0, 0]} />
                <Bar dataKey="actual" name="Actual" fill="#b94a48" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted">Labeled prediction rows appear after tracked lessons and quizzes.</p>
          )}
        </div>

        <div className="research-viz">
          <div className="research-viz__title">Residual drift</div>
          {residuals.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={residuals}>
                <CartesianGrid stroke="#d8ded8" strokeDasharray="3 3" />
                <XAxis dataKey="student" tick={{ fontSize: 11 }} />
                <YAxis domain={[-1, 1]} />
                <Tooltip />
                <Line type="monotone" dataKey="residual" stroke="#78350f" strokeWidth={3} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted">Residuals need both predicted and actual scores.</p>
          )}
        </div>

        <div className="research-viz">
          <div className="research-viz__title">Material engagement</div>
          {engagement.length ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={engagement}>
                <CartesianGrid stroke="#d8ded8" strokeDasharray="3 3" />
                <XAxis dataKey="title" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Bar dataKey="completion" name="Completion %" fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="gazePresent" name="Gaze present %" fill="#0f7b66" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted">Engagement appears after lesson sessions end.</p>
          )}
        </div>
      </div>

      <div className="research-split">
        <div>
          <div className="research-viz__title">Students</div>
          <div className="research-list">
            {workbench.students.map(student => (
              <button
                className={`research-row ${selectedStudentId === student.id ? "research-row--active" : ""}`}
                key={student.id}
                onClick={() => onSelectStudent(student.id)}
              >
                <span>{student.email}</span>
                <span>
                  {student.neural_model
                    ? `${student.neural_model.status} / ${student.neural_model.student_sample_count}/${student.neural_model.sample_count}`
                    : `${student.profile_entry_count} profile entries`}
                </span>
              </button>
            ))}
          </div>
        </div>
        <div>
          <div className="research-viz__title">Materials</div>
          <div className="research-list">
            {workbench.materials.map(material => (
              <button
                className={`research-row ${selectedMaterialId === material.id ? "research-row--active" : ""}`}
                key={material.id}
                onClick={() => onSelectMaterial(material.id)}
              >
                <span>{material.title}</span>
                <span>
                  {material.published_at ? "published" : "draft"} / {material.word_count} words
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
