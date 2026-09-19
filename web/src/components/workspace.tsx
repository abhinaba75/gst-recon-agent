import { lazy, Suspense, useEffect, useRef, useState, type CSSProperties } from "react";

import { Alert, AlertDescription } from "./ui/alert";
import { Activity, Footer, Glossary } from "./Activity";
import { AppSidebar } from "./app-sidebar";
import { CommandPalette } from "./command-palette";
import { Comparison } from "./Comparison";
import { GetStarted } from "./GetStarted";
import { Hero } from "./Hero";
import { Kpis } from "./Kpis";
import { Ledger } from "./Ledger";
import { Recovery } from "./Recovery";
import { SiteHeader } from "./site-header";
import { SubmitBills } from "./SubmitBills";
import { SidebarInset, SidebarProvider } from "./ui/sidebar";
import { TooltipProvider } from "./ui/tooltip";
import { coverageOf, tr, type Lang } from "../lib/i18n";
import { authOptions, type SessionUser } from "../lib/session";
import { getSnapshot, seedEvents } from "../lib/snapshot";
import type { Theme } from "../lib/theme";
import type { ActivityEvent } from "../lib/types";

// The assistant is behind a button, so it has no business in the first paint.
const Assistant = lazy(() =>
  import("./Assistant").then((m) => ({ default: m.Assistant })),
);

/**
 * The signed-in product: the dashboard shell, the sections, the assistant.
 * Split out from App so the gate and the workspace can be rendered and
 * asserted separately, without a browser or a session.
 */
export function Workspace({
  lang,
  setLang,
  theme,
  toggleTheme,
  user,
  onSignOut,
  unverified = false,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  theme: Theme;
  toggleTheme: () => void;
  user: SessionUser;
  onSignOut: () => void;
  /** True when the session was admitted by the browser, not the engine. */
  unverified?: boolean;
}) {
  const [events, setEvents] = useState<ActivityEvent[]>(() => seedEvents(getSnapshot()));
  const [announcement, setAnnouncement] = useState("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [clerkConfig, setClerkConfig] = useState<Awaited<
    ReturnType<typeof authOptions>
  > | null>(null);

  // The header may offer Clerk's account button only for a session Clerk
  // created — the flag travels on the account, set by whichever door minted
  // it. One fetch, only for those sessions; nobody else downloads anything.
  useEffect(() => {
    if (user.provider !== "clerk") return;
    let alive = true;
    void authOptions().then((options) => {
      if (alive && options?.clerk) setClerkConfig(options);
    });
    return () => {
      alive = false;
    };
  }, [user.provider]);

  // A screen reader gets told when the mode changes; an icon cannot say it.
  // Skipped on first render, so arriving on the page is not announced as a
  // toggle the reader never performed.
  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    setAnnouncement(
      tr(theme === "dark" ? "theme_now_dark" : "theme_now_light", lang),
    );
  }, [theme, lang]);

  return (
    <>
      {/* First in the DOM on purpose: the first Tab from the address bar must
          offer the way past the sidebar and the header. */}
      <a className="skip-link" href="#main">
        {tr("skip_to_main", lang)}
      </a>

      <TooltipProvider>
        <SidebarProvider
          style={{ "--header-height": "3.5rem" } as CSSProperties}
          className="min-h-dvh"
        >
          <AppSidebar
            lang={lang}
            user={user}
            onSignOut={onSignOut}
            onOpenSearch={() => setPaletteOpen(true)}
          />

          <SidebarInset>
            <SiteHeader
              lang={lang}
              setLang={setLang}
              theme={theme}
              toggleTheme={toggleTheme}
              user={user}
              unverified={unverified}
              onOpenSearch={() => setPaletteOpen(true)}
              clerkConfig={clerkConfig?.clerk ?? null}
              onClerkEnded={onSignOut}
            />

            <p className="sr-only" role="status" aria-live="polite">
              {announcement}
            </p>

            {/* An unverified session must not look like a verified one. */}
            {unverified && (
              <Alert
                variant="destructive"
                className="rounded-none border-x-0 border-t-0"
              >
                <AlertDescription className="text-center text-[0.82rem]">
                  {tr("offline_session", lang)}
                </AlertDescription>
              </Alert>
            )}

            {coverageOf(lang) === "core" && (
              <Alert className="bg-secondary rounded-none border-x-0 border-t-0">
                <AlertDescription className="text-center text-[0.82rem]">
                  {tr("coverage_note", lang)}
                </AlertDescription>
              </Alert>
            )}

            <main id="main" className="flex-1">
              <Hero lang={lang} />
              <GetStarted lang={lang} />
              <Kpis lang={lang} />
              <SubmitBills lang={lang} />
              <Comparison lang={lang} />
              <Recovery
                lang={lang}
                onEvent={(event) => setEvents((prev) => [...prev, event])}
              />
              <Ledger lang={lang} />
              <Activity lang={lang} events={events} />
              <Glossary lang={lang} />
            </main>

            <Footer lang={lang} />
          </SidebarInset>

          <Suspense fallback={null}>
            <Assistant lang={lang} theme={theme} />
          </Suspense>

          {/* ⌘K over the sections and the bills — mounted always, opened by
              the header button, the sidebar's Search row, or the shortcut. */}
          <CommandPalette lang={lang} open={paletteOpen} onOpenChange={setPaletteOpen} />
        </SidebarProvider>
      </TooltipProvider>
    </>
  );
}
