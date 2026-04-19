"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  api,
  ClassAnalytics,
  clearAuth,
  getStoredAuth,
  MechanisticView,
  PersonalizationAudit,
  ResearchWorkbench,
  TribePredictionPayload,
} from "@/lib/api";
import { CohortOverview } from "@/components/ResearchWorkbench/CohortOverview";
import { NeuralMicroscope } from "@/components/ResearchWorkbench/NeuralMicroscope";
import { PersonalizationAuditPanel } from "@/components/ResearchWorkbench/PersonalizationAuditPanel";
import { StudentSignalPanel } from "@/components/ResearchWorkbench/StudentSignalPanel";
import { TribeNeuroView } from "@/components/ResearchWorkbench/TribeNeuroView";
import TopBar from "@/components/ui/TopBar";

export default function ResearchWorkbenchPage() {
  const params = useParams<{ id: string }>();
  const classId = Number(params.id);
  const router = useRouter();
  const [workbench, setWorkbench] = useState<ResearchWorkbench | null>(null);
  const [analytics, setAnalytics] = useState<ClassAnalytics | null>(null);
  const [mechanistic, setMechanistic] = useState<MechanisticView | null>(null);
  const [audit, setAudit] = useState<PersonalizationAudit | null>(null);
  const [tribe, setTribe] = useState<TribePredictionPayload | null>(null);
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null);
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const auth = getStoredAuth();
    if (!auth) { router.replace("/login"); return; }
    if (auth.user.role !== "researcher") { router.replace("/dashboard"); return; }
    let cancelled = false;
    (async () => {
      try {
        const [wb, an] = await Promise.all([api.getResearchWorkbench(classId), api.getClassAnalytics(classId)]);
        if (cancelled) return;
        setWorkbench(wb); setAnalytics(an);
        setSelectedStudentId(wb.students[0]?.id ?? null);
        setSelectedMaterialId(wb.materials.find((m) => m.type === "lesson")?.id ?? wb.materials[0]?.id ?? null);
      } catch (err: any) { if (!cancelled) setError(err?.message ?? "Could not load research workbench"); }
    })();
    return () => { cancelled = true; };
  }, [classId, router]);

  const selectedStudent = useMemo(() => workbench?.students.find((s) => s.id === selectedStudentId) || null, [selectedStudentId, workbench]);
  const selectedMaterial = useMemo(() => workbench?.materials.find((m) => m.id === selectedMaterialId) || null, [selectedMaterialId, workbench]);

  async function loadStudentMaterial(studentId: number | null, materialId: number | null) {
    if (!studentId) return;
    setLoading(true); setError(null);
    try {
      const [mech, auditResult, tribeResult] = await Promise.all([
        api.getMechanisticView(studentId, classId),
        materialId ? api.getPersonalizationAudit(materialId, studentId) : Promise.resolve(null),
        materialId ? api.getTribePrediction(materialId, studentId) : Promise.resolve(null),
      ]);
      setMechanistic(mech); setAudit(auditResult); setTribe(tribeResult);
    } catch (err: any) { setError(err?.message ?? "Could not load research detail"); }
    finally { setLoading(false); }
  }

  useEffect(() => { loadStudentMaterial(selectedStudentId, selectedMaterialId); }, [selectedStudentId, selectedMaterialId]);

  async function retrain() {
    if (!selectedStudentId) return;
    setLoading(true); setError(null);
    try {
      await api.trainResearchSurrogate(selectedStudentId, classId);
      setMechanistic(await api.getMechanisticView(selectedStudentId, classId));
      setWorkbench(await api.getResearchWorkbench(classId));
    } catch (err: any) { setError(err?.message ?? "Could not retrain surrogate"); }
    finally { setLoading(false); }
  }

  async function runTribe() {
    if (!selectedStudentId || !selectedMaterialId) return;
    setLoading(true); setError(null);
    try {
      setTribe(await api.runTribePrediction(selectedMaterialId, selectedStudentId));
      setWorkbench(await api.getResearchWorkbench(classId));
    } catch (err: any) { setError(err?.message ?? "Could not run TRIBE v2"); }
    finally { setLoading(false); }
  }

  if (!workbench) {
    return (
      <main className="max-w-4xl mx-auto px-6 py-16">
        <p className="font-body text-on-surface-variant">{error || "Loading research workbench..."}</p>
      </main>
    );
  }

  return (
    <div className="min-h-screen research-shell">
      <TopBar
        navLinks={[
          { label: "Class", href: `/classes/${classId}` },
          { label: "Dashboard", href: "/dashboard" },
        ]}
        activeLink="Class"
        onLogout={() => { clearAuth(); router.replace("/login"); }}
      />

      <main className="research-main">
        <section className="research-hero">
          <div>
            <div className="research-kicker">Research Workbench</div>
            <h1>{workbench.class.title}</h1>
            <p>
              Mechanistic inspection for the adaptive layer: personalized neural surrogate, content
              audit, and TRIBE v2 neuro-response predictions.
            </p>
          </div>
          <div className="research-context">
            <span>{selectedStudent?.email || "No student selected"}</span>
            <span>{selectedMaterial?.title || "No material selected"}</span>
            <span>{loading ? "Loading" : "Ready"}</span>
          </div>
          <div className="research-hero__instrument" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
        </section>

        {error && (
          <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
            {error}
          </p>
        )}

        <StudentSignalPanel
          workbench={workbench}
          analytics={analytics}
          selectedStudentId={selectedStudentId}
          selectedMaterialId={selectedMaterialId}
          mechanistic={mechanistic}
          audit={audit}
          tribe={tribe}
          loading={loading}
          onSelectStudent={setSelectedStudentId}
          onSelectMaterial={setSelectedMaterialId}
        />

        <CohortOverview
          workbench={workbench}
          analytics={analytics}
          selectedStudentId={selectedStudentId}
          selectedMaterialId={selectedMaterialId}
          onSelectStudent={setSelectedStudentId}
          onSelectMaterial={setSelectedMaterialId}
        />

        <NeuralMicroscope view={mechanistic} loading={loading} onRetrain={retrain} />

        <PersonalizationAuditPanel audit={audit} />

        <TribeNeuroView tribe={tribe} loading={loading} onRun={runTribe} />
      </main>
    </div>
  );
}
