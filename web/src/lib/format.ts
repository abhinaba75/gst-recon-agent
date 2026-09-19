import type { Lang } from "./i18n";

/**
 * Money formatting follows the invoice the user is holding: Indian digit
 * grouping (₹1,07,971) from `Intl`, never a hand-rolled pattern. The grouping
 * is the same in every Indian language, so the figure never changes shape
 * when the interface does.
 */

const GROUPED = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const GROUPED_2 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function inr(amount: number): string {
  return `₹${GROUPED.format(Math.round(amount))}`;
}

export function inr2(amount: number): string {
  return `₹${GROUPED_2.format(amount)}`;
}

/**
 * Short spoken form. Hindi keeps its own lakh/crore words; every other
 * language asks the browser for its compact notation rather than us guessing
 * a word, and falls back to the full figure if the runtime has no data.
 */
export function inrShort(amount: number, lang: Lang): string {
  const abs = Math.abs(amount);
  if (abs < 1e5) return inr(amount);

  if (lang === "hi") {
    if (abs >= 1e7) return `₹${(amount / 1e7).toFixed(2)} करोड़`;
    return `₹${(amount / 1e5).toFixed(2)} लाख`;
  }
  try {
    return `₹${new Intl.NumberFormat(`${lang}-IN`, {
      notation: "compact",
      maximumFractionDigits: 1,
    }).format(amount)}`;
  } catch {
    return inr(amount);
  }
}

export function pct(ratio: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(ratio);
}

/** '2026-09-18T20:43:36Z' → '18 Sep 2026, 20:43 UTC', written in `lang`. */
export function stampDate(iso: string, lang: Lang = "en"): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  try {
    return (
      new Intl.DateTimeFormat(`${lang}-IN`, {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
        hour12: false,
      }).format(d) + " UTC"
    );
  } catch {
    return d.toISOString();
  }
}
