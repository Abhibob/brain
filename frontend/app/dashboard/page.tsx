"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, AuthState, ClassOut, clearAuth, getStoredAuth } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [classes, setClasses] = useState<ClassOut[]>([]);
  const [classId, setClassId] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [auth, setAuth] = useState<AuthState | null>(null);

  useEffect(() => {
    const stored = getStoredAuth();
    if (!stored) {
      router.replace("/login");
      return;
    }
    setAuth(stored);
    api.listClasses().then(setClasses).catch(err => setError(err.message));
  }, [router]);

  async function enroll(event: FormEvent) {
    event.preventDefault();
    setError(null);
    await api.enroll(Number(classId), code);
    setClasses(await api.listClasses());
    setClassId("");
    setCode("");
  }

  if (!auth) return null;

  return (
    <div className="shell">
      <header className="topbar">
        <Link className="brand" href="/dashboard">
          EduTrack
        </Link>
        <nav className="nav">
          <span>{auth.user.email}</span>
          <button
            className="button secondary"
            onClick={() => {
              clearAuth();
              router.push("/login");
            }}
          >
            Sign out
          </button>
        </nav>
      </header>
      <main className="main stack">
        <div className="band">
          <div>
            <h1>{auth.user.role === "educator" ? "Educator dashboard" : auth.user.role === "researcher" ? "Research dashboard" : "Student dashboard"}</h1>
            <p className="muted">
              {auth.user.role === "researcher" ? "Review learning system telemetry and model behavior." : "Classes, lessons, and quizzes are managed from here."}
            </p>
          </div>
          <img className="banner-image" alt="Open books and notes" src="https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=1200&q=80" />
        </div>

        {auth.user.role === "educator" ? (
          <Link className="button" href="/educator/classes/new">
            Create class
          </Link>
        ) : auth.user.role === "student" ? (
          <form className="card stack" onSubmit={enroll}>
            <h2>Join a class</h2>
            <label className="field">
              <span>Class ID</span>
              <input className="input" value={classId} onChange={event => setClassId(event.target.value)} required />
            </label>
            <label className="field">
              <span>Enrollment code</span>
              <input className="input" value={code} onChange={event => setCode(event.target.value)} required />
            </label>
            <button className="button" type="submit">
              Enroll
            </button>
          </form>
        ) : (
          <p className="muted">Open a class to inspect research-only analytics.</p>
        )}

        {error ? <p className="error">{error}</p> : null}
        <section className="grid">
          {classes.map(item => (
            <Link className="card" href={`/classes/${item.id}`} key={item.id}>
              <h2>{item.title}</h2>
              <p>{item.description || "No description"}</p>
              {auth.user.role === "educator" ? <p className="muted">Code: {item.enrollment_code}</p> : null}
            </Link>
          ))}
        </section>
      </main>
    </div>
  );
}
