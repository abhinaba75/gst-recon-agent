import { MoonIcon, SearchIcon, SunIcon } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { Kbd } from "@/components/ui/kbd";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { tr, type Lang } from "@/lib/i18n";
import { LOCALES, localeOf } from "@/lib/locales";
import { useActiveSection } from "@/lib/navigation";
import { ClerkUserButton, type ClerkConfig } from "@/components/clerk-signin";
import type { SessionUser } from "@/lib/session";
import type { Theme } from "@/lib/theme";
import { ALL_ENTRIES } from "./nav-sections";

/**
 * The dashboard header: the panel toggle, where you are, and the four controls
 * that change how the page looks. The breadcrumb is the section actually on
 * screen, observed rather than guessed from clicks, and the search box is the
 * ⌘K palette rather than a second search that behaves differently.
 */
export function SiteHeader({
  lang,
  setLang,
  theme,
  toggleTheme,
  user,
  unverified = false,
  onOpenSearch,
  clerkConfig = null,
  onClerkEnded,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  theme: Theme;
  toggleTheme: () => void;
  user: SessionUser;
  unverified?: boolean;
  onOpenSearch: () => void;
  /** Present only when the header may offer Clerk's account button. */
  clerkConfig?: ClerkConfig | null;
  /** The engine session to end when the operator signs out from Clerk's menu. */
  onClerkEnded?: () => void;
}) {
  const dark = theme === "dark";
  const themeLabel = dark ? tr("theme_to_light", lang) : tr("theme_to_dark", lang);
  const active = useActiveSection();
  const current = ALL_ENTRIES.find((entry) => entry.target === active);
  const where = current ? tr(current.labelKey, lang) : tr("nav_home", lang);

  return (
    <header className="bg-card sticky top-0 z-30 flex h-(--header-height) shrink-0 items-center gap-2 border-b">
      <div className="flex w-full items-center gap-2 px-3 lg:gap-3 lg:px-4">
        <SidebarTrigger
          className="-ms-1"
          aria-label={tr("nav_menu", lang)}
          title={tr("nav_menu", lang)}
        />
        <Separator orientation="vertical" className="data-[orientation=vertical]:h-4" />

        <Breadcrumb className="min-w-0">
          <BreadcrumbList className="flex-nowrap">
            <BreadcrumbItem className="hidden sm:block">
              <BreadcrumbLink href="#top">Recon-Agent</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden sm:block" />
            <BreadcrumbItem className="min-w-0">
              <BreadcrumbPage className="truncate">{where}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>

        <div className="ms-auto flex items-center gap-2">
          <Button
            variant="outline"
            onClick={onOpenSearch}
            className="justify-start gap-2 font-normal md:w-56"
            aria-label={`${tr("search", lang)} (⌘K)`}
          >
            <SearchIcon aria-hidden="true" />
            <span className="hidden truncate md:inline">{tr("search", lang)}</span>
            <Kbd className="ms-auto hidden md:inline-flex">⌘K</Kbd>
          </Button>

          <Button
            variant="outline"
            size="icon"
            onClick={toggleTheme}
            aria-pressed={dark}
            aria-label={themeLabel}
            title={themeLabel}
          >
            {dark ? <SunIcon /> : <MoonIcon />}
          </Button>

          <Select value={lang} onValueChange={setLang}>
            <SelectTrigger
              className="w-[7.5rem] max-w-[38vw]"
              aria-label={tr("nav_language", lang)}
            >
              <SelectValue>{localeOf(lang).native}</SelectValue>
            </SelectTrigger>
            <SelectContent className="max-h-[70vh]">
              {LOCALES.map((l) => (
                <SelectItem key={l.code} value={l.code} lang={l.code}>
                  {l.native}
                  {l.native === l.english ? "" : ` · ${l.english}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* The account control follows the session's own door: a session
              created by Clerk gets Clerk's button — its menu (profile,
              sessions, manage account, sign out) acts on a Clerk account and
              would promise what it cannot do over any other kind. Every other
              session gets this project's avatar card, which says who signed
              in and flags a session the browser admitted unverified. */}
          {clerkConfig && onClerkEnded ? (
            <ClerkUserButton config={clerkConfig} onEnded={onClerkEnded} />
          ) : (
            <HoverCard openDelay={120} closeDelay={80}>
              <HoverCardTrigger asChild>
                <button
                  type="button"
                  aria-label={`${tr("signed_in_as", lang)} ${user.email}`}
                  className="rounded-full"
                >
                  <Avatar className="size-8">
                    <AvatarFallback className="text-[0.8rem] font-medium">
                      {user.email.slice(0, 1).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                </button>
              </HoverCardTrigger>
              <HoverCardContent className="w-64 text-[0.82rem] leading-relaxed">
                <p className="font-medium">
                  {tr("signed_in_as", lang)} <span translate="no">{user.email}</span>
                </p>
                <p className="text-muted-foreground mt-1">
                  {unverified ? tr("offline_session", lang) : tr("snapshot_note", lang)}
                </p>
              </HoverCardContent>
            </HoverCard>
          )}
        </div>
      </div>
    </header>
  );
}
