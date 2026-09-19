import type { ComponentType } from "react";
import {
  ActivityIcon,
  AlertTriangleIcon,
  BookTextIcon,
  ChartColumnIcon,
  CheckIcon,
  ClockIcon,
  LayoutDashboardIcon,
  ListIcon,
  PlayCircleIcon,
  SearchIcon,
  SendIcon,
  SparklesIcon,
  TableIcon,
  TagsIcon,
  UploadIcon,
} from "lucide-react";

import type { SectionId } from "../lib/navigation";
import type { Snapshot, Status } from "../lib/types";

export type Icon = ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;

/** A child of a sidebar row: one status of the ledger, as a filter. */
export interface NavChild {
  key: string;
  labelKey: string;
  icon: Icon;
  status: Status | "all";
}

/**
 * One row of the sidebar. `target` is where it scrolls to; `action` is what it
 * does instead; `count` is a live figure from the reconciliation, never a
 * number invented for the navigation. The same registry feeds the command
 * palette, so a section can never be listed in one place and missing in the
 * other.
 */
export interface NavEntry {
  key: string;
  labelKey: string;
  icon: Icon;
  target?: SectionId;
  action?: "search";
  shortcut?: string;
  count?: (snapshot: Snapshot) => number;
  children?: NavChild[];
  /** Rendered as the one highlighted action in the sidebar. */
  highlight?: boolean;
}

export const TODAY_ITEMS: NavEntry[] = [
  {
    key: "start",
    labelKey: "cta_start",
    icon: PlayCircleIcon,
    target: "get-started",
    highlight: true,
  },
  {
    key: "search",
    labelKey: "search",
    icon: SearchIcon,
    action: "search",
    shortcut: "⌘K",
  },
  {
    key: "home",
    labelKey: "nav_home",
    icon: LayoutDashboardIcon,
    target: "top",
  },
  {
    key: "numbers",
    labelKey: "nav_numbers",
    icon: ChartColumnIcon,
    target: "numbers",
  },
];

export const RECONCILE_ITEMS: NavEntry[] = [
  { key: "submit", labelKey: "nav_submit", icon: UploadIcon, target: "submit" },
  { key: "compare", labelKey: "nav_compare", icon: TableIcon, target: "compare" },
  {
    key: "recovery",
    labelKey: "nav_recovery",
    icon: SendIcon,
    target: "recovery",
    // The number of vendors who have collected tax and not filed.
    count: (snapshot) => snapshot.counts.missing,
  },
  {
    key: "ledger",
    labelKey: "nav_ledger",
    icon: BookTextIcon,
    target: "ledger",
    children: [
      { key: "ledger-all", labelKey: "nav_ledger", icon: ListIcon, status: "all" },
      { key: "ledger-exact", labelKey: "status_matched", icon: CheckIcon, status: "exact" },
      {
        key: "ledger-ai",
        labelKey: "status_recovered",
        icon: SparklesIcon,
        status: "ai",
      },
      {
        key: "ledger-missing",
        labelKey: "status_defaulting",
        icon: AlertTriangleIcon,
        status: "missing",
      },
      {
        key: "ledger-late",
        labelKey: "status_late",
        icon: ClockIcon,
        status: "portal_only",
      },
    ],
  },
  { key: "activity", labelKey: "nav_log", icon: ActivityIcon, target: "activity" },
  { key: "glossary", labelKey: "nav_glossary", icon: TagsIcon, target: "glossary" },
];

/** Every row, in page order — what the command palette searches. */
export const ALL_ENTRIES: NavEntry[] = [...TODAY_ITEMS, ...RECONCILE_ITEMS];
