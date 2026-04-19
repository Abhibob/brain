"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, storeAuth } from "@/lib/api";
import MaterialIcon from "@/components/ui/MaterialIcon";

type Role = "student" | "educator" | "researcher";

const ROLES: Array<{
  role: Role;
  title: string;
  icon: string;
  summary: string;
}> = [
  {
    role: "student",
    title: "Student",
    icon: "school",
    summary: "Access coursework, view grades, and engage with learning materials.",
  },
  {
    role: "educator",
    title: "Educator",
    icon: "history_edu",
    summary: "Manage curriculum, evaluate assignments, and monitor student progress.",
  },
  {
    role: "researcher",
    title: "Researcher",
    icon: "biotech",
    summary: "Explore academic archives, analyze data, and publish findings.",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [busy, setBusy] = useState<Role | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function pick(role: Role) {
    setBusy(role);
    setError(null);
    try {
      const auth = await api.demoLogin(role);
      storeAuth(auth);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(null);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-background">
      {/* Grid pattern background */}
      <div className="absolute inset-0 bg-grid-pattern pointer-events-none z-0" />
      <div className="absolute inset-0 bg-gradient-to-br from-surface via-surface-container-low to-surface-container-high opacity-80 pointer-events-none z-0" />

      <div className="relative z-10 w-full max-w-7xl mx-auto px-6 py-12 md:py-24 flex flex-col lg:flex-row items-center gap-16 lg:gap-24">
        {/* Left Half */}
        <div className="w-full lg:w-1/2 flex flex-col gap-10">
          <div className="space-y-4">
            {/* Brand */}
            <div className="inline-flex items-center gap-2 mb-2">
              <MaterialIcon name="local_library" filled className="text-primary text-2xl" />
              <span className="font-headline font-bold text-xl text-primary tracking-tight">
                EduTrack
              </span>
            </div>

            {/* Headline */}
            <h1 className="font-headline text-5xl md:text-6xl text-on-background leading-tight tracking-[-0.02em]">
              Select your <br />
              <span className="italic text-primary">academic persona.</span>
            </h1>

            {/* Subtitle */}
            <p className="font-body text-lg text-on-surface-variant max-w-md leading-relaxed mt-4">
              Welcome to the scholarly portal. Please choose your primary role to curate your
              personalized academic environment.
            </p>

            {/* Error */}
            {error && (
              <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
                {error}
              </p>
            )}
          </div>

          {/* Role Cards */}
          <div className="flex flex-col gap-6">
            {ROLES.map((option) => (
              <button
                key={option.role}
                onClick={() => pick(option.role)}
                disabled={busy !== null}
                className="group relative bg-surface-container-lowest p-6 rounded-3xl shadow-[0_20px_40px_rgba(27,28,26,0.06)] flex items-center justify-between text-left transition-transform duration-300 hover:scale-[1.02] disabled:opacity-50 disabled:cursor-wait"
                style={{
                  opacity: busy && busy !== option.role ? 0.4 : 1,
                }}
              >
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-3xl" />

                <div className="relative z-10 flex items-start gap-6">
                  {/* Icon */}
                  <div className="bg-surface-container-low p-4 rounded-full flex-shrink-0 group-hover:bg-primary-container transition-colors duration-300">
                    <MaterialIcon
                      name={option.icon}
                      filled
                      className="text-primary group-hover:text-on-primary-container text-3xl transition-colors duration-300"
                    />
                  </div>

                  {/* Text */}
                  <div>
                    <h3 className="font-headline text-2xl text-on-background mb-1">
                      {option.title}
                    </h3>
                    <p className="font-body text-sm text-on-surface-variant leading-snug">
                      {option.summary}
                    </p>
                  </div>
                </div>

                {/* Arrow */}
                <span className="material-symbols-outlined text-primary opacity-0 group-hover:opacity-100 transform translate-x-[-10px] group-hover:translate-x-0 transition-all duration-300 relative z-10">
                  {busy === option.role ? "progress_activity" : "arrow_forward"}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Right Half - Book Image */}
        <div className="w-full lg:w-1/2 justify-center lg:justify-end relative hidden md:flex">
          <div className="relative w-full max-w-lg aspect-square shadow-2xl rounded-[32px] overflow-hidden bg-surface-container-lowest border border-surface-dim">
            <img
              alt="3D Book illustration"
              className="w-full h-full object-cover opacity-90 mix-blend-multiply"
              src="/images/book-3d-green.png"
            />
            <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-transparent mix-blend-overlay" />
          </div>

          {/* Decorative blur blobs */}
          <div className="absolute -bottom-10 -right-10 w-64 h-64 bg-primary-fixed-dim rounded-full mix-blend-multiply blur-3xl opacity-30" />
          <div className="absolute -top-10 -left-10 w-48 h-48 bg-secondary-fixed-dim rounded-full mix-blend-multiply blur-3xl opacity-40" />
        </div>
      </div>
    </div>
  );
}
