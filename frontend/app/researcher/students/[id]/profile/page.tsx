"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

export default function LegacyResearcherProfileRedirect() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  useEffect(() => {
    router.replace(`/students/${params.id}`);
  }, [params.id, router]);
  return <main className="main">Redirecting…</main>;
}
