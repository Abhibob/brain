"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { LessonViewer } from "@/components/LessonViewer/LessonViewer";
import { api, MaterialOut } from "@/lib/api";

export default function MaterialPage() {
  const params = useParams<{ id: string; mid: string }>();
  const [material, setMaterial] = useState<MaterialOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getMaterial(Number(params.mid)).then(setMaterial).catch(error => setError(error.message));
  }, [params.mid]);

  if (error) return <main className="main error">{error}</main>;
  if (!material) return <main className="main">Loading lesson...</main>;

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href={`/classes/${params.id}`}>
          {material.title}
        </Link>
      </header>
      <main className="main">
        <LessonViewer material={material} />
      </main>
    </div>
  );
}

