"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { StudentProfileCard } from "@/components/StudentProfileCard/StudentProfileCard";
import { api, ProfileEntry } from "@/lib/api";

export default function ResearcherStudentProfilePage() {
  const params = useParams<{ id: string }>();
  const [entries, setEntries] = useState<ProfileEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getProfile(Number(params.id))
      .then(response => setEntries(response.entries))
      .catch((error: Error) => setError(error.message));
  }, [params.id]);

  return (
    <main className="main stack">
      <h1>Research profile entries</h1>
      <p className="muted">Append-only observations generated after quiz sessions.</p>
      {error ? <p className="error">{error}</p> : null}
      {entries.map(entry => (
        <StudentProfileCard entry={entry} key={entry.id} />
      ))}
      {!entries.length && !error ? <p>No profile entries yet.</p> : null}
    </main>
  );
}
