import { useEffect, useState, useSyncExternalStore } from "react";

import type { Status } from "./types";

/**
 * Navigation state for the dashboard shell: which section is on screen, where
 * a click should take you, and which ledger filter the sidebar has asked for.
 *
 * The sidebar's children are not decoration — "Defaulting" under Ledger really
 * does filter the ledger. That is why the filter lives here in a small store
 * rather than inside the Ledger: the nav and the table are two views of one
 * piece of state, which is the only way the tree can stay honest.
 */

/** Every section the shell can point at, in page order. */
export const SECTION_IDS = [
  "top",
  "get-started",
  "submit",
  "numbers",
  "compare",
  "recovery",
  "ledger",
  "activity",
  "glossary",
] as const;

export type SectionId = (typeof SECTION_IDS)[number];

const LEDGER_FILTERS: (Status | "all")[] = [
  "all",
  "exact",
  "ai",
  "missing",
  "portal_only",
];

/** Scroll to a section, honouring a reduced-motion preference. */
export function goTo(id: SectionId | string): void {
  if (typeof document === "undefined") return;
  const node = document.getElementById(id);
  if (!node) return;
  const reduce =
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  node.scrollIntoView({
    behavior: reduce ? "auto" : "smooth",
    block: "start",
  });
}

/**
 * The section the reader is actually looking at.
 *
 * Observed rather than tracked from clicks, so the sidebar stays correct when
 * the reader scrolls, uses the browser's back button, or arrives from a deep
 * link. The most-visible section wins, which keeps the highlight on the
 * content that fills the screen rather than the one peeking in at the top.
 */
export function useActiveSection(): SectionId {
  const [active, setActive] = useState<SectionId>("top");

  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const nodes = SECTION_IDS.map((id) => document.getElementById(id)).filter(
      (node): node is HTMLElement => node !== null,
    );
    if (!nodes.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        const best = visible[0]?.target.id;
        if (best && SECTION_IDS.includes(best as SectionId)) {
          setActive(best as SectionId);
        }
      },
      { rootMargin: "-15% 0px -55% 0px", threshold: [0, 0.2, 0.5, 0.9] },
    );

    for (const node of nodes) observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return active;
}

/* ── the shared ledger filter ──────────────────────────────────────────── */

let filter: Status | "all" = "all";
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function read(): Status | "all" {
  return filter;
}

export function setLedgerFilter(next: Status | "all"): void {
  if (!LEDGER_FILTERS.includes(next) || filter === next) return;
  filter = next;
  for (const listener of listeners) listener();
}

/** The filter the ledger is showing. Any component can read or set it. */
export function useLedgerFilter(): Status | "all" {
  return useSyncExternalStore(subscribe, read, read);
}

/** Jump to the ledger with a status already filtered — what the nav does. */
export function openLedger(next: Status | "all" = "all"): void {
  setLedgerFilter(next);
  goTo("ledger");
}
