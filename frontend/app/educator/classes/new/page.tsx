"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function NewClassPage() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const classOut = await api.createClass({ title, description });
      router.push(`/classes/${classOut.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create class");
    }
  }

  return (
    <main className="main">
      <form className="card stack" onSubmit={submit}>
        <h1>Create class</h1>
        <label className="field">
          <span>Title</span>
          <input className="input" value={title} onChange={event => setTitle(event.target.value)} required />
        </label>
        <label className="field">
          <span>Description</span>
          <textarea className="textarea" value={description} onChange={event => setDescription(event.target.value)} />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button className="button" type="submit">
          Save class
        </button>
      </form>
    </main>
  );
}

