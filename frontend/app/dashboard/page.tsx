"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, AuthState, ClassOut, clearAuth, getStoredAuth } from "@/lib/api";
import TopBar from "@/components/ui/TopBar";
import MaterialIcon from "@/components/ui/MaterialIcon";

const EDUCATOR_NAV = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Lesson Studio", href: "/educator/lesson-studio" },
];

const STUDENT_NAV = [
  { label: "Dashboard", href: "/dashboard" },
];

const RESEARCHER_NAV = [
  { label: "Dashboard", href: "/dashboard" },
];

const CLASS_ICONS = ["science", "history_edu", "calculate", "psychology", "code", "menu_book"];
const CLASS_COLORS = [
  "bg-secondary-container text-on-secondary-container",
  "bg-tertiary-fixed-dim text-on-tertiary-fixed-variant",
  "bg-secondary-fixed text-on-secondary-fixed",
  "bg-primary-fixed text-on-primary-fixed",
];

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
    api.listClasses().then(setClasses).catch((err) => {
      if (err.message === "Not authenticated" || err.message === "Could not validate credentials") {
        clearAuth();
        router.replace("/login");
      } else {
        setError(err.message);
      }
    });
  }, [router]);

  async function enroll(event: FormEvent) {
    event.preventDefault();
    setError(null);
    await api.enroll(Number(classId), code);
    setClasses(await api.listClasses());
    setClassId("");
    setCode("");
  }

  function handleLogout() {
    clearAuth();
    router.push("/login");
  }

  if (!auth) return (
    <div className="min-h-screen bg-background flex items-center justify-center">
      <p className="font-body text-on-surface-variant">Loading…</p>
    </div>
  );

  const role = auth.user.role;

  return (
    <div className="min-h-screen bg-background relative">
      {/* Ambient Background Depth */}
      <div className="fixed inset-0 z-[-1] pointer-events-none">
        <div className="absolute top-[-10%] right-[-5%] w-[60%] h-[60%] rounded-full bg-gradient-to-br from-secondary-fixed/30 to-transparent blur-3xl opacity-50 mix-blend-multiply" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[50%] h-[50%] rounded-full bg-gradient-to-tr from-surface-dim to-transparent blur-3xl opacity-40 mix-blend-multiply" />
      </div>

      {/* TopBar */}
      <TopBar
        navLinks={role === "educator" ? EDUCATOR_NAV : role === "researcher" ? RESEARCHER_NAV : STUDENT_NAV}
        activeLink="Dashboard"
        onLogout={handleLogout}
      />

      {/* Main Canvas */}
      <main className="max-w-screen-2xl mx-auto px-6 md:px-12 py-16 lg:py-24 space-y-24">
        {error && (
          <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
            {error}
          </p>
        )}

        {/* ===== EDUCATOR VIEW ===== */}
        {role === "educator" && (
          <>
            {/* Hero Bento Grid */}
            <section className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-stretch relative z-10">
              {/* Hero Content - Left 8 cols */}
              <div className="lg:col-span-8 bg-surface-container-lowest rounded-[32px] p-10 md:p-16 relative overflow-hidden shadow-[0px_20px_40px_rgba(27,28,26,0.04)] border border-surface-dim/20 flex flex-col justify-center">
                {/* Internal gradient */}
                <div className="absolute inset-0 bg-gradient-to-br from-primary-fixed/10 via-transparent to-surface-dim/10 pointer-events-none" />
                {/* Hero image */}
                <img
                  alt="Stylized 3D Book and Brain"
                  className="absolute right-4 bottom-4 w-80 lg:w-[26rem] h-auto object-contain mix-blend-multiply pointer-events-none z-0 opacity-90"
                  src="/images/brain-book-hero.png"
                />
                <div className="relative z-10 max-w-xl">
                  <h1 className="font-headline text-5xl md:text-6xl text-primary font-medium tracking-[-0.03em] leading-[1.05] mb-6">
                    Design adaptive lessons.
                  </h1>
                  <p className="font-body text-lg md:text-xl text-on-surface-variant leading-relaxed mb-10 max-w-lg font-light">
                    Orchestrate personalized learning pathways. Your neural repository intelligently
                    adapts to cohort performance in real-time.
                  </p>
                  <div className="flex flex-wrap gap-4 items-center">
                    <Link
                      href="/educator/classes/new"
                      className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2 group"
                    >
                      Create class
                      <MaterialIcon
                        name="add"
                        className="text-[18px] group-hover:translate-x-1 transition-transform"
                      />
                    </Link>
                    <Link
                      href="/educator/lesson-studio"
                      className="bg-surface-container-high hover:bg-surface-dim text-on-surface font-body font-medium px-8 py-4 rounded-full transition-all duration-300 flex items-center gap-2 group"
                    >
                      Open lesson studio
                      <MaterialIcon
                        name="edit_note"
                        className="text-[18px] text-on-surface-variant group-hover:text-primary transition-colors"
                      />
                    </Link>
                  </div>
                </div>
              </div>

              {/* Right Column: Metrics & Insight */}
              <div className="lg:col-span-4 flex flex-col gap-8 h-full">
                {/* Metrics Row */}
                <div className="grid grid-cols-2 gap-8">
                  <div className="bg-surface-container-low rounded-[32px] p-6 shadow-[inset_0px_2px_4px_rgba(255,255,255,0.6)] border border-surface-dim/30 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                      <MaterialIcon name="groups" className="text-4xl text-primary" />
                    </div>
                    <h3 className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant mb-2">
                      Active Roster
                    </h3>
                    <div className="font-headline text-4xl text-primary font-medium tracking-tight">
                      {classes.length > 0 ? classes.length * 12 : "—"}
                    </div>
                  </div>
                  <div className="bg-surface-container-low rounded-[32px] p-6 shadow-[inset_0px_2px_4px_rgba(255,255,255,0.6)] border border-surface-dim/30 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                      <MaterialIcon name="menu_book" className="text-4xl text-primary" />
                    </div>
                    <h3 className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant mb-2">
                      Classes
                    </h3>
                    <div className="font-headline text-4xl text-primary font-medium tracking-tight">
                      {classes.length}
                    </div>
                  </div>
                </div>

                {/* Insight Card */}
                <div className="bg-primary-container rounded-[32px] p-8 text-on-primary-container flex-grow relative overflow-hidden shadow-[0px_20px_40px_rgba(26,67,62,0.15)]">
                  <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-transparent mix-blend-overlay" />
                  <div className="relative z-10 flex flex-col h-full justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-4">
                        <MaterialIcon
                          name="lightbulb"
                          filled
                          className="text-[18px] text-primary-fixed"
                        />
                        <h4 className="font-body text-xs uppercase tracking-widest text-primary-fixed font-semibold">
                          Workflow Insight
                        </h4>
                      </div>
                      <p className="font-headline text-2xl leading-snug font-medium mb-4">
                        Monitor cohort engagement with{" "}
                        <span className="italic font-light">adaptive content</span> across your
                        classes.
                      </p>
                    </div>
                    <div className="mt-6 pt-6 border-t border-primary-fixed/20">
                      <span className="text-sm font-body font-medium flex items-center gap-2">
                        Review interaction logs
                        <MaterialIcon name="arrow_forward" className="text-[16px]" />
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            {/* Active Cohorts */}
            <section className="space-y-12">
              <div className="flex items-end justify-between border-b border-surface-dim/40 pb-6">
                <div>
                  <h2 className="font-headline text-4xl text-primary tracking-tight font-medium">
                    Active Cohorts
                  </h2>
                  <p className="font-body text-sm text-on-surface-variant mt-2 tracking-wide">
                    Monitor real-time progress and module completion rates.
                  </p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {classes.map((item, i) => (
                  <Link
                    key={item.id}
                    href={`/classes/${item.id}`}
                    className="bg-surface-container-lowest rounded-[32px] p-8 hover:bg-surface-container-low transition-colors duration-300 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] group border border-surface-dim/20"
                  >
                    <div className="flex justify-between items-start mb-6">
                      <div
                        className={`w-12 h-12 rounded-2xl ${CLASS_COLORS[i % CLASS_COLORS.length]} flex items-center justify-center shadow-[inset_0px_2px_4px_rgba(255,255,255,0.5)]`}
                      >
                        <MaterialIcon
                          name={CLASS_ICONS[i % CLASS_ICONS.length]}
                          className="text-2xl"
                        />
                      </div>
                      <span className="bg-surface-dim/30 text-on-surface-variant text-xs font-body px-3 py-1 rounded-full uppercase tracking-widest font-semibold">
                        Active
                      </span>
                    </div>
                    <h3 className="font-headline text-2xl text-primary font-medium mb-2 group-hover:text-primary-container transition-colors">
                      {item.title}
                    </h3>
                    <p className="font-body text-sm text-on-surface-variant mb-8 line-clamp-2">
                      {item.description || "No description"}
                    </p>
                    <div className="space-y-3">
                      <div className="flex justify-between text-xs font-body text-on-surface-variant">
                        <span>Enrollment Code</span>
                        <span className="font-bold text-primary">{item.enrollment_code}</span>
                      </div>
                      <div className="h-1.5 w-full bg-surface-dim rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${Math.min(100, (i + 1) * 30)}%` }}
                        />
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          </>
        )}

        {/* ===== STUDENT VIEW ===== */}
        {role === "student" && (
          <>
            {/* Hero */}
            <section className="bg-surface-container-lowest rounded-[32px] p-10 md:p-16 relative overflow-hidden shadow-[0px_20px_40px_rgba(27,28,26,0.04)] border border-surface-dim/20">
              <div className="absolute inset-0 bg-gradient-to-br from-primary-fixed/10 via-transparent to-surface-dim/10 pointer-events-none" />
              <div className="relative z-10 max-w-xl">
                <h1 className="font-headline text-5xl md:text-6xl text-primary font-medium tracking-[-0.03em] leading-[1.05] mb-6">
                  Your learning journey.
                </h1>
                <p className="font-body text-lg md:text-xl text-on-surface-variant leading-relaxed mb-10 max-w-lg font-light">
                  Access your courses, track progress, and engage with personalized learning
                  materials.
                </p>
              </div>
            </section>

            {/* Class Cards */}
            <section className="space-y-8">
              <h2 className="font-headline text-4xl text-primary tracking-tight font-medium">
                Your Classes
              </h2>
              {classes.length === 0 ? (
                <p className="font-body text-on-surface-variant">
                  You're not enrolled in any classes yet. Use the form below to join one.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                  {classes.map((item, i) => (
                    <Link
                      key={item.id}
                      href={`/classes/${item.id}`}
                      className="bg-surface-container-lowest rounded-[32px] p-8 hover:bg-surface-container-low transition-colors duration-300 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] group border border-surface-dim/20"
                    >
                      <div className="flex justify-between items-start mb-6">
                        <div
                          className={`w-12 h-12 rounded-2xl ${CLASS_COLORS[i % CLASS_COLORS.length]} flex items-center justify-center`}
                        >
                          <MaterialIcon
                            name={CLASS_ICONS[i % CLASS_ICONS.length]}
                            className="text-2xl"
                          />
                        </div>
                      </div>
                      <h3 className="font-headline text-2xl text-primary font-medium mb-2 group-hover:text-primary-container transition-colors">
                        {item.title}
                      </h3>
                      <p className="font-body text-sm text-on-surface-variant line-clamp-2">
                        {item.description || "No description"}
                      </p>
                    </Link>
                  ))}
                </div>
              )}
            </section>

            {/* Enroll Form */}
            <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="bg-surface-container-lowest rounded-[32px] p-8 shadow-[0px_10px_30px_rgba(27,28,26,0.04)] border border-surface-dim/20">
                <h2 className="font-headline text-2xl text-primary font-medium mb-6">
                  Join a class
                </h2>
                <form onSubmit={enroll} className="space-y-5">
                  <div className="space-y-2">
                    <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                      Class ID
                    </label>
                    <input
                      className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                      value={classId}
                      onChange={(e) => setClassId(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold">
                      Enrollment code
                    </label>
                    <input
                      className="w-full bg-surface-container-low border-0 border-b-2 border-outline rounded-t-lg px-4 py-3 text-on-surface font-body focus:border-primary focus:outline-none transition-colors"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      required
                    />
                  </div>
                  <button
                    type="submit"
                    className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2"
                  >
                    Enroll
                    <MaterialIcon name="arrow_forward" className="text-[18px]" />
                  </button>
                </form>
              </div>
            </section>
          </>
        )}

        {/* ===== RESEARCHER VIEW ===== */}
        {role === "researcher" && (
          <>
            {/* Hero */}
            <section className="bg-surface-container-lowest rounded-[32px] p-10 md:p-16 relative overflow-hidden shadow-[0px_20px_40px_rgba(27,28,26,0.04)] border border-surface-dim/20">
              <div className="absolute inset-0 bg-gradient-to-br from-primary-fixed/10 via-transparent to-surface-dim/10 pointer-events-none" />
              <div className="relative z-10 max-w-xl">
                <h1 className="font-headline text-5xl md:text-6xl text-primary font-medium tracking-[-0.03em] leading-[1.05] mb-6">
                  Research dashboard.
                </h1>
                <p className="font-body text-lg md:text-xl text-on-surface-variant leading-relaxed max-w-lg font-light">
                  Review learning system telemetry, model behavior, and cohort analytics.
                </p>
              </div>
            </section>

            {/* Class Cards */}
            <section className="space-y-8">
              <h2 className="font-headline text-4xl text-primary tracking-tight font-medium">
                Research Cohorts
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                {classes.map((item, i) => (
                  <Link
                    key={item.id}
                    href={`/research/classes/${item.id}/workbench`}
                    className="bg-surface-container-lowest rounded-[32px] p-8 hover:bg-surface-container-low transition-colors duration-300 shadow-[0px_10px_30px_rgba(27,28,26,0.02)] group border border-surface-dim/20"
                  >
                    <div className="flex justify-between items-start mb-6">
                      <div
                        className={`w-12 h-12 rounded-2xl ${CLASS_COLORS[i % CLASS_COLORS.length]} flex items-center justify-center`}
                      >
                        <MaterialIcon
                          name={CLASS_ICONS[i % CLASS_ICONS.length]}
                          className="text-2xl"
                        />
                      </div>
                      <span className="bg-surface-dim/30 text-on-surface-variant text-xs font-body px-3 py-1 rounded-full uppercase tracking-widest font-semibold">
                        Research
                      </span>
                    </div>
                    <h3 className="font-headline text-2xl text-primary font-medium mb-2 group-hover:text-primary-container transition-colors">
                      {item.title}
                    </h3>
                    <p className="font-body text-sm text-on-surface-variant mb-4 line-clamp-2">
                      {item.description || "No description"}
                    </p>
                    <span className="text-sm font-body text-primary font-medium flex items-center gap-2">
                      Open research workbench
                      <MaterialIcon name="arrow_forward" className="text-[16px]" />
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
