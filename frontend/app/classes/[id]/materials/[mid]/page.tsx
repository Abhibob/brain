"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { LessonViewer } from "@/components/LessonViewer/LessonViewer";
import { api, clearAuth, MaterialOut } from "@/lib/api";
import TopBar from "@/components/ui/TopBar";

export default function MaterialPage() {
  const params = useParams<{ id: string; mid: string }>();
  const router = useRouter();
  const [material, setMaterial] = useState<MaterialOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getMaterial(Number(params.mid)).then(setMaterial).catch((e) => setError(e.message));
  }, [params.mid]);

  if (error)
    return (
      <main className="max-w-4xl mx-auto px-6 py-16">
        <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
          {error}
        </p>
      </main>
    );
  if (!material)
    return (
      <main className="max-w-4xl mx-auto px-6 py-16">
        <p className="font-body text-on-surface-variant">Loading lesson...</p>
      </main>
    );

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[{ label: "Back to class", href: `/classes/${params.id}` }]}
        activeLink="Back to class"
        onLogout={() => { clearAuth(); router.push("/login"); }}
      />
      <main className="max-w-4xl mx-auto px-6 py-16">
        <LessonViewer material={material} />
      </main>
    </div>
  );
}
