"use client";

import Link from "next/link";

interface NavLink {
  label: string;
  href: string;
}

interface TopBarProps {
  navLinks?: NavLink[];
  activeLink?: string;
  onLogout: () => void;
}

export default function TopBar({ navLinks, activeLink, onLogout }: TopBarProps) {
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

        {/* Logout — right */}
        <div className="flex items-center gap-6 justify-self-end">
          <button
            onClick={onLogout}
            className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center text-on-surface hover:bg-surface-dim transition-colors shadow-[inset_0px_2px_4px_rgba(27,28,26,0.06)]"
          >
            <span className="material-symbols-outlined text-[20px]">logout</span>
          </button>
        </div>
      </div>
    </header>
  );
}
