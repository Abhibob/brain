"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getStoredAuth } from "@/lib/api";

interface NavLink {
  label: string;
  href: string;
}

interface TopBarProps {
  navLinks?: NavLink[];
  activeLink?: string;
  onLogout: () => void;
}

type Role = "student" | "educator" | "researcher";

const ROLE_LABEL: Record<Role, string> = {
  student: "Student",
  educator: "Teacher",
  researcher: "Researcher"
};

const ROLE_TONE: Record<Role, string> = {
  student: "bg-primary-fixed text-on-primary-fixed",
  educator: "bg-secondary-container text-on-secondary-container",
  researcher: "bg-tertiary-fixed text-on-tertiary-fixed"
};

function initials(email: string): string {
  const local = email.split("@")[0] || email;
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((p) => p[0].toUpperCase())
    .join("")
    .slice(0, 2);
}

export default function TopBar({ navLinks, activeLink, onLogout }: TopBarProps) {
  const [auth, setAuth] = useState<{ role: Role; email: string } | null>(null);

  useEffect(() => {
    const stored = getStoredAuth();
    if (stored) setAuth({ role: stored.user.role as Role, email: stored.user.email });
  }, []);

  return (
    <header className="bg-[#fbf9f5]/80 backdrop-blur-xl sticky top-0 w-full z-50 transition-colors duration-300">
      <div className="grid grid-cols-[1fr_auto_1fr] items-center w-full px-6 md:px-12 h-20 max-w-screen-2xl mx-auto border-b border-surface-dim">
        {/* Brand — left */}
        <Link href="/dashboard" className="flex items-center gap-4 justify-self-start">
          <span className="text-2xl font-headline italic font-bold text-primary tracking-tight">
            EduTrack
          </span>
        </Link>

        {/* Navigation Links — center */}
        {navLinks && navLinks.length > 0 ? (
          <nav className="hidden md:flex gap-8 items-center h-full">
            {navLinks.map((link) => (
              <Link
                key={link.label}
                href={link.href}
                className={
                  activeLink === link.label
                    ? "h-full flex items-center px-2 text-primary border-b-[3px] border-primary font-bold font-body text-sm tracking-wide pt-[3px]"
                    : "h-full flex items-center px-2 text-outline font-medium font-body text-sm tracking-wide hover:text-primary transition-all duration-300"
                }
              >
                {link.label}
              </Link>
            ))}
          </nav>
        ) : (
          <div />
        )}

        {/* Role + logout — right */}
        <div className="flex items-center gap-3 justify-self-end">
          {auth && (
            <div
              className={`flex items-center gap-2 rounded-full pl-1.5 pr-3 py-1 ${ROLE_TONE[auth.role]}`}
              title={auth.email}
            >
              <span className="w-7 h-7 rounded-full bg-white/70 flex items-center justify-center font-bold text-[11px] text-primary">
                {initials(auth.email)}
              </span>
              <span className="font-body text-xs font-semibold tracking-wide">
                {ROLE_LABEL[auth.role]}
              </span>
            </div>
          )}
          <button
            onClick={onLogout}
            className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-on-surface hover:bg-surface-dim transition-colors shadow-[inset_0px_2px_4px_rgba(27,28,26,0.06)]"
            aria-label="Sign out"
          >
            <span className="material-symbols-outlined text-[20px]">logout</span>
          </button>
        </div>
      </div>
    </header>
  );
}
