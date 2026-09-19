"use client";

/**
 * Clerk, when this deployment has it.
 *
 * Clerk is the one sign-in option whose settings live entirely in its
 * dashboard: accounts, email verification, password reset, social
 * connections, attack protection. When the engine reports a publishable key
 * this component mounts {@link ClerkProvider} and, instead of the built-in
 * form, the card holds Clerk's own hosted `<SignIn />` — themed by this
 * project's CSS variables, because Clerk reads its palette from the same
 * custom properties shadcn sets. The workspace never learns about Clerk: a
 * successful session is exchanged for the same opaque token every other
 * sign-in produces, and {@link App}'s `onSignedIn` runs as it always has.
 *
 * Written to fail quiet and honest: no key, no provider. The SDK itself is
 * imported lazily — it is a large dependency for a first paint, and the
 * sign-in page is what a shop owner on a phone loads first — so an
 * unconfigured deployment never downloads any of it.
 */

import {
  Component,
  useEffect,
  useRef,
  useState,
  type ErrorInfo,
  type ReactNode,
} from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import { TriangleAlertIcon } from "lucide-react";

/** One social sign-in the deployment has actually configured. */
export interface ClerkConfig {
  configured: boolean;
  publishable_key: string | null;
  issuer: string | null;
  allowed_origins: string[];
  missing: string[];
  docs: string;
}

/**
 * The SDK pieces, typed just enough to use without importing the module at
 * the top level — the dynamic import below is what keeps Clerk out of the
 * first-paint bundle.
 */
interface ClerkModule {
  ClerkProvider: (props: {
    publishableKey: string;
    children: ReactNode;
  }) => ReactNode;
  SignIn: (props: Record<string, unknown>) => ReactNode;
  UserButton: (props: Record<string, unknown>) => ReactNode;
  useSession: () => {
    isLoaded: boolean;
    session: { getToken: () => Promise<string | null> } | null | undefined;
  };
}

/**
 * Whether Clerk can work from this browser at all.
 *
 * A development Clerk instance serves its hosted sign-in only from
 * localhost/127.0.0.1 or an origin the operator allow-listed; from anywhere
 * else clerk-js fails its handshake, and a provider that throws on mount
 * takes the whole React tree down with it — the blank page. The engine
 * reports the origins it will vouch for, so the same list decides whether
 * the card is offered: a sign-in option that cannot work is worse than none.
 * Exported for the smoke test, which pins the localhost and foreign-origin
 * decisions without a browser.
 */
export function clerkWorksHere(config: ClerkConfig, here?: string): boolean {
  const origin = here ?? (typeof window === "undefined" ? "" : window.location.origin);
  if (!origin) return true; // static render: harmless
  if (config.allowed_origins.includes(origin)) return true;
  // A development instance always accepts localhost on any port.
  try {
    const host = new URL(origin).hostname;
    return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
  } catch {
    return false;
  }
}

/**
 * A Clerk failure must never blank the page around it.
 *
 * ClerkProvider and its hosted card are third-party code that mounts into
 * this tree; if it throws — a handshake failure, an SDK surprise — React
 * unmounts everything above it, which is how the page goes blank. The
 * boundary contains the damage to Clerk's own slot; the password form below
 * is this project's code and keeps working. Exported so the account button
 * in the header is protected by exactly the same rule.
 */
export class ClerkBoundary extends Component<
  { children: ReactNode; onFail: () => void },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Said once in the console for whoever is watching; the UI falls back.
    console.error("Clerk sign-in failed; the password form stays available.", error, info.componentStack);
    this.props.onFail();
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * One appearance for every Clerk surface, so the hosted card and the account
 * button wear this project's palette from the same CSS variables shadcn sets.
 * Shared rather than copied, so they cannot drift apart.
 */
export const CLERK_APPEARANCE = {
  variables: {
    colorPrimary: "var(--primary)",
    colorBackground: "var(--card)",
    colorInput: "var(--background)",
    colorText: "var(--foreground)",
    colorTextSecondary: "var(--muted-foreground)",
    colorDanger: "var(--destructive)",
    borderRadius: "0.75rem",
    fontFamily: "var(--font-sans)",
  },
} as const;

function ClerkReady({
  clerk,
  publishableKey,
  onSessionToken,
}: {
  clerk: ClerkModule;
  publishableKey: string;
  onSessionToken: (token: string) => void;
}) {
  const Provider = clerk.ClerkProvider;
  const SignInCard = clerk.SignIn;
  return (
    <Provider publishableKey={publishableKey}>
      <SignInCard
        afterSignOutUrl="/"
        // A successful hosted sign-in resolves on this page; the token is
        // picked up below and swapped for the engine's own session.
        fallbackRedirectUrl={typeof window === "undefined" ? "/" : window.location.pathname}
        signUpFallbackRedirectUrl={typeof window === "undefined" ? "/" : window.location.pathname}
        appearance={CLERK_APPEARANCE}
      />
      <SessionProbe useSession={clerk.useSession} onSessionToken={onSessionToken} />
    </Provider>
  );
}

/**
 * Watches Clerk's session and, once there is one, hands its token to the
 * caller — exactly once per token, so a re-render cannot loop the exchange.
 * Needs a provider above it, so it is a component rather than a hook call.
 */
function SessionProbe({
  useSession,
  onSessionToken,
}: {
  useSession: () => {
    isLoaded: boolean;
    session: { getToken: () => Promise<string | null> } | null | undefined;
  };
  onSessionToken: (token: string) => void;
}) {
  const { isLoaded, session } = useSession();
  const seen = useRef<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !session) return;
    let alive = true;
    void session.getToken().then((token) => {
      if (!alive || !token || seen.current === token) return;
      seen.current = token;
      onSessionToken(token);
    });
    return () => {
      alive = false;
    };
  }, [isLoaded, session, onSessionToken]);

  return null;
}

export function ClerkSignIn({
  config,
  lang,
  onSessionToken,
  children,
}: {
  config: ClerkConfig | null;
  lang: string;
  onSessionToken: (token: string) => void;
  children?: ReactNode;
}) {
  const [failed, setFailed] = useState(false);
  const [clerk, setClerk] = useState<ClerkModule | null>(null);

  // Loaded only when this deployment actually has Clerk configured — an
  // unconfigured page never downloads the SDK. One retry: a failed import is
  // often Vite still optimising the dependency, which the next attempt fixes.
  useEffect(() => {
    if (!config?.configured || !config.publishable_key || clerk || failed) return;
    // An origin the Clerk instance will refuse never sees the SDK: the card
    // is not offered, so nothing about it can fail on this page.
    if (!clerkWorksHere(config)) return;
    let alive = true;
    let tries = 0;
    const load = () => {
      void import("@clerk/clerk-react")
        .then((mod) => {
          if (alive) setClerk(mod as unknown as ClerkModule);
        })
        .catch(() => {
          if (!alive) return;
          tries += 1;
          if (tries < 2) window.setTimeout(load, 1500);
          else setFailed(true);
        });
    };
    load();
    return () => {
      alive = false;
    };
  }, [config, clerk, failed]);

  if (!config?.configured || !config.publishable_key) return <>{children}</>;
  if (!clerkWorksHere(config)) return <>{children}</>;
  if (failed) {
    return (
      <Alert variant="destructive" role="alert" className="text-start" aria-live="polite">
        <TriangleAlertIcon aria-hidden="true" />
        <AlertTitle>Sign-in unavailable</AlertTitle>
        <AlertDescription>
          The hosted sign-in could not be loaded after a retry. The password
          form is unaffected.
        </AlertDescription>
      </Alert>
    );
  }
  if (!clerk) {
    // Downloading, not broken: the alert above is reserved for real failures.
    return (
      <p className="text-muted-foreground flex items-center justify-center gap-2 text-[0.8rem]">
        <Spinner className="size-4" aria-hidden="true" />
        Loading hosted sign-in…
      </p>
    );
  }

  return (
    <div data-testid="clerk-signin" lang={lang}>
      <ClerkBoundary onFail={() => setFailed(true)}>
        <ClerkReady
          clerk={clerk}
          publishableKey={config.publishable_key}
          onSessionToken={onSessionToken}
        />
      </ClerkBoundary>
    </div>
  );
}

/**
 * Clerk's account button, for a signed-in operator.
 *
 * Rendered in the site header only for sessions that actually came from
 * Clerk — a password or OAuth session gets this project's own avatar card,
 * which is the honest thing: this button's menu (profile, sessions, manage
 * account, sign out) acts on a Clerk account, and showing it over any other
 * kind would promise what it cannot do.
 *
 * The SDK is imported lazily exactly as on the sign-in page, and it mounts
 * inside its own provider + the same error boundary, so a Clerk surprise can
 * only ever remove the button, never the header. When the operator signs out
 * from Clerk's own menu, ``onEnded`` tells the app to drop the engine session
 * too — the two ends of one logout must not disagree.
 */
export function ClerkUserButton({
  config,
  onEnded,
}: {
  config: ClerkConfig | null;
  onEnded: () => void;
}) {
  const [failed, setFailed] = useState(false);
  const [clerk, setClerk] = useState<ClerkModule | null>(null);

  useEffect(() => {
    if (!config?.configured || !config.publishable_key || clerk || failed) return;
    if (!clerkWorksHere(config)) return;
    let alive = true;
    void import("@clerk/clerk-react")
      .then((mod) => {
        if (alive) setClerk(mod as unknown as ClerkModule);
      })
      .catch(() => {
        if (alive) setFailed(true);
      });
    return () => {
      alive = false;
    };
  }, [config, clerk, failed]);

  if (!config?.configured || !config.publishable_key) return null;
  if (!clerkWorksHere(config)) return null;
  if (failed || !clerk) return null; // the avatar beside it still works

  const Provider = clerk.ClerkProvider;
  const UserButton = clerk.UserButton;
  return (
    <ClerkBoundary onFail={() => setFailed(true)}>
      <Provider publishableKey={config.publishable_key}>
        <ClerkSignOutWatch useSession={clerk.useSession} onEnded={onEnded} />
        <UserButton afterSignOutUrl="/" appearance={CLERK_APPEARANCE} />
      </Provider>
    </ClerkBoundary>
  );
}

/**
 * Fires once when Clerk's session disappears — the operator signed out from
 * Clerk's own menu. The app then ends its engine session, so both sides of
 * the logout agree.
 */
function ClerkSignOutWatch({
  useSession,
  onEnded,
}: {
  useSession: ClerkModule["useSession"];
  onEnded: () => void;
}) {
  const { isLoaded, session } = useSession();
  const wasSignedIn = useRef(false);

  useEffect(() => {
    if (isLoaded && session) wasSignedIn.current = true;
  }, [isLoaded, session]);

  useEffect(() => {
    if (isLoaded && !session && wasSignedIn.current) onEnded();
  }, [isLoaded, session, onEnded]);

  return null;
}
