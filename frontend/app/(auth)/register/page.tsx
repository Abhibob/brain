"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, storeAuth } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [role, setRole] = useState<"student" | "educator" | "researcher">("student");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [institution, setInstitution] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const auth = await api.register({ email, password, role, institution: institution || undefined });
      storeAuth(auth);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    }
  }

  return (
    <div className="shell">
      <main className="main">
        <div className="band">
          <form className="card stack" onSubmit={submit}>
            <h1>Create account</h1>
            <label className="field">
              <span>Role</span>
              <select className="select" value={role} onChange={event => setRole(event.target.value as "student" | "educator" | "researcher")}>
                <option value="student">Student</option>
                <option value="educator">Educator</option>
                <option value="researcher">Researcher</option>
              </select>
            </label>
            <label className="field">
              <span>Email</span>
              <input className="input" value={email} onChange={event => setEmail(event.target.value)} type="email" required />
            </label>
            <label className="field">
              <span>Password</span>
              <input className="input" value={password} onChange={event => setPassword(event.target.value)} type="password" required minLength={8} />
            </label>
            {role === "educator" ? (
              <label className="field">
                <span>Institution</span>
                <input className="input" value={institution} onChange={event => setInstitution(event.target.value)} />
              </label>
            ) : null}
            {error ? <p className="error">{error}</p> : null}
            <button className="button" type="submit">
              Register
            </button>
            <Link href="/login">I already have an account</Link>
          </form>
          <img className="banner-image" alt="Classroom lesson" src="https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=1200&q=80" />
        </div>
      </main>
    </div>
  );
}
