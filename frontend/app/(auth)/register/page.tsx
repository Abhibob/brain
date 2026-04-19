"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, storeAuth } from "@/lib/api";
import MaterialIcon from "@/components/ui/MaterialIcon";

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
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background">
      {/* Grid pattern background */}
      <div className="absolute inset-0 bg-grid-pattern pointer-events-none z-0" />
      <div className="absolute inset-0 bg-gradient-to-br from-surface via-surface-container-low to-surface-container-high opacity-80 pointer-events-none z-0" />

      <div className="relative z-10 w-full max-w-xl mx-auto px-6 py-12 md:py-24">
        {/* Brand */}
        <div className="inline-flex items-center gap-2 mb-8">
          <MaterialIcon name="local_library" filled className="text-primary text-2xl" />
          <span className="font-headline font-bold text-xl text-primary tracking-tight">
            EduTrack
          </span>
        </div>

        <div className="bg-surface-container-lowest rounded-[32px] p-8 md:p-10 shadow-[0_20px_40px_rgba(27,28,26,0.06)]">
          <h1 className="font-headline text-4xl text-primary tracking-[-0.02em] mb-2">
            Create account
          </h1>
          <p className="font-body text-on-surface-variant mb-8">
            Join the scholarly community to begin your academic journey.
          </p>

          <form onSubmit={submit} className="space-y-5">
            <div className="space-y-2">
              <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                Role
              </label>
              <select
                className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors appearance-none"
                value={role}
                onChange={(e) => setRole(e.target.value as "student" | "educator" | "researcher")}
              >
                <option value="student">Student</option>
                <option value="educator">Educator</option>
                <option value="researcher">Researcher</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                Email
              </label>
              <input
                className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                required
              />
            </div>

            <div className="space-y-2">
              <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                Password
              </label>
              <input
                className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                type="password"
                required
                minLength={8}
              />
            </div>

            {role === "educator" && (
              <div className="space-y-2">
                <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                  Institution
                </label>
                <input
                  className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                  value={institution}
                  onChange={(e) => setInstitution(e.target.value)}
                />
              </div>
            )}

            {error && (
              <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
                {error}
              </p>
            )}

            <button
              type="submit"
              className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2"
            >
              Register
              <MaterialIcon name="arrow_forward" className="text-[18px]" />
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-surface-dim/40">
            <Link
              href="/login"
              className="text-sm font-body text-primary font-medium flex items-center gap-2 hover:text-primary-container transition-colors"
            >
              I already have an account
              <MaterialIcon name="arrow_forward" className="text-[16px]" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
