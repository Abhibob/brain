"use client";

import { FormEvent, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, MaterialOut } from "@/lib/api";

export default function MaterialEditPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const materialId = Number(params.id);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [material, setMaterial] = useState<MaterialOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getMaterial(materialId)
      .then(response => {
        setMaterial(response);
        setTitle(response.title);
        setContent(response.sections.map(section => `${section.title}\n${section.content}`).join("\n\n---\n\n"));
      })
      .catch((err: Error) => setError(err.message));
  }, [materialId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const sections = content.split(/\n---\n/g).map((block, index) => {
        const [firstLine, ...rest] = block.trim().split("\n");
        return {
          title: firstLine || `Section ${index + 1}`,
          content: rest.join("\n").trim() || firstLine || "",
          order_index: index
        };
      });
      const updated = await api.updateMaterial(materialId, {
        title,
        type: material?.type === "quiz" ? "quiz" : "lesson",
        sections
      });
      router.push(`/classes/${updated.class_id}/materials/${updated.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save material");
    }
  }

  return (
    <main className="main">
      <form className="card stack" onSubmit={submit}>
        <h1>Lesson editor</h1>
        <p className="muted">Separate sections with a line containing only three hyphens.</p>
        <label className="field">
          <span>Title</span>
          <input className="input" value={title} onChange={event => setTitle(event.target.value)} required />
        </label>
        <label className="field">
          <span>Lesson content</span>
          <textarea className="textarea" value={content} onChange={event => setContent(event.target.value)} required />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button className="button" type="submit">
          Save lesson
        </button>
      </form>
    </main>
  );
}
