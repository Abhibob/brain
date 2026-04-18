"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getStoredAuth } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getStoredAuth() ? "/dashboard" : "/login");
  }, [router]);

  return <main className="main">Loading EduTrack...</main>;
}

