"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  ClassOut,
  clearAuth,
  getStoredAuth,
  LearningView,
  LessonPlanDraft,
} from "@/lib/api";
import { CompactLearningProfileCard } from "@/components/LearningProfileView/LearningProfileView";
import { AssetPalette } from "@/components/LessonStudio/AssetPalette";
import { PlanCanvas } from "@/components/LessonStudio/PlanCanvas";
import { TopicInput } from "@/components/LessonStudio/TopicInput";
import TopBar from "@/components/ui/TopBar";
import MaterialIcon from "@/components/ui/MaterialIcon";

type RosterEntry = { id: number; email: string; profile_entry_count?: number };

function emailToName(email: string): string {
  const local = email.split("@")[0] || email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

function LessonStudioContent() {
  const router = useRouter();
  const params = useSearchParams();
  const studentIdParam = params.get("student_id");
  const classIdParam = params.get("class_id");

  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(
    classIdParam ? Number(classIdParam) : null
  );
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(
    studentIdParam ? Number(studentIdParam) : null
  );

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
    api
      .listClasses()
      .then((cls) => {
        setClasses(cls);
        if (!selectedClassId && cls.length > 0) setSelectedClassId(cls[0].id);
      })
      .catch((err) => setError(err.message));
  }, [router]);

  useEffect(() => {
    if (!selectedClassId) return;
    setRoster([]);
    setSelectedStudentId(null);
    setView(null);
    setDraft(null);
    api
      .roster(selectedClassId)
      .then((r) => {
        setRoster(r);
        if (r.length > 0) setSelectedStudentId(r[0].id);
      })
      .catch((err) => setError(err.message));
  }, [selectedClassId]);

  useEffect(() => {
    if (!selectedStudentId) return;
    setView(null);
    setDraft(null);
    api.getLearningView(selectedStudentId).then(setView).catch((err) => setError(err.message));
  }, [selectedStudentId]);

  const createDraft = useCallback(
    async (payload: { topic: string; description: string }) => {
      if (!selectedStudentId) return;
      setBusy(true);
      setError(null);
      try {
        const next = await api.createLessonPlan({
          student_id: selectedStudentId,
          topic: payload.topic,
          description: payload.description || undefined,
          class_id: selectedClassId ?? undefined,
        });
        setDraft(next);
        setSelectedTopic(payload.topic.toLowerCase());
      } catch (err: any) {
        setError(err.message);
      } finally {
        setBusy(false);
      }
    },
    [selectedStudentId, selectedClassId]
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
    async (
      nodes: Array<{
        asset_id: number;
        order_index: number;
        teacher_adjusted?: boolean;
        label?: string | null;
        notes?: string | null;
      }>
    ) => {
      if (!draft) return;
      const next = await api.patchLessonPlan(
        draft.id,
        nodes.map((node) => ({
          asset_id: node.asset_id,
          order_index: node.order_index,
          label: node.label ?? undefined,
          notes: node.notes ?? undefined,
          teacher_adjusted: node.teacher_adjusted ?? true,
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
      if (selectedClassId)
        router.push(`/classes/${selectedClassId}/materials/${material.id}`);
    } catch (err: any) {
      setError(err.message);
      setPublishing(false);
    }
  }, [draft, selectedClassId, router]);

  const totalFitAverage = useMemo(() => {
    if (!draft?.nodes.length) return null;
    const scores = draft.nodes.map((n) => n.fit_score ?? 0).filter((v) => v > 0);
    return scores.length
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : null;
  }, [draft]);

  const usedIds = useMemo(
    () => new Set((draft?.nodes ?? []).map((n) => n.asset_id)),
    [draft]
  );

  const selectedStudent = roster.find((s) => s.id === selectedStudentId);

  if (signedIn === false) return null;

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[
          { label: "Dashboard", href: "/dashboard" },
          ...(selectedClassId
            ? [{ label: "Class", href: `/classes/${selectedClassId}` }]
            : []),
        ]}
        activeLink="Dashboard"
        onLogout={() => {
          clearAuth();
          router.replace("/login");
        }}
      />

      <main className="max-w-screen-2xl mx-auto px-4 md:px-8 lg:px-12 py-8 space-y-6">
        {/* Header row */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="font-headline text-4xl text-primary font-medium tracking-[-0.025em]">
              Lesson studio
            </h1>
            <p className="font-body text-on-surface-variant mt-1">
              Design personalized, adaptive lessons for each student.
            </p>
          </div>

          {/* Class & Student selectors inline */}
          <div className="flex flex-wrap items-end gap-4">
            <div className="space-y-1">
              <label className="font-body text-[10px] uppercase tracking-[0.08em] text-on-surface-variant font-semibold">
                Class
              </label>
              <select
                className="bg-surface-container-lowest border border-surface-dim/30 rounded-xl px-4 py-2.5 text-sm text-on-surface font-body focus:border-primary focus:outline-none transition-colors min-w-[180px]"
                value={selectedClassId ?? ""}
                onChange={(e) =>
                  setSelectedClassId(e.target.value ? Number(e.target.value) : null)
                }
              >
                <option value="">Select class…</option>
                {classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="font-body text-[10px] uppercase tracking-[0.08em] text-on-surface-variant font-semibold">
                Student
              </label>
              <select
                className="bg-surface-container-lowest border border-surface-dim/30 rounded-xl px-4 py-2.5 text-sm text-on-surface font-body focus:border-primary focus:outline-none transition-colors min-w-[180px]"
                value={selectedStudentId ?? ""}
                onChange={(e) =>
                  setSelectedStudentId(e.target.value ? Number(e.target.value) : null)
                }
                disabled={roster.length === 0}
              >
                <option value="">
                  {roster.length === 0 ? "No students" : "Select student…"}
                </option>
                {roster.map((s) => (
                  <option key={s.id} value={s.id}>
                    {emailToName(s.email)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {error && (
          <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
            {error}
          </p>
        )}

        {/* No student selected state */}
        {!selectedStudentId && (
          <div className="bg-surface-container-lowest rounded-[32px] border border-surface-dim/20 p-16 text-center">
            <div className="w-20 h-20 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-6">
              <MaterialIcon name="school" className="text-4xl text-on-surface-variant" />
            </div>
            <h2 className="font-headline text-2xl text-primary font-medium mb-2">
              Select a class and student
            </h2>
            <p className="font-body text-on-surface-variant max-w-md mx-auto">
              Choose a class and student above to begin designing an adaptive lesson tailored to
              their learning style.
            </p>
          </div>
        )}

        {/* Main 3-column builder */}
        {selectedStudentId && (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] xl:grid-cols-[320px_1fr_360px] gap-6 items-start">
            {/* LEFT — Learning Profile */}
            <aside className="space-y-6 lg:sticky lg:top-24">
              {/* Student card */}
              {selectedStudent && (
                <div className="bg-surface-container-lowest rounded-[32px] border border-surface-dim/20 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-primary-container flex items-center justify-center text-on-primary font-bold text-sm">
                      {emailToName(selectedStudent.email)
                        .split(" ")
                        .map((p) => p[0])
                        .join("")
                        .slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-body text-[10px] uppercase tracking-widest text-on-surface-variant">
                        Designing for
                      </div>
                      <div className="font-body font-semibold text-on-surface text-sm">
                        {emailToName(selectedStudent.email)}
                      </div>
                    </div>
                  </div>
                  <Link
                    href={`/students/${selectedStudent.id}`}
                    className="font-body text-xs text-primary font-medium flex items-center gap-1 hover:text-primary-container transition-colors"
                  >
                    View full profile
                    <MaterialIcon name="arrow_forward" className="text-sm" />
                  </Link>
                </div>
              )}

              {/* Learning profile */}
              {view ? (
                <CompactLearningProfileCard view={view} />
              ) : (
                <div className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20 flex items-center justify-center min-h-[200px]">
                  <p className="font-body text-sm text-on-surface-variant">
                    Loading profile...
                  </p>
                </div>
              )}
            </aside>

            {/* CENTER — Topic Input + Plan Canvas */}
            <div className="space-y-6">
              {/* Topic input */}
              <div className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-xl bg-tertiary-fixed text-on-tertiary-fixed flex items-center justify-center">
                    <MaterialIcon name="edit_note" className="text-lg" />
                  </div>
                  <div>
                    <h3 className="font-headline text-lg text-primary font-medium">
                      Describe the lesson
                    </h3>
                    <p className="font-body text-xs text-on-surface-variant">
                      Enter a topic to generate personalized content
                    </p>
                  </div>
                </div>
                <TopicInput onSubmit={createDraft} busy={busy} />
                {draft && (
                  <div className="flex items-center gap-4 mt-4 pt-4 border-t border-surface-dim/30">
                    <span className="font-body text-xs font-semibold px-3 py-1 rounded-full bg-primary-fixed text-on-primary-fixed">
                      Draft #{draft.id}
                    </span>
                    <span className="font-body text-sm text-on-surface-variant">
                      {draft.nodes.length} nodes · avg fit {totalFitAverage ?? "–"}
                    </span>
                  </div>
                )}
              </div>

              {/* Plan canvas */}
              {draft ? (
                <>
                  <PlanCanvas
                    nodes={draft.nodes}
                    candidates={draft.candidates}
                    onChange={updateNodes}
                  />

                  {/* Action bar */}
                  <div className="flex flex-wrap gap-3 justify-end">
                    <button
                      className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm flex items-center gap-2"
                      onClick={regenerate}
                      disabled={busy}
                    >
                      <MaterialIcon name="refresh" className={`text-base ${busy ? "animate-spin" : ""}`} />
                      {busy ? "Regenerating…" : "Regenerate"}
                    </button>
                    <button
                      className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2"
                      onClick={publish}
                      disabled={
                        publishing || !selectedClassId || draft.nodes.length === 0
                      }
                    >
                      <MaterialIcon name="publish" className="text-base" />
                      {publishing ? "Publishing…" : "Publish to class"}
                    </button>
                  </div>
                </>
              ) : (
                <div className="bg-surface-container-lowest rounded-[32px] border-2 border-dashed border-surface-dim/30 p-16 text-center">
                  <div className="w-16 h-16 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4">
                    <MaterialIcon name="draw" className="text-3xl text-on-surface-variant" />
                  </div>
                  <p className="font-headline text-lg text-on-surface font-medium mb-2">
                    Enter a topic to get started
                  </p>
                  <p className="font-body text-sm text-on-surface-variant max-w-sm mx-auto">
                    Describe what you want to teach and we'll generate personalized content
                    suggestions.
                  </p>
                </div>
              )}
            </div>

            {/* RIGHT — Suggestions Palette */}
            <aside className="lg:sticky lg:top-24">
              {draft ? (
                <AssetPalette
                  candidates={draft.candidates}
                  usedAssetIds={usedIds}
                  onRegenerate={regenerate}
                  busy={busy}
                />
              ) : (
                <div className="bg-surface-container-lowest rounded-[32px] border border-surface-dim/20 p-8 text-center">
                  <div className="w-14 h-14 rounded-full bg-surface-container-high flex items-center justify-center mx-auto mb-4">
                    <MaterialIcon
                      name="auto_awesome"
                      className="text-2xl text-on-surface-variant"
                    />
                  </div>
                  <h3 className="font-headline text-lg text-primary font-medium mb-2">
                    Suggestions
                  </h3>
                  <p className="font-body text-sm text-on-surface-variant">
                    Content suggestions will appear here after you describe a lesson topic.
                  </p>
                </div>
              )}
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}

export default function LessonStudioPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-background flex items-center justify-center">
          <p className="font-body text-on-surface-variant">Loading lesson studio...</p>
        </main>
      }
    >
      <LessonStudioContent />
    </Suspense>
  );
}
