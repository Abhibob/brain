"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getStoredAuth() ? "/dashboard" : "/login");
  }, [router]);

  return (
    <main className="min-h-screen bg-background flex items-center justify-center">
      <p className="font-body text-on-surface-variant">Loading EduTrack...</p>
    </main>
  );
}

