"use client";

import { ProfileEntry } from "@/lib/api";

export function StudentProfileCard({ entry }: { entry: ProfileEntry }) {
  return (
    <article className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20">
      <p className="font-body text-sm text-on-surface-variant">
        {new Date(entry.created_at).toLocaleString()}
      </p>
      <p className="font-body text-on-surface mt-2">{entry.profile_text}</p>
    </article>
  );
}
