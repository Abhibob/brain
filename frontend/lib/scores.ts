export type FitTier = "strong" | "ok" | "weak";

/** Convert a backend 0-100 fit score into a 0-10 display value (1 decimal). */
export function fitTen(fit: number | null | undefined): number {
  if (fit === null || fit === undefined || Number.isNaN(fit)) return 0;
  const clamped = Math.max(0, Math.min(100, fit));
  return Math.round(clamped) / 10;
}

export function fitTier(fit: number | null | undefined): FitTier {
  const ten = fitTen(fit);
  if (ten >= 7.5) return "strong";
  if (ten >= 5) return "ok";
  return "weak";
}

export function fitRingClass(fit: number | null | undefined): string {
  const tier = fitTier(fit);
  return tier === "strong" ? "score-ring--strong" : tier === "ok" ? "score-ring--ok" : "score-ring--weak";
}

/** Map a 0-1 score to a red → amber → green hex. */
export function masteryColor(score: number): string {
  const s = Math.max(0, Math.min(1, score));
  if (s >= 0.66) return "#16a34a"; // green
  if (s >= 0.33) return "#f59e0b"; // amber
  return "#dc2626"; // red
}

/** Readable short label for a focus label string. */
export function focusLabelColor(label: string | null | undefined): string {
  switch ((label || "").toLowerCase()) {
    case "focused":
      return "#15803d";
    case "engaged":
      return "#16a34a";
    case "distracted":
      return "#ea580c";
    case "skimming":
      return "#d97706";
    case "abandoned":
      return "#b91c1c";
    default:
      return "#94a3b8";
  }
}
