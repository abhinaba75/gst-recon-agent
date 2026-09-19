import { useSyncExternalStore } from "react";

import raw from "../data/snapshot.json";
import type { ActivityEvent, MatchRow, Snapshot } from "./types";

/**
 * The snapshot is written by `scripts/export_snapshot.py` from the live Python
 * engine, so its schema is guaranteed by the exporter rather than inferred at
 * runtime. The cast is the seam; the shapes are hand-kept in sync with it.
 *
 * It is held in a tiny store rather than exported as a constant because the
 * operator can submit their own register and GSTR-2B file: when the engine
 * answers with a fresh reconciliation, every section on the page has to show
 * the new figures. A constant would leave the ledger describing a run the
 * operator no longer has on screen.
 */
const initial = raw as unknown as Snapshot;

let current: Snapshot = initial;
let isDemo = true;

const listeners = new Set<() => void>();

export function getSnapshot(): Snapshot {
  return current;
}

/** True while the page is showing the period shipped with the fixtures. */
export function showingDemo(): boolean {
  return isDemo;
}

export function setSnapshot(next: Snapshot, demo = false): void {
  current = next;
  isDemo = demo;
  for (const listener of listeners) listener();
}

/** Put the bundled period back, after an operator has run their own file. */
export function resetSnapshot(): void {
  setSnapshot(initial, true);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The snapshot every section renders. Re-renders when a run replaces it. */
export function useSnapshot(): Snapshot {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function rescuedOf(s: Snapshot): MatchRow[] {
  return s.matches.filter((m) => m.status === "ai");
}

export function recoveryOf(s: Snapshot): MatchRow[] {
  return s.matches.filter((m) => m.status === "missing");
}

export function portalOnlyOf(s: Snapshot): MatchRow[] {
  return s.matches.filter((m) => m.status === "portal_only");
}

export function statusCountsOf(s: Snapshot): Record<string, number> {
  return s.matches.reduce(
    (acc, m) => {
      acc[m.status] = (acc[m.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
}

/** The narration a run produced, so the activity log matches the figures. */
export function seedEvents(s: Snapshot = current): ActivityEvent[] {
  const { counts, period, totals } = s;
  const at = s.generated_at.slice(11, 19);
  const counts_ = statusCountsOf(s);
  return [
    {
      at,
      tag: "DATA",
      text: `${counts.books} purchase bills and ${counts.portal} GSTR-2B entries loaded for ${period}`,
    },
    {
      at,
      tag: "EXCEL",
      text: `Spreadsheet check: ${counts.excel_unmatched} bills returned #N/A and were about to be written off`,
    },
    {
      at,
      tag: "AGENT",
      text: `${counts_["exact"] ?? 0} bills matched exactly on GSTIN, invoice number and tax`,
    },
    {
      at,
      tag: "AGENT",
      text: `${counts.rescued} bills recovered — ${Math.round(
        totals.rescued,
      ).toLocaleString("en-IN")} of credit the spreadsheet had written off`,
    },
    {
      at,
      tag: "A2A",
      text: `${counts.missing} suppliers who have not filed GSTR-1 queued for a recovery notice`,
    },
  ];
}
