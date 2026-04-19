"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { QuizEngine } from "@/components/QuizEngine/QuizEngine";
import { clearAuth } from "@/lib/api";
import TopBar from "@/components/ui/TopBar";

export default function QuizPage() {
  const params = useParams<{ id: string; mid: string }>();
  const router = useRouter();

  return (
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[{ label: "Back to lesson", href: `/classes/${params.id}/materials/${params.mid}` }]}
        activeLink="Back to lesson"
        onLogout={() => { clearAuth(); router.push("/login"); }}
      />
      <main className="max-w-3xl mx-auto px-6 py-16 space-y-8">
        <h1 className="font-headline text-4xl text-primary tracking-tight font-medium">Quiz</h1>
        <QuizEngine materialId={Number(params.mid)} />
      </main>
    </div>
  );
}
