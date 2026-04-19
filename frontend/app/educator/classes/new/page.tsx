"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearAuth } from "@/lib/api";
import TopBar from "@/components/ui/TopBar";
import MaterialIcon from "@/components/ui/MaterialIcon";

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
    <div className="min-h-screen bg-background">
      <TopBar
        navLinks={[
          { label: "Library", href: "/dashboard" },
          { label: "Curriculum", href: "/dashboard" },
          { label: "Grades", href: "/dashboard" },
        ]}
        activeLink="Curriculum"
        onLogout={() => { clearAuth(); router.push("/login"); }}
      />

      <main className="max-w-2xl mx-auto px-6 py-16 lg:py-24">
        <div className="bg-surface-container-lowest rounded-[32px] p-8 md:p-10 shadow-[0_20px_40px_rgba(27,28,26,0.06)]">
          <h1 className="font-headline text-4xl text-primary tracking-[-0.02em] mb-2">
            Create class
          </h1>
          <p className="font-body text-on-surface-variant mb-8">
            Set up a new class to begin building adaptive lessons.
          </p>

          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-2">
              <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                Title
              </label>
              <input
                className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div className="space-y-2">
              <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                Description
              </label>
              <textarea
                className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors min-h-[140px] resize-y"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            {error && (
              <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
                {error}
              </p>
            )}

            <button
              type="submit"
              className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2"
            >
              Save class
              <MaterialIcon name="arrow_forward" className="text-[18px]" />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
