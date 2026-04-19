"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ClassAnalytics, ClassOut, clearAuth, getStoredAuth } from "@/lib/api";
import TopBar from "@/components/ui/TopBar";
import MaterialIcon from "@/components/ui/MaterialIcon";

export default function ClassPage() {
  const params = useParams<{ id: string }>();
  const classId = Number(params.id);
  const router = useRouter();
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
    load().catch((e) => setError(e.message));
  }, [classId]);

  async function createLesson(event: FormEvent) {
    event.preventDefault();
    const material = await api.createMaterial(classId, {
      title,
      type: "lesson",
      sections: [
        { title: "Core idea", content, order_index: 0 },
        { title: "Worked example", content: "Trace each call, write down the base case, then return values one layer at a time.", order_index: 1 },
      ],
    });
    await api.createQuiz(material.id, [
      {
        question: "What must every recursive function include?",
        options: ["Only a loop", "A base case", "A database", "A timer"],
        correct_answer: "A base case",
        points: 1,
      },
    ]);
    await load();
  }

  if (!classOut)
    return (
      <main className="max-w-4xl mx-auto px-6 py-16">
        <p className="font-body text-on-surface-variant">{error || "Loading class..."}</p>
      </main>
    );

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[
          { label: "Dashboard", href: "/dashboard" },
          { label: classOut.title, href: `/classes/${classId}` },
        ]}
        activeLink={classOut.title}
        onLogout={() => { clearAuth(); router.push("/login"); }}
      />

      <main className="max-w-screen-xl mx-auto px-6 md:px-12 py-16 space-y-16">
        {/* Class Header */}
        <section className="bg-surface-container-lowest rounded-[32px] p-10 md:p-16 relative overflow-hidden shadow-[0px_20px_40px_rgba(27,28,26,0.04)] border border-surface-dim/20">
          <div className="absolute inset-0 bg-gradient-to-br from-primary-fixed/10 via-transparent to-surface-dim/10 pointer-events-none" />
          <div className="relative z-10">
            <h1 className="font-headline text-4xl md:text-5xl text-primary font-medium tracking-[-0.03em] leading-[1.05] mb-4">
              {classOut.title}
            </h1>
            <p className="font-body text-lg text-on-surface-variant leading-relaxed max-w-lg">
              {classOut.description}
            </p>
            {auth?.user.role === "educator" && (
              <p className="font-body text-sm text-on-surface-variant mt-4">
                Enrollment code:{" "}
                <span className="font-semibold text-primary">{classOut.enrollment_code}</span>
              </p>
            )}
          </div>
        </section>

        {error && (
          <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
            {error}
          </p>
        )}

        {/* Create Lesson Form (Educator) */}
        {auth?.user.role === "educator" && (
          <section className="bg-surface-container-lowest rounded-[32px] p-8 shadow-[0_20px_40px_rgba(27,28,26,0.06)] border border-surface-dim/20">
            <h2 className="font-headline text-2xl text-primary font-medium mb-6">Create lesson</h2>
            <form onSubmit={createLesson} className="space-y-5">
              <div className="space-y-2">
                <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                  Title
                </label>
                <input
                  className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                  Content
                </label>
                <textarea
                  className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors min-h-[140px] resize-y"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  required
                />
              </div>
              <button
                type="submit"
                className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2"
              >
                Create lesson and quiz
                <MaterialIcon name="add" className="text-[18px]" />
              </button>
            </form>
          </section>
        )}

        {/* Materials */}
        <section className="space-y-8">
          <h2 className="font-headline text-3xl text-primary tracking-tight font-medium">
            Materials
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {(classOut.materials || []).map((material) => (
              <div
                key={material.id}
                className="bg-surface-container-lowest rounded-[32px] p-8 hover:bg-surface-container-low transition-colors duration-300 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] border border-surface-dim/20"
              >
                <h3 className="font-headline text-xl text-primary font-medium mb-2">
                  {material.title}
                </h3>
                <p className="font-body text-sm text-on-surface-variant mb-6">
                  {material.published_at ? "Published" : "Draft"}
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link
                    href={`/classes/${classId}/materials/${material.id}`}
                    className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm flex items-center gap-2"
                  >
                    Open
                  </Link>
                  {auth?.user.role === "educator" && (
                    <>
                      <Link
                        href={`/educator/materials/${material.id}/edit`}
                        className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm"
                      >
                        Edit
                      </Link>
                      <button
                        className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm"
                        onClick={() => api.publishMaterial(material.id).then(load)}
                      >
                        Publish
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Research Section */}
        {auth?.user.role === "researcher" && (
          <>
            <section className="research-entry">
              <div>
                <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-2">
                  Research workbench
                </div>
                <h2 className="font-headline text-2xl text-primary font-medium">
                  Mechanistic and neuro-response inspection
                </h2>
                <p className="font-body text-sm text-on-surface-variant mt-2">
                  Open the researcher-only workspace for personalized neural surrogates, backprop
                  traces, content audits, and TRIBE v2 predicted fMRI views.
                </p>
              </div>
              <Link
                href={`/research/classes/${classId}/workbench`}
                className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2 flex-shrink-0"
              >
                Open workbench
                <MaterialIcon name="arrow_forward" className="text-[18px]" />
              </Link>
            </section>

            <section className="space-y-8">
              <h2 className="font-headline text-3xl text-primary tracking-tight font-medium">
                Research dashboard
              </h2>
              {analytics?.students.length ? (
                <div className="bg-surface-container-lowest rounded-[32px] p-8 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] border border-surface-dim/20 min-h-[300px]">
                  <ResponsiveContainer width="100%" height={260}>
                    <BarChart data={analytics.students}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#dbdad6" />
                      <XAxis dataKey="email" tick={{ fontSize: 12 }} stroke="#414847" />
                      <YAxis domain={[0, 1]} stroke="#414847" />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="average_predicted" name="Predicted" fill="#002d28" />
                      <Bar dataKey="average_actual" name="Actual" fill="#3e1e12" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <p className="font-body text-on-surface-variant">
                  Predictions appear after students complete tracked sessions.
                </p>
              )}
              {analytics?.model ? (
                <div className="bg-surface-container-lowest rounded-[32px] p-8 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] border border-surface-dim/20">
                  <h3 className="font-headline text-xl text-primary font-medium mb-4">
                    Active class model
                  </h3>
                  <p className="font-body text-on-surface-variant">
                    {analytics.model.model_type} trained on {analytics.model.sample_count} labeled
                    sessions. RMSE {analytics.model.rmse.toFixed(3)}.
                  </p>
                  <p
                    className={
                      analytics.drift.flagged
                        ? "text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm mt-4"
                        : "font-body text-on-surface-variant mt-2"
                    }
                  >
                    Drift:{" "}
                    {analytics.drift.flagged ? "retraining recommended" : "no retraining flag"}
                  </p>
                  <h4 className="font-headline text-lg text-primary font-medium mt-6 mb-3">
                    Top feature importances
                  </h4>
                  {Object.entries(analytics.model.feature_importances)
                    .sort((left, right) => right[1] - left[1])
                    .slice(0, 5)
                    .map(([feature, value]) => (
                      <p className="font-body text-sm text-on-surface-variant" key={feature}>
                        {feature}: {value.toFixed(3)}
                      </p>
                    ))}
                </div>
              ) : (
                <p className="font-body text-on-surface-variant">
                  The heuristic scorer is active until 50 labeled sessions are available.
                </p>
              )}
            </section>

            <section className="space-y-8">
              <h2 className="font-headline text-3xl text-primary tracking-tight font-medium">
                Engagement heatmap
              </h2>
              {analytics?.section_heatmap.length ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                  {analytics.section_heatmap.map((section) => (
                    <div
                      key={section.section_id}
                      className="bg-surface-container-lowest rounded-[32px] p-8 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] border border-surface-dim/20"
                    >
                      <h3 className="font-headline text-xl text-primary font-medium mb-2">
                        {section.title}
                      </h3>
                      <p className="font-body text-on-surface">
                        {section.average_time_s.toFixed(1)} seconds average time
                      </p>
                      <p className="font-body text-sm text-on-surface-variant">
                        {section.average_hovers.toFixed(1)} average hovers
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="font-body text-on-surface-variant">
                  Section engagement appears after tracked reading sessions.
                </p>
              )}
            </section>
          </>
        )}

        {/* Roster */}
        {(auth?.user.role === "educator" || auth?.user.role === "researcher") && (
          <section className="space-y-8">
            <h2 className="font-headline text-3xl text-primary tracking-tight font-medium">
              Roster
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {roster.map((student) => (
                <div
                  key={student.id}
                  className="bg-surface-container-lowest rounded-[32px] p-8 hover:bg-surface-container-low transition-colors duration-300 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] border border-surface-dim/20"
                >
                  <Link
                    href={`/students/${student.id}`}
                    className="font-headline text-xl text-primary font-medium hover:text-primary-container transition-colors"
                  >
                    {student.email}
                  </Link>
                  {auth?.user.role === "researcher" && (
                    <p className="font-body text-sm text-on-surface-variant mt-2">
                      {student.profile_entry_count || 0} profile entries
                    </p>
                  )}
                  <div className="mt-4">
                    <Link
                      href={`/students/${student.id}`}
                      className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm inline-block"
                    >
                      View learning
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
