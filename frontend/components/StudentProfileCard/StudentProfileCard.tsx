"use client";

import { ProfileEntry } from "@/lib/api";

export function StudentProfileCard({ entry }: { entry: ProfileEntry }) {
  return (
    <article className="card">
      <p className="muted">{new Date(entry.created_at).toLocaleString()}</p>
      <p>{entry.profile_text}</p>
    </article>
  );
}

