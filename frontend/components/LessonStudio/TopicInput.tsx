"use client";

import { FormEvent, useState } from "react";

type Props = {
  onSubmit: (payload: { topic: string; description: string }) => Promise<void> | void;
  busy?: boolean;
};

export function TopicInput({ onSubmit, busy }: Props) {
  const [topic, setTopic] = useState("");
  const [description, setDescription] = useState("");

  async function handle(event: FormEvent) {
    event.preventDefault();
    if (!topic.trim()) return;
    await onSubmit({ topic: topic.trim(), description: description.trim() });
  }

  return (
    <form className="space-y-4" onSubmit={handle}>
      <div className="space-y-2">
        <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
          Topic
        </label>
        <input
          className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
          placeholder="e.g. Pythagorean theorem"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          disabled={busy}
          required
        />
      </div>
      <div className="space-y-2">
        <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
          What should this lesson do?
        </label>
        <textarea
          className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors min-h-[80px] resize-y"
          placeholder="one or two sentences about the goal or angle"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={busy}
          rows={3}
        />
      </div>
      <button
        className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-6 py-3 rounded-full transition-all duration-300 text-sm shadow-[0px_10px_20px_rgba(0,45,40,0.15)]"
        type="submit"
        disabled={busy}
      >
        {busy ? "Generating..." : "Generate candidate assets"}
      </button>
    </form>
  );
}
