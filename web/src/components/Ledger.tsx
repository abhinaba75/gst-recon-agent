import { useId, useMemo, useState } from "react";
import { FrownIcon, SearchIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { inr } from "../lib/format";
import { tr, type Lang } from "../lib/i18n";
import { setLedgerFilter, useLedgerFilter } from "../lib/navigation";
import { statusCountsOf, useSnapshot } from "../lib/snapshot";
import type { Status } from "../lib/types";
import { SectionHead, Stamp } from "./ui";

const FILTERS: (Status | "all")[] = ["all", "exact", "ai", "missing", "portal_only"];

/** Eight rows a page: about one phone screen, so nobody scrolls a wall of table. */
const PAGE_SIZE = 8;

const STATUS_KEY: Record<string, string> = {
  all: "all",
  exact: "status_matched",
  ai: "status_recovered",
  missing: "status_defaulting",
  portal_only: "status_late",
};

/**
 * The full reconciliation, as a shadcn Table: a real `<table>` with a sticky
 * head, and on a phone the same rows restacked as labelled cards. Search is a
 * shadcn Input, the status filters are a ToggleGroup, and an Empty state
 * replaces the old bare sentence when nothing matches.
 */
export function Ledger({ lang }: { lang: Lang }) {
  const snapshot = useSnapshot();
  const statusCounts = statusCountsOf(snapshot);
  const [query, setQuery] = useState("");
  // Shared with the sidebar: choosing "Defaulting" under Ledger, or a status
  // in the command palette, filters this table.
  const status = useLedgerFilter();
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(1);
  const searchId = useId();

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const filtered = snapshot.matches.filter((m) => {
      if (status !== "all" && m.status !== status) return false;
      if (!needle) return true;
      return (
        m.supplier_name.toLowerCase().includes(needle) ||
        m.register_no.toLowerCase().includes(needle) ||
        m.portal_no.toLowerCase().includes(needle) ||
        m.supplier_gstin.toLowerCase().includes(needle)
      );
    });
    return [...filtered].sort((a, b) => (sortDesc ? b.tax - a.tax : a.tax - b.tax));
  }, [query, status, sortDesc, snapshot]);

  const sortLabel = tr(sortDesc ? "sort_itc_desc" : "sort_itc_asc", lang);

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const current = Math.min(page, pageCount);
  const visible = rows.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  return (
    <section id="ledger" className="border-border scroll-mt-20 border-t">
      <div className="shell py-12 md:py-14">
        <SectionHead
          id="ledger-title"
          titleKey="ledger_title"
          subKey="ledger_sub"
          lang={lang}
        />

        <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-end">
          <div className="min-w-0 flex-1 lg:max-w-sm">
            <Label htmlFor={searchId} className="text-muted-foreground text-[0.85rem]">
              {tr("search", lang)}
            </Label>
            <div className="relative mt-1">
              <SearchIcon
                aria-hidden="true"
                className="text-muted-foreground pointer-events-none absolute inset-y-0 start-3 my-auto size-4"
              />
              <Input
                id={searchId}
                type="search"
                inputMode="search"
                autoComplete="off"
                spellCheck={false}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setPage(1);
                }}
                placeholder={tr("search_example", lang)}
                className="min-h-11 ps-9 text-[0.95rem]"
              />
            </div>
          </div>

          <div>
            <span className="text-muted-foreground block text-[0.85rem]">
              {tr("filter", lang)}
            </span>
            <ToggleGroup
              type="single"
              variant="outline"
              value={status}
              onValueChange={(next) => {
                if (!next) return;
                setLedgerFilter(next as Status | "all");
                setPage(1);
              }}
              aria-label={tr("filter", lang)}
              className="mt-1 flex-wrap"
            >
              {FILTERS.map((key) => {
                const count =
                  key === "all" ? snapshot.matches.length : (statusCounts[key] ?? 0);
                return (
                  <ToggleGroupItem
                    key={key}
                    value={key}
                    className="min-h-11 gap-1.5 rounded-lg px-3 text-[0.85rem] font-medium data-[state=on]:border-primary data-[state=on]:bg-brass/15 data-[state=on]:text-foreground"
                  >
                    {tr(STATUS_KEY[key], lang)}
                    <span className="font-mono tabular-nums">· {count}</span>
                  </ToggleGroupItem>
                );
              })}
            </ToggleGroup>
          </div>
        </div>

        <p className="text-muted-foreground mb-2 text-[0.85rem]" aria-live="polite">
          {tr("show", lang)} {rows.length} {tr("of", lang)} {snapshot.matches.length}{" "}
          {tr("rows", lang)}
          {pageCount > 1 && (
            <span className="ms-2 font-mono tabular-nums">
              {current} / {pageCount}
            </span>
          )}
        </p>

        {rows.length === 0 ? (
          <Empty className="border">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <FrownIcon aria-hidden="true" />
              </EmptyMedia>
              <EmptyTitle>{tr("ledger_title", lang)}</EmptyTitle>
              <EmptyDescription>{tr("empty_filter", lang)}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <Card className="overflow-hidden p-0">
            <div className="ledger-wrap max-h-[32rem] overflow-auto">
              <Table className="ledger-table">
                <TableCaption className="sr-only">{tr("ledger_title", lang)}</TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead>{tr("col_books", lang)}</TableHead>
                    <TableHead>{tr("col_portal", lang)}</TableHead>
                    <TableHead>{tr("col_supplier", lang)}</TableHead>
                    <TableHead>{tr("col_gstin", lang)}</TableHead>
                    <TableHead aria-sort={sortDesc ? "descending" : "ascending"}>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-ms-2 h-8 gap-1 px-2 text-[0.85rem] font-semibold"
                        onClick={() => {
                          setSortDesc((v) => !v);
                          setPage(1);
                        }}
                        title={sortLabel}
                      >
                        {tr("col_itc", lang)}
                        <span aria-hidden="true">{sortDesc ? "↓" : "↑"}</span>
                        <span className="sr-only">{sortLabel}</span>
                      </Button>
                    </TableHead>
                    <TableHead>{tr("col_status", lang)}</TableHead>
                    <TableHead>{tr("col_conf", lang)}</TableHead>
                    <TableHead>{tr("col_evidence", lang)}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visible.map((m) => (
                    <TableRow key={`${m.register_no}-${m.portal_no}`}>
                      <TableCell data-label={tr("col_books", lang)}>
                        <code className="id text-[0.82rem]" translate="no">
                          {m.register_no}
                        </code>
                      </TableCell>
                      <TableCell data-label={tr("col_portal", lang)}>
                        <code className="id text-[0.82rem]" translate="no">
                          {m.portal_no}
                        </code>
                      </TableCell>
                      <TableCell
                        data-label={tr("col_supplier", lang)}
                        className="min-w-[12rem] whitespace-normal"
                      >
                        {m.supplier_name}
                      </TableCell>
                      <TableCell data-label={tr("col_gstin", lang)}>
                        <code
                          className="id text-muted-foreground text-[0.78rem]"
                          translate="no"
                        >
                          {m.supplier_gstin}
                        </code>
                      </TableCell>
                      <TableCell
                        data-label={tr("col_itc", lang)}
                        className="font-mono tabular-nums"
                      >
                        {inr(m.tax)}
                      </TableCell>
                      <TableCell data-label={tr("col_status", lang)}>
                        <Stamp status={m.status} conf={m.ai_conf} lang={lang} />
                      </TableCell>
                      <TableCell
                        data-label={tr("col_conf", lang)}
                        className="text-muted-foreground font-mono text-[0.82rem] tabular-nums"
                      >
                        {m.ai_conf ? `${m.ai_conf}%` : "—"}
                      </TableCell>
                      <TableCell
                        data-label={tr("col_evidence", lang)}
                        className="text-muted-foreground max-w-[24rem] min-w-[14rem] text-[0.82rem] leading-relaxed whitespace-normal"
                      >
                        {m.reason || "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        )}

        {pageCount > 1 && (
          <Pagination aria-label={tr("ledger_title", lang)} className="mt-4">
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious
                  href="#ledger"
                  text={tr("page_prev", lang)}
                  aria-label={tr("page_prev", lang)}
                  aria-disabled={current === 1}
                  className={current === 1 ? "pointer-events-none opacity-50" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    setPage(Math.max(1, current - 1));
                  }}
                />
              </PaginationItem>

              {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
                <PaginationItem key={n}>
                  <PaginationLink
                    href="#ledger"
                    size="default"
                    className="min-w-11 justify-center"
                    isActive={n === current}
                    aria-label={`${tr("ledger_title", lang)} · ${n} / ${pageCount}`}
                    onClick={(e) => {
                      e.preventDefault();
                      setPage(n);
                    }}
                  >
                    {n}
                  </PaginationLink>
                </PaginationItem>
              ))}

              <PaginationItem>
                <PaginationNext
                  href="#ledger"
                  text={tr("page_next", lang)}
                  aria-label={tr("page_next", lang)}
                  aria-disabled={current === pageCount}
                  className={
                    current === pageCount ? "pointer-events-none opacity-50" : undefined
                  }
                  onClick={(e) => {
                    e.preventDefault();
                    setPage(Math.min(pageCount, current + 1));
                  }}
                />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        )}
      </div>
    </section>
  );
}
