"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  clearAuth,
  getStoredAuth,
  LearningView,
  LessonAsset,
  LessonPlanDraft,
  MaterialOut,
} from "@/lib/api";
import { AssetPalette } from "@/components/LessonStudio/AssetPalette";
import { AssetPreviewModal } from "@/components/LessonStudio/AssetPreviewModal";
import { PlanCanvas } from "@/components/LessonStudio/PlanCanvas";
import { CompactLearningProfileCard } from "@/components/LearningProfileView/LearningProfileView";
import { fitTen } from "@/lib/scores";
import TopBar from "@/components/ui/TopBar";
import MaterialIcon from "@/components/ui/MaterialIcon";

type PreviewState = { asset: LessonAsset; fitScore?: number | null; rationale?: string | null } | null;
type RosterEntry = { id: number; email: string; profile_entry_count?: number };

function emailToName(email: string): string {
  const local = email.split("@")[0] || email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

function initials(email: string): string {
  return emailToName(email)
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export default function MaterialEditPage() {
  const params = useParams<{ id: string }>();
  const materialId = Number(params.id);
  const router = useRouter();

  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [material, setMaterial] = useState<MaterialOut | null>(null);
  const [roster, setRoster] = useState<RosterEntry[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<RosterEntry | null>(null);
  const [view, setView] = useState<LearningView | null>(null);
  const [draft, setDraft] = useState<LessonPlanDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewState>(null);

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth) { setSignedIn(false); router.replace("/login"); return; }
    setSignedIn(true);
    let cancelled = false;
    (async () => {
      try {
        const m = await api.getMaterial(materialId);
        if (cancelled) return;
        setMaterial(m);
        try {
          const r = await api.roster(m.class_id);
          if (cancelled) return;
          setRoster(r);
          if (r.length > 0) setSelectedStudent(r[0]);
        } catch (err: any) {
          if (!cancelled) setError(err?.message ?? "Could not load roster");
        }
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Could not load lesson");
      }
    })();
    return () => { cancelled = true; };
  }, [router, materialId]);

  useEffect(() => {
    if (!material || !selectedStudent) return;
    let cancelled = false;
    setBusy(true);
    (async () => {
      try {
        const [next, nextDraft] = await Promise.all([
          api.getLearningView(selectedStudent.id),
          api.createLessonPlan({
            student_id: selectedStudent.id,
            topic: material.title,
            description: `Personalize "${material.title}" for this student.`,
            class_id: material.class_id,
            material_id: material.id,
          }),
        ]);
        if (!cancelled) { setView(next); setDraft(nextDraft); setError(null); }
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Failed to build draft");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => { cancelled = true; };
  }, [material, selectedStudent]);

  const updateNodes = useCallback(
    async (nodes: Array<{ asset_id: number; order_index: number; teacher_adjusted?: boolean; label?: string | null; notes?: string | null }>) => {
      if (!draft) return;
      try {
        const next = await api.patchLessonPlan(draft.id, nodes.map((node) => ({
          asset_id: node.asset_id, order_index: node.order_index,
          label: node.label ?? undefined, notes: node.notes ?? undefined,
          teacher_adjusted: node.teacher_adjusted ?? true,
        })));
        setDraft(next);
      } catch (err: any) { setError(err?.message ?? "Couldn't save changes"); }
    }, [draft]
  );

  const regenerate = useCallback(async () => {
    if (!draft) return;
    setRegenerating(true);
    try { const next = await api.regenerateLessonPlan(draft.id); setDraft(next); }
    catch (err: any) { setError(err?.message ?? "Regenerate failed"); }
    finally { setRegenerating(false); }
  }, [draft]);

  const publish = useCallback(async () => {
    if (!draft || !material) return;
    setPublishing(true);
    try {
      await api.publishLessonPlan(draft.id, material.id);
      router.push(`/classes/${material.class_id}/materials/${material.id}`);
    } catch (err: any) { setError(err?.message ?? "Publish failed"); setPublishing(false); }
  }, [draft, material, router]);

  const usedIds = useMemo(() => new Set((draft?.nodes ?? []).map((n) => n.asset_id)), [draft]);
  const avgFit = useMemo(() => {
    const scores = (draft?.nodes ?? []).map((n) => n.fit_score ?? 0).filter((x) => x > 0);
    if (scores.length === 0) return null;
    return scores.reduce((a, b) => a + b, 0) / scores.length;
  }, [draft]);

  if (signedIn === false) return null;

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[
          { label: "Dashboard", href: "/dashboard" },
          ...(material ? [{ label: "Class", href: `/classes/${material.class_id}` }] : []),
        ]}
        activeLink="Dashboard"
        onLogout={() => { clearAuth(); router.replace("/login"); }}
      />

      <main className="max-w-screen-2xl mx-auto px-6 md:px-12 py-12 space-y-8">
        {/* Hero */}
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex-1 min-w-[260px]">
            <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-1">
              Lesson builder
            </div>
            <h1 className="font-headline text-3xl text-primary font-medium tracking-[-0.025em]">
              {material?.title ?? "Loading…"}
            </h1>
            {material && (
              <p className="font-body text-sm text-on-surface-variant mt-2 max-w-lg">
                Building a personalized version — drag cards into your lesson from the suggestions
                on the right. Each card shows a score out of 10 for how well this student tends to
                learn from it.
              </p>
            )}
          </div>
          {selectedStudent && (
            <div className="bg-surface-container-lowest rounded-2xl p-3 px-4 flex items-center gap-3 border border-surface-dim/20">
              <div className="w-9 h-9 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-sm font-bold">
                {initials(selectedStudent.email)}
              </div>
              <div className="text-sm">
                <div className="font-body text-xs text-on-surface-variant uppercase tracking-widest">
                  Designing for
                </div>
                <div className="font-body font-semibold text-on-surface">
                  {emailToName(selectedStudent.email)}
                </div>
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
            {error}
          </p>
        )}

        {/* Builder 3-Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[minmax(260px,300px)_minmax(0,1fr)_minmax(280px,340px)] gap-6">
          {/* Student Sidebar */}
          <aside className="space-y-6">
            <section className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
              <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
                Student
              </div>
              {roster.length === 0 ? (
                <p className="font-body text-sm text-on-surface-variant">No enrolled students yet.</p>
              ) : (
                <div className="space-y-2">
                  {roster.map((student) => {
                    const active = selectedStudent?.id === student.id;
                    return (
                      <button
                        key={student.id}
                        type="button"
                        onClick={() => setSelectedStudent(student)}
                        className={`w-full text-left rounded-2xl p-3 flex items-center gap-3 transition-colors duration-200 ${
                          active
                            ? "bg-primary-fixed border border-primary/20"
                            : "bg-surface border border-surface-dim/20 hover:bg-surface-container-low"
                        }`}
                      >
                        <div className="w-9 h-9 rounded-full bg-primary-fixed text-on-primary-fixed flex items-center justify-center text-sm font-bold flex-shrink-0">
                          {initials(student.email)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-body font-semibold text-sm text-on-surface truncate">
                            {emailToName(student.email)}
                          </div>
                          <div className="font-body text-xs text-on-surface-variant truncate">
                            {student.email}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>
            {selectedStudent && (
              <Link
                href={`/students/${selectedStudent.id}`}
                className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm flex items-center justify-center gap-2"
              >
                View learning tree
                <MaterialIcon name="arrow_forward" className="text-[16px]" />
              </Link>
            )}
            {view && <CompactLearningProfileCard view={view} />}
          </aside>

          {/* Canvas */}
          <section className="space-y-4">
            {busy && (
              <div className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
                <span className="font-body text-sm text-on-surface-variant">
                  Loading suggestions for this student…
                </span>
              </div>
            )}
            {draft ? (
              <PlanCanvas
                nodes={draft.nodes}
                candidates={draft.candidates}
                onChange={updateNodes}
                onPreviewAsset={(asset, fit, rationale) => {
                  if (asset) setPreview({ asset, fitScore: fit ?? null, rationale });
                }}
              />
            ) : (
              !busy && (
                <p className="font-body text-on-surface-variant">
                  Pick a student to start building.
                </p>
              )
            )}
          </section>

          {/* Suggestions Sidebar */}
          <aside>
            {draft ? (
              <AssetPalette
                candidates={draft.candidates}
                usedAssetIds={usedIds}
                onRegenerate={regenerate}
                onPreviewAsset={(candidate) =>
                  setPreview({
                    asset: candidate.asset,
                    fitScore: candidate.fit_score,
                    rationale: candidate.rationale,
                  })
                }
                busy={regenerating}
              />
            ) : (
              <div className="bg-surface-container-lowest rounded-[32px] p-6 border border-surface-dim/20">
                <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-2">
                  Suggestions
                </div>
                <p className="font-body text-sm text-on-surface-variant">
                  Pick a student to see suggestions scored for them.
                </p>
              </div>
            )}
          </aside>
        </div>

        {/* Sticky Bottom Bar */}
        {draft && (
          <div className="sticky bottom-4 bg-surface-container-lowest rounded-[32px] p-4 px-6 border border-surface-dim/20 shadow-[0px_20px_40px_rgba(27,28,26,0.1)] flex flex-wrap gap-4 items-center justify-between">
            <div>
              <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                Draft ready
              </div>
              <div className="font-body text-sm text-on-surface-variant">
                {draft.nodes.length} card{draft.nodes.length === 1 ? "" : "s"} ·{" "}
                {avgFit !== null ? `avg fit ${fitTen(avgFit).toFixed(1)}/10` : "drag your first card"}
              </div>
            </div>
            <div className="flex gap-3">
              <button
                className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm"
                onClick={regenerate}
                disabled={regenerating}
              >
                {regenerating ? "Regenerating…" : "Regenerate"}
              </button>
              <button
                className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm shadow-[0px_10px_20px_rgba(0,45,40,0.15)]"
                onClick={publish}
                disabled={publishing || draft.nodes.length === 0}
              >
                {publishing ? "Publishing…" : "Publish to class"}
              </button>
            </div>
          </div>
        )}
      </main>

      {preview && (
        <AssetPreviewModal
          asset={preview.asset}
          fitScore={preview.fitScore ?? null}
          rationale={preview.rationale ?? null}
          onClose={() => setPreview(null)}
        />
      )}
    </div>
  );
}
