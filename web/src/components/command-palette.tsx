import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { CommandIcon, SearchIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Kbd } from "@/components/ui/kbd";
import { inr } from "../lib/format";
import { tr, type Lang } from "../lib/i18n";
import { goTo, openLedger } from "../lib/navigation";
import { useSnapshot } from "../lib/snapshot";
import type { Snapshot, Status } from "../lib/types";
import { ALL_ENTRIES } from "./nav-sections";
import { Stamp } from "./ui";

export interface PaletteRow {
  id: string;
  group: "section" | "bill";
  label: string;
  hint?: string;
  status?: Status;
  onPick: () => void;
}

/**
 * What the palette can find: the sections of this page, and the bills in the
 * reconciliation. A bill goes to the ledger — the only view that shows a bill
 * in full — so the palette never promises a destination that does not exist.
 */
export function paletteRows(
  query: string,
  lang: Lang,
  snapshot: Snapshot,
): PaletteRow[] {
  const needle = query.trim().toLowerCase();

  const entries = needle
    ? ALL_ENTRIES.filter(
        (entry) =>
          tr(entry.labelKey, lang).toLowerCase().includes(needle) ||
          (entry.children ?? []).some((child) =>
            tr(child.labelKey, lang).toLowerCase().includes(needle),
          ),
      )
    : ALL_ENTRIES;

  const sections: PaletteRow[] = entries.map((entry) => ({
    id: `section-${entry.key}`,
    group: "section",
    label: tr(entry.labelKey, lang),
    hint: entry.shortcut,
    onPick: () => {
      if (entry.target) goTo(entry.target);
    },
  }));

  if (!needle) return sections;

  const bills: PaletteRow[] = snapshot.matches
    .filter(
      (m) =>
        m.supplier_name.toLowerCase().includes(needle) ||
        m.register_no.toLowerCase().includes(needle) ||
        m.portal_no.toLowerCase().includes(needle) ||
        m.supplier_gstin.toLowerCase().includes(needle),
    )
    .slice(0, 6)
    .map((m) => ({
      id: `bill-${m.register_no}`,
      group: "bill",
      label: `${m.register_no} · ${m.supplier_name}`,
      hint: inr(m.tax),
      status: m.status,
      onPick: () => openLedger("all"),
    }));

  return [...sections, ...bills];
}

/** The result list on its own, so it can be rendered without a browser. */
export function PaletteResults({
  lang,
  rows,
  cursor,
  onHover,
  onPick,
}: {
  lang: Lang;
  rows: PaletteRow[];
  cursor: number;
  onHover: (index: number) => void;
  onPick: (index: number) => void;
}) {
  const sections = rows.filter((row) => row.group === "section");
  const bills = rows.filter((row) => row.group === "bill");

  function row(row: PaletteRow) {
    const index = rows.indexOf(row);
    const active = index === cursor;
    return (
      <Button
        key={row.id}
        type="button"
        variant="ghost"
        size="lg"
        role="option"
        aria-selected={active}
        data-active={active}
        onMouseEnter={() => onHover(index)}
        onClick={() => onPick(index)}
        className={`h-auto min-h-11 w-full justify-start gap-3 px-2.5 py-2 text-start font-normal ${
          active ? "bg-muted text-foreground" : ""
        }`}
      >
        <span className="min-w-0 flex-1 truncate">{row.label}</span>
        {row.status && <Stamp status={row.status} lang={lang} />}
        {row.hint && (
          <span className="text-muted-foreground shrink-0 font-mono text-[0.8rem] tabular-nums">
            {row.hint}
          </span>
        )}
      </Button>
    );
  }

  if (rows.length === 0) {
    return (
      <div
        role="listbox"
        aria-label={tr("palette_placeholder", lang)}
        className="p-2"
      >
        <Empty className="border-0 py-8">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <CommandIcon aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>{tr("search", lang)}</EmptyTitle>
            <EmptyDescription>{tr("palette_empty", lang)}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    );
  }

  return (
    <div
      role="listbox"
      aria-label={tr("palette_placeholder", lang)}
      className="max-h-[52vh] overflow-y-auto p-2"
    >
      {sections.length > 0 && (
        <p className="text-muted-foreground px-2 py-1.5 text-[0.72rem] font-semibold tracking-wide uppercase">
          {tr("nav_sections", lang)}
        </p>
      )}
      {sections.map(row)}
      {bills.length > 0 && (
        <p className="text-muted-foreground mt-2 px-2 py-1.5 text-[0.72rem] font-semibold tracking-wide uppercase">
          {tr("ledger_title", lang)}
        </p>
      )}
      {bills.map(row)}
    </div>
  );
}

/**
 * The command palette behind ⌘K / Ctrl+K, the header's search box, and the
 * sidebar's Search row. Arrow keys move, Enter opens, Escape closes.
 */
export function CommandPalette({
  lang,
  open,
  onOpenChange,
}: {
  lang: Lang;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const snapshot = useSnapshot();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const openRef = useRef(open);
  openRef.current = open;

  // ⌘K / Ctrl+K from anywhere in the workspace.
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpenChange(!openRef.current);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onOpenChange]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
    }
  }, [open]);

  const rows = useMemo(() => paletteRows(query, lang, snapshot), [query, lang, snapshot]);

  useEffect(() => {
    setCursor(0);
  }, [query]);

  function pick(index: number) {
    const row = rows[index];
    if (!row) return;
    row.onPick();
    onOpenChange(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setCursor((c) => Math.min(c + 1, rows.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      pick(cursor);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[12vh] max-w-xl gap-0 p-0">
        <DialogHeader className="sr-only">
          <DialogTitle>{tr("search", lang)}</DialogTitle>
          <DialogDescription>{tr("palette_placeholder", lang)}</DialogDescription>
        </DialogHeader>

        <div className="border-border flex items-center gap-2 border-b px-3">
          <SearchIcon aria-hidden="true" className="text-muted-foreground size-4 shrink-0" />
          <Input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label={tr("palette_placeholder", lang)}
            placeholder={tr("palette_placeholder", lang)}
            className="border-0 bg-transparent shadow-none focus-visible:ring-0 dark:bg-transparent"
          />
          <Kbd className="hidden sm:inline-flex">Esc</Kbd>
        </div>

        <PaletteResults
          lang={lang}
          rows={rows}
          cursor={cursor}
          onHover={setCursor}
          onPick={pick}
        />
      </DialogContent>
    </Dialog>
  );
}
