import { useState, type ComponentProps } from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  FileSpreadsheetIcon,
  LogOutIcon,
  UploadIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { Kbd } from "@/components/ui/kbd";
import { tr, type Lang } from "@/lib/i18n";
import { goTo, openLedger, useActiveSection, useLedgerFilter } from "@/lib/navigation";
import type { SessionUser } from "@/lib/session";
import { resetSnapshot, showingDemo, useSnapshot } from "@/lib/snapshot";
import { cn } from "@/lib/utils";
import { RECONCILE_ITEMS, TODAY_ITEMS, type NavChild, type NavEntry } from "./nav-sections";

/**
 * The workspace shell's navigation.
 *
 * Two groups, in the order a first-time reader needs them: the sections that
 * orient you, then the reconciliation itself. Counts come from the snapshot,
 * the children under Ledger really filter the ledger, and the header says
 * which dataset the page is showing instead of inventing a company to switch
 * between.
 */
export function AppSidebar({
  lang,
  user,
  onSignOut,
  onOpenSearch,
  ...props
}: ComponentProps<typeof Sidebar> & {
  lang: Lang;
  user: SessionUser;
  onSignOut: () => void;
  onOpenSearch: () => void;
}) {
  const snapshot = useSnapshot();
  const { setOpenMobile } = useSidebar();
  const active = useActiveSection();
  const filter = useLedgerFilter();
  const demo = showingDemo();

  // Ledger starts expanded: its children are the four statuses, which is the
  // fastest way into the evidence.
  const [expanded, setExpanded] = useState<string[]>(["ledger"]);

  const close = () => setOpenMobile(false);

  function activate(entry: NavEntry) {
    if (entry.action === "search") {
      onOpenSearch();
      close();
      return;
    }
    if (entry.children) {
      setExpanded((keys) =>
        keys.includes(entry.key)
          ? keys.filter((key) => key !== entry.key)
          : [...keys, entry.key],
      );
      if (entry.key === "ledger") openLedger("all");
    } else if (entry.target) {
      goTo(entry.target);
    }
    close();
  }

  function isActive(entry: NavEntry): boolean {
    if (entry.key === "ledger") return active === "ledger";
    return entry.target !== undefined && entry.target === active;
  }

  function chooseChild(child: NavChild) {
    openLedger(child.status);
    close();
  }

  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader className="px-2 pt-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="lg"
              className="h-auto w-full justify-start gap-3 px-2 py-2"
            >
              <span
                aria-hidden="true"
                className="bg-primary text-primary-foreground flex size-8 shrink-0 items-center justify-center rounded-md text-[0.8rem] font-semibold"
              >
                <FileSpreadsheetIcon className="size-4" />
              </span>
              <span className="min-w-0 flex-1 text-start">
                <span className="block truncate text-[0.85rem] font-medium">
                  {demo ? tr("source_demo", lang) : tr("source_own", lang)}
                </span>
                <span className="text-muted-foreground block truncate text-[0.72rem]">
                  {snapshot.period} · fp {snapshot.fp}
                </span>
              </span>
              <ChevronDownIcon
                aria-hidden="true"
                className="text-muted-foreground size-4 shrink-0"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuCheckboxItem
              checked={demo}
              onCheckedChange={() => {
                resetSnapshot();
                close();
              }}
            >
              {tr("source_demo", lang)}
            </DropdownMenuCheckboxItem>
            <DropdownMenuCheckboxItem
              checked={!demo}
              onCheckedChange={() => {
                goTo("submit");
                close();
              }}
            >
              {tr("source_own", lang)}
            </DropdownMenuCheckboxItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => {
              goTo("submit");
              close();
            }}>
              <UploadIcon aria-hidden="true" />
              {tr("nav_submit", lang)}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupContent>
            <SidebarMenu>
              {TODAY_ITEMS.map((entry) => (
                <NavRow
                  key={entry.key}
                  entry={entry}
                  lang={lang}
                  active={isActive(entry)}
                  filter={filter}
                  expanded={expanded.includes(entry.key)}
                  count={entry.count?.(snapshot)}
                  onActivate={() => activate(entry)}
                  onChild={chooseChild}
                />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel>{tr("group_reconcile", lang)}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {RECONCILE_ITEMS.map((entry) => (
                <NavRow
                  key={entry.key}
                  entry={entry}
                  lang={lang}
                  active={isActive(entry)}
                  filter={filter}
                  expanded={expanded.includes(entry.key)}
                  count={entry.count?.(snapshot)}
                  onActivate={() => activate(entry)}
                  onChild={chooseChild}
                />
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <SidebarSeparator />
        <div className="px-2 pb-2">
          <p className="text-muted-foreground text-xs">
            {tr("signed_in_as", lang)} {user.email}
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 w-full justify-start"
            onClick={onSignOut}
          >
            <LogOutIcon aria-hidden="true" />
            {tr("sign_out", lang)}
          </Button>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}

/**
 * One row, plus its children when it has any. The parent row toggles its
 * children *and* takes you to the section, because both are what a reader
 * means by clicking "Ledger"; the children then set the status filter.
 */
function NavRow({
  entry,
  lang,
  active,
  filter,
  expanded,
  count,
  onActivate,
  onChild,
}: {
  entry: NavEntry;
  lang: Lang;
  active: boolean;
  filter: string;
  expanded: boolean;
  count?: number;
  onActivate: () => void;
  onChild: (child: NavChild) => void;
}) {
  const label = tr(entry.labelKey, lang);
  const Icon = entry.icon;
  const hasChildren = (entry.children?.length ?? 0) > 0;

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        isActive={active}
        tooltip={label}
        onClick={onActivate}
        aria-expanded={hasChildren ? expanded : undefined}
        className={cn(
          entry.highlight &&
            "bg-primary text-primary-foreground hover:bg-primary/90 hover:text-primary-foreground",
        )}
      >
        <Icon aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate">{label}</span>

        {entry.shortcut && (
          <Kbd className="hidden group-hover/menu-button:inline-flex group-data-[collapsible=icon]:hidden">
            {entry.shortcut}
          </Kbd>
        )}
        {count !== undefined && count > 0 && (
          <Badge
            variant="secondary"
            className="shrink-0 tabular-nums group-data-[collapsible=icon]:hidden"
          >
            {count}
          </Badge>
        )}
        {hasChildren && (
          <ChevronRightIcon
            aria-hidden="true"
            className={cn(
              "size-4 shrink-0 transition-transform duration-200 group-data-[collapsible=icon]:hidden",
              expanded && "rotate-90",
            )}
          />
        )}
      </SidebarMenuButton>

      {/* Collapsed by height, and taken out of the tab order and the
          accessibility tree while it is closed: a folded menu must not be
          reachable by keyboard or read aloud. */}
      {hasChildren && (
        <div
          inert={!expanded}
          aria-hidden={!expanded}
          className={cn(
            "grid transition-[grid-template-rows,opacity] duration-300 ease-in-out",
            expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
          )}
        >
          <div className="min-h-0 overflow-hidden">
            <SidebarMenuSub>
              {entry.children!.map((child) => {
                const ChildIcon = child.icon;
                const isChild = active && filter === child.status;
                return (
                  <SidebarMenuSubItem key={child.key}>
                    <SidebarMenuSubButton asChild isActive={isChild} className="w-full">
                      <button type="button" onClick={() => onChild(child)}>
                        <ChildIcon aria-hidden="true" />
                        <span>{tr(child.labelKey, lang)}</span>
                      </button>
                    </SidebarMenuSubButton>
                  </SidebarMenuSubItem>
                );
              })}
            </SidebarMenuSub>
          </div>
        </div>
      )}
    </SidebarMenuItem>
  );
}
