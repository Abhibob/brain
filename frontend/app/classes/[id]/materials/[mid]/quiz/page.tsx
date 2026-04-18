"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { QuizEngine } from "@/components/QuizEngine/QuizEngine";

export default function QuizPage() {
  const params = useParams<{ id: string; mid: string }>();
  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href={`/classes/${params.id}/materials/${params.mid}`}>
          Back to lesson
        </Link>
      </header>
      <main className="main stack">
        <h1>Quiz</h1>
        <QuizEngine materialId={Number(params.mid)} />
      </main>
    </div>
  );
}

