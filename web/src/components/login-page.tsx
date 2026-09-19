import { useEffect, useState, type ReactNode } from "react";
import {
  IndianRupeeIcon,
  MoonIcon,
  SunIcon,
  TriangleAlertIcon,
} from "lucide-react";

import { ClerkSignIn, type ClerkConfig } from "@/components/clerk-signin";
import { DotCanvas } from "@/components/dot-canvas";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { tr, type Lang } from "@/lib/i18n";
import { LOCALES, localeOf } from "@/lib/locales";
import {
  authOptions,
  exchangeAuthCode,
  exchangeClerkToken,
  providerStartUrl,
  register,
  signIn,
  offlineSession,
  type AuthOptions,
  type ProviderOption,
  type Session,
} from "@/lib/session";
import { useSnapshot } from "@/lib/snapshot";
import type { Theme } from "@/lib/theme";

/** The provider marks, drawn rather than fetched: two buttons, no image request. */
function GoogleMark() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="size-4 shrink-0">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  );
}

function GitHubMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="size-4 shrink-0">
      <path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.699-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.379.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.577.688.48C19.138 20.161 22 16.416 22 12c0-5.523-4.477-10-10-10z" />
    </svg>
  );
}

function AppleMark() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className="size-4 shrink-0">
      <path d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.04 2.26-.79 3.59-.76 1.56.04 2.88.75 3.65 1.89-3.08 1.75-2.58 5.61.35 6.75-1.01 2.37-2.39 4.39-4.29 4.29zM12.03 7.25c-.15-2.23 1.66-4.07 3.72-4.25.36 2.38-1.92 4.34-3.72 4.25z" />
    </svg>
  );
}

/**
 * The provider marks, drawn rather than fetched: a button per provider, no
 * image request. A provider the engine can offer but this table does not know
 * still gets its button — it simply reads as its name, which is the part that
 * has to be right.
 */
const MARKS: Record<string, () => ReactNode> = {
  google: GoogleMark,
  github: GitHubMark,
  apple: AppleMark,
};

/**
 * The provider buttons, as a component of its own.
 *
 * Extracted so a headless render can check them: the page only mounts them
 * after the engine has answered which providers are live, which is after the
 * first paint. Each button starts that provider's real flow, and a provider the
 * deployment has not configured gets no button at all — a sign-in option that
 * cannot work is worse than none.
 */
export function ProviderButtons({
  providers,
  lang,
}: {
  providers: ProviderOption[];
  lang: Lang;
}) {
  const live = providers.filter((provider) => provider.configured);
  if (live.length === 0) return null;

  return (
    <div className="flex w-full flex-col gap-2" data-testid="auth-providers">
      {live.map((provider) => {
        const Mark = MARKS[provider.slug];
        return (
          <Button
            key={provider.slug}
            type="button"
            variant="outline"
            size="lg"
            data-provider={provider.slug}
            className="min-h-11 w-full gap-2 font-normal"
            onClick={() => window.location.assign(providerStartUrl(provider.slug))}
          >
            {Mark ? <Mark /> : null}
            {tr("login_continue_with", lang)} {provider.label}
          </Button>
        );
      })}
    </div>
  );
}

/**
 * The way into the workspace.
 *
 * Every method offered here is verified by the engine: the password form posts
 * to `/api/login`, sign-up posts to `/api/auth/register`, and a provider button
 * starts a real OAuth flow — a button appears only when that provider is
 * configured, because a sign-in option that cannot work is worse than none.
 * The engine's own sentence is what the reader sees when something fails.
 *
 * A provider that finishes by posting its answer back (Apple) returns to the
 * same page with a one-time code, which the effect below swaps for a session.
 */
export function LoginPage({
  lang,
  setLang,
  theme,
  toggleTheme,
  onSignedIn,
  initialError = null,
  authCode = null,
}: {
  lang: Lang;
  setLang: (l: Lang) => void;
  theme: Theme;
  toggleTheme: () => void;
  onSignedIn: (session: Session) => void;
  initialError?: string | null;
  authCode?: string | null;
}) {
  const snapshot = useSnapshot();
  const dark = theme === "dark";

  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [options, setOptions] = useState<AuthOptions | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(initialError);
  const [clerkDone, setClerkDone] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // What this deployment can offer. Until it answers, only the password form
  // is shown — never a provider button that has not been confirmed.
  useEffect(() => {
    let alive = true;
    void authOptions().then((found) => {
      if (alive) setOptions(found);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Coming back from a provider: swap the one-time code for a session, once.
  useEffect(() => {
    if (!authCode) return;
    let alive = true;
    setBusy(true);
    void exchangeAuthCode(authCode).then((result) => {
      if (!alive) return;
      setBusy(false);
      if (result.ok && result.session) {
        onSignedIn(result.session);
        return;
      }
      setError(result.detail === "offline" ? tr("login_offline", lang) : tr("login_provider_error", lang));
    });
    return () => {
      alive = false;
    };
  }, [authCode, lang, onSignedIn]);

  const providers = (options?.providers ?? []).filter((provider) => provider.configured);
  const themeLabel = dark ? tr("theme_to_light", lang) : tr("theme_to_dark", lang);

  async function submit() {
    setBusy(true);
    setError(null);
    const result =
      mode === "signup"
        ? await register(name, email, password)
        : await signIn(email, password);
    setBusy(false);
    if (result.ok && result.session) {
      onSignedIn(result.session);
      return;
    }
    if (result.detail && result.detail !== "offline") {
      // The engine's own sentence: it says what to fix, so it is shown as-is.
      setError(result.detail);
      return;
    }
    setError(
      result.detail === "offline" ? tr("login_offline", lang) : tr("login_failed", lang),
    );
  }

  /**
   * The hosted Clerk card produced a verified session: swap it for the
   * engine's own and enter the workspace exactly as any other sign-in does.
   * One exchange per token — the watcher passes each token once, and a
   * finished exchange must not run again.
   */
  async function clerkHandoff(token: string) {
    if (clerkDone) return;
    setClerkDone(true);
    setBusy(true);
    setError(null);
    const result = await exchangeClerkToken(token);
    setBusy(false);
    if (result.ok && result.session) {
      onSignedIn(result.session);
      return;
    }
    setError(
      result.detail === "offline" ? tr("login_offline", lang) : tr("login_provider_error", lang),
    );
  }

  /** Temporary demo entry, requested for reviews: opens the workspace unverified. */
  function skipSignIn() {
    onSignedIn(offlineSession());
  }

  return (
    <div className="bg-background relative flex min-h-dvh flex-col overflow-hidden">
      <DotCanvas dark={dark} />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-[1]"
        style={{
          background:
            "radial-gradient(circle at center, color-mix(in oklab, var(--background) 78%, transparent) 0%, transparent 100%)",
        }}
      />

      <header className="relative z-[2] flex items-center gap-3 px-4 py-4 lg:px-6">
        <span className="font-display flex items-center gap-2 text-[1.05rem] font-semibold">
          <IndianRupeeIcon aria-hidden="true" className="text-primary size-5" />
          Recon-Agent
        </span>
        <span className="text-muted-foreground hidden text-[0.82rem] sm:inline">
          {snapshot.period} · {tr("brand_tagline", lang)}
        </span>

        <div className="ms-auto flex items-center gap-2">
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
            <SelectTrigger className="w-[7.5rem] max-w-[38vw]" aria-label={tr("nav_language", lang)}>
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
        </div>
      </header>

      <main className="relative z-[2] flex flex-1 items-center justify-center px-4 pb-10">
        <Card className="w-full max-w-[26rem] shadow-2xl">
          <CardContent className="flex flex-col items-center text-center">
            <span
              aria-hidden="true"
              className="bg-secondary border-border font-display mb-3 flex size-11 items-center justify-center rounded-full border text-[1.05rem] font-semibold"
            >
              RA
            </span>

            <h1 className="text-[1.3rem] font-semibold tracking-tight">
              {mode === "signup" ? tr("login_signup_title", lang) : tr("login_title", lang)}
            </h1>
            <p className="text-muted-foreground mt-1 text-[0.85rem] leading-relaxed">
              {mode === "signup" ? tr("login_signup_sub", lang) : tr("login_sub", lang)}
            </p>

            <form
              className="mt-4 flex w-full flex-col gap-3"
              onSubmit={(e) => {
                e.preventDefault();
                void submit();
              }}
            >
              {mode === "signup" && (
                <Field className="gap-1 text-start">
                  <FieldLabel htmlFor="login-name">{tr("login_name", lang)}</FieldLabel>
                  <Input
                    id="login-name"
                    name="name"
                    autoComplete="name"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </Field>
              )}

              <Field className="gap-1 text-start">
                <FieldLabel htmlFor="login-email">{tr("login_email", lang)}</FieldLabel>
                <Input
                  id="login-email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  spellCheck={false}
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>

              <Field className="gap-1 text-start">
                <FieldLabel htmlFor="login-password">{tr("login_password", lang)}</FieldLabel>
                <Input
                  id="login-password"
                  name="password"
                  type="password"
                  autoComplete={mode === "signup" ? "new-password" : "current-password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                {mode === "signup" && (
                  <FieldDescription>{tr("login_password_hint", lang)}</FieldDescription>
                )}
              </Field>

              <Button type="submit" size="lg" className="min-h-11 w-full" disabled={busy} aria-busy={busy}>
                {busy ? <Spinner className="text-current" /> : null}
                {busy
                  ? tr("login_checking", lang)
                  : mode === "signup"
                    ? tr("login_register", lang)
                    : tr("login_submit", lang)}
              </Button>
            </form>

            {error && (
              <Alert variant="destructive" className="mt-3 text-start" role="alert" aria-live="polite">
                <TriangleAlertIcon aria-hidden="true" />
                <AlertTitle>{tr("login_failed", lang)}</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {providers.length > 0 && (
              <>
                <div className="my-4 flex w-full items-center gap-3">
                  <Separator className="flex-1" />
                  <span className="text-muted-foreground text-[0.78rem]">{tr("login_or", lang)}</span>
                  <Separator className="flex-1" />
                </div>

                <ProviderButtons providers={providers} lang={lang} />
              </>
            )}

            {/*
             * Clerk, when this deployment has it: its hosted card replaces
             * nothing here — it sits beside the built-in form, and its
             * settings (accounts, verification, reset, social connections)
             * are handled in Clerk's dashboard, not in this code.
             */}
            <ClerkSignIn
              config={(options?.clerk ?? null) as ClerkConfig | null}
              lang={lang}
              onSessionToken={(token) => void clerkHandoff(token)}
            />

            <p className="mt-5 text-[0.85rem]">
              {mode === "signup" ? (
                <>
                  <span className="text-muted-foreground">{tr("login_have_account", lang)}</span>{" "}
                  <Button
                    type="button"
                    variant="link"
                    className="h-auto p-0 font-medium"
                    onClick={() => {
                      setMode("signin");
                      setError(null);
                    }}
                  >
                    {tr("login_submit", lang)}
                  </Button>
                </>
              ) : (
                <>
                  <span className="text-muted-foreground">{tr("login_no_account", lang)}</span>{" "}
                  <Button
                    type="button"
                    variant="link"
                    className="h-auto p-0 font-medium"
                    onClick={() => {
                      setMode("signup");
                      setError(null);
                    }}
                  >
                    {tr("login_signup_title", lang)}
                  </Button>
                </>
              )}
            </p>

            {options?.demo && (
              // Demo mode means the published pair really does work: saying so
              // is the difference between a demo and a broken login.
              <p className="text-muted-foreground mt-3 text-[0.8rem]">
                {tr("login_demo_hint", lang)}
              </p>
            )}

            {/* Temporary demo entry, clearly labelled as what it is. */}
            <div className="border-border mt-4 w-full rounded-xl border p-3">
              <Button variant="outline" className="min-h-11 w-full" onClick={skipSignIn}>
                {tr("login_skip", lang)}
              </Button>
              <p className="text-muted-foreground mt-2 text-[0.78rem] leading-relaxed">
                {tr("login_skip_note", lang)}
              </p>
            </div>
          </CardContent>
        </Card>
      </main>

      <footer className="text-muted-foreground relative z-[2] px-4 pb-6 text-center text-[0.78rem] leading-relaxed">
        <p>{tr("footer_legal", lang)}</p>
        <p className="mt-1">{tr("footer_fixtures", lang)}</p>
      </footer>
    </div>
  );
}
