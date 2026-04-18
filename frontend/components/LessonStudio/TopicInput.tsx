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
    <form className="stack" onSubmit={handle} style={{ gap: 10 }}>
      <label className="field">
        <span>Topic</span>
        <input
          className="input"
          placeholder="e.g. Pythagorean theorem"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          disabled={busy}
          required
        />
      </label>
      <label className="field">
        <span>What should this lesson do?</span>
        <textarea
          className="textarea"
          placeholder="one or two sentences about the goal or angle"
          value={description}
          onChange={e => setDescription(e.target.value)}
          disabled={busy}
          rows={3}
        />
      </label>
      <button className="button" type="submit" disabled={busy}>
        {busy ? "Generating..." : "Generate candidate assets"}
      </button>
    </form>
  );
}
