import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { VerdictLabel } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function verdictColor(verdict: VerdictLabel): string {
  switch (verdict) {
    case "Eligible":
      return "emerald";
    case "NotEligible":
      return "rose";
    case "NeedsManualReview":
      return "amber";
  }
}

export function verdictLabel(verdict: VerdictLabel): string {
  switch (verdict) {
    case "Eligible":
      return "Eligible";
    case "NotEligible":
      return "Not Eligible";
    case "NeedsManualReview":
      return "Manual Review";
  }
}

export function verdictBgClass(verdict: VerdictLabel): string {
  switch (verdict) {
    case "Eligible":
      return "bg-emerald-50 border-emerald-200 text-emerald-800";
    case "NotEligible":
      return "bg-rose-50 border-rose-200 text-rose-800";
    case "NeedsManualReview":
      return "bg-amber-50 border-amber-200 text-amber-800";
  }
}

export function verdictDotClass(verdict: VerdictLabel): string {
  switch (verdict) {
    case "Eligible":
      return "bg-emerald-500";
    case "NotEligible":
      return "bg-rose-500";
    case "NeedsManualReview":
      return "bg-amber-500";
  }
}

export function formatCurrency(value: number | null): string {
  if (value === null) return "N/A";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export function truncate(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "…";
}
