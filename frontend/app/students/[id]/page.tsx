"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  clearAuth,
  getStoredAuth,
  LearningView,
  ProfileEntry,
} from "@/lib/api";
import { FocusTimeline } from "@/components/LearningProfileView/FocusTimeline";
import { LearningStyleNet } from "@/components/LearningProfileView/LearningStyleNet";
import { BrainModel, activationsForLesson } from "@/components/BrainModel/BrainModel";
import TopBar from "@/components/ui/TopBar";

function emailToName(email: string): string {
  const local = email.split("@")[0] || email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1))
    .join(" ");
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

type Meta = { id: number; email: string; name: string };

export default function StudentPage() {
  const params = useParams<{ id: string }>();
  const studentId = Number(params.id);
  const router = useRouter();

  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [view, setView] = useState<LearningView | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [entries, setEntries] = useState<ProfileEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

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
        const v = await api.getLearningView(studentId);
        if (!cancelled) setView(v);
      } catch (err: any) {
        if (!cancelled) setError(err?.message ?? "Couldn't load learning view");
      }
      try {
        const res = await api.getProfile(studentId);
        if (!cancelled) setEntries(res.entries);
      } catch {
        // 403 is expected for educators — silently ignore.
      }
      if (auth.user.id === studentId) {
        if (!cancelled) {
          setMeta({ id: studentId, email: auth.user.email, name: emailToName(auth.user.email) });
        }
        return;
      }
      try {
        const classes = await api.listClasses();
        for (const cls of classes) {
          try {
            const roster = await api.roster(cls.id);
            const match = roster.find((r) => r.id === studentId);
            if (match) {
              if (!cancelled) {
                setMeta({ id: studentId, email: match.email, name: emailToName(match.email) });
              }
              return;
            }
          } catch {
            // ignore classes we can't read
          }
        }
      } catch {
        // swallow
      }
      if (!cancelled) {
        setMeta({ id: studentId, email: `#${studentId}`, name: `Student #${studentId}` });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, studentId]);

  if (signedIn === false) return null;

  const name = meta?.name ?? "Student";

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[{ label: "Dashboard", href: "/dashboard" }]}
        activeLink="Dashboard"
        onLogout={() => {
          clearAuth();
          router.replace("/login");
        }}
      />

      <main className="max-w-screen-xl mx-auto px-6 md:px-12 py-16 space-y-8">
        {/* Header */}
        <section className="bg-surface-container-lowest rounded-[32px] p-8 md:p-10 shadow-[0px_20px_40px_rgba(27,28,26,0.04)] border border-surface-dim/20 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-br from-primary-fixed/15 via-transparent to-secondary-container/10 pointer-events-none" />
          <div className="relative z-10">
            <div className="flex items-center gap-5 flex-wrap">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary to-primary-container flex items-center justify-center text-on-primary font-bold text-xl tracking-wider">
                {initials(name)}
              </div>
              <div className="flex-1 min-w-[220px]">
                <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-1">
                  Student
                </div>
                <h1 className="font-headline text-3xl text-primary font-medium tracking-[-0.025em]">
                  {name}
                </h1>
                {meta && (
                  <div className="font-body text-sm text-on-surface-variant mt-1">
                    {meta.email}
                  </div>
                )}
              </div>
            </div>
            {error && (
              <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm mt-6">
                {error}
              </p>
            )}
          </div>
        </section>

        {/* Learning Style Net */}
        {view ? (
          <LearningStyleNet view={view} />
        ) : (
          <div className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20 min-h-[320px] flex items-center justify-center">
            <p className="font-body text-on-surface-variant">Loading learning style…</p>
          </div>
        )}

        {/* Simulated neural activation (TRIBE v2 preview) */}
        {view ? (
          (() => {
            const latest = view.recent_focus?.[0];
            const topic =
              view.top_mastery?.[0]?.topic ||
              view.top_struggles?.[0]?.topic ||
              "Algebra";
            const focus = latest?.focus_score ?? view.learning_profile?.rolling_focus_score ?? 0.6;
            const acts = activationsForLesson(topic, focus);
            return (
              <BrainModel
                activations={acts}
                contextLabel={`Most recent lesson · ${topic}`}
                heading="How this student's brain engages"
              />
            );
          })()
        ) : null}

        {/* Focus Timeline */}
        <section className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20">
          <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
            Recent focus
          </div>
          {view ? (
            <FocusTimeline entries={view.recent_focus} />
          ) : (
            <p className="font-body text-on-surface-variant">Loading…</p>
          )}
        </section>

        {/* Narrative Timeline */}
        <section className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20">
          <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-4">
            Narrative timeline
          </div>
          {entries.length === 0 && (view?.narrative_notes?.length ?? 0) === 0 ? (
            <p className="font-body text-on-surface-variant">
              No notes yet. They'll appear here as the student completes lessons and quizzes.
            </p>
          ) : (
            <div className="space-y-4">
              {(view?.narrative_notes ?? [])
                .slice(-3)
                .reverse()
                .map((n, i) => (
                  <article
                    key={`n-${i}`}
                    className="border-l-[3px] border-primary-container pl-4 text-sm text-on-surface"
                  >
                    <div className="font-body text-xs text-outline mb-1">
                      {new Date(n.ts).toLocaleString()} · AI summary
                    </div>
                    {n.note}
                  </article>
                ))}
              {entries.slice(0, 4).map((entry) => (
                <article
                  key={entry.id}
                  className="border-l-[3px] border-primary pl-4 text-sm text-on-surface"
                >
                  <div className="font-body text-xs text-outline mb-1">
                    {new Date(entry.created_at).toLocaleString()} · profile entry
                    {entry.quiz_score !== null && entry.quiz_score !== undefined && (
                      <span> · quiz {(entry.quiz_score * 10).toFixed(1)}/10</span>
                    )}
                  </div>
                  {entry.profile_text}
                </article>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
