"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  clearAuth,
  getStoredAuth,
  LearningView,
  LessonPlanDraft
} from "@/lib/api";
import { LearningProfileView } from "@/components/LearningProfileView/LearningProfileView";
import { AssetPalette } from "@/components/LessonStudio/AssetPalette";
import { PlanCanvas } from "@/components/LessonStudio/PlanCanvas";
import { TopicInput } from "@/components/LessonStudio/TopicInput";

function LessonStudioContent() {
  const router = useRouter();
  const params = useSearchParams();
  const studentIdParam = params.get("student_id");
  const classIdParam = params.get("class_id");
  const studentId = studentIdParam ? Number(studentIdParam) : null;
  const classId = classIdParam ? Number(classIdParam) : null;
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [view, setView] = useState<LearningView | null>(null);
  const [draft, setDraft] = useState<LessonPlanDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth) {
      setSignedIn(false);
      router.replace("/login");
      return;
    }
    setSignedIn(true);
    if (!studentId) return;
    api
      .getLearningView(studentId)
      .then(setView)
      .catch(err => setError(err.message));
  }, [router, studentId]);

  const createDraft = useCallback(
    async (payload: { topic: string; description: string }) => {
      if (!studentId) return;
      setBusy(true);
      setError(null);
      try {
        const next = await api.createLessonPlan({
          student_id: studentId,
          topic: payload.topic,
          description: payload.description || undefined,
          class_id: classId ?? undefined
        });
        setDraft(next);
        setSelectedTopic(payload.topic.toLowerCase());
      } catch (err: any) {
        setError(err.message);
      } finally {
        setBusy(false);
      }
    },
    [studentId, classId]
  );

  const regenerate = useCallback(async () => {
    if (!draft) return;
    setBusy(true);
    try {
      const next = await api.regenerateLessonPlan(draft.id);
      setDraft(next);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }, [draft]);

  const updateNodes = useCallback(
    async (nodes: Array<{ asset_id: number; order_index: number; teacher_adjusted?: boolean; label?: string | null; notes?: string | null }>) => {
      if (!draft) return;
      const next = await api.patchLessonPlan(
        draft.id,
        nodes.map(node => ({
          asset_id: node.asset_id,
          order_index: node.order_index,
          label: node.label ?? undefined,
          notes: node.notes ?? undefined,
          teacher_adjusted: node.teacher_adjusted ?? true
        }))
      );
      setDraft(next);
    },
    [draft]
  );

  const publish = useCallback(async () => {
    if (!draft) return;
    setPublishing(true);
    try {
      const material = await api.publishLessonPlan(draft.id);
      setPublishing(false);
      if (classId) router.push(`/classes/${classId}/materials/${material.id}`);
    } catch (err: any) {
      setError(err.message);
      setPublishing(false);
    }
  }, [draft, classId, router]);

  const totalFitAverage = useMemo(() => {
    if (!draft?.nodes.length) return null;
    const scores = draft.nodes.map(n => n.fit_score ?? 0).filter(v => v > 0);
    return scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : null;
  }, [draft]);

  if (signedIn === false) return null;

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/dashboard">
          EduTrack
        </Link>
        <nav className="nav">
          <Link href="/dashboard">Dashboard</Link>
          {classId ? <Link href={`/classes/${classId}`}>Class</Link> : null}
          <button
            className="button secondary"
            onClick={() => {
              clearAuth();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </nav>
      </header>
      <main className="main">
        <div className="band">
          <h1>Lesson studio</h1>
          {studentId ? (
            <p className="muted">Designing a personalized lesson for student #{studentId}.</p>
          ) : (
            <p className="error">No student selected. Open the studio from the class roster.</p>
          )}
          {error && <p className="error">{error}</p>}
        </div>

        {studentId && (
          <div style={{ display: "grid", gridTemplateColumns: "minmax(320px, 420px) 1fr", gap: 24 }}>
            <aside>
              {view ? (
                <LearningProfileView view={view} selectedTopic={selectedTopic} onSelectTopic={setSelectedTopic} />
              ) : (
                <p className="muted">Loading learning profile...</p>
              )}
            </aside>

            <div className="stack" style={{ gap: 18 }}>
              <section className="card">
                <h3 style={{ marginTop: 0 }}>Describe the lesson</h3>
                <TopicInput onSubmit={createDraft} busy={busy} />
                {draft && (
                  <p className="muted" style={{ marginTop: 10 }}>
                    Draft #{draft.id} · {draft.nodes.length} nodes · average fit {totalFitAverage ?? "–"}
                  </p>
                )}
              </section>

              {draft && (
                <>
                  <PlanCanvas nodes={draft.nodes} candidates={draft.candidates} onChange={updateNodes} />
                  <div className="toolbar" style={{ justifyContent: "flex-end" }}>
                    <button className="button ghost" onClick={regenerate} disabled={busy}>
                      {busy ? "Regenerating…" : "Regenerate"}
                    </button>
                    <button
                      className="button"
                      onClick={publish}
                      disabled={publishing || !classId || draft.nodes.length === 0}
                    >
                      {publishing ? "Publishing…" : "Publish to class"}
                    </button>
                  </div>
                  <AssetPalette candidates={draft.candidates} onRegenerate={regenerate} busy={busy} />
                </>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default function LessonStudioPage() {
  return (
    <Suspense fallback={<main className="main">Loading lesson studio...</main>}>
      <LessonStudioContent />
    </Suspense>
  );
}
