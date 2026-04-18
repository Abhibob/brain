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
  MaterialOut
} from "@/lib/api";
import { AssetPalette } from "@/components/LessonStudio/AssetPalette";
import { AssetPreviewModal } from "@/components/LessonStudio/AssetPreviewModal";
import { PlanCanvas } from "@/components/LessonStudio/PlanCanvas";
import { CompactLearningProfileCard } from "@/components/LearningProfileView/LearningProfileView";
import { fitTen } from "@/lib/scores";

type PreviewState = { asset: LessonAsset; fitScore?: number | null; rationale?: string | null } | null;

type RosterEntry = { id: number; email: string; profile_entry_count?: number };

function emailToName(email: string): string {
  const local = email.split("@")[0] || email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map(p => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

function initials(email: string): string {
  return emailToName(email)
    .split(" ")
    .map(p => p[0])
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

  // Load material + roster once.
  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth) {
      setSignedIn(false);
      router.replace("/login");
      return;
    }
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
    return () => {
      cancelled = true;
    };
  }, [router, materialId]);

  // When student changes, refresh their learning view + draft for this material.
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
            material_id: material.id
          })
        ]);
        if (!cancelled) {
          setView(next);
          setDraft(nextDraft);
          setError(null);
        }
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Failed to build draft");
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [material, selectedStudent]);

  const updateNodes = useCallback(
    async (nodes: Array<{ asset_id: number; order_index: number; teacher_adjusted?: boolean; label?: string | null; notes?: string | null }>) => {
      if (!draft) return;
      try {
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
      } catch (err: any) {
        setError(err?.message ?? "Couldn't save changes");
      }
    },
    [draft]
  );

  const regenerate = useCallback(async () => {
    if (!draft) return;
    setRegenerating(true);
    try {
      const next = await api.regenerateLessonPlan(draft.id);
      setDraft(next);
    } catch (err: any) {
      setError(err?.message ?? "Regenerate failed");
    } finally {
      setRegenerating(false);
    }
  }, [draft]);

  const publish = useCallback(async () => {
    if (!draft || !material) return;
    setPublishing(true);
    try {
      await api.publishLessonPlan(draft.id, material.id);
      router.push(`/classes/${material.class_id}/materials/${material.id}`);
    } catch (err: any) {
      setError(err?.message ?? "Publish failed");
      setPublishing(false);
    }
  }, [draft, material, router]);

  const usedIds = useMemo(() => new Set((draft?.nodes ?? []).map(n => n.asset_id)), [draft]);

  const avgFit = useMemo(() => {
    const scores = (draft?.nodes ?? []).map(n => n.fit_score ?? 0).filter(x => x > 0);
    if (scores.length === 0) return null;
    return scores.reduce((a, b) => a + b, 0) / scores.length;
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
          {material && <Link href={`/classes/${material.class_id}`}>Class</Link>}
          <button
            className="button ghost"
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
        <div className="builder-hero">
          <div>
            <div className="section-heading" style={{ margin: 0 }}>
              Lesson builder
            </div>
            <h1>{material?.title ?? "Loading…"}</h1>
            {material && (
              <div className="muted" style={{ fontSize: 14 }}>
                Building a personalized version — drag cards into your lesson from the suggestions on the right. Each
                card shows a score out of 10 for how well this student tends to learn from it.
              </div>
            )}
          </div>
          {selectedStudent && (
            <div
              className="card card--flat"
              style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 10 }}
            >
              <div className="avatar-sm">{initials(selectedStudent.email)}</div>
              <div style={{ fontSize: 13 }}>
                <div className="faint" style={{ fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                  Designing for
                </div>
                <div style={{ fontWeight: 600 }}>{emailToName(selectedStudent.email)}</div>
              </div>
            </div>
          )}
        </div>

        {error && <p className="error" style={{ marginBottom: 12 }}>{error}</p>}

        <div className="builder-shell">
          <aside className="builder-col">
            <section className="card" style={{ padding: 18 }}>
              <div className="section-heading">Student</div>
              {roster.length === 0 ? (
                <p className="muted" style={{ fontSize: 13 }}>
                  No enrolled students yet.
                </p>
              ) : (
                <div className="stack" style={{ gap: 8 }}>
                  {roster.map(student => {
                    const active = selectedStudent?.id === student.id;
                    return (
                      <button
                        key={student.id}
                        type="button"
                        onClick={() => setSelectedStudent(student)}
                        className="card card--flat"
                        style={{
                          padding: "10px 12px",
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          cursor: "pointer",
                          textAlign: "left",
                          borderColor: active ? "var(--highlight)" : "var(--line)",
                          background: active ? "var(--highlight-soft)" : "var(--surface)"
                        }}
                      >
                        <div className="avatar-sm">{initials(student.email)}</div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: 14 }}>{emailToName(student.email)}</div>
                          <div className="muted" style={{ fontSize: 12 }}>
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
                className="button secondary"
                style={{ textDecoration: "none", justifyContent: "center" }}
              >
                View learning tree →
              </Link>
            )}
            {view && <CompactLearningProfileCard view={view} />}
          </aside>

          <section className="builder-col">
            {busy && (
              <div className="card" style={{ padding: 14, fontSize: 13 }}>
                <span className="muted">Loading suggestions for this student…</span>
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
              !busy && <p className="muted">Pick a student to start building.</p>
            )}
          </section>

          <aside className="builder-col">
            {draft ? (
              <AssetPalette
                candidates={draft.candidates}
                usedAssetIds={usedIds}
                onRegenerate={regenerate}
                onPreviewAsset={candidate =>
                  setPreview({ asset: candidate.asset, fitScore: candidate.fit_score, rationale: candidate.rationale })
                }
                busy={regenerating}
              />
            ) : (
              <div className="card" style={{ padding: 18 }}>
                <div className="section-heading">Suggestions</div>
                <p className="muted" style={{ fontSize: 13 }}>
                  Pick a student to see suggestions scored for them.
                </p>
              </div>
            )}
          </aside>
        </div>

        {draft && (
          <div className="builder-sticky-bar">
            <div style={{ display: "flex", flexDirection: "column" }}>
              <div className="section-heading" style={{ margin: 0 }}>
                Draft ready
              </div>
              <div className="muted" style={{ fontSize: 13 }}>
                {draft.nodes.length} card{draft.nodes.length === 1 ? "" : "s"} ·{" "}
                {avgFit !== null ? `avg fit ${fitTen(avgFit).toFixed(1)}/10` : "drag your first card"}
              </div>
            </div>
            <div className="toolbar">
              <button className="button ghost" onClick={regenerate} disabled={regenerating}>
                {regenerating ? "Regenerating…" : "Regenerate"}
              </button>
              <button className="button" onClick={publish} disabled={publishing || draft.nodes.length === 0}>
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
