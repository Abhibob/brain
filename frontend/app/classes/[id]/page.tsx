"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ClassAnalytics, ClassOut, getStoredAuth } from "@/lib/api";

export default function ClassPage() {
  const params = useParams<{ id: string }>();
  const classId = Number(params.id);
  const auth = getStoredAuth();
  const [classOut, setClassOut] = useState<ClassOut | null>(null);
  const [roster, setRoster] = useState<Array<{ id: number; email: string; profile_entry_count?: number }>>([]);
  const [analytics, setAnalytics] = useState<ClassAnalytics | null>(null);
  const [title, setTitle] = useState("Recursion lesson");
  const [content, setContent] = useState("Recursion solves a problem by reducing it into smaller versions of the same problem. Every recursive function needs a base case and a recursive step.");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setClassOut(await api.getClass(classId));
    if (auth?.user.role === "educator" || auth?.user.role === "researcher") {
      setRoster(await api.roster(classId));
    }
    if (auth?.user.role === "researcher") {
      setAnalytics(await api.getClassAnalytics(classId));
    }
  }

  useEffect(() => {
    load().catch(error => setError(error.message));
  }, [classId]);

  async function createLesson(event: FormEvent) {
    event.preventDefault();
    const material = await api.createMaterial(classId, {
      title,
      type: "lesson",
      sections: [
        { title: "Core idea", content, order_index: 0 },
        { title: "Worked example", content: "Trace each call, write down the base case, then return values one layer at a time.", order_index: 1 }
      ]
    });
    await api.createQuiz(material.id, [
      {
        question: "What must every recursive function include?",
        options: ["Only a loop", "A base case", "A database", "A timer"],
        correct_answer: "A base case",
        points: 1
      }
    ]);
    await load();
  }

  if (!classOut) return <main className="main">{error || "Loading class..."}</main>;

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/dashboard">
          EduTrack
        </Link>
        <span>{classOut.title}</span>
      </header>
      <main className="main stack">
        <section>
          <h1>{classOut.title}</h1>
          <p>{classOut.description}</p>
          {auth?.user.role === "educator" ? <p className="muted">Enrollment code: {classOut.enrollment_code}</p> : null}
        </section>

        {auth?.user.role === "educator" ? (
          <form className="card stack" onSubmit={createLesson}>
            <h2>Create lesson</h2>
            <label className="field">
              <span>Title</span>
              <input className="input" value={title} onChange={event => setTitle(event.target.value)} required />
            </label>
            <label className="field">
              <span>Content</span>
              <textarea className="textarea" value={content} onChange={event => setContent(event.target.value)} required />
            </label>
            <button className="button" type="submit">
              Create lesson and quiz
            </button>
          </form>
        ) : null}

        <section className="grid">
          {(classOut.materials || []).map(material => (
            <article className="card" key={material.id}>
              <h2>{material.title}</h2>
              <p className="muted">{material.published_at ? "Published" : "Draft"}</p>
              <div className="toolbar">
                <Link className="button" href={`/classes/${classId}/materials/${material.id}`}>
                  Open
                </Link>
                {auth?.user.role === "educator" ? (
                  <Link className="button secondary" href={`/educator/materials/${material.id}/edit`}>
                    Edit
                  </Link>
                ) : null}
                {auth?.user.role === "educator" ? (
                  <button className="button secondary" onClick={() => api.publishMaterial(material.id).then(load)}>
                    Publish
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </section>

        {auth?.user.role === "researcher" ? (
          <>
            <section className="stack">
              <h2>Research dashboard</h2>
              {analytics?.students.length ? (
                <div className="card chart-card">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={analytics.students}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="email" tick={{ fontSize: 12 }} />
                      <YAxis domain={[0, 1]} />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="average_predicted" name="Predicted" fill="#0f7b66" />
                      <Bar dataKey="average_actual" name="Actual" fill="#c8503d" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="muted">Predictions appear after students complete tracked sessions.</p>
              )}
              {analytics?.model ? (
                <div className="card">
                  <h3>Active class model</h3>
                  <p>
                    {analytics.model.model_type} trained on {analytics.model.sample_count} labeled sessions. RMSE {analytics.model.rmse.toFixed(3)}.
                  </p>
                  <p className={analytics.drift.flagged ? "error" : "muted"}>
                    Drift: {analytics.drift.flagged ? "retraining recommended" : "no retraining flag"}
                  </p>
                  <h4>Top feature importances</h4>
                  {Object.entries(analytics.model.feature_importances)
                    .sort((left, right) => right[1] - left[1])
                    .slice(0, 5)
                    .map(([feature, value]) => (
                      <p className="muted" key={feature}>
                        {feature}: {value.toFixed(3)}
                      </p>
                    ))}
                </div>
              ) : (
                <p className="muted">The heuristic scorer is active until 50 labeled sessions are available.</p>
              )}
            </section>

            <section className="stack">
              <h2>Engagement heatmap</h2>
              {analytics?.section_heatmap.length ? (
                <div className="grid">
                  {analytics.section_heatmap.map(section => (
                    <article className="card" key={section.section_id}>
                      <h3>{section.title}</h3>
                      <p>{section.average_time_s.toFixed(1)} seconds average time</p>
                      <p className="muted">{section.average_hovers.toFixed(1)} average hovers</p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="muted">Section engagement appears after tracked reading sessions.</p>
              )}
            </section>
          </>
        ) : null}

        {auth?.user.role === "educator" || auth?.user.role === "researcher" ? (
          <section className="stack">
            <h2>Roster</h2>
            <div className="grid">
              {roster.map(student => (
                <article className="card" key={student.id}>
                  <Link
                    href={`/students/${student.id}`}
                    style={{ fontWeight: 600, fontSize: 15, color: "var(--ink)" }}
                  >
                    {student.email}
                  </Link>
                  {auth.user.role === "researcher" && (
                    <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
                      {student.profile_entry_count || 0} profile entries
                    </p>
                  )}
                  <div className="toolbar" style={{ marginTop: 10 }}>
                    <Link className="button secondary" href={`/students/${student.id}`}>
                      View learning
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}
