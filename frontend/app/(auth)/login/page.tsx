"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, storeAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const auth = await api.login({ email, password });
      storeAuth(auth);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  }

  return (
    <div className="shell">
      <main className="main">
        <div className="band">
          <form className="card stack" onSubmit={submit}>
            <h1>Sign in</h1>
            <label className="field">
              <span>Email</span>
              <input className="input" value={email} onChange={event => setEmail(event.target.value)} type="email" required />
            </label>
            <label className="field">
              <span>Password</span>
              <input className="input" value={password} onChange={event => setPassword(event.target.value)} type="password" required />
            </label>
            {error ? <p className="error">{error}</p> : null}
            <button className="button" type="submit">
              Sign in
            </button>
            <Link href="/register">Create an account</Link>
          </form>
          <img className="banner-image" alt="Students working together" src="https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80" />
        </div>
      </main>
    </div>
  );
}

