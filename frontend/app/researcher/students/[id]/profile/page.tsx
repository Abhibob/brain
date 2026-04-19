"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function LegacyResearcherProfileRedirect() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/students/${params.id}`);
  }, [params.id, router]);
  return <main className="min-h-screen bg-background flex items-center justify-center"><p className="font-body text-on-surface-variant">Redirecting…</p></main>;
}
